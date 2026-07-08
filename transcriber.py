import json
from pathlib import Path
from typing import List

from faster_whisper import WhisperModel


def transcribe(audio_path: str, model_name: str = "large-v3") -> List[dict]:
    """Transcribe audio with word-level timestamps.
    Returns list of {word, start, end}.
    """
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(
        audio_path,
        language="ja",
        word_timestamps=True,
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
