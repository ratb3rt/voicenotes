import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List

# Wrapper around whisper.cpp CLI for JSON with word timestamps
# Assumes binary supports -oj (output json) and -of (output base name)

def run_whisper(in_wav: Path, binary: Path, model: Path, language: str, beam_size: int, threads: int, vad: bool, vad_model: Path = None) -> Dict[str, Any]:
    out_json = in_wav.with_suffix("")  # whisper adds .json when -oj used
    cmd = [
        str(binary), "-m", str(model), "-f", str(in_wav),
        "-l", language, "-oj", "-of", str(out_json),
        "-bs", str(beam_size), "-t", str(threads)
    ]
    if vad:
        cmd += ["--vad", "--vad-model", vad_model]
    subprocess.run(cmd, check=True)
    data = json.loads((Path(str(out_json)) .with_suffix(".json")).read_text())
    return data

# Simple sentence segmentation from word-level timestamps
# Groups words until sentence-ending punctuation, emits start/end

def words_to_sentences(whisper_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    words = []
    for seg in whisper_json.get("segments", []):
        for w in seg.get("words", []):
            words.append({
                "text": w.get("word", "").strip(),
                "start": w.get("start", seg.get("start")),
                "end": w.get("end", seg.get("end"))
            })
    sentences = []
    buf, s_start = [], None
    for w in words:
        if s_start is None:
            s_start = w["start"]
        buf.append(w)
        if w["text"].endswith(('.', '!', '?')):
            sentences.append({
                "start": s_start,
                "end": w["end"],
                "text": " ".join(x["text"] for x in buf).strip()
            })
            buf, s_start = [], None
    if buf:
        sentences.append({
            "start": s_start,
            "end": buf[-1]["end"],
            "text": " ".join(x["text"] for x in buf).strip()
        })
    return sentences