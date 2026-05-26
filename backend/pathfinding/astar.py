"""
A* pathfinding on a 2D occupancy grid.

Grid convention: 0 = free, 1 = obstacle.
Supports 8-directional movement (diagonal allowed).

Cost function: g(n) = accumulated travel cost
                       straight move = 1.0
                       diagonal move = √2 ≈ 1.414
               h(n) = octile distance heuristic
               f(n) = g(n) + h(n)

Octile heuristic is consistent (never overestimates), so the first path
found is guaranteed optimal.
"""

import heapq
import math
from typing import Optional


# 8-directional neighbours: (row_delta, col_delta, move_cost)
_NEIGHBOURS = [
    (-1,  0, 1.0),   # N
    ( 1,  0, 1.0),   # S
    ( 0,  1, 1.0),   # E
    ( 0, -1, 1.0),   # W
    (-1,  1, math.sqrt(2)),  # NE
    (-1, -1, math.sqrt(2)),  # NW
    ( 1,  1, math.sqrt(2)),  # SE
    ( 1, -1, math.sqrt(2)),  # SW
]


def _octile(r1: int, c1: int, r2: int, c2: int) -> float:
    """
    Octile distance — exact cost to reach (r2,c2) from (r1,c1) in 8-dir grid.
    Cheaper than Euclidean to compute, tighter than Chebyshev.
    """
    dr, dc = abs(r2 - r1), abs(c2 - c1)
    return max(dr, dc) + (math.sqrt(2) - 1) * min(dr, dc)


def run(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> Optional[list[tuple[int, int]]]:
    """
    Returns the shortest path as a list of (row, col) tuples, start to goal.
    Returns None if no path exists.
    """
    rows, cols = len(grid), len(grid[0])
    sr, sc = start
    gr, gc = goal

    if grid[sr][sc] == 1 or grid[gr][gc] == 1:
        return None

    # g_score[r][c] = best known cost from start to (r, c)
    g = [[math.inf] * cols for _ in range(rows)]
    g[sr][sc] = 0.0

    # came_from[r][c] = parent node on the best path found so far
    came_from: dict[tuple, Optional[tuple]] = {(sr, sc): None}

    # Min-heap: (f_score, row, col)
    open_heap: list[tuple[float, int, int]] = []
    heapq.heappush(open_heap, (_octile(sr, sc, gr, gc), sr, sc))

    while open_heap:
        f, r, c = heapq.heappop(open_heap)

        if (r, c) == (gr, gc):
            return _reconstruct(came_from, goal)

        # Skip stale heap entries (lazy deletion)
        if f > g[r][c] + _octile(r, c, gr, gc) + 1e-9:
            continue

        for dr, dc, cost in _NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            if grid[nr][nc] == 1:
                continue

            tentative_g = g[r][c] + cost
            if tentative_g < g[nr][nc]:
                g[nr][nc] = tentative_g
                came_from[(nr, nc)] = (r, c)
                f_new = tentative_g + _octile(nr, nc, gr, gc)
                heapq.heappush(open_heap, (f_new, nr, nc))

    return None  # no path


def _reconstruct(came_from: dict, goal: tuple) -> list[tuple[int, int]]:
    path = []
    node = goal
    while node is not None:
        path.append(node)
        node = came_from[node]
    path.reverse()
    return path
