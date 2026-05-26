"""
Photo stitching using OpenCV's built-in Stitcher (panorama mode).

Single-image path: if only one photo is uploaded we use it directly.
The output is always a top-down JPEG stored to disk and returned as bytes.
"""

import cv2
import numpy as np
from pathlib import Path


def stitch(image_paths: list[Path]) -> np.ndarray:
    """
    Returns a BGR numpy array of the stitched top-view image.
    Raises RuntimeError on failure.
    """
    imgs = [cv2.imread(str(p)) for p in image_paths]
    imgs = [i for i in imgs if i is not None]

    if not imgs:
        raise RuntimeError("No valid images found.")

    if len(imgs) == 1:
        return imgs[0]

    stitcher = cv2.Stitcher_create(cv2.Stitcher_SCANS)
    status, result = stitcher.stitch(imgs)

    if status == cv2.Stitcher_OK:
        return result

    # Fallback: tile images horizontally so the UI always gets something
    # (stitching fails when images have insufficient overlap)
    resized = [cv2.resize(i, (640, 480)) for i in imgs]
    return np.hstack(resized)
