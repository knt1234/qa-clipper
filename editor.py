import datetime
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

FILLER_BUFFER = 0.05

# a_end を音声波形の無音位置に合わせる際のパラメータ
SILENCE_MIN_DUR = 0.30    # 秒: これ以上続く無音を「区切り」とみなす
SILENCE_SEARCH_BACK = 0.4  # 秒: a_end のどれだけ手前から無音を探すか
END_TAIL = 0.12           # 秒: 語尾の余韻を切らないための微小マージン

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

if not FFMPEG or not FFPROBE:
    sys.exit("エラー: ffmpeg/ffprobe が見つかりません。`brew install ffmpeg` を実行してください")


def _run_ffmpeg(cmd: List[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-20:])
        sys.exit(f"エラー: ffmpeg の実行に失敗しました\n{tail}")


def _get_duration(video_path: str) -> float:
    result = subprocess.run(
        [
            FFPROBE, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def _mean_volume(media_path: str) -> float:
    """音声全体の平均音量(dB)を返す。無音検出の閾値を音源に合わせるために使う。"""
    result = subprocess.run(
        [FFMPEG, "-i", media_path, "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    m = re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB", result.stderr)
    return float(m.group(1)) if m else -40.0


def _find_silence_starts(media_path: str, win_start: float, win_end: float,
                          noise_db: float) -> List[float]:
    """[win_start, win_end] の範囲で無音の開始時刻(絶対秒)のリストを返す。"""
    result = subprocess.run(
        [FFMPEG, "-ss", str(win_start), "-to", str(win_end), "-i", media_path,
         "-af", f"silencedetect=noise={noise_db}dB:d={SILENCE_MIN_DUR}",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return [win_start + float(m)
            for m in re.findall(r"silence_start:\s*([\d.]+)", result.stderr)]


def refine_endings_by_silence(media_path: str, qa_pairs: List[dict],
                              duration: float) -> List[dict]:
    """各 a_end を実際の音声波形の無音位置に合わせて補正する。

    Whisper の単語終了タイムスタンプは実際の発声より 0.2〜0.5 秒早く出るため、
    そのまま余白なしで切ると語尾が欠ける。a_end 付近から後方を探し、
    最初に現れる無音（＝発話の自然な終わり）まで延長する。
    無音は次のペアの q_start を超えて探さない。
    """
    noise_db = _mean_volume(media_path) - 6.0  # 平均音量より少し下を無音の閾値にする

    result: List[dict] = []
    for i, pair in enumerate(qa_pairs):
        a_end = pair["a_end"]
        limit = qa_pairs[i + 1]["q_start"] if i + 1 < len(qa_pairs) else duration

        win_start = max(0.0, a_end - SILENCE_SEARCH_BACK)
        win_end = min(duration, limit + 0.5)
        starts = _find_silence_starts(media_path, win_start, win_end, noise_db)

        # a_end 以降で最初に来る無音の開始 = 発話の終端
        after = [s for s in starts if s >= a_end - SILENCE_SEARCH_BACK]
        if after:
            new_end = min(after[0] + END_TAIL, limit, duration)
            new_end = max(new_end, a_end)  # 手前には縮めない
        else:
            new_end = a_end

        result.append({**pair, "a_end": new_end})

    return result


def remove_fillers(video_path: str, fillers: List[dict], output_path: str) -> str:
    if not fillers:
        _run_ffmpeg([FFMPEG, "-y", "-i", video_path, "-c", "copy", output_path])
        return output_path

    duration = _get_duration(video_path)

    filler_intervals = sorted(
        [(max(0.0, f["start"] - FILLER_BUFFER), min(duration, f["end"] + FILLER_BUFFER))
         for f in fillers],
        key=lambda x: x[0],
    )

    merged: List[Tuple[float, float]] = []
    for s, e in filler_intervals:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    keep: List[Tuple[float, float]] = []
    prev = 0.0
    for s, e in merged:
        if prev < s:
            keep.append((prev, s))
        prev = e
    if prev < duration:
        keep.append((prev, duration))

    if not keep:
        raise ValueError("All segments would be removed after filler cutting")

    # filter_complex で trim+setpts による正確なカット＆結合（再エンコード）
    filter_parts = []
    v_labels = []
    a_labels = []
    for i, (s, e) in enumerate(keep):
        filter_parts.append(
            f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}];"
            f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]"
        )
        v_labels.append(f"[v{i}]")
        a_labels.append(f"[a{i}]")

    n = len(keep)
    # concat フィルターは [v0][a0][v1][a1]... の交互順が必要
    interleaved = "".join(f"{v}{a}" for v, a in zip(v_labels, a_labels))
    concat_filter = interleaved + f"concat=n={n}:v=1:a=1[vout][aout]"
    filter_complex = ";".join(filter_parts) + ";" + concat_filter

    _run_ffmpeg([
        FFMPEG, "-y",
        "-i", video_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ])

    return output_path


def extract_qa_clips(video_path: str, qa_pairs: List[dict], output_dir: str,
                     padding: float = 0.0) -> List[str]:
    """Extract Q&A clips from q_start to a_end (padding=0 で話始め・話終わりぴったり）.

    再エンコード方式で切り出す（-c copy はキーフレーム単位でしかカットできず、
    開始位置が数秒ズレたり冒頭が乱れることがあるため）。
    padding を指定した場合、後方の余白は次のペアの q_start を超えないようにクランプする
    （次の質問の冒頭が混入するのを防ぐ）。
    """
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    duration = _get_duration(video_path)

    paths = []
    for i, pair in enumerate(qa_pairs, start=1):
        title = _sanitize_filename(pair.get("title", f"clip_{i:03d}"))
        out = str(output_dir_path / f"{i:03d}_{title}.mp4")
        start = max(0.0, pair["q_start"] - padding)

        next_q_start = qa_pairs[i]["q_start"] if i < len(qa_pairs) else None
        end_limit = min(duration, next_q_start) if next_q_start is not None else duration
        end = min(end_limit, pair["a_end"] + padding)

        _run_ffmpeg([
            FFMPEG, "-y",
            "-ss", str(start),
            "-to", str(end),
            "-i", video_path,
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-reset_timestamps", "1",
            out,
        ])
        paths.append(out)

    return paths


# ── 事後検証（verify_clips） ──

HEAD_TAIL_WINDOW = 6.0     # 秒: 冒頭/末尾のチェック窓
COVERAGE_GAP_MIN = 10.0    # 秒: これを超える未使用区間を警告対象にする
LENGTH_TOLERANCE = 1.5     # 秒: 実測長とa_end-q_startの許容差


def _transcribe_window(clip_path: str, start: float, duration: Optional[float]) -> str:
    """クリップの一部区間を tiny モデルで文字起こしし、結合テキストを返す（検査用途）。"""
    from transcriber import transcribe

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        cmd = [FFMPEG, "-y", "-ss", str(max(0.0, start))]
        if duration is not None:
            cmd += ["-t", str(duration)]
        cmd += ["-i", clip_path, "-vn", "-ar", "16000", "-ac", "1", tmp_path]
        subprocess.run(cmd, capture_output=True, text=True)
        words = transcribe(tmp_path, model_name="tiny", vad_filter=False)
        return "".join(w["word"] for w in words)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _stream_types(clip_path: str) -> List[str]:
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", clip_path],
        capture_output=True, text=True,
    )
    return result.stdout.split()


def _stream_codec(clip_path: str, stream: str) -> str:
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", stream,
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", clip_path],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _tail_frame_decodable(clip_path: str) -> bool:
    result = subprocess.run(
        [FFMPEG, "-v", "error", "-sseof", "-1", "-i", clip_path,
         "-frames:v", "1", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def _check_naming(clip_paths: List[str]) -> bool:
    for i, p in enumerate(clip_paths, start=1):
        if not re.match(rf"^{i:03d}_.+\.mp4$", Path(p).name):
            return False
    return True


def _coverage_gaps(qa_pairs: List[dict], words: List[dict], duration: float) -> List[str]:
    segments = sorted((p["q_start"], p["a_end"]) for p in qa_pairs)
    unused: List[Tuple[float, float]] = []
    prev_end = 0.0
    for s, e in segments:
        if s - prev_end > COVERAGE_GAP_MIN:
            unused.append((prev_end, s))
        prev_end = max(prev_end, e)
    if duration - prev_end > COVERAGE_GAP_MIN:
        unused.append((prev_end, duration))

    lines = []
    for s, e in unused:
        preview_words = [w["word"] for w in words if s <= w["start"] < e][:15]
        preview = "".join(preview_words)[:30]
        sm, ss = divmod(int(s), 60)
        em, es = divmod(int(e), 60)
        suffix = f"「{preview}…」" if preview else "（発話なし）"
        lines.append(f"- {sm}:{ss:02d}〜{em}:{es:02d}（未使用 {e - s:.0f}秒）: {suffix}")
    return lines


def verify_clips(video_path: str, clip_paths: List[str], qa_pairs: List[dict],
                  words: List[dict], output_dir: str,
                  analysis: Optional[dict] = None, mode: str = "qa") -> Path:
    """生成済みクリップを多面的に検証し、qa_report.md を生成する。

    A. ファイル健全性（存在・ストリーム・長さ・末尾フレーム）
    B. 境界検査（冒頭/末尾の文字起こしとマーカー照合）
    C. カバレッジ検査（未使用区間の洗い出し）
    D. 仕様準拠チェック（SKILL.md に記載した約束事項の機械照合）

    analysis（analysis.jsonの生データ）を渡すと、終端3段補正の適用有無と
    フィラー検出の有無も照合できる。

    mode: Bの質問マーカー判定は「◯つ目の質問」等の定型句前提のため qa/both 専用。
    group-consult / whole では冒頭・末尾テキストをレポートに表示するだけに留め、
    ⚠️（合否）には反映しない（指名パターンや通常の会話には質問マーカーが出ないため）。
    """
    from analyzer import STRONG_MARKER_PATTERN, WEAK_MARKER_PATTERN

    duration = _get_duration(video_path)
    total_warnings = 0

    clip_rows = []
    tail_has_next_marker_any = False
    reencode_ok_all = True
    length_ok_all = True

    for i, (clip_path, pair) in enumerate(zip(clip_paths, qa_pairs), start=1):
        issues: List[str] = []
        head_text = ""
        tail_text = ""
        clip_exists = Path(clip_path).exists() and Path(clip_path).stat().st_size > 0

        if not clip_exists:
            issues.append("ファイルが存在しないか空")
            length_ok_all = False
            reencode_ok_all = False
        else:
            streams = _stream_types(clip_path)
            if "video" not in streams or "audio" not in streams:
                issues.append("映像または音声ストリームが欠落")

            actual_dur = _get_duration(clip_path)
            expected_dur = pair["a_end"] - pair["q_start"]
            if abs(actual_dur - expected_dur) > LENGTH_TOLERANCE:
                issues.append(f"長さ不一致(実測{actual_dur:.1f}s/想定{expected_dur:.1f}s)")
                length_ok_all = False

            if not _tail_frame_decodable(clip_path):
                issues.append("末尾フレームがデコードできない(破損の疑い)")

            vcodec = _stream_codec(clip_path, "v:0")
            acodec = _stream_codec(clip_path, "a:0")
            if vcodec != "h264" or acodec != "aac":
                reencode_ok_all = False

            head_text = _transcribe_window(clip_path, 0, HEAD_TAIL_WINDOW)
            tail_start = max(0.0, actual_dur - HEAD_TAIL_WINDOW)
            tail_text = _transcribe_window(clip_path, tail_start, None)

            if mode in ("qa", "both"):
                if STRONG_MARKER_PATTERN.search(tail_text):
                    issues.append("末尾に次の質問マーカー検出(混入の疑い)")
                    tail_has_next_marker_any = True
                if not (STRONG_MARKER_PATTERN.search(head_text) or WEAK_MARKER_PATTERN.search(head_text)):
                    issues.append("冒頭に質問マーカーが見当たらない(要目視確認)")

        verdict = "✅" if not issues else "⚠️ " + " / ".join(issues)
        if issues:
            total_warnings += 1

        dur_str = f"{int(expected_dur // 60)}:{int(expected_dur % 60):02d}" if clip_exists else "-"
        clip_rows.append(
            f"| {i} | {Path(clip_path).name} | {dur_str} | "
            f"{'✅' if clip_exists and not any('ストリーム' in x or 'デコード' in x or '存在' in x for x in issues) else '⚠️'} | "
            f"「{head_text[:30]}」 | 「{tail_text[:30]}」 | {verdict} |"
        )

    # カバレッジ検査は純粋に参考情報（未使用区間が挨拶なのか取りこぼしなのかは
    # 人間の判断材料として提示するのみ）であり、総合判定の合否には含めない。
    # 質問の取りこぼし自体は事前チェック（cross_check_qa_pairs）が別途検出する。
    coverage_lines = _coverage_gaps(qa_pairs, words, duration)

    naming_ok = _check_naming(clip_paths)
    if not naming_ok:
        total_warnings += 1

    output_dir_path = Path(output_dir)
    files_present = all(
        (output_dir_path / name).exists()
        for name in ("transcript.json", "analysis.json", "qa_list.md")
    ) and (output_dir_path / "qa").is_dir()
    if not files_present:
        total_warnings += 1

    endings_corrected = None
    fillers_empty = None
    if analysis is not None:
        raw_pairs = analysis.get("qa_pairs", [])
        if len(raw_pairs) == len(qa_pairs):
            endings_corrected = any(
                abs(raw.get("a_end", 0.0) - final["a_end"]) > 0.01
                for raw, final in zip(raw_pairs, qa_pairs)
            )
        fillers_empty = len(analysis.get("fillers", [])) == 0
        if endings_corrected is False:
            total_warnings += 1
        if fillers_empty is False:
            total_warnings += 1

    compliance_rows = [
        f"| 余白なし | {'✅' if length_ok_all else '⚠️'} |",
        f"| 次質問非食い込み | {'⚠️' if tail_has_next_marker_any else '✅'} |",
        f"| 再エンコード方式 | {'✅' if reencode_ok_all else '⚠️'} |",
        f"| 終端3段補正の適用 | {'✅' if endings_corrected else ('⚠️' if endings_corrected is False else '未検証(analysis.json未指定)')} |",
        f"| 出力ファイル一式 | {'✅' if files_present else '⚠️'} |",
        f"| 命名規則 | {'✅' if naming_ok else '⚠️'} |",
        f"| qaモードでフィラー検出なし | {'✅' if fillers_empty else ('⚠️' if fillers_empty is False else '未検証(analysis.json未指定)')} |",
    ]

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    overall = "✅ 合格" if total_warnings == 0 else f"⚠️ 要確認 {total_warnings}件"

    lines = [
        f"# クリップ検証レポート（{now}）",
        f"総合判定: {overall}",
        "",
        "## クリップ検査",
        "| # | ファイル | 長さ | 健全性 | 冒頭 | 末尾 | 判定 |",
        "|---|---------|------|--------|------|------|------|",
        *clip_rows,
        "",
        "## カバレッジ",
    ]
    if coverage_lines:
        lines.extend(coverage_lines)
    else:
        lines.append("- 未使用区間なし ✅")
    lines += [
        "",
        "## 仕様準拠チェック",
        "| 項目 | 結果 |",
        "|---|---|",
        *compliance_rows,
    ]

    report_path = output_dir_path / "qa_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path
