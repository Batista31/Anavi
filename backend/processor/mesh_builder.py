"""
Builds a 3D height-map mesh from a stitched top-view image.

Pipeline (with AI layer):
  1.  Send image to Gemini Vision → get space type, orientation, floor mask hint.
  2.  Rotate image if AI suggests an orientation correction.
  3.  Run Canny edge detection on the (possibly rotated) image.
  4.  Blend Canny edges with the AI floor mask:
        - Regions the AI says are floor  → suppress edges (lower height)
        - Regions the AI says are walls  → amplify edges  (taller spikes)
  5.  Dilate the blended result for pathfinding.
  6.  Downsample to GRID_SIZE × GRID_SIZE.
  7.  Return heightmap, occupancy, AI metadata.

Falls back to pure Canny if GEMINI_API_KEY is absent or the API call fails.

Occupancy grid : 0 = free, 1 = obstacle.
Height map     : float [0, 1], 1 = raised wall, 0 = floor.
"""

import cv2
import numpy as np
from processor.ai_analyzer import analyze, build_floor_mask

GRID_SIZE = 200   # pathfinding grid resolution (rows × cols)


def build(image_bgr: np.ndarray) -> dict:
    """
    Args:
        image_bgr: stitched top-view image as a BGR numpy array.

    Returns a dict:
        heightmap     – float32 ndarray (GRID_SIZE, GRID_SIZE) [0, 1]
        occupancy     – int32  ndarray (GRID_SIZE, GRID_SIZE) {0, 1}
        image_h       – original height (px)
        image_w       – original width  (px)
        grid_size     – GRID_SIZE constant
        ai_analysis   – dict from Gemini (or None)
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

    # Adaptive thresholds based on AI obstacle density
    obstacle_density = ai.get("obstacle_density", 0.4) if ai else 0.4
    # More obstacles → higher thresholds (less noise sensitivity)
    t_low  = int(20 + obstacle_density * 40)   # 20–60
    t_high = int(60 + obstacle_density * 80)   # 60–140
    edges  = cv2.Canny(blurred, t_low, t_high)

    # ── 4. Blend with AI floor mask ───────────────────────────────────────────
    if ai:
        hint       = ai.get("floor_mask_hint", "scattered_obstacles")
        floor_mask = build_floor_mask(hint, edges.shape)   # 1=floor, 0=wall

        # Suppress edges in AI-identified floor zones (reduce false walls)
        nav_frac   = float(ai.get("navigable_fraction", 0.5))
        suppression = min(0.80, 0.40 + nav_frac * 0.40)   # 0.40–0.80
        edges_f    = edges.astype(np.float32)
        edges_f   *= (1.0 - suppression * floor_mask)      # dampen floor edges
        edges      = np.clip(edges_f, 0, 255).astype(np.uint8)

    # ── 5. Dilate for thick walls ─────────────────────────────────────────────
    kernel        = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges_dilated = cv2.dilate(edges, kernel, iterations=2)

    # ── 6. Downsample to GRID_SIZE × GRID_SIZE ────────────────────────────────
    small = cv2.resize(edges_dilated, (GRID_SIZE, GRID_SIZE),
                       interpolation=cv2.INTER_AREA)

    # ── 7. Occupancy + heightmap ──────────────────────────────────────────────
    # Dynamic obstacle threshold — sparser spaces need lower threshold
    occ_threshold = int(15 + obstacle_density * 25) if ai else 30
    occupancy = (small > occ_threshold).astype(np.int32)

    # Apply AI floor mask directly to occupancy (guaranteed clear paths)
    if ai:
        hint       = ai.get("floor_mask_hint", "scattered_obstacles")
        floor_mask_small = build_floor_mask(hint, (GRID_SIZE, GRID_SIZE))
        # Where AI says floor AND Canny found no strong edge → force free
        strong_edge = (small > 80).astype(np.int32)
        floor_guaranteed = (floor_mask_small > 0.5).astype(np.int32)
        occupancy = np.where(
            (floor_guaranteed == 1) & (strong_edge == 0),
            0,           # guaranteed navigable
            occupancy,   # keep Canny result elsewhere
        )

    heightmap = (small / 255.0).astype(np.float32)

    return {
        "heightmap":   heightmap,
        "occupancy":   occupancy,
        "image_h":     image_bgr.shape[0],
        "image_w":     image_bgr.shape[1],
        "grid_size":   GRID_SIZE,
        "ai_analysis": ai,   # None if Gemini unavailable
    }
