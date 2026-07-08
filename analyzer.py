import json
import os
import re
from pathlib import Path
from typing import List

import anthropic

FILLER_SECTION = """\
1. **フィラー検出**
   フィラーとは話しことばの「えー」「あー」「えっと」「うーん」「まあ」「なんか」「そうですね（単独）」「あのー」など、
   情報を持たない間投詞や言いよどみです。
   各フィラーの開始・終了タイムスタンプを返してください。

"""

QA_SECTION = """\
{n}. **Q&Aペア検出**
   質疑応答セッションから、質問の開始〜回答の終了までをひとつのペアとして検出してください。
   以下のルールを厳守してください：
   - q_start は質問の最初の単語のタイムスタンプにすること
   - a_end は【次の質問が始まる直前】のタイムスタンプにすること（最後のQ&Aは音声の終わり）
   - 回答の途中で切らないこと。話者が次の質問に移るまで回答は続いていると考えること
   - 「と思います」「ですね」などの文末表現だけで回答終了と判断しないこと
   - 「続いての質問」「◯つ目の質問」「最後の質問」などの前振りフレーズが出たら、必ずそこで新しいペアを開始すること。1つのペアに複数の質問を含めてはならない
   - 各ペアには短い日本語タイトル（内容を表す10文字以内）を付けてください

"""

JSON_FORMAT_FILLER = """\
  "fillers": [
    {"start": 12.3, "end": 12.8, "text": "えー"}
  ],
"""

JSON_FORMAT_QA = """\
  "qa_pairs": [
    {"q_start": 30.0, "a_end": 95.2, "title": "自己紹介について"}
  ]
"""


def _build_system_prompt(mode: str) -> str:
    sections = []
    json_fields = []
    n = 1
    if mode in ("filler", "both"):
        sections.append(FILLER_SECTION)
        json_fields.append(JSON_FORMAT_FILLER)
        n += 1
    if mode in ("qa", "both"):
        sections.append(QA_SECTION.format(n=n))
        json_fields.append(JSON_FORMAT_QA)

    json_fields_str = ",\n".join(f.rstrip(",\n") for f in json_fields)
    return f"""\
あなたは動画編集の専門家です。
日本語の文字起こしデータ（単語・タイムスタンプ付き）を受け取り、以下の解析を行ってください。

{"".join(sections)}必ず以下のJSON形式のみで回答してください（説明文は不要）:
{{
{json_fields_str}
}}
"""


def validate_qa_pairs(qa_pairs: List[dict], duration: float) -> List[dict]:
    """Q&Aペアを検証・整形する。異常なペアは除外し、警告を表示する。"""
    pairs = sorted(qa_pairs, key=lambda p: p.get("q_start", 0.0))

    cleaned: List[dict] = []
    for i, p in enumerate(pairs, start=1):
        q_start = p.get("q_start")
        a_end = p.get("a_end")
        title = p.get("title") or f"質問{i}"

        if q_start is None or a_end is None:
            print(f"      [警告] q_start/a_end が欠けているペアを除外: {p}")
            continue

        q_start = max(0.0, min(float(q_start), duration))
        a_end = max(0.0, min(float(a_end), duration))

        if q_start >= a_end:
            print(f"      [警告] q_start >= a_end のペアを除外: {p}")
            continue

        if cleaned:
            prev = cleaned[-1]
            prev_len = prev["a_end"] - prev["q_start"]
            overlap = prev["a_end"] - q_start
            if prev_len > 0 and overlap > 0 and overlap / prev_len >= 0.5:
                print(f"      [警告] 前のペアと50%以上重複するペアを除外: {p}")
                continue

        cleaned.append({"q_start": q_start, "a_end": a_end, "title": title})

    return cleaned


PAUSE_THRESHOLD = 0.8   # 秒: これ以上の無音が来たら自然な区切りとみなして止める
MAX_EXTEND = 5.0        # 秒: 誤検出で暴走しないための延長上限


def snap_answer_endings(qa_pairs: List[dict], words: List[dict],
                         duration: float) -> List[dict]:
    """a_end を話の途中で止めず、次の自然な間（無音）まで延長する。

    Claude が返す a_end は言い直しや相槌の直前で止まっていることがあり、
    余白なしで切ると文末が欠けて聞こえる。単語間の間隔が PAUSE_THRESHOLD 未満の
    間は同じひと続きの発話とみなして延長し、間隔が空いたところ（自然な区切り）
    か次のペアの q_start に達したところで止める。
    """
    result: List[dict] = []
    for i, pair in enumerate(qa_pairs):
        a_end = pair["a_end"]
        limit = qa_pairs[i + 1]["q_start"] if i + 1 < len(qa_pairs) else duration

        following = sorted(
            (w for w in words if w["start"] >= a_end - 0.01 and w["start"] < limit),
            key=lambda w: w["start"],
        )

        cur_end = a_end
        for w in following:
            gap = w["start"] - cur_end
            if gap >= PAUSE_THRESHOLD:
                break
            if w["end"] - a_end > MAX_EXTEND:
                break
            cur_end = min(w["end"], limit)

        result.append({**pair, "a_end": cur_end})

    return result


STRONG_MARKER_PATTERN = re.compile(
    r"続いての質問|次の質問|最後の質問|最初の質問|一つ目の質問|"
    r"[0-9一二三四五六七八九十１-９]+つ目の質問"
)
WEAK_MARKER_PATTERN = re.compile(r"質問です|質問ですが|ご質問")

CROSS_CHECK_TOLERANCE = 5.0   # 秒: マーカーとq_startの許容差
LENGTH_OUTLIER_RATIO = 1.8    # 倍: 中央値に対する結合疑いの閾値


def detect_question_markers(words: List[dict]) -> List[dict]:
    """文字起こし全文から質問の前振りフレーズを検出し、タイムスタンプ付きで返す。

    Claudeの解析結果とは独立に、ルールベースで境界の手がかりを洗い出す。
    「今日最後の質問ですね」のような定型句をAIが見逃した場合に検出漏れを発見するため。
    """
    text_words = [(w["start"], w["word"]) for w in words]
    full = "".join(w for _, w in text_words)

    markers: List[dict] = []
    for pattern, strength in ((STRONG_MARKER_PATTERN, "strong"), (WEAK_MARKER_PATTERN, "weak")):
        for m in pattern.finditer(full):
            idx = m.start()
            acc = 0
            time = None
            for start, w in text_words:
                acc += len(w)
                if acc > idx:
                    time = start
                    break
            if time is not None:
                markers.append({"time": time, "phrase": m.group(), "strength": strength})

    markers.sort(key=lambda m: m["time"])
    return markers


def cross_check_qa_pairs(qa_pairs: List[dict], markers: List[dict]) -> List[str]:
    """Claudeの検出結果をマーカーと突き合わせ、検出漏れ・結合の疑いを警告として返す。

    空リストなら問題なし。
    """
    warnings: List[str] = []
    q_starts = [p["q_start"] for p in qa_pairs]

    for marker in markers:
        if marker["strength"] != "strong":
            continue
        if not any(abs(marker["time"] - qs) <= CROSS_CHECK_TOLERANCE for qs in q_starts):
            t = marker["time"]
            m, s = divmod(int(t), 60)
            warnings.append(
                f"[検出漏れの疑い] {m}:{s:02d} に「{marker['phrase']}」があるが、"
                f"対応するQ&Aペアがない。q_start={t:.1f} での分割を検討"
            )

    if len(qa_pairs) >= 3:
        lengths = sorted(p["a_end"] - p["q_start"] for p in qa_pairs)
        mid = len(lengths) // 2
        median = lengths[mid] if len(lengths) % 2 == 1 else (lengths[mid - 1] + lengths[mid]) / 2
        if median > 0:
            for i, p in enumerate(qa_pairs, start=1):
                length = p["a_end"] - p["q_start"]
                if length > median * LENGTH_OUTLIER_RATIO:
                    m, s = divmod(int(length), 60)
                    warnings.append(
                        f"[結合の疑い] #{i} は {m}:{s:02d} で他より突出して長い"
                        f"（中央値の{LENGTH_OUTLIER_RATIO}倍超）。複数の質問が結合されていないか確認"
                    )

    return warnings


def analyze(words: List[dict], model: str = "claude-haiku-4-5-20251001",
            mode: str = "both") -> dict:
    """Analyze transcript with Claude API.
    mode: "filler" / "qa" / "both" — 不要な解析はプロンプトから除外し、
    トークン消費と出力打ち切りのリスクを減らす。
    Returns {"fillers": [...], "qa_pairs": [...]}.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    system_prompt = _build_system_prompt(mode)
    transcript_text = json.dumps(words, ensure_ascii=False)

    raw = None
    last_error = None
    for attempt in range(2):
        message = client.messages.create(
            model=model,
            max_tokens=8192,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": transcript_text}],
                }
            ],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            result = json.loads(raw)
            result.setdefault("fillers", [])
            result.setdefault("qa_pairs", [])
            return result
        except json.JSONDecodeError as e:
            last_error = e
            print(f"      [警告] JSON解析に失敗（{attempt + 1}回目）。再試行します…")

    Path("analysis_raw.txt").write_text(raw or "", encoding="utf-8")
    raise ValueError(
        f"Claude の応答をJSONとして解析できませんでした: {last_error}\n"
        f"生の応答を analysis_raw.txt に保存しました"
    )


def save_analysis(analysis: dict, output_path: str) -> None:
    Path(output_path).write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_analysis(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
