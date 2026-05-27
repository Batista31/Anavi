"""
ANAVI Backend — FastAPI

Endpoints:
  POST /process        Upload photos → classify axes → project → stitch → build mesh
  POST /pathfind       Given session + start/end grid coords + algorithm → path
  GET  /topview/{sid}  Serve the stitched top-view JPEG
  DELETE /session/{sid} Clean up session files
"""

import uuid
import shutil
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv

load_dotenv()   # loads .env from the working directory

import os as _os
_key = _os.getenv("GEMINI_API_KEY", "")
print(
    f"[ANAVI] GEMINI_API_KEY {'SET (…' + _key[-6:] + ')' if _key else 'NOT SET — AI analysis disabled'}",
    flush=True,
)

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from processor.stitcher          import stitch
from processor.mesh_builder      import build
from processor.image_classifier  import classify_batch
from processor.projector         import project_images
from pathfinding import astar, dijkstra, rrt


def _pick_best_image(imgs: list[np.ndarray]) -> np.ndarray | None:
    """
    Return the floor image with the highest Laplacian variance (most texture /
    edge content).  Used to give mesh_builder a single clean image instead of a
    mosaic full of seam artefacts.
    """
    if not imgs:
        return None
    if len(imgs) == 1:
        return imgs[0]
    best: np.ndarray | None = None
    best_score = -1.0
    for img in imgs:
        gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if score > best_score:
            best_score = score
            best = img
    return best

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


# ─── Pydantic models ──────────────────────────────────────────────────────────

class ImageClassification(BaseModel):
    perspective: str                    # top_down | oblique_floor | eye_level | ceiling
    horizon_y: float | None = None      # normalised Y [0,1] where floor meets wall
    floor_fraction: float = 0.0         # fraction of image that is navigable floor
    wall_direction: str = "unknown"     # north|south|east|west|unknown
    tilt_from_vertical_deg: float = 90.0
    navigable_floor_visible: bool = True
    obstacle_density: float = 0.35


class ProcessResponse(BaseModel):
    session_id: str
    image_w: int
    image_h: int
    grid_size: int
    heightmap: list[list[float]]        # GRID_SIZE × GRID_SIZE
    occupancy: list[list[int]]          # GRID_SIZE × GRID_SIZE
    ai_analysis: dict | None = None
    # 3-axis fields
    image_classifications: list[ImageClassification] = []
    has_3d_data: bool = False
    perspective_summary: dict[str, int] = {}


class PathRequest(BaseModel):
    session_id: str
    start: tuple[int, int]              # (row, col) in grid coordinates
    goal:  tuple[int, int]
    algorithm: Literal["astar", "dijkstra", "rrt"] = "astar"


class PathResponse(BaseModel):
    algorithm: str
    path: list[tuple[int, int]] | None  # None = no path found
    nodes_explored: int | None = None


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.post("/process", response_model=ProcessResponse)
async def process_images(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "No files uploaded.")

    session_id = str(uuid.uuid4())[:8]
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # ── Save uploaded files ────────────────────────────────────────────────────
    saved_paths: list[Path] = []
    for f in files:
        filename = f.filename.replace('\\', '/')
        parts = [p for p in filename.split('/') if p and p not in ('.', '..')]
        if parts and parts[0].endswith(':'):
            parts = parts[1:]
        if not parts:
            parts = [Path(filename).name]

        dest = session_dir.joinpath(*parts)
        dest.parent.mkdir(parents=True, exist_ok=True)

        content = await f.read()
        dest.write_bytes(content)
        saved_paths.append(dest)

    print(f"[ANAVI] /process — {len(files)} file(s), session {session_id}", flush=True)

    # ── 1. Classify each image's viewing axis ──────────────────────────────────
    classifications = classify_batch(saved_paths)

    summary: dict[str, int] = {}
    for c in classifications:
        p = c.get("perspective", "unknown")
        summary[p] = summary.get(p, 0) + 1
    print(f"[ANAVI] Perspective summary: {summary}", flush=True)

    # ── 2. Project images onto correct spatial planes ──────────────────────────
    projection = project_images(saved_paths, classifications)

    # ── 3. Stitch floor images into a top-view composite ──────────────────────
    try:
        stitched = stitch(saved_paths, floor_images=projection["floor_images"])
    except Exception as e:
        shutil.rmtree(session_dir, ignore_errors=True)
        raise HTTPException(500, f"Stitching failed: {e}")

    # Clamp stitched image to a JPEG-safe size (JPEG max dim = 65 535 px).
    # The fallback mosaic is already bounded, but panorama results can be large.
    MAX_DIM = 4096
    h_px, w_px = stitched.shape[:2]
    if max(h_px, w_px) > MAX_DIM:
        scale   = MAX_DIM / max(h_px, w_px)
        new_w   = max(1, int(w_px * scale))
        new_h   = max(1, int(h_px * scale))
        stitched = cv2.resize(stitched, (new_w, new_h), interpolation=cv2.INTER_AREA)
        print(f"[ANAVI] Topview clamped to {new_w}x{new_h} (was {w_px}x{h_px})", flush=True)

    # Save top-view JPEG (check return value — imwrite returns False on failure)
    topview_path = session_dir / "topview.jpg"
    ok = cv2.imwrite(str(topview_path), stitched)
    if not ok:
        print(f"[ANAVI] WARNING: imwrite failed for {topview_path}", flush=True)

    print(f"[ANAVI] Stitching done — shape {stitched.shape}, building mesh…", flush=True)

    # ── 4. Build mesh using top-view + wall contributions ─────────────────────
    # When stitching fell back to a grid mosaic, Canny fires on every cell
    # boundary (each photo can have a different overall brightness level, so
    # the hard cuts between cells look like walls).
    # Fix: give mesh_builder the single most-textured floor image.  The mosaic
    # is already saved as the visual texture; the 200×200 grid spans the floor
    # plane uniformly regardless of which source image is used for edges.
    mesh_source = _pick_best_image(projection["floor_images"])
    if mesh_source is None:
        mesh_source = stitched

    wall_contrib = projection["wall_contrib"] if projection["has_wall_data"] else None
    mesh = build(mesh_source, wall_contrib=wall_contrib)

    # Restore texture dimensions (mosaic may differ from mesh_source)
    mesh["image_w"] = stitched.shape[1]
    mesh["image_h"] = stitched.shape[0]

    _sessions[session_id] = {
        "mesh":        mesh,
        "session_dir": session_dir,
    }

    # Strip private _keys before serialising classifications
    public_cls = [
        ImageClassification(
            perspective=c.get("perspective", "oblique_floor"),
            horizon_y=c.get("horizon_y"),
            floor_fraction=float(c.get("floor_fraction", 0.35)),
            wall_direction=c.get("wall_direction", "unknown"),
            tilt_from_vertical_deg=float(c.get("tilt_from_vertical_deg", 55.0)),
            navigable_floor_visible=bool(c.get("navigable_floor_visible", True)),
            obstacle_density=float(c.get("obstacle_density", 0.35)),
        )
        for c in classifications
    ]

    return ProcessResponse(
        session_id=session_id,
        image_w=mesh["image_w"],
        image_h=mesh["image_h"],
        grid_size=mesh["grid_size"],
        heightmap=mesh["heightmap"].tolist(),
        occupancy=mesh["occupancy"].tolist(),
        ai_analysis=mesh.get("ai_analysis"),
        image_classifications=public_cls,
        has_3d_data=projection["has_wall_data"],
        perspective_summary=summary,
    )


@app.post("/pathfind", response_model=PathResponse)
def pathfind(req: PathRequest):
    session = _sessions.get(req.session_id)
    if session is None:
        raise HTTPException(404, "Session not found.")

    occupancy = session["mesh"]["occupancy"].tolist()
    grid_size = session["mesh"]["grid_size"]

    def clamp(rc: tuple[int, int]) -> tuple[int, int]:
        r = max(0, min(grid_size - 1, rc[0]))
        c = max(0, min(grid_size - 1, rc[1]))
        return (r, c)

    start = clamp(req.start)
    goal  = clamp(req.goal)

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
    """Test Gemini + classifier pipeline with a synthetic image."""
    import os
    from processor.ai_analyzer    import analyze
    from processor.image_classifier import classify_single

    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        return {"error": "GEMINI_API_KEY not set", "key_loaded": False}

    test_img = np.full((200, 200, 3), 128, dtype=np.uint8)
    try:
        ai_result  = analyze(test_img)
        cls_result = classify_single(test_img, label="debug_test")
        return {
            "key_loaded":   True,
            "key_suffix":   key[-6:],
            "ai_analysis":  ai_result,
            "classification": {k: v for k, v in cls_result.items() if not k.startswith("_")},
        }
    except Exception as e:
        return {"key_loaded": True, "key_suffix": key[-6:], "error": str(e)}
