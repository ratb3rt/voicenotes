import aiosqlite
from contextlib import asynccontextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS recordings (
  id TEXT PRIMARY KEY,
  source_path TEXT NOT NULL,
  source_mtime INTEGER NOT NULL,
  source_hash TEXT NOT NULL,
  subdir TEXT NOT NULL,
  trimmed_path TEXT NOT NULL,
  duration_sec REAL NOT NULL,
  imported_at INTEGER NOT NULL,
  transcription_json TEXT NOT NULL,
  diarized INTEGER NOT NULL DEFAULT 0,
  deleted INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_recordings_hash ON recordings(source_hash);
CREATE INDEX IF NOT EXISTS idx_recordings_mtime ON recordings(source_mtime);
"""

@asynccontextmanager
async def connect(db_path: str):
    db = await aiosqlite.connect(db_path)
    try:
        await db.executescript(SCHEMA)
        await db.commit()
        yield db
    finally:
        await db.close()