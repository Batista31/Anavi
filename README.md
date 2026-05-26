# ANAVI — Autonomous Navigation & Visual Intelligence

Upload overlapping photos of a space → get a stitched top-view map → interactive 3D height mesh → click start & goal → pathfinding (A\*, Dijkstra, RRT) → export waypoints for a ground robot.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React + TypeScript + Vite + Tailwind CSS v4 |
| 3D Viewer | React Three Fiber (Three.js) |
| Backend | FastAPI + Python 3.11 |
| Image Processing | OpenCV (stitching + Canny edge detection) |
| AI Analysis | Google Gemini Vision (spatial layout understanding) |
| Pathfinding | A\*, Dijkstra, RRT |

## Project Structure

```
Anavi/
├── backend/
│   ├── main.py                  # FastAPI app
│   ├── requirements.txt
│   ├── processor/
│   │   ├── stitcher.py          # OpenCV image stitching
│   │   ├── mesh_builder.py      # Heightmap + occupancy grid
│   │   └── ai_analyzer.py       # Gemini Vision layout analysis
│   └── pathfinding/
│       ├── astar.py
│       ├── dijkstra.py
│       └── rrt.py
└── frontend/
    ├── src/
    │   ├── pages/               # Home, Upload, Viewer
    │   ├── components/          # MeshViewer (3D), ThemeToggle
    │   ├── hooks/               # useScrollReveal
    │   └── api.ts               # Backend client
    └── vite.config.ts           # Proxy /api → :8000
```

## Setup

### Backend
```bash
cd backend
pip install -r requirements.txt

# Create .env with your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env

python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev     # Vite proxies /api → http://127.0.0.1:8000
```

Open **http://localhost:5173**

## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/process` | Upload photos → stitch → mesh → AI analysis |
| POST | `/pathfind` | Run A\*/Dijkstra/RRT on session mesh |
| GET | `/topview/{sid}` | Serve stitched top-view JPEG |
| DELETE | `/session/{sid}` | Clean up session |
| GET | `/debug/ai` | Test Gemini connection |
| GET | `/health` | Health check |

## AI Layer

Gemini Vision analyzes the stitched top-view image to determine:
- **Space type** (room, corridor, outdoor, etc.)
- **Orientation correction** (rotate to canonical left-right travel axis)
- **Floor mask hint** (where navigable floor is)
- **Navigable fraction** & **obstacle density**

These signals tune the Canny edge thresholds and occupancy grid generation for better path quality.
