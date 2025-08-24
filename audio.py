import subprocess
from pathlib import Path

class AudioError(Exception):
    pass

# Use ffmpeg silenceremove to trim leading/trailing silence efficiently
# https://ffmpeg.org/ffmpeg-filters.html#silenceremove

def trim_silence(in_wav: Path, out_wav: Path, threshold_db: int, min_sil_ms: int, keep_ms: int) -> float:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    filt = (
        f"silenceremove=start_periods=1:start_silence={min_sil_ms/1000:.3f}:start_threshold={threshold_db}dB:"
        f"detection=peak,aformat=dblp,areverse,"
        f"silenceremove=start_periods=1:start_silence={min_sil_ms/1000:.3f}:start_threshold={threshold_db}dB,areverse"
    )
    # keep_silence achieved by padding after trim; simpler: fade pad is optional
    cmd = [
        "ffmpeg", "-y", "-i", str(in_wav),
        "-af", filt,
        str(out_wav)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise AudioError(e.stderr.decode(errors="ignore"))

    # Probe duration
    probe = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(out_wav)]
    p = subprocess.run(probe, check=True, capture_output=True)
    return float(p.stdout.decode().strip())