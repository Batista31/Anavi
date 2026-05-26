/**
 * MeshViewer — Three.js 3D scene using React Three Fiber.
 *
 * What it renders:
 *  - A PlaneGeometry displaced by the height map (edges/walls raised)
 *  - The stitched top-view image as a texture on the plane
 *  - Green sphere = start, Red sphere = goal
 *  - Yellow tube = computed path
 *
 * Coordinate systems:
 *  - Grid: (row, col) ∈ [0, GRID_SIZE)
 *  - World: plane spans [-aspect/2, aspect/2] on X and [-0.5, 0.5] on Z
 *            Y axis = height (0 = floor, up to ~0.3 for walls)
 *  - UV: (col/GRID_SIZE, row/GRID_SIZE) — standard Three.js plane UV
 */

import { useMemo, useCallback } from 'react'
import { Canvas, useLoader } from '@react-three/fiber'
import type { ThreeEvent } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import type { ProcessResponse } from '../api'
import { topviewUrl } from '../api'
import type { Waypoint } from '../types'

const HEIGHT_SCALE = 0.25   // max displacement of walls in world units
const PLANE_SIZE = 10        // plane width in world units; height = 10 / aspect

interface Props {
  session: ProcessResponse
  start: Waypoint | null
  goal: Waypoint | null
  path: [number, number][] | null
  onMeshClick: (row: number, col: number) => void
  isPlacing: boolean
}

export default function MeshViewer({ session, start, goal, path, onMeshClick, isPlacing }: Props) {
  // Read the theme from <html data-theme> so the canvas bg matches
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  const canvasBg = isDark ? '#05080a' : '#ccdcba'

  return (
    <Canvas
      camera={{ position: [0, 8, 0], fov: 50 }}
      style={{ background: canvasBg, cursor: isPlacing ? 'crosshair' : 'grab' }}
    >
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 10, 5]} intensity={1.2} />
      <Scene
        session={session}
        start={start}
        goal={goal}
        path={path}
        onMeshClick={onMeshClick}
        isPlacing={isPlacing}
      />
      <OrbitControls
        enablePan
        enableZoom
        enableRotate={!isPlacing}
        mouseButtons={{ LEFT: isPlacing ? undefined : THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN }}
      />
      <gridHelper args={[12, 24, '#0a2a2a', '#0a1a1a']} position={[0, -0.01, 0]} />
    </Canvas>
  )
}

function Scene({ session, start, goal, path, onMeshClick, isPlacing }: Props) {
  const { grid_size, heightmap, image_w, image_h, session_id } = session
  const aspect = image_w / image_h
  const planeW = PLANE_SIZE
  const planeH = PLANE_SIZE / aspect

  // Load the top-view texture via the Vite proxy (no CORS)
  const texture = useLoader(
    THREE.TextureLoader,
    topviewUrl(session_id),
  )

  // Build displaced geometry from heightmap
  const geometry = useMemo(() => {
    const segs = grid_size - 1
    const geo = new THREE.PlaneGeometry(planeW, planeH, segs, segs)
    geo.rotateX(-Math.PI / 2)  // lay flat (XZ plane)

    const positions = geo.attributes.position
    // PlaneGeometry vertices go row by row (top→bottom in UV space = -Z→+Z)
    for (let i = 0; i < positions.count; i++) {
      const row = Math.floor(i / grid_size)
      const col = i % grid_size
      const h = heightmap[row]?.[col] ?? 0
      positions.setY(i, h * HEIGHT_SCALE)
    }
    geo.computeVertexNormals()
    return geo
  }, [grid_size, heightmap, planeW, planeH])

  // Convert grid (row, col) → world XZ
  const gridToWorld = useCallback(
    (row: number, col: number): [number, number, number] => {
      const x = (col / (grid_size - 1) - 0.5) * planeW
      const z = (row / (grid_size - 1) - 0.5) * planeH
      const h = (heightmap[row]?.[col] ?? 0) * HEIGHT_SCALE + 0.05
      return [x, h, z]
    },
    [grid_size, heightmap, planeW, planeH],
  )

  // Convert world XZ → grid (row, col)
  const worldToGrid = useCallback(
    (x: number, z: number): [number, number] => {
      const col = Math.round(((x / planeW) + 0.5) * (grid_size - 1))
      const row = Math.round(((z / planeH) + 0.5) * (grid_size - 1))
      return [
        Math.max(0, Math.min(grid_size - 1, row)),
        Math.max(0, Math.min(grid_size - 1, col)),
      ]
    },
    [grid_size, planeW, planeH],
  )

  const handleClick = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      if (!isPlacing) return
      e.stopPropagation()
      const [row, col] = worldToGrid(e.point.x, e.point.z)
      onMeshClick(row, col)
    },
    [isPlacing, worldToGrid, onMeshClick],
  )

  // Build path tube
  const pathPoints = useMemo(() => {
    if (!path || path.length < 2) return null
    return path.map(([r, c]) => new THREE.Vector3(...gridToWorld(r, c)))
  }, [path, gridToWorld])

  const pathCurve = useMemo(
    () => pathPoints ? new THREE.CatmullRomCurve3(pathPoints) : null,
    [pathPoints],
  )

  return (
    <>
      {/* Displaced terrain mesh */}
      <mesh geometry={geometry} onClick={handleClick} receiveShadow>
        <meshStandardMaterial map={texture} roughness={0.8} metalness={0.1} />
      </mesh>

      {/* Start marker */}
      {start && (
        <mesh position={gridToWorld(start.row, start.col)}>
          <sphereGeometry args={[0.12, 16, 16]} />
          <meshStandardMaterial color="#22ff88" emissive="#00ff44" emissiveIntensity={0.5} />
        </mesh>
      )}

      {/* Goal marker */}
      {goal && (
        <mesh position={gridToWorld(goal.row, goal.col)}>
          <sphereGeometry args={[0.12, 16, 16]} />
          <meshStandardMaterial color="#ff4455" emissive="#ff0022" emissiveIntensity={0.5} />
        </mesh>
      )}

      {/* Path tube */}
      {pathCurve && (
        <mesh>
          <tubeGeometry args={[pathCurve, path!.length * 2, 0.04, 8, false]} />
          <meshStandardMaterial color="#facc15" emissive="#f59e0b" emissiveIntensity={0.6} />
        </mesh>
      )}
    </>
  )
}
