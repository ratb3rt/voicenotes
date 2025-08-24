import argparse
import asyncio
import json
from pathlib import Path
import time
from datetime import datetime

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from db import connect
from importer import Importer

# Define the datetime filter
def datetime_filter(value: int) -> str:
    """Convert an integer timestamp to a formatted date string."""
    try:
        return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return "Invalid date"

app = FastAPI()

# Templates & static
base_dir = Path(__file__).parent
(app_dir := base_dir / "static").mkdir(exist_ok=True)
(templates_dir := base_dir / "templates").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(app_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))
templates.env.filters["datetime"] = datetime_filter

default_config_path = base_dir / "config.yaml"

IMP: Importer|None = None

def load_cfg(path: str):
    global CFG, IMP
    CFG = yaml.safe_load(Path(path).read_text())
    IMP = Importer(path)

load_cfg(str(default_config_path))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    async with connect(CFG["db_path"]) as db:
        rows = []
        async with db.execute("SELECT id, imported_at, duration_sec, trimmed_path FROM recordings WHERE deleted=0 ORDER BY imported_at DESC") as cur:
            async for r in cur:
                rows.append({"id": r[0], "imported_at": r[1], "duration": r[2], "trimmed": r[3]})
    return templates.TemplateResponse("index.html", {"request": request, "rows": rows})

@app.get("/recordings/{rid}", response_class=HTMLResponse)
async def recording(request: Request, rid: str):
    async with connect(CFG["db_path"]) as db:
        async with db.execute("SELECT id, trimmed_path, transcription_json, imported_at, duration_sec FROM recordings WHERE id=? AND deleted=0", (rid,)) as cur:
            row = await cur.fetchone()
            if not row:
                raise HTTPException(404)
    payload = json.loads(row[2])
    return templates.TemplateResponse("recording.html", {
        "request": request,
        "id": row[0],
        "audio_path": f"/audio/{row[0]}",
        "imported_at": row[3],
        "duration": row[4],
        "sentences": payload.get("sentences", []),
    })

@app.get("/audio/{rid}")
async def audio(rid: str):
    async with connect(CFG["db_path"]) as db:
        async with db.execute("SELECT trimmed_path FROM recordings WHERE id=?", (rid,)) as cur:
            row = await cur.fetchone()
            if not row:
                raise HTTPException(404)
    return FileResponse(row[0], media_type="audio/wav")

@app.post("/recordings/{rid}/delete")
async def delete_rec(rid: str):
    async with connect(CFG["db_path"]) as db:
        await db.execute("UPDATE recordings SET deleted=1 WHERE id=?", (rid,))
        await db.commit()
    return {"ok": True}

# Background tasks for nightly retention if running as server
async def retention_job():
    while True:
        try:
            await Importer(CFG_PATH).retention_cleanup()
        except Exception:
            pass
        await asyncio.sleep(24*3600)

# CLI entrypoint for one-shot import (udev‑triggered)
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--mount", help="Mount path when triggered by udev")
    args = parser.parse_args()

    CFG_PATH = args.config
    load_cfg(CFG_PATH)

    if args.once:
        # One‑shot import
        asyncio.run(Importer(CFG_PATH).import_from_mount(args.mount))
    else:
        # Run API server (uvicorn loads app:app via systemd unit)
        pass