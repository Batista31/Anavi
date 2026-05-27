"""
Photo stitching -- 3-axis aware.

Accepts pre-projected floor images (warped to near-top-down by projector.py)
when available; falls back to the raw uploaded paths otherwise.

Fallback strategy when OpenCV panorama stitching fails:
  1. Try stitching just the first 6 images (more likely to have overlap).
  2. If that also fails, arrange all images in a square grid mosaic so the
     output has bounded dimensions (never exceeds ~4096 x 4096 px, well within
     JPEG's 65 535-pixel limit).
"""

import math
import cv2
import numpy as np
from pathlib import Path

_CELL_W, _CELL_H = 640, 480   # cell size used in the grid-mosaic fallback


def stitch(
    image_paths: list[Path],
    floor_images: list[np.ndarray] | None = None,
) -> np.ndarray:
    """
    Stitch images into a single top-view BGR array.

    If floor_images (pre-warped by the projector) are supplied they are used
    instead of reading the raw files, giving better top-down alignment when
    the originals were taken at an angle.
    """
    if floor_images:
        imgs = [i for i in floor_images if i is not None]
    else:
        imgs = [cv2.imread(str(p)) for p in image_paths]
        imgs = [i for i in imgs if i is not None]

    if not imgs:
        raise RuntimeError("No valid images found.")

    if len(imgs) == 1:
        return imgs[0]

    # Attempt 1: full panorama stitch
    stitcher = cv2.Stitcher_create(cv2.Stitcher_SCANS)
    status, result = stitcher.stitch(imgs)
    if status == cv2.Stitcher_OK:
        return result

    # Attempt 2: stitch a smaller subset (first 6) -- more likely to have overlap
    if len(imgs) > 6:
        status2, result2 = stitcher.stitch(imgs[:6])
        if status2 == cv2.Stitcher_OK:
            return result2

    # Fallback: square grid mosaic with bounded output size
    return _grid_mosaic(imgs)


def _grid_mosaic(imgs: list[np.ndarray]) -> np.ndarray:
    """
    Arrange images in a roughly square grid at fixed cell size, then blend
    the seam lines so Canny edge detection doesn't fire on every cell boundary.

    Output width  ~ ceil(sqrt(N)) * CELL_W
    Output height ~ ceil(N / cols) * CELL_H
    Both stay well within JPEG's 65 535-pixel limit for any reasonable N.
    """
    resized = [cv2.resize(i, (_CELL_W, _CELL_H)) for i in imgs]
    n    = len(resized)
    cols = max(1, math.ceil(math.sqrt(n)))
    rows = math.ceil(n / cols)

    # Mid-grey padding so spare cells don't produce hard black edges
    blank = np.full((_CELL_H, _CELL_W, 3), 100, dtype=np.uint8)
    grid_rows = []
    for r in range(rows):
        row_imgs = resized[r * cols: (r + 1) * cols]
        while len(row_imgs) < cols:
            row_imgs.append(blank)
        grid_rows.append(np.hstack(row_imgs))

    mosaic = np.vstack(grid_rows)

    # ── Blend seam lines ───────────────────────────────────────────────────────
    # Cell boundaries produce hard colour jumps that Canny interprets as walls.
    # We blur a narrow band (±SEAM_R pixels) around each seam so the gradient
    # at the boundary drops below Canny's threshold.
    SEAM_R = 6   # half-width of the blending band in pixels
    H, W   = mosaic.shape[:2]

    # Horizontal seams (rows between grid rows)
    for sr in range(_CELL_H, H, _CELL_H):
        r0, r1 = max(0, sr - SEAM_R), min(H, sr + SEAM_R)
        band = mosaic[r0:r1, :]
        mosaic[r0:r1, :] = cv2.GaussianBlur(band, (1, SEAM_R * 2 + 1), 0)

    # Vertical seams (columns between grid columns)
    for sc in range(_CELL_W, W, _CELL_W):
        c0, c1 = max(0, sc - SEAM_R), min(W, sc + SEAM_R)
        band = mosaic[:, c0:c1]
        mosaic[:, c0:c1] = cv2.GaussianBlur(band, (SEAM_R * 2 + 1, 1), 0)

    return mosaic
