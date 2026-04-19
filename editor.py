import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple

FILLER_BUFFER = 0.05


def _get_duration(video_path: str) -> float:
    result = subprocess.run(
        [
            "/opt/homebrew/bin/ffprobe", "-v", "error",
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


def remove_fillers(video_path: str, fillers: List[dict], output_path: str) -> str:
    if not fillers:
        subprocess.run(
            ["/opt/homebrew/bin/ffmpeg", "-y", "-i", video_path, "-c", "copy", output_path],
            check=True, capture_output=True,
        )
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

    subprocess.run(
        [
            "/opt/homebrew/bin/ffmpeg", "-y",
            "-i", video_path,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ],
        check=True, capture_output=True,
    )

    return output_path


def extract_qa_clips(video_path: str, qa_pairs: List[dict], output_dir: str,
                     padding: float = 1.5) -> List[str]:
    """Extract Q&A clips with padding before/after each clip.
    padding: seconds to add before q_start and after a_end (default 1.5s).
    """
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    duration = _get_duration(video_path)

    paths = []
    for i, pair in enumerate(qa_pairs, start=1):
        title = _sanitize_filename(pair.get("title", f"clip_{i:03d}"))
        out = str(output_dir_path / f"{i:03d}_{title}.mp4")
        start = max(0.0, pair["q_start"] - padding)
        end = min(duration, pair["a_end"] + padding)
        subprocess.run(
            [
                "/opt/homebrew/bin/ffmpeg", "-y",
                "-ss", str(start),
                "-to", str(end),
                "-i", video_path,
                "-c", "copy",
                "-reset_timestamps", "1",
                out,
            ],
            check=True, capture_output=True,
        )
        paths.append(out)

    return paths
