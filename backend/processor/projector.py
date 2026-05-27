"""
3-axis image projector.

Converts each classified image into a contribution on the correct spatial plane:

  top_down      → used directly as a floor image
  oblique_floor → inverse-perspective warp of the floor region → bird's-eye patch
  eye_level     → wall obstacle profile stamped onto the matching grid edge
  ceiling       → ignored

Coordinate convention (top-down grid view):
  row 0        = north edge
  row N-1      = south edge
  col 0        = west edge
  col N-1      = east edge
  Y / height   = upward (walls have Y > 0)
"""

import cv2
import numpy as np
from pathlib import Path

GRID_SIZE = 200


# ── Floor projection ──────────────────────────────────────────────────────────

def warp_floor_to_topdown(bgr_img: np.ndarray, horizon_y: float) -> np.ndarray:
    """
    Inverse perspective mapping: turns the floor region (below the horizon line)
    of an oblique photo into an approximate bird's-eye rectangle.

    The perspective compression at the far end (near the horizon) is estimated
    from the horizon position:
      horizon_y ≈ 0.5  → near eye-level → heavy compression (wide trapezoid)
      horizon_y ≈ 0.85 → nearly overhead → light compression (narrow trapezoid)
    """
    H, W = bgr_img.shape[:2]
    hy = int(np.clip(horizon_y, 0.1, 0.95) * H)
    floor_h = H - hy
    if floor_h < 20:
        return bgr_img  # too little floor visible; return as-is

    # Estimate lateral compression at the horizon.
    # Camera tilt: horizon_y≈0.5 means ~90° (eye-level), 1.0 means 0° (top-down).
    # tan of the apparent half-angle at horizon ≈ (1 - horizon_y) * 0.6
    far_frac = float(np.clip(0.5 - horizon_y * 0.45, 0.03, 0.35))
    far_margin = int(W * far_frac)

    src_pts = np.float32([
        [far_margin,     hy],       # far-left of floor
        [W - far_margin, hy],       # far-right of floor
        [W - 1,          H - 1],    # near-right
        [0,              H - 1],    # near-left
    ])
    out_W, out_H = W, floor_h
    dst_pts = np.float32([
        [0,        0],
        [out_W-1,  0],
        [out_W-1,  out_H-1],
        [0,        out_H-1],
    ])

    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    return cv2.warpPerspective(bgr_img, M, (out_W, out_H))


# ── Wall projection ───────────────────────────────────────────────────────────

def extract_wall_contribution(
    bgr_img: np.ndarray,
    cls_info: dict,
    grid_size: int = GRID_SIZE,
) -> np.ndarray:
    """
    From an eye-level photo, produce a (grid_size × grid_size) float32 array
    where values in [0, 1] represent obstacle/wall presence at that grid position.

    The wall_direction hint controls which edge of the grid is stamped:
      north  → top rows   (row 0 … wall_depth)
      south  → bottom rows
      east   → right cols
      west   → left cols
      unknown→ all four edges at lower weight (conservative)

    Obstacle evidence comes from Canny edges in the wall region of the photo
    (above the horizon line, where walls/objects appear).
    """
    H, W = bgr_img.shape[:2]
    direction = cls_info.get("wall_direction", "unknown")
    horizon_y = cls_info.get("horizon_y")

    # Isolate the wall/object region above the horizon
    if horizon_y and 0.05 < horizon_y < 0.98:
        wall_region = bgr_img[:int(horizon_y * H), :]
    else:
        wall_region = bgr_img

    if wall_region.shape[0] < 4:
        return np.zeros((grid_size, grid_size), dtype=np.float32)

    gray    = cv2.cvtColor(wall_region, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges   = cv2.Canny(blurred, 25, 75)

    # Column profile: how much edge content is in each horizontal slice of the photo.
    # This maps to the lateral (X) position along the wall face.
    col_profile = edges.sum(axis=0).astype(np.float32)
    max_val = col_profile.max()
    if max_val > 0:
        col_profile /= max_val

    # Resize the column profile to grid_size columns
    col_grid = cv2.resize(
        col_profile.reshape(1, -1), (grid_size, 1),
        interpolation=cv2.INTER_LINEAR,
    )[0]

    contrib    = np.zeros((grid_size, grid_size), dtype=np.float32)
    wall_depth = max(4, grid_size // 20)  # cells deep that the wall influence reaches

    def _stamp_rows(start_row: int, step: int) -> None:
        for d in range(wall_depth):
            weight = 1.0 - d / wall_depth
            r = start_row + step * d
            contrib[r, :] = np.maximum(contrib[r, :], col_grid * weight)

    def _stamp_cols(start_col: int, step: int) -> None:
        for d in range(wall_depth):
            weight = 1.0 - d / wall_depth
            c = start_col + step * d
            contrib[:, c] = np.maximum(contrib[:, c], col_grid * weight)

    if direction == "north":
        _stamp_rows(0, +1)
    elif direction == "south":
        _stamp_rows(grid_size - 1, -1)
    elif direction == "east":
        _stamp_cols(grid_size - 1, -1)
    elif direction == "west":
        _stamp_cols(0, +1)
    else:
        # Unknown direction: stamp all four edges at reduced weight
        full = cv2.resize(edges, (grid_size, grid_size),
                          interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        contrib = full * 0.5

    return contrib


# ── Master projector ──────────────────────────────────────────────────────────

def project_images(
    image_paths: list[Path],
    classifications: list[dict],
    grid_size: int = GRID_SIZE,
) -> dict:
    """
    Project every image onto the correct spatial plane and merge results.

    Returns:
      floor_images        – list[np.ndarray]  BGR images warped to near-top-down
      wall_contrib        – (grid_size, grid_size) float32  merged wall evidence
      has_wall_data       – bool  any eye-level photos contributed
      has_floor_data      – bool  any floor/oblique photos contributed
      perspective_summary – dict[str, int]  counts per perspective type
    """
    floor_images: list[np.ndarray] = []
    wall_contrib = np.zeros((grid_size, grid_size), dtype=np.float32)
    has_wall_data  = False
    has_floor_data = False
    summary: dict[str, int] = {}

    for path, cls in zip(image_paths, classifications):
        img = cv2.imread(str(path))
        if img is None:
            continue

        persp = cls.get("perspective", "oblique_floor")
        summary[persp] = summary.get(persp, 0) + 1

        if persp == "top_down":
            floor_images.append(img)
            has_floor_data = True

        elif persp == "oblique_floor":
            horizon_y = cls.get("horizon_y") or 0.65
            warped = warp_floor_to_topdown(img, float(horizon_y))
            floor_images.append(warped)
            has_floor_data = True

        elif persp == "eye_level":
            wc = extract_wall_contribution(img, cls, grid_size)
            wall_contrib = np.maximum(wall_contrib, wc)
            has_wall_data = True

        # "ceiling" photos are silently skipped

    # If no floor images at all, fall back to using every image as floor input
    if not floor_images:
        for path in image_paths:
            img = cv2.imread(str(path))
            if img is not None:
                floor_images.append(img)
                has_floor_data = True

    return {
        "floor_images":        floor_images,
        "wall_contrib":        wall_contrib,
        "has_wall_data":       has_wall_data,
        "has_floor_data":      has_floor_data,
        "perspective_summary": summary,
    }
