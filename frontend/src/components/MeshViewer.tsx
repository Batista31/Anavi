/**
 * MeshViewer — Three.js 3D scene using React Three Fiber.
 *
 * Renders:
 *  - Flat textured floor plane (top-view JPEG as albedo)
 *  - WallBoxes: InstancedMesh of extruded boxes for each obstacle cell
 *    (replaces the old height-displaced plane for proper 3D wall geometry)
 *  - Green sphere = start, Red sphere = goal
 *  - Yellow tube = computed path
 *
 * Coordinate systems:
 *  Grid : (row, col) ∈ [0, GRID_SIZE)
 *  World: X ∈ [-planeW/2, planeW/2],  Z ∈ [-planeH/2, planeH/2],  Y = height
 */

import { useMemo, useCallback, useRef, useEffect } from 'react'
import { Canvas, useLoader } from '@react-three/fiber'
import type { ThreeEvent } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import type { ProcessResponse } from '../api'
import { topviewUrl } from '../api'
import type { Waypoint } from '../types'

const HEIGHT_SCALE  = 0.55  // world-unit height of a full-height wall cell
const PLANE_SIZE    = 10    // floor plane width in world units
const MIN_WALL_H    = 0.15  // minimum world-unit height so small boxes are still visible

interface Props {
  session: ProcessResponse
  start: Waypoint | null
  goal: Waypoint | null
  path: [number, number][] | null
  onMeshClick: (row: number, col: number) => void
  isPlacing: boolean
}

export default function MeshViewer(props: Props) {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  const canvasBg = isDark ? '#05080a' : '#ccdcba'

  return (
    <Canvas
      camera={{ position: [0, 7, 8], fov: 50 }}
      style={{ background: canvasBg, cursor: props.isPlacing ? 'crosshair' : 'grab' }}
    >
      <ambientLight intensity={0.55} />
      <directionalLight position={[6, 12, 6]} intensity={1.1} castShadow />
      <Scene {...props} />
      <OrbitControls
        enablePan
        enableZoom
        enableRotate={!props.isPlacing}
        mouseButtons={{
          LEFT:   props.isPlacing ? undefined : THREE.MOUSE.ROTATE,
          MIDDLE: THREE.MOUSE.DOLLY,
          RIGHT:  THREE.MOUSE.PAN,
        }}
      />
      <gridHelper args={[14, 28, '#0a2a2a', '#0a1a1a']} position={[0, -0.01, 0]} />
    </Canvas>
  )
}

// ── Scene ─────────────────────────────────────────────────────────────────────

function Scene({ session, start, goal, path, onMeshClick, isPlacing }: Props) {
  const { grid_size, heightmap, occupancy, image_w, image_h, session_id } = session
  const aspect = image_w / image_h
  const planeW = PLANE_SIZE
  const planeH = PLANE_SIZE / aspect

  const texture = useLoader(THREE.TextureLoader, topviewUrl(session_id))

  // ── Flat floor plane (textured) ────────────────────────────────────────────
  const floorGeo = useMemo(() => {
    const geo = new THREE.PlaneGeometry(planeW, planeH)
    geo.rotateX(-Math.PI / 2)
    return geo
  }, [planeW, planeH])

  // ── Coordinate helpers ─────────────────────────────────────────────────────
  const gridToWorld = useCallback(
    (row: number, col: number): [number, number, number] => {
      const x = (col / (grid_size - 1) - 0.5) * planeW
      const z = (row / (grid_size - 1) - 0.5) * planeH
      const h = (heightmap[row]?.[col] ?? 0) * HEIGHT_SCALE + 0.05
      return [x, h, z]
    },
    [grid_size, heightmap, planeW, planeH],
  )

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

  // ── Path tube ──────────────────────────────────────────────────────────────
  const pathPoints = useMemo(() => {
    if (!path || path.length < 2) return null
    return path.map(([r, c]) => new THREE.Vector3(...gridToWorld(r, c)))
  }, [path, gridToWorld])

  const pathCurve = useMemo(
    () => (pathPoints ? new THREE.CatmullRomCurve3(pathPoints) : null),
    [pathPoints],
  )

  return (
    <>
      {/* Textured floor — clickable for waypoint placement */}
      <mesh geometry={floorGeo} onClick={handleClick} receiveShadow>
        <meshStandardMaterial map={texture} roughness={0.85} metalness={0.05} />
      </mesh>

      {/* 3D wall boxes — only where occupancy === 1 (high-confidence obstacles) */}
      <WallBoxes
        heightmap={heightmap}
        occupancy={occupancy}
        grid_size={grid_size}
        planeW={planeW}
        planeH={planeH}
      />

      {/* Start marker */}
      {start && (
        <mesh position={gridToWorld(start.row, start.col)}>
          <sphereGeometry args={[0.14, 16, 16]} />
          <meshStandardMaterial color="#22ff88" emissive="#00ff44" emissiveIntensity={0.5} />
        </mesh>
      )}

      {/* Goal marker */}
      {goal && (
        <mesh position={gridToWorld(goal.row, goal.col)}>
          <sphereGeometry args={[0.14, 16, 16]} />
          <meshStandardMaterial color="#ff4455" emissive="#ff0022" emissiveIntensity={0.5} />
        </mesh>
      )}

      {/* Path tube */}
      {pathCurve && (
        <mesh>
          <tubeGeometry args={[pathCurve, path!.length * 2, 0.045, 8, false]} />
          <meshStandardMaterial color="#facc15" emissive="#f59e0b" emissiveIntensity={0.6} />
        </mesh>
      )}
    </>
  )
}

// ── WallBoxes ─────────────────────────────────────────────────────────────────
// Renders one instanced box per OCCUPIED cell (occupancy === 1).
// Using the binary occupancy grid (not raw heightmap threshold) means only
// high-confidence obstacles become boxes — mosaic seam artifacts are excluded.

interface WallBoxesProps {
  heightmap: number[][]
  occupancy: number[][]
  grid_size: number
  planeW: number
  planeH: number
}

function WallBoxes({ heightmap, occupancy, grid_size, planeW, planeH }: WallBoxesProps) {
  const stepX = planeW / grid_size
  const stepZ = planeH / grid_size

  // Collect (x, z, height) only where occupancy === 1
  const wallCells = useMemo(() => {
    const result: [number, number, number][] = []
    for (let r = 0; r < grid_size; r++) {
      for (let c = 0; c < grid_size; c++) {
        if ((occupancy[r]?.[c] ?? 0) !== 1) continue
        const h = Math.max(MIN_WALL_H / HEIGHT_SCALE, heightmap[r]?.[c] ?? 0)
        const x = (c / (grid_size - 1) - 0.5) * planeW
        const z = (r / (grid_size - 1) - 0.5) * planeH
        result.push([x, z, h])
      }
    }
    return result
  }, [occupancy, heightmap, grid_size, planeW, planeH])

  const meshRef = useRef<THREE.InstancedMesh>(null)

  useEffect(() => {
    const mesh = meshRef.current
    if (!mesh || wallCells.length === 0) return

    const matrix = new THREE.Matrix4()
    const pos    = new THREE.Vector3()
    const quat   = new THREE.Quaternion()   // identity — no rotation
    const scale  = new THREE.Vector3()

    wallCells.forEach(([x, z, h], i) => {
      const wallH = Math.max(MIN_WALL_H, h * HEIGHT_SCALE)
      pos.set(x, wallH / 2, z)
      scale.set(stepX * 1.05, wallH, stepZ * 1.05)
      matrix.compose(pos, quat, scale)
      mesh.setMatrixAt(i, matrix)
    })
    mesh.instanceMatrix.needsUpdate = true
  }, [wallCells, stepX, stepZ])

  if (wallCells.length === 0) return null

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, wallCells.length]} castShadow receiveShadow>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="#6B7FA0" roughness={0.85} metalness={0.08} />
    </instancedMesh>
  )
}
