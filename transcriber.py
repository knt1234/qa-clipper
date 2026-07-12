import json
import os
from pathlib import Path
from typing import List

from faster_whisper import WhisperModel


def transcribe(audio_path: str, model_name: str = "large-v3-turbo",
               vad_filter: bool = True) -> List[dict]:
    """Transcribe audio with word-level timestamps.
    Returns list of {word, start, end}.

    large-v3-turbo は large-v3 のデコーダー層を間引いた軽量版で、精度をほぼ保ったまま
    CPU実行でも約2.6倍高速（実測: 3分音声で496秒→189秒）。vad_filter で無音区間を
    スキップし、cpu_threads で全コアを使わせることでさらに速度を稼ぐ。

    vad_filter は検査用途（editor.py の短い区間チェック）では False にすること。
    低音量の音源ではVADが実際の発話を無音と誤判定し、検査テキストが欠けることがある。
    """
    model = WhisperModel(model_name, device="cpu", compute_type="int8",
                          cpu_threads=os.cpu_count() or 4)
    segments, _info = model.transcribe(
        audio_path,
        language="ja",
        word_timestamps=True,
        vad_filter=vad_filter,
    )

    words = []
    for segment in segments:
        for w in segment.words or []:
            words.append({
                "word": w.word.strip(),
                "start": round(w.start, 3),
                "end": round(w.end, 3),
            })

    return words


def save_transcript(words: List[dict], output_path: str) -> None:
    Path(output_path).write_text(
        json.dumps(words, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_transcript(path: str) -> List[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
