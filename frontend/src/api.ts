import axios from 'axios'

// All requests go to /api/* which Vite proxies to http://127.0.0.1:8000/*.
const BASE = '/api'

export interface AiAnalysis {
  space_type: string
  orientation_correction: number
  floor_mask_hint: string
  navigable_fraction: number
  obstacle_density: number
  primary_axis: string
  description: string
}

export interface ImageClassification {
  perspective: 'top_down' | 'oblique_floor' | 'eye_level' | 'ceiling'
  horizon_y: number | null
  floor_fraction: number
  wall_direction: string
  tilt_from_vertical_deg: number
  navigable_floor_visible: boolean
  obstacle_density: number
}

export interface ProcessResponse {
  session_id: string
  image_w: number
  image_h: number
  grid_size: number
  heightmap: number[][]
  occupancy: number[][]
  ai_analysis: AiAnalysis | null
  // 3-axis fields
  image_classifications: ImageClassification[]
  has_3d_data: boolean
  perspective_summary: Record<string, number>
}

export interface PathResponse {
  algorithm: string
  path: [number, number][] | null
}

export async function processImages(files: File[]): Promise<ProcessResponse> {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  const { data } = await axios.post<ProcessResponse>(`${BASE}/process`, form)
  return data
}

export async function pathfind(
  session_id: string,
  start: [number, number],
  goal: [number, number],
  algorithm: 'astar' | 'dijkstra' | 'rrt',
): Promise<PathResponse> {
  const { data } = await axios.post<PathResponse>(`${BASE}/pathfind`, {
    session_id,
    start,
    goal,
    algorithm,
  })
  return data
}

export function topviewUrl(session_id: string): string {
  return `${BASE}/topview/${session_id}`
}
