from sightline_core import (
    DIRS, WALL, SMOKE, GUN, SWORD, TRAP_SPIKE, TRAP_STUN, AOE_ACID, AOE_MAGMA, EMPTY
)


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class GAEncodingMixin:

    GA_GENOME_LENGTH = 40
    _MOVE_LIST = list(DIRS.items())

    def _tile_step_cost(self, tile, is_goal_tile, joker_alive, joker_pos, neighbor):
        cost = 1
        if tile in (TRAP_SPIKE, TRAP_STUN) and not is_goal_tile:
            cost += 16
        elif tile in (AOE_ACID, AOE_MAGMA) and not is_goal_tile:
            cost += 8
        if joker_alive and joker_pos:
            if neighbor == joker_pos and not is_goal_tile:
                cost += 35
            elif manhattan(neighbor, joker_pos) == 1 and not is_goal_tile:
                cost += 6
        return cost

    def _fitness(self, genome, start, goal, grid, joker_pos, joker_alive):
        path = self._simulate_genome(genome, start, goal, grid)
        cur = start
        cost = 0
        for step in path:
            tile = grid.tiles[step[1]][step[0]]
            cost += self._tile_step_cost(tile, step == goal, joker_alive, joker_pos, step)
            cur = step
        cost += manhattan(cur, goal) * 5
        cost += len(path) * 0.1
        if cur == goal:
            cost -= 100
        return cost

    def _simulate_genome(self, genome, start, goal, grid):
        path = []
        cur = start
        for gene in genome:
            if cur == goal:
                break
            _, (dx, dy) = self._MOVE_LIST[gene % len(self._MOVE_LIST)]
            nx, ny = cur[0] + dx, cur[1] + dy
            if grid.in_bounds(nx, ny) and grid.tiles[ny][nx] not in (WALL, SMOKE):
                cur = (nx, ny)
                path.append(cur)
        return path

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

        if not agent.armed:
            if best_gun and not best_sword:
                self.dialogue = f"{wounded_prefix}Evolving a route to the Rifle!"
                return ("GET_WEAPON", best_gun)
            if best_sword and not best_gun:
                self.dialogue = f"{wounded_prefix}Evolving a route to the Blade!"
                return ("GET_WEAPON", best_sword)
            if best_gun and best_sword:
                gun_dist = manhattan(pos, best_gun)
                sword_dist = manhattan(pos, best_sword)
                joker_risk = 10 if (joker_alive and joker_pos and manhattan(joker_pos, best_gun) <= 2) else 0
                if (gun_dist + joker_risk) <= (sword_dist + 3):
                    self.dialogue = f"{wounded_prefix}Breeding a path to the Rifle!"
                    return ("GET_WEAPON", best_gun)
                else:
                    self.dialogue = f"{wounded_prefix}Rifle guarded. Evolving toward Sword!"
                    return ("GET_WEAPON", best_sword)

            if other_living:
                nearest = other_living[0]
                self.dialogue = f"{wounded_prefix}Unarmed! Evolved stalking of {nearest.algo_type}!"
                ambush_tiles = self.get_flank_tiles((nearest.x, nearest.y), nearest.facing, grid)
                return ("STALK", ambush_tiles[0])
            return ("ROAM", (grid.cols // 2, grid.rows // 2))

        if agent.armed and agent.weapon_type == "SWORD":
            if best_gun and self.swap_cooldown <= 0:
                joker_blocking = joker_alive and joker_pos and manhattan(joker_pos, best_gun) <= 1
                if not joker_blocking:
                    test_path = self.genetic_algorithm_search(pos, best_gun, grid, joker_pos, joker_alive)
                    if test_path:
                        self.swap_cooldown = 16
                        self.dialogue = f"{wounded_prefix}Upgrading: Dropping blade for Rifle!"
                        return ("UPGRADE_GUN", best_gun)

            dist_joker = manhattan(pos, joker_pos) if (joker_alive and joker_pos) else 999
            dist_rival = manhattan(pos, (other_living[0].x, other_living[0].y)) if other_living else 999

            if joker_alive and joker_pos and (dist_joker <= dist_rival or not other_living):
                ambush_tiles = self.get_flank_tiles(joker_pos, joker_facing, grid)
                best_flank = min(ambush_tiles, key=lambda p: manhattan(pos, p))
                self.dialogue = f"{wounded_prefix}Blade armed! Evolved stalk on Joker's rear!"
                return ("KILL_JOKER", best_flank)

            if other_living:
                nearest = other_living[0]
                ambush_tiles = self.get_flank_tiles((nearest.x, nearest.y), nearest.facing, grid)
                best_flank = min(ambush_tiles, key=lambda p: manhattan(pos, p))
                self.dialogue = f"{wounded_prefix}Tracking nearest rival {nearest.algo_type}!"
                return ("HUNT_AGENT", best_flank)

        if agent.armed and agent.weapon_type == "GUN":
            dist_joker = manhattan(pos, joker_pos) if (joker_alive and joker_pos) else 999
            dist_rival = manhattan(pos, (other_living[0].x, other_living[0].y)) if other_living else 999

            if joker_alive and joker_pos and (dist_joker <= dist_rival or not other_living):
                ambush_tiles = self.get_flank_tiles(joker_pos, joker_facing, grid)
                best_flank = min(ambush_tiles, key=lambda p: manhattan(pos, p))
                self.dialogue = f"{wounded_prefix}Rifle ready! Evolved flank on Joker!"
                return ("KILL_JOKER", best_flank)

            if other_living:
                nearest = other_living[0]
                ambush_tiles = self.get_flank_tiles((nearest.x, nearest.y), nearest.facing, grid)
                best_flank = min(ambush_tiles, key=lambda p: manhattan(pos, p))
                self.dialogue = f"{wounded_prefix}Hunting nearest rival {nearest.algo_type}!"
                return ("HUNT_AGENT", best_flank)

        return ("ROAM", (grid.cols // 2, grid.rows // 2))

    def find_empty_adjacent_tile(self, agent, grid):
        opp_dirs = [DIRS["down"], DIRS["up"], DIRS["left"], DIRS["right"]]
        for dx, dy in opp_dirs:
            tx, ty = agent.x + dx, agent.y + dy
            if grid.in_bounds(tx, ty) and grid.tiles[ty][tx] == EMPTY:
                return (tx, ty)
        return None

    def get_flank_tiles(self, target_pos, target_facing, grid):
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

        rdx, rdy = rear_dirs.get(target_facing, (0, 1))
        rear_pos = (target_pos[0] + rdx, target_pos[1] + rdy)
        candidates = [rear_pos]

        for fdx, fdy in flank_dirs.get(target_facing, []):
            candidates.append((target_pos[0] + fdx, target_pos[1] + fdy))

        for _, (dx, dy) in DIRS.items():
            candidates.append((target_pos[0] + dx, target_pos[1] + dy))

        valid = [p for p in candidates if grid.in_bounds(p[0], p[1]) and grid.is_walkable(p[0], p[1])]
        return valid if valid else [target_pos]

    def is_ambush_angle(self, hunter_facing, target_facing):
        opp_face = {
            "up": "down",
            "down": "up",
            "left": "right",
            "right": "left"
        }
        return hunter_facing != opp_face.get(target_facing)

    def check_immediate_shot(self, agent, joker_alive, joker_pos, joker_facing,
                              dist_to_joker, closest_rival, closest_rival_dist):
        if agent.armed and joker_alive and joker_pos and dist_to_joker <= 2:
            if dist_to_joker <= closest_rival_dist:
                if self.is_ambush_angle(agent.facing, joker_facing):
                    self.dialogue = f"Joker in range ({dist_to_joker} grids)! Striking rear!"
                    return "shoot"

        if closest_rival and agent.armed and agent.ammo > 0:
            if closest_rival_dist == 1:
                if self.is_ambush_angle(agent.facing, closest_rival.facing):
                    self.dialogue = f"Adjacent backstab executed on {closest_rival.algo_type}!"
                    return "shoot"

        if agent.armed and joker_alive and joker_pos and dist_to_joker <= 2:
            if self.is_ambush_angle(agent.facing, joker_facing):
                self.dialogue = f"Joker in range ({dist_to_joker} grids)! Striking rear!"
                return "shoot"

        return None
