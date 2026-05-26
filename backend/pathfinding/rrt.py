"""
RRT (Rapidly-exploring Random Tree) on a 2D occupancy grid.

Unlike A*/Dijkstra, RRT does NOT guarantee an optimal path — it finds
*a* feasible path by randomly sampling the free space. Useful for:
  - High-dimensional or continuous spaces
  - Seeing how different exploration strategies compare

Grid convention: 0 = free, 1 = obstacle.
Coordinates are (row, col) integers.

Parameters:
  max_iter    – maximum tree expansions before giving up
  step_size   – maximum number of grid cells per tree extension
  goal_radius – accept goal if we land within this many cells
  goal_bias   – probability [0, 1] of sampling the goal directly
                (trades exploration for exploitation — set ~0.1–0.2)
"""

import math
import random
from typing import Optional


class _Node:
    __slots__ = ("r", "c", "parent")

    def __init__(self, r: int, c: int, parent: Optional["_Node"] = None):
        self.r = r
        self.c = c
        self.parent = parent


def _dist(a: _Node, b: _Node) -> float:
    return math.hypot(a.r - b.r, a.c - b.c)


def _steer(near: _Node, sample: _Node, step: int) -> _Node:
    """Move from `near` toward `sample` by at most `step` cells."""
    d = _dist(near, sample)
    if d <= step:
        return _Node(sample.r, sample.c, near)
    ratio = step / d
    nr = int(round(near.r + ratio * (sample.r - near.r)))
    nc = int(round(near.c + ratio * (sample.c - near.c)))
    return _Node(nr, nc, near)


def _collision_free(grid: list[list[int]], a: _Node, b: _Node) -> bool:
    """
    Bresenham line between a and b — returns False if any cell is an obstacle.
    """
    r0, c0, r1, c1 = a.r, a.c, b.r, b.c
    dr = abs(r1 - r0)
    dc = abs(c1 - c0)
    sr = 1 if r1 > r0 else -1
    sc = 1 if c1 > c0 else -1
    err = dr - dc
    rows, cols = len(grid), len(grid[0])

    r, c = r0, c0
    while True:
        if not (0 <= r < rows and 0 <= c < cols):
            return False
        if grid[r][c] == 1:
            return False
        if r == r1 and c == c1:
            break
        e2 = 2 * err
        if e2 > -dc:
            err -= dc
            r += sr
        if e2 < dr:
            err += dr
            c += sc

    return True


def run(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
    max_iter: int = 5000,
    step_size: int = 10,
    goal_radius: int = 5,
    goal_bias: float = 0.15,
    seed: Optional[int] = None,
) -> Optional[list[tuple[int, int]]]:
    rows, cols = len(grid), len(grid[0])
    rng = random.Random(seed)

    start_node = _Node(*start)
    goal_node = _Node(*goal)

    if grid[start[0]][start[1]] == 1 or grid[goal[0]][goal[1]] == 1:
        return None

    tree: list[_Node] = [start_node]

    for _ in range(max_iter):
        # Sample: with probability goal_bias sample goal, else random free cell
        if rng.random() < goal_bias:
            sample = goal_node
        else:
            sample = _Node(rng.randint(0, rows - 1), rng.randint(0, cols - 1))

        # Find nearest node in tree
        nearest = min(tree, key=lambda n: _dist(n, sample))

        # Steer toward sample
        new_node = _steer(nearest, sample, step_size)

        if not (0 <= new_node.r < rows and 0 <= new_node.c < cols):
            continue
        if grid[new_node.r][new_node.c] == 1:
            continue
        if not _collision_free(grid, nearest, new_node):
            continue

        tree.append(new_node)

        # Check if we reached goal
        if _dist(new_node, goal_node) <= goal_radius:
            if _collision_free(grid, new_node, goal_node):
                goal_node.parent = new_node
                tree.append(goal_node)
                return _extract_path(goal_node)

    return None  # no path found within max_iter


def _extract_path(node: _Node) -> list[tuple[int, int]]:
    path = []
    cur = node
    while cur is not None:
        path.append((cur.r, cur.c))
        cur = cur.parent
    path.reverse()
    return path
