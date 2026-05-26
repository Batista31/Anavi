"""
ANAVI Backend — FastAPI

Endpoints:
  POST /process        Upload photos → stitch → build mesh → return session data
  POST /pathfind       Given session + start/end grid coords + algorithm → path
  GET  /topview/{sid}  Serve the stitched top-view JPEG
  DELETE /session/{sid} Clean up session files
"""

import uuid
import shutil
import base64
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv

load_dotenv()   # loads .env from the working directory

import os as _os
_key = _os.getenv("GEMINI_API_KEY", "")
print(f"[ANAVI] GEMINI_API_KEY {'SET (…' + _key[-6:] + ')' if _key else 'NOT SET — AI analysis disabled'}", flush=True)

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from processor.stitcher import stitch
from processor.mesh_builder import build
from pathfinding import astar, dijkstra, rrt

app = FastAPI(title="ANAVI Navigation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

# In-memory store: session_id → mesh metadata dict
_sessions: dict[str, dict] = {}


# ─── Models ──────────────────────────────────────────────────────────────────

class ProcessResponse(BaseModel):
    session_id: str
    image_w: int
    image_h: int
    grid_size: int
    heightmap: list[list[float]]   # GRID_SIZE × GRID_SIZE, sent as nested list
    occupancy: list[list[int]]     # GRID_SIZE × GRID_SIZE
    ai_analysis: dict | None = None   # Gemini layout analysis (None if unavailable)


class PathRequest(BaseModel):
    session_id: str
    start: tuple[int, int]   # (row, col) in grid coordinates
    goal: tuple[int, int]
    algorithm: Literal["astar", "dijkstra", "rrt"] = "astar"


class PathResponse(BaseModel):
    algorithm: str
    path: list[tuple[int, int]] | None   # None = no path found
    nodes_explored: int | None = None


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.post("/process", response_model=ProcessResponse)
async def process_images(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "No files uploaded.")

    session_id = str(uuid.uuid4())[:8]
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir()

    # Save uploaded files
    saved_paths: list[Path] = []
    for f in files:
        dest = session_dir / f.filename
        content = await f.read()
        dest.write_bytes(content)
        saved_paths.append(dest)

    print(f"[ANAVI] /process called — {len(files)} files, session {session_id}", flush=True)

    # Stitch images
    try:
        stitched = stitch(saved_paths)
    except Exception as e:
        shutil.rmtree(session_dir, ignore_errors=True)
        raise HTTPException(500, f"Stitching failed: {e}")

    # Save top-view JPEG
    topview_path = session_dir / "topview.jpg"
    cv2.imwrite(str(topview_path), stitched)

    print(f"[ANAVI] Stitching done — shape {stitched.shape}, calling build()...", flush=True)
    # Build mesh metadata
    mesh = build(stitched)
    _sessions[session_id] = {
        "mesh": mesh,
        "session_dir": session_dir,
    }

    return ProcessResponse(
        session_id=session_id,
        image_w=mesh["image_w"],
        image_h=mesh["image_h"],
        grid_size=mesh["grid_size"],
        heightmap=mesh["heightmap"].tolist(),
        occupancy=mesh["occupancy"].tolist(),
        ai_analysis=mesh.get("ai_analysis"),
    )


@app.post("/pathfind", response_model=PathResponse)
def pathfind(req: PathRequest):
    session = _sessions.get(req.session_id)
    if session is None:
        raise HTTPException(404, "Session not found.")

    occupancy = session["mesh"]["occupancy"].tolist()
    grid_size = session["mesh"]["grid_size"]

    # Clamp coordinates to grid bounds
    def clamp(rc):
        r = max(0, min(grid_size - 1, rc[0]))
        c = max(0, min(grid_size - 1, rc[1]))
        return (r, c)

    start = clamp(req.start)
    goal = clamp(req.goal)

    if req.algorithm == "astar":
        path = astar.run(occupancy, start, goal)
    elif req.algorithm == "dijkstra":
        path = dijkstra.run(occupancy, start, goal)
    elif req.algorithm == "rrt":
        path = rrt.run(occupancy, start, goal)
    else:
        raise HTTPException(400, "Unknown algorithm.")

    return PathResponse(algorithm=req.algorithm, path=path)


@app.get("/topview/{session_id}")
def get_topview(session_id: str):
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "Session not found.")
    topview = session["session_dir"] / "topview.jpg"
    if not topview.exists():
        raise HTTPException(404, "Top view not generated yet.")
    return FileResponse(str(topview), media_type="image/jpeg")


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    session = _sessions.pop(session_id, None)
    if session:
        shutil.rmtree(session["session_dir"], ignore_errors=True)
    return {"deleted": session_id}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/debug/ai")
def debug_ai():
    """Test Gemini connection with a blank image. Visit /api/debug/ai in browser."""
    import os
    import numpy as np
    from processor.ai_analyzer import analyze

    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        return {"error": "GEMINI_API_KEY not set", "key_loaded": False}

    # Tiny 100x100 grey test image
    test_img = np.full((100, 100, 3), 128, dtype=np.uint8)
    try:
        result = analyze(test_img)
        return {"key_loaded": True, "key_suffix": key[-6:], "ai_result": result}
    except Exception as e:
        return {"key_loaded": True, "key_suffix": key[-6:], "error": str(e)}
