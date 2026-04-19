import subprocess
import os
from pathlib import Path
from typing import Optional, Tuple


def download_video(url: str, output_dir: str, cookies_from_browser: Optional[str] = None) -> Tuple[str, str]:
    """Download YouTube video and extract audio WAV.
    Returns (video_path, audio_path).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_template = str(output_dir / "%(title)s.%(ext)s")
    cmd = [
        "/opt/homebrew/bin/yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", video_template,
        "--print", "filename",
        "--no-simulate",
    ]
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    cmd.append(url)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )

    video_path = result.stdout.strip().splitlines()[-1]
    if not os.path.exists(video_path):
        candidates = list(output_dir.glob("*.mp4"))
        if not candidates:
            raise FileNotFoundError(f"Downloaded video not found in {output_dir}")
        video_path = str(sorted(candidates, key=os.path.getmtime)[-1])

    audio_path = str(Path(video_path).with_suffix(".wav"))
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-ar", "16000",
            "-ac", "1",
            "-vn",
            audio_path,
        ],
        check=True,
        capture_output=True,
    )

    return video_path, audio_path
