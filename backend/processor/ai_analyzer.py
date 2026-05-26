"""
AI layout analyzer — Gemini 2.0 Flash Vision (google-genai SDK).
Falls back gracefully if GEMINI_API_KEY is unset or the call fails.
"""

import os
import json
import sys
import numpy as np
import cv2

_PROMPT = """Analyze this image of a physical space for robot navigation.
Return ONLY a valid JSON object with no explanation or markdown:
{
  "space_type": "room|corridor|outdoor_path|building_exterior|courtyard|unknown",
  "orientation_correction": 0,
  "floor_mask_hint": "center_open|edges_are_walls|top_bottom_walls|left_right_walls|scattered_obstacles|mostly_open",
  "navigable_fraction": 0.6,
  "obstacle_density": 0.3,
  "primary_axis": "horizontal|vertical|radial|unknown",
  "description": "One sentence describing the space for robot navigation."
}
orientation_correction: clockwise degrees to rotate so main travel goes left-to-right (0/90/180/270).
navigable_fraction: 0.0-1.0 fraction a wheeled robot can traverse.
obstacle_density: 0.0=all clear, 1.0=all blocked."""


def analyze(bgr_image: np.ndarray) -> dict | None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[ANAVI] GEMINI_API_KEY not set — skipping AI analysis.", flush=True)
        return None

    print(f"[ANAVI] Running Gemini analysis (key: ...{api_key[-6:]})", flush=True)

    try:
        from google import genai
        from google.genai import types
        from PIL import Image as PILImage
    except ImportError as e:
        print(f"[ANAVI] Missing package: {e}", flush=True)
        return None

    try:
        client = genai.Client(api_key=api_key)

        # Resize to ≤1024px for API efficiency
        h, w = bgr_image.shape[:2]
        if max(h, w) > 1024:
            scale = 1024 / max(h, w)
            bgr_image = cv2.resize(bgr_image, (int(w * scale), int(h * scale)))

        # Convert BGR → RGB PIL image
        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        pil_img = PILImage.fromarray(rgb)

        # Try models in preference order — skip on 429/503 and fall back
        _MODELS = ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-2.5-flash"]
        response = None
        last_err = None
        for model_name in _MODELS:
            try:
                print(f"[ANAVI] Trying model: {model_name}", flush=True)
                response = client.models.generate_content(
                    model=model_name,
                    contents=[_PROMPT, pil_img],
                )
                print(f"[ANAVI] Model {model_name} succeeded.", flush=True)
                break
            except Exception as e:
                last_err = e
                print(f"[ANAVI] {model_name} failed: {str(e)[:120]}", file=sys.stderr, flush=True)

        if response is None:
            print(f"[ANAVI] All models failed. Last error: {last_err}", file=sys.stderr, flush=True)
            return None

        text = response.text.strip()
        print(f"[ANAVI] Gemini raw response: {text[:300]}", flush=True)

        start = text.find("{")
        end   = text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
            print(f"[ANAVI] AI analysis OK: {result}", flush=True)
            return result

        print(f"[ANAVI] No JSON in Gemini response.", flush=True)
        return None

    except Exception as exc:
        print(f"[ANAVI] Gemini error: {exc}", file=sys.stderr, flush=True)
        return None


def build_floor_mask(hint: str, shape: tuple[int, int]) -> np.ndarray:
    rows, cols = shape
    mask = np.ones((rows, cols), dtype=np.float32)

    if hint == "edges_are_walls":
        br, bc = max(1, int(rows * 0.15)), max(1, int(cols * 0.15))
        mask[:br, :] = 0; mask[-br:, :] = 0
        mask[:, :bc] = 0; mask[:, -bc:] = 0
    elif hint == "top_bottom_walls":
        b = max(1, int(rows * 0.18))
        mask[:b, :] = 0; mask[-b:, :] = 0
    elif hint == "left_right_walls":
        b = max(1, int(cols * 0.18))
        mask[:, :b] = 0; mask[:, -b:] = 0
    elif hint == "center_open":
        br, bc = max(1, int(rows * 0.20)), max(1, int(cols * 0.20))
        mask[:br, :] = 0; mask[-br:, :] = 0
        mask[:, :bc] = 0; mask[:, -bc:] = 0

    return mask
