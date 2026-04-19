import json
import os
from pathlib import Path
from typing import List

import anthropic

SYSTEM_PROMPT = """\
あなたは動画編集の専門家です。
日本語の文字起こしデータ（単語・タイムスタンプ付き）を受け取り、以下の2つの解析を行ってください。

1. **フィラー検出**
   フィラーとは話しことばの「えー」「あー」「えっと」「うーん」「まあ」「なんか」「そうですね（単独）」「あのー」など、
   情報を持たない間投詞や言いよどみです。
   各フィラーの開始・終了タイムスタンプを返してください。

2. **Q&Aペア検出**
   質疑応答セッションから、質問の開始〜回答の終了までをひとつのペアとして検出してください。
   以下のルールを厳守してください：
   - q_start は質問の最初の単語のタイムスタンプにすること
   - a_end は【次の質問が始まる直前】のタイムスタンプにすること（最後のQ&Aは音声の終わり）
   - 回答の途中で切らないこと。話者が次の質問に移るまで回答は続いていると考えること
   - 「と思います」「ですね」などの文末表現だけで回答終了と判断しないこと
   - 各ペアには短い日本語タイトル（内容を表す10文字以内）を付けてください

必ず以下のJSON形式のみで回答してください（説明文は不要）:
{
  "fillers": [
    {"start": 12.3, "end": 12.8, "text": "えー"}
  ],
  "qa_pairs": [
    {"q_start": 30.0, "a_end": 95.2, "title": "自己紹介について"}
  ]
}
"""


def analyze(words: List[dict], model: str = "claude-haiku-4-5-20251001") -> dict:
    """Analyze transcript with Claude API.
    Returns {"fillers": [...], "qa_pairs": [...]}.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    transcript_text = json.dumps(words, ensure_ascii=False)

    message = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": transcript_text,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def save_analysis(analysis: dict, output_path: str) -> None:
    Path(output_path).write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_analysis(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
