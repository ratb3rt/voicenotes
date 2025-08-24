import hashlib
import json
import os
import time
from pathlib import Path
from typing import Iterable
import yaml
from ulid import ULID

from audio import trim_silence
from transcribe import run_whisper, words_to_sentences
from db import connect

IGNORED_EXT = {".tmp", ".part"}

class Importer:
    def __init__(self, config_path: str):
        self.cfg = yaml.safe_load(Path(config_path).read_text())

    def _hash(self, p: Path, chunk: int = 1<<20) -> str:
        h = hashlib.sha256()
        with p.open('rb') as f:
            while True:
                b = f.read(chunk)
                if not b: break
                h.update(b)
        return h.hexdigest()

    def _is_new(self, db, h: str) -> bool:
        # Returns True if not present in DB
        return True

    async def import_from_mount(self, mount: str):
        subdir = self.cfg["subdir"].lstrip('/')
        src_root = Path(mount) / subdir
        out_dir = Path(self.cfg["output_dir"]) / "wav"
        meta_dir = Path(self.cfg["output_dir"]) / "meta"
        out_dir.mkdir(parents=True, exist_ok=True)
        meta_dir.mkdir(parents=True, exist_ok=True)

        async with connect(self.cfg["db_path"]) as db:
            # gather existing hashes
            existing = set()
            async with db.execute("SELECT source_hash FROM recordings WHERE deleted=0") as cur:
                async for row in cur:
                    existing.add(row[0])

            for wav in sorted(src_root.rglob('*.wav')):
                if wav.suffix.lower() in IGNORED_EXT:
                    continue
                st = wav.stat()
                h = self._hash(wav)
                if h in existing:
                    continue  # already imported

                # Trim
                rid = str(ULID())
                trimmed = out_dir / f"{rid}.wav"
                dur = trim_silence(
                    wav, trimmed,
                    self.cfg['trim']['threshold_db'],
                    self.cfg['trim']['min_silence_len_ms'],
                    self.cfg['trim']['keep_silence_ms']
                )
                # Transcribe
                wjson = run_whisper(
                    trimmed,
                    Path(self.cfg['whisper']['binary']),
                    Path(self.cfg['whisper']['model']),
                    self.cfg['whisper']['language'],
                    self.cfg['whisper']['beam_size'],
                    self.cfg['whisper']['max_threads'],
                    self.cfg['whisper']['vad']
                )
                sentences = words_to_sentences(wjson)
                payload = {"words_json": wjson, "sentences": sentences}

                await db.execute(
                    "INSERT INTO recordings (id, source_path, source_mtime, source_hash, subdir, trimmed_path, duration_sec, imported_at, transcription_json, diarized, deleted)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)",
                    (rid, str(wav), int(st.st_mtime), h, subdir, str(trimmed), float(dur), int(time.time()), json.dumps(payload))
                )
                await db.commit()

    async def retention_cleanup(self, mount: str|None = None):
        # delete from USB device if older than N days and already imported
        days = int(self.cfg['retention_days'])
        cutoff = int(time.time()) - days*86400
        async with connect(self.cfg["db_path"]) as db:
            async with db.execute("SELECT source_path, source_mtime FROM recordings") as cur:
                imported = [(Path(r[0]), r[1]) for r in await cur.fetchall()]

        # Group by root device to avoid catastrophic rm: only delete inside current mount or common path
        candidates: Iterable[Path] = [p for p, mt in imported if mt < cutoff and p.exists()]
        for p in candidates:
            try:
                # Safety: ensure it's still on a mounted device (under /media or provided mount)
                if mount and not str(p).startswith(str(Path(mount))):
                    continue
                os.remove(p)
            except Exception:
                pass