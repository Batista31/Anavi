"""
Per-image perspective classifier for 3-axis spatial mapping.

Classifies each uploaded photo's viewing angle so it can be correctly
projected onto the right plane of the 3D grid:
  top_down     → XY floor plane (bird's eye)
  oblique_floor→ XY floor plane after inverse-perspective warp
  eye_level    → XZ or YZ wall plane
  ceiling      → ignored (not useful for floor navigation)

AI (Gemini) is tried first; robust heuristic fallback when quota is exhausted.
"""

import os
import json
import sys
import numpy as np
import cv2
from pathlib import Path

_CLASSIFY_PROMPT = """\
Analyze this photo taken inside or near a physical space for 3D robot-navigation mapping.
Determine the camera viewing angle and what spatial plane this image represents.
Return ONLY valid JSON — no markdown, no explanation:
{
  "perspective": "top_down",
  "horizon_y": null,
  "floor_fraction": 0.0,
  "wall_direction": "unknown",
  "tilt_from_vertical_deg": 0,
  "navigable_floor_visible": false,
  "obstacle_density": 0.1
}

perspective values:
  "top_down"      = camera pointing straight down at the floor (overhead/drone shot)
  "oblique_floor" = camera angled downward; floor visible in the lower portion of the frame
  "eye_level"     = camera roughly horizontal; image mostly shows walls or objects at eye height
  "ceiling"       = camera pointing upward at the ceiling

horizon_y: normalized Y in [0.0, 1.0] where floor meets wall/background. null for top_down or ceiling.
floor_fraction: fraction of image area [0.0-1.0] that shows navigable floor.
wall_direction: for eye_level shots the compass direction the camera faces — "north", "south", "east", "west", or "unknown".
tilt_from_vertical_deg: 0 = straight down, 90 = horizontal, 180 = straight up.
navigable_floor_visible: true if any floor a wheeled robot could drive on is visible.
obstacle_density: 0.0 = fully clear, 1.0 = completely blocked.\
"""


# ── Quota state (module-level) ────────────────────────────────────────────────
# Once any model returns 429 the free-tier daily quota is gone for this run.
# Skip all further AI classification calls to avoid wasting time and log spam.
_gemini_quota_exhausted: bool = False


# ── AI call ───────────────────────────────────────────────────────────────────

def _call_gemini(bgr_img: np.ndarray) -> dict | None:
    global _gemini_quota_exhausted
    if _gemini_quota_exhausted:
        return None

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from google import genai
        from PIL import Image as PILImage
    except ImportError:
        return None

    try:
        h, w = bgr_img.shape[:2]
        if max(h, w) > 800:
            scale = 800 / max(h, w)
            bgr_img = cv2.resize(bgr_img, (int(w * scale), int(h * scale)))

        rgb = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
        pil_img = PILImage.fromarray(rgb)
        client = genai.Client(api_key=api_key)

        for model_name in ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-2.5-flash"]:
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=[_CLASSIFY_PROMPT, pil_img],
                )
                text = resp.text.strip()
                s, e = text.find("{"), text.rfind("}") + 1
                if s >= 0 and e > s:
                    return json.loads(text[s:e])
            except Exception as ex:
                err = str(ex)
                if "429" in err:
                    # Daily quota exhausted — stop trying all models & all images
                    _gemini_quota_exhausted = True
                    print("[ANAVI] Gemini quota exhausted — switching to heuristic classifier.", flush=True)
                    return None
                if "503" in err:
                    continue  # temporary overload, try next model
                break
    except Exception:
        pass

    return None


# ── Heuristic fallback ────────────────────────────────────────────────────────

def _heuristic_classify(bgr_img: np.ndarray) -> dict:
    """
    Estimates perspective from image statistics when AI is unavailable.

    Strategy:
    - Divide the image into 8 horizontal bands.
    - If brightness increases sharply from bottom to top and variance peaks
      in the middle bands → oblique floor shot (common phone photo).
    - If brightness is roughly uniform top-to-bottom → eye-level wall shot.
    - Defaults to oblique_floor (most common real-world upload).
    """
    H, W = bgr_img.shape[:2]
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY).astype(np.float32)

    band_means = [gray[i * H // 8:(i + 1) * H // 8, :].mean() for i in range(8)]
    band_vars  = [gray[i * H // 8:(i + 1) * H // 8, :].var()  for i in range(8)]

    top_mean    = float(np.mean(band_means[:4]))
    bot_mean    = float(np.mean(band_means[4:]))
    max_var_band = int(np.argmax(band_vars))
    mean_range  = float(max(band_means) - min(band_means))

    # Strong top-brighter gradient with variance peak in mid-image → oblique floor
    if top_mean > bot_mean + 15 and max_var_band in range(2, 7):
        horizon_y = float(np.clip((max_var_band + 0.5) / 8.0, 0.30, 0.85))
        return {
            "perspective": "oblique_floor",
            "horizon_y": round(horizon_y, 2),
            "floor_fraction": round(1.0 - horizon_y, 2),
            "wall_direction": "unknown",
            "tilt_from_vertical_deg": 55.0,
            "navigable_floor_visible": True,
            "obstacle_density": 0.30,
        }

    # Low brightness variation → eye-level
    if mean_range < 20:
        return {
            "perspective": "eye_level",
            "horizon_y": 0.5,
            "floor_fraction": 0.15,
            "wall_direction": "unknown",
            "tilt_from_vertical_deg": 90.0,
            "navigable_floor_visible": False,
            "obstacle_density": 0.40,
        }

    # Default: treat as oblique floor
    return {
        "perspective": "oblique_floor",
        "horizon_y": 0.65,
        "floor_fraction": 0.35,
        "wall_direction": "unknown",
        "tilt_from_vertical_deg": 55.0,
        "navigable_floor_visible": True,
        "obstacle_density": 0.35,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def classify_single(bgr_img: np.ndarray, label: str = "") -> dict:
    """Classify one image. AI first, heuristic on failure."""
    result = _call_gemini(bgr_img)
    source = "ai"
    if result is None:
        result = _heuristic_classify(bgr_img)
        source = "heuristic"

    result["_source"] = source
    result["_label"]  = label

    # Ensure required keys have defaults
    result.setdefault("horizon_y", None)
    result.setdefault("floor_fraction", 0.35)
    result.setdefault("wall_direction", "unknown")
    result.setdefault("tilt_from_vertical_deg", 55.0)
    result.setdefault("navigable_floor_visible", True)
    result.setdefault("obstacle_density", 0.35)

    return result


def classify_batch(image_paths: list[Path]) -> list[dict]:
    """Classify every image in the batch. Returns a list parallel to image_paths."""
    results = []
    for path in image_paths:
        img = cv2.imread(str(path))
        if img is None:
            cls = {
                "perspective": "oblique_floor",
                "horizon_y": 0.65,
                "floor_fraction": 0.35,
                "wall_direction": "unknown",
                "tilt_from_vertical_deg": 55.0,
                "navigable_floor_visible": True,
                "obstacle_density": 0.35,
                "_source": "default",
                "_label": path.name,
            }
        else:
            cls = classify_single(img, label=path.name)

        print(
            f"[ANAVI] classify {path.name!r:30s} = {cls['perspective']:15s}"
            f" horizon={cls.get('horizon_y')}  src={cls['_source']}",
            flush=True,
        )
        results.append(cls)

    return results
