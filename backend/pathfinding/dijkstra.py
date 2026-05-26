"""
Dijkstra's algorithm on a 2D occupancy grid.

Like A* but with h(n) = 0 — explores uniformly in all directions.
Guaranteed optimal. Useful baseline to compare against A* speed.

Grid convention: 0 = free, 1 = obstacle.
"""

import heapq
import math
from typing import Optional

_NEIGHBOURS = [
    (-1,  0, 1.0),
    ( 1,  0, 1.0),
    ( 0,  1, 1.0),
    ( 0, -1, 1.0),
    (-1,  1, math.sqrt(2)),
    (-1, -1, math.sqrt(2)),
    ( 1,  1, math.sqrt(2)),
    ( 1, -1, math.sqrt(2)),
]


def run(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> Optional[list[tuple[int, int]]]:
    rows, cols = len(grid), len(grid[0])
    sr, sc = start
    gr, gc = goal

    if grid[sr][sc] == 1 or grid[gr][gc] == 1:
        return None

    dist = [[math.inf] * cols for _ in range(rows)]
    dist[sr][sc] = 0.0
    came_from: dict[tuple, Optional[tuple]] = {(sr, sc): None}

    heap: list[tuple[float, int, int]] = [(0.0, sr, sc)]

    while heap:
        d, r, c = heapq.heappop(heap)

        if (r, c) == (gr, gc):
            return _reconstruct(came_from, goal)

        if d > dist[r][c] + 1e-9:
            continue

        for dr, dc, cost in _NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            if grid[nr][nc] == 1:
                continue

            new_d = dist[r][c] + cost
            if new_d < dist[nr][nc]:
                dist[nr][nc] = new_d
                came_from[(nr, nc)] = (r, c)
                heapq.heappush(heap, (new_d, nr, nc))

    return None


def _reconstruct(came_from: dict, goal: tuple) -> list[tuple[int, int]]:
    path = []
    node = goal
    while node is not None:
        path.append(node)
        node = came_from[node]
    path.reverse()
    return path
