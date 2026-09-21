"Sightline — Simulated Annealing Pathfinder part-1"

import math
import random
from sightline_core import (
    Brain, DIRS, WALL, SMOKE, GUN, SWORD, TRAP_SPIKE, TRAP_STUN, AOE_ACID, AOE_MAGMA, EMPTY
)

def manhatten (a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class SABrain(Brain):
    def __init__(self):
        self.current_path = []
        self.last_target = None
        self.nodes_expanded = 0
        self.dialogue = "Warming up the annealer..."
        self.swap_cooldown = 0
        self.last_target_id = None
        self.sa_iterations = 30
        self.sa_start_temp = 20.0
        self.sa_cooling_rate = 0.85
        self.sa_max_path_len = 45

    # Cost = how risky this path is. Traps, hazards, and getting cozy with the Joker
    # all tax it hard. Lower number, safer walk — that's what we're hunting for.

    def _tile_step_cost(self, tile, is_goal_tile, joker_alive, joker_pos, neighbor):
        cost = 1
        if tile in (TRAP_SPIKE, TRAP_STUN) and not is_goal_tile:
            cost += 16
        elif tile in (AOE_ACID, AOE_MAGMA) and not is_goal_tile:
            cost += 8
        if joker_alive and joker_pos:
            if neighbor == joker_pos and not is_goal_tile:
                cost += 35
            elif manhatten(neighbor, joker_pos) == 1 and not is_goal_tile:
                cost += 6
        return cost

    def _path_cost(self, start, path, goal, grid, joker_pos, joker_alive):
        cost = 0
        cur = start
        for step in path:
            tile = grid.tiles[step[1]][step[0]]
            cost += self._tile_step_cost(tile, step == goal, joker_alive, joker_pos, step)
            cur = step
        cost += manhatten(cur, goal) * 3  # heavy penalty for not actually arriving
        return cost

    def _walkable_neighbors(self, pos, grid):
        result = []
        for _, (dx, dy) in DIRS.items():
            nx, ny = pos[0] + dx, pos[1] + dy
            if grid.in_bounds(nx, ny):
                tile = grid.tiles[ny][nx]
                if tile not in (WALL, SMOKE):
                    result.append((nx, ny))
        return result

    def _greedy_random_path(self, start, goal, grid, greedy_bias=0.75):

        "A rough starting guess: mostly steps toward the goal, sometimes a random step, capped in length so it never runs away."

        path = []
        cur = start
        visited = {start}
        for _ in range(self.sa_max_path_len):
            if cur == goal:
                break
            options = self._walkable_neighbors(cur, grid)
            if not options:
                break
            options.sort(key=lambda p: manhatten(p, goal))
            if random.random() < greedy_bias:
                nxt = options[0]
            else:
                nxt = random.choice(options)
            path.append(nxt)
            cur = nxt
            if cur in visited and random.random() < 0.4:
                break
            visited.add(cur)
        return path

  
    # .................SA base code....................
    
    def simulated_annealing_search(self, start, goal, grid, joker_pos=None, joker_alive=True):
        if start == goal:
            return []

        current_path = self._greedy_random_path(start, goal, grid)
        current_cost = self._path_cost(start, current_path, goal, grid, joker_pos, joker_alive)

        best_path = current_path
        best_cost = current_cost

        temperature = self.sa_start_temp

        for _ in range(self.sa_iterations):
            self.nodes_expanded += 1

            # Either roll the dice on a totally new path, or tweak the one we've got.
            # (50/50 — sometimes you scrap the plan, sometimes you just patch it.)
            
            if random.random() < 0.5 or not current_path:
                candidate = self._greedy_random_path(start, goal, grid)
            else:
                cut = random.randrange(1, len(current_path) + 1)
                resume = current_path[cut - 1] if cut > 0 else start
                tail = self._greedy_random_path(resume, goal, grid)
                candidate = current_path[:cut] + tail

            candidate_cost = self._path_cost(start, candidate, goal, grid, joker_pos, joker_alive)

            delta = candidate_cost - current_cost
            if delta < 0 or random.random() < math.exp(-delta / max(temperature, 0.01)):
                current_path = candidate
                current_cost = candidate_cost
                if current_cost < best_cost:
                    best_path = candidate
                    best_cost = current_cost

            temperature *= self.sa_cooling_rate

        return best_path
