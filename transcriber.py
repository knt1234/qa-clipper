import json
from pathlib import Path
from typing import List

import whisper


def transcribe(audio_path: str, model_name: str = "large-v3") -> List[dict]:
    """Transcribe audio with word-level timestamps.
    Returns list of {word, start, end}.
    """
    model = whisper.load_model(model_name)
    result = model.transcribe(
        audio_path,
        language="ja",
        word_timestamps=True,
        verbose=False,
    )

    words = []
    for segment in result["segments"]:
        for w in segment.get("words", []):
            words.append({
                "word": w["word"].strip(),
                "start": round(w["start"], 3),
                "end": round(w["end"], 3),
            })

    return words


def save_transcript(words: List[dict], output_path: str) -> None:
    Path(output_path).write_text(
        json.dumps(words, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_transcript(path: str) -> List[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
