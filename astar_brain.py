"""
Sightline — A* Pathfinder (Anti-Stall & Continuous Dynamic Pursuit)
===================================================================
"""

import heapq
from sightline_core import (
    Brain, DIRS, WALL, SMOKE, GUN, SWORD, TRAP_SPIKE, TRAP_STUN, AOE_ACID, AOE_MAGMA, EMPTY
)

def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

class AStarBrain(Brain):
    def __init__(self):
        self.current_path = []
        self.last_target = None
        self.nodes_expanded = 0
        self.dialogue = "Scanning arena..."
        self.swap_cooldown = 0
        self.last_target_id = None

    def get_flank_tiles(self, target_pos, target_facing, grid):
        """Calculates rear, left, and right ambush tiles around the target."""
        rear_dirs = {
            "up": (0, 1),
            "down": (0, -1),
            "left": (1, 0),
            "right": (-1, 0)
        }
        flank_dirs = {
            "up": [(1, 0), (-1, 0)],
            "down": [(1, 0), (-1, 0)],
            "left": [(0, 1), (0, -1)],
            "right": [(0, 1), (0, -1)]
        }

        # 1. Primary choice: Directly behind target's back
        rdx, rdy = rear_dirs.get(target_facing, (0, 1))
        rear_pos = (target_pos[0] + rdx, target_pos[1] + rdy)
        candidates = [rear_pos]

        # 2. Secondary choices: Lateral flanks
        for fdx, fdy in flank_dirs.get(target_facing, []):
            candidates.append((target_pos[0] + fdx, target_pos[1] + fdy))

        # 3. Fallback: Any adjacent walkable tile
        for _, (dx, dy) in DIRS.items():
            candidates.append((target_pos[0] + dx, target_pos[1] + dy))

        valid = [p for p in candidates if grid.in_bounds(p[0], p[1]) and grid.is_walkable(p[0], p[1])]
        return valid if valid else [target_pos]

    def is_ambush_angle(self, hunter_facing, target_facing):
        """Ambush succeeds from behind or flank, never head-on."""
        opp_face = {
            "up": "down",
            "down": "up",
            "left": "right",
            "right": "left"
        }
        return hunter_facing != opp_face.get(target_facing)

    def evaluate_optimal_target(self, agent, grid, all_agents, joker=None):
        if self.swap_cooldown > 0:
            self.swap_cooldown -= 1

        guns, swords = [], []
        for y in range(grid.rows):
            for x in range(grid.cols):
                t = grid.tiles[y][x]
                if t == GUN:
                    guns.append((x, y))
                elif t == SWORD:
                    swords.append((x, y))

        pos = (agent.x, agent.y)
        best_gun = min(guns, key=lambda p: manhattan(pos, p)) if guns else None
        best_sword = min(swords, key=lambda p: manhattan(pos, p)) if swords else None

        other_living = [a for a in all_agents if a.id != agent.id and a.alive]
        other_living.sort(key=lambda e: manhattan(pos, (e.x, e.y)))

        joker_alive = bool(joker and getattr(joker, 'alive', False))
        joker_pos = (joker.x, joker.y) if joker_alive else None
        joker_facing = getattr(joker, 'facing', 'down') if joker_alive else 'down'

        wounded_prefix = "[WOUNDED 1 HP] " if agent.is_wounded else ""

        # --- 1. UNARMED: Prioritize closest weapon ---
        if not agent.armed:
            if best_gun and not best_sword:
                self.dialogue = f"{wounded_prefix}Rushing for Rifle!"
                return ("GET_WEAPON", best_gun)
            if best_sword and not best_gun:
                self.dialogue = f"{wounded_prefix}Securing Blade!"
                return ("GET_WEAPON", best_sword)
            if best_gun and best_sword:
                gun_dist = manhattan(pos, best_gun)
                sword_dist = manhattan(pos, best_sword)
                joker_risk = 10 if (joker_alive and joker_pos and manhattan(joker_pos, best_gun) <= 2) else 0
                if (gun_dist + joker_risk) <= (sword_dist + 3):
                    self.dialogue = f"{wounded_prefix}Charging for Rifle!"
                    return ("GET_WEAPON", best_gun)
                else:
                    self.dialogue = f"{wounded_prefix}Rifle guarded. Taking Sword!"
                    return ("GET_WEAPON", best_sword)

            # All weapons taken -> stalk closest target or keep moving
            if other_living:
                nearest = other_living[0]
                self.dialogue = f"{wounded_prefix}Unarmed! Evasive stalking of {nearest.algo_type}!"
                ambush_tiles = self.get_flank_tiles((nearest.x, nearest.y), nearest.facing, grid)
                return ("STALK", ambush_tiles[0])
            return ("ROAM", (grid.cols // 2, grid.rows // 2))

        # --- 2. ARMED WITH SWORD: Upgrade if Gun is reachable, else continuously hunt ---
        if agent.armed and agent.weapon_type == "SWORD":
            # Attempt upgrade only if Rifle exists, is reachable, and Joker isn't directly camping it
            if best_gun and self.swap_cooldown <= 0:
                joker_blocking = joker_alive and joker_pos and manhattan(joker_pos, best_gun) <= 1
                if not joker_blocking:
                    test_path = self.astar_search(pos, best_gun, grid, joker_pos, joker_alive)
                    if test_path:
                        self.swap_cooldown = 16
                        self.dialogue = f"{wounded_prefix}Upgrading: Dropping blade for Rifle!"
                        return ("UPGRADE_GUN", best_gun)

            # Continuous target pursuit
            dist_joker = manhattan(pos, joker_pos) if (joker_alive and joker_pos) else 999
            dist_rival = manhattan(pos, (other_living[0].x, other_living[0].y)) if other_living else 999

            if joker_alive and joker_pos and (dist_joker <= dist_rival or not other_living):
                ambush_tiles = self.get_flank_tiles(joker_pos, joker_facing, grid)
                best_flank = min(ambush_tiles, key=lambda p: manhattan(pos, p))
                self.dialogue = f"{wounded_prefix}Blade armed! Stalking Joker's rear!"
                return ("KILL_JOKER", best_flank)

            if other_living:
                nearest = other_living[0]
                ambush_tiles = self.get_flank_tiles((nearest.x, nearest.y), nearest.facing, grid)
                best_flank = min(ambush_tiles, key=lambda p: manhattan(pos, p))
                self.dialogue = f"{wounded_prefix}Tracking nearest rival {nearest.algo_type}!"
                return ("HUNT_AGENT", best_flank)

        # --- 3. ARMED WITH GUN: Prioritize closest threat and pursue relentlessly ---
        if agent.armed and agent.weapon_type == "GUN":
            dist_joker = manhattan(pos, joker_pos) if (joker_alive and joker_pos) else 999
            dist_rival = manhattan(pos, (other_living[0].x, other_living[0].y)) if other_living else 999

            if joker_alive and joker_pos and (dist_joker <= dist_rival or not other_living):
                ambush_tiles = self.get_flank_tiles(joker_pos, joker_facing, grid)
                best_flank = min(ambush_tiles, key=lambda p: manhattan(pos, p))
                self.dialogue = f"{wounded_prefix}Rifle ready! Flanking Joker!"
                return ("KILL_JOKER", best_flank)

            if other_living:
                nearest = other_living[0]
                ambush_tiles = self.get_flank_tiles((nearest.x, nearest.y), nearest.facing, grid)
                best_flank = min(ambush_tiles, key=lambda p: manhattan(pos, p))
                self.dialogue = f"{wounded_prefix}Hunting nearest rival {nearest.algo_type}!"
                return ("HUNT_AGENT", best_flank)

        return ("ROAM", (grid.cols // 2, grid.rows // 2))

    def astar_search(self, start, goal, grid, joker_pos=None, joker_alive=True):
        frontier = []
        heapq.heappush(frontier, (0, 0, start))
        came_from = {start: None}
        cost_so_far = {start: 0}
        counter = 0

        while frontier:
            _, _, current = heapq.heappop(frontier)
            self.nodes_expanded += 1

            if current == goal:
                path = []
                curr = current
                while curr and curr != start:
                    path.append(curr)
                    curr = came_from[curr]
                path.reverse()
                return path

            for _, (dx, dy) in DIRS.items():
                nx, ny = current[0] + dx, current[1] + dy
                neighbor = (nx, ny)

                if not grid.in_bounds(nx, ny):
                    continue
                tile = grid.tiles[ny][nx]
                if tile in (WALL, SMOKE):
                    continue

                step_cost = 1
                if tile in (TRAP_SPIKE, TRAP_STUN) and neighbor != goal:
                    step_cost += 16
                elif tile in (AOE_ACID, AOE_MAGMA) and neighbor != goal:
                    step_cost += 8

                if joker_alive and joker_pos:
                    if neighbor == joker_pos and neighbor != goal:
                        step_cost += 35
                    elif manhattan(neighbor, joker_pos) == 1 and neighbor != goal:
                        step_cost += 6

                new_cost = cost_so_far[current] + step_cost
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    priority = new_cost + manhattan(neighbor, goal)
                    counter += 1
                    heapq.heappush(frontier, (priority, counter, neighbor))
                    came_from[neighbor] = current

        return []

    def find_empty_adjacent_tile(self, agent, grid):
        opp_dirs = [DIRS["down"], DIRS["up"], DIRS["left"], DIRS["right"]]
        for dx, dy in opp_dirs:
            tx, ty = agent.x + dx, agent.y + dy
            if grid.in_bounds(tx, ty) and grid.tiles[ty][tx] == EMPTY:
                return (tx, ty)
        return None

    def decide(self, agent, grid, visible_agents, all_agents=None, joker=None):
        if all_agents is None:
            all_agents = [agent] + (visible_agents or [])

        joker_alive = bool(joker and getattr(joker, 'alive', False))
        joker_pos = (joker.x, joker.y) if joker_alive else None
        joker_facing = getattr(joker, 'facing', 'down') if joker_alive else 'down'

        pos = (agent.x, agent.y)
        sorted_visible = sorted(visible_agents or [], key=lambda v: manhattan(pos, (v.x, v.y)))

        dist_to_joker = manhattan(pos, joker_pos) if (joker_alive and joker_pos) else 999
        closest_rival = sorted_visible[0] if sorted_visible else None
        closest_rival_dist = manhattan(pos, (closest_rival.x, closest_rival.y)) if closest_rival else 999

        # --- 1. Immediate Execution Check ---
        # Target Joker (within 2 tiles, rear or flank)
        if agent.armed and joker_alive and joker_pos and dist_to_joker <= 2:
            if dist_to_joker <= closest_rival_dist:
                if self.is_ambush_angle(agent.facing, joker_facing):
                    self.dialogue = f"Joker in range ({dist_to_joker} grids)! Striking rear!"
                    return "shoot"

        # Target Rival Operative (strictly adjacent, rear or flank)
        if closest_rival and agent.armed and agent.ammo > 0:
            if closest_rival_dist == 1:
                if self.is_ambush_angle(agent.facing, closest_rival.facing):
                    self.dialogue = f"Adjacent backstab executed on {closest_rival.algo_type}!"
                    return "shoot"

        # Fallback Joker shot if rival cannot be hit
        if agent.armed and joker_alive and joker_pos and dist_to_joker <= 2:
            if self.is_ambush_angle(agent.facing, joker_facing):
                self.dialogue = f"Joker in range ({dist_to_joker} grids)! Striking rear!"
                return "shoot"

        # --- 2. Dynamic Strategic Decision ---
        action_type, target_pos = self.evaluate_optimal_target(agent, grid, all_agents, joker)

        # Handle safe weapon dropping without looping
        if action_type == "UPGRADE_GUN":
            drop_pos = self.find_empty_adjacent_tile(agent, grid)
            if drop_pos:
                grid.set_tile(drop_pos[0], drop_pos[1], SWORD)
                agent.armed = False
                agent.weapon_type = None
                self.current_path = []
                self.last_target = None
            else:
                # If no adjacent tile is open, retain weapon and continue hunting
                action_type, target_pos = ("HUNT_AGENT", target_pos)

        if not target_pos:
            target_pos = (grid.cols // 2, grid.rows // 2)

        # --- 3. Path Replanning ---
        replan = False
        if not self.current_path:
            replan = True
        elif self.last_target is None or manhattan(target_pos, self.last_target) > 1:
            replan = True
        elif not grid.is_walkable(self.current_path[0][0], self.current_path[0][1]):
            replan = True
        elif joker_alive and joker_pos and self.current_path[0] == joker_pos:
            replan = True

        if replan:
            self.last_target = target_pos
            self.current_path = self.astar_search(pos, target_pos, grid, joker_pos, joker_alive)

        # --- 4. Step Execution & Emergency Un-Stuck Fallback ---
        if self.current_path:
            next_step = self.current_path.pop(0)
            for act, (dx, dy) in DIRS.items():
                if (agent.x + dx, agent.y + dy) == next_step:
                    return act

        # If no A* path exists to optimal rear, step toward target greedily
        best_act = None
        best_dist = 999
        for act, (dx, dy) in DIRS.items():
            nx, ny = agent.x + dx, agent.y + dy
            if grid.is_walkable(nx, ny):
                if not (joker_alive and joker_pos and (nx, ny) == joker_pos):
                    d = manhattan((nx, ny), target_pos)
                    if d < best_dist:
                        best_dist = d
                        best_act = act

        if best_act:
            return best_act

        return "stay"