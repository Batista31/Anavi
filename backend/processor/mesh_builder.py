"""
Builds heightmap + occupancy grid from a stitched top-view image.

3-axis extension:
  wall_contrib (optional) is a (GRID_SIZE x GRID_SIZE) float32 array produced
  by projector.py from eye-level wall photos.  Values near 1.0 indicate wall /
  obstacle presence seen from the side.

Occupancy grid : 0 = free, 1 = obstacle.
Height map     : float32 [0, 1], 1 = raised wall / obstacle, 0 = floor.
"""

import cv2
import numpy as np
from processor.ai_analyzer import analyze, build_floor_mask

GRID_SIZE = 200


# ── Color-based floor mask (used when AI is unavailable) ─────────────────────

def _color_floor_mask(image_bgr: np.ndarray, shape: tuple) -> np.ndarray:
    """
    Estimate which pixels are floor by colour similarity to the bottom-centre
    of the image (where the floor is most reliably visible).

    Returns a float mask at `shape` (rows, cols) with:
      1.0 = floor-coloured  (suppress Canny here — probably not a wall)
      0.0 = non-floor / unknown
    """
    H, W = image_bgr.shape[:2]
    rows, cols = shape

    # Sample floor colour from the bottom 25 % of the image, centre 50 %
    r0 = int(H * 0.75)
    c0, c1 = int(W * 0.25), int(W * 0.75)
    sample = image_bgr[r0:, c0:c1]
    if sample.size == 0:
        return np.ones(shape, dtype=np.float32)

    # Robust median colour of the sample
    floor_bgr = np.median(sample.reshape(-1, 3), axis=0).astype(np.uint8)

    # Per-pixel Lab colour distance from the floor colour
    lab_img   = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    floor_lab = cv2.cvtColor(
        floor_bgr.reshape(1, 1, 3), cv2.COLOR_BGR2LAB,
    ).astype(np.float32).squeeze()

    dist      = np.sqrt(np.sum((lab_img - floor_lab) ** 2, axis=2))
    max_dist  = float(dist.max()) + 1e-6
    dist_norm = dist / max_dist

    # Pixels within 35 % of the colour-distance range → floor
    floor_full = (dist_norm < 0.35).astype(np.float32)
    return cv2.resize(floor_full, (cols, rows), interpolation=cv2.INTER_AREA)


# ── Main build function ───────────────────────────────────────────────────────

def build(
    image_bgr: np.ndarray,
    wall_contrib: np.ndarray | None = None,
) -> dict:
    """
    Args:
        image_bgr:    top-view source image (BGR numpy array).
        wall_contrib: optional (GRID_SIZE, GRID_SIZE) float32 from eye-level
                      wall photos (output of projector.project_images).

    Returns a dict with:
        heightmap   – float32 ndarray (GRID_SIZE, GRID_SIZE) [0, 1]
        occupancy   – int32  ndarray (GRID_SIZE, GRID_SIZE) {0, 1}
        image_h / image_w / grid_size / ai_analysis
    """

    # ── 1. AI analysis ────────────────────────────────────────────────────────
    ai = analyze(image_bgr)

    # ── 2. Orientation correction ─────────────────────────────────────────────
    working = image_bgr.copy()
    if ai:
        correction = int(ai.get("orientation_correction", 0))
        if correction == 90:
            working = cv2.rotate(working, cv2.ROTATE_90_CLOCKWISE)
        elif correction == 180:
            working = cv2.rotate(working, cv2.ROTATE_180)
        elif correction == 270:
            working = cv2.rotate(working, cv2.ROTATE_90_COUNTERCLOCKWISE)

    # ── 3. Canny edge map ─────────────────────────────────────────────────────
    gray    = cv2.cvtColor(working, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    obstacle_density = ai.get("obstacle_density", 0.4) if ai else 0.4
    t_low  = int(20 + obstacle_density * 40)   # 20-60
    t_high = int(60 + obstacle_density * 80)   # 60-140
    edges  = cv2.Canny(blurred, t_low, t_high)

    # ── 4. Floor-mask edge suppression ────────────────────────────────────────
    if ai:
        # AI-provided layout hint
        hint        = ai.get("floor_mask_hint", "scattered_obstacles")
        floor_mask  = build_floor_mask(hint, edges.shape)
        nav_frac    = float(ai.get("navigable_fraction", 0.5))
        suppression = min(0.85, 0.45 + nav_frac * 0.40)
    else:
        # No AI: derive floor mask from image colour statistics
        floor_mask  = _color_floor_mask(working, edges.shape)
        suppression = 0.80   # strongly suppress edges in floor-coloured areas

    edges_f  = edges.astype(np.float32)
    edges_f *= (1.0 - suppression * floor_mask)   # dampen edges on the floor
    edges    = np.clip(edges_f, 0, 255).astype(np.uint8)

    # ── 5. Dilate for thick walls ─────────────────────────────────────────────
    dil_kernel    = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges_dilated = cv2.dilate(edges, dil_kernel, iterations=2)

    # ── 6. Downsample to GRID_SIZE x GRID_SIZE ────────────────────────────────
    small = cv2.resize(
        edges_dilated, (GRID_SIZE, GRID_SIZE), interpolation=cv2.INTER_AREA,
    ).astype(np.float32)

    # ── 7. Merge wall contributions from eye-level photos ─────────────────────
    wall_small: np.ndarray | None = None
    if wall_contrib is not None:
        wall_small = (
            cv2.resize(wall_contrib, (GRID_SIZE, GRID_SIZE),
                       interpolation=cv2.INTER_LINEAR)
            if wall_contrib.shape != (GRID_SIZE, GRID_SIZE)
            else wall_contrib.copy()
        )
        small = np.clip(small + wall_small * 200.0, 0, 255)

    # ── 8. Occupancy threshold ────────────────────────────────────────────────
    occ_threshold = int(15 + obstacle_density * 25) if ai else 30
    occupancy = (small > occ_threshold).astype(np.int32)

    # AI-guaranteed floor zones force occupancy to 0 (unless wall evidence says otherwise)
    if ai:
        hint             = ai.get("floor_mask_hint", "scattered_obstacles")
        floor_mask_small = build_floor_mask(hint, (GRID_SIZE, GRID_SIZE))
        strong_edge      = (small > 80).astype(np.int32)
        floor_guaranteed = (floor_mask_small > 0.5).astype(np.int32)
        wall_obstacle    = (
            (wall_small > 0.4).astype(np.int32)
            if wall_small is not None
            else np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.int32)
        )
        occupancy = np.where(
            (floor_guaranteed == 1) & (strong_edge == 0) & (wall_obstacle == 0),
            0,
            occupancy,
        )

    heightmap = (small / 255.0).astype(np.float32)

    return {
        "heightmap":   heightmap,
        "occupancy":   occupancy,
        "image_h":     image_bgr.shape[0],
        "image_w":     image_bgr.shape[1],
        "grid_size":   GRID_SIZE,
        "ai_analysis": ai,
    }
