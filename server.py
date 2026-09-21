"""
Sightline — Server Engine (Complete Reset & Random Repositioning)
================================================================
"""

import asyncio
import json
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

from sightline_core import (
    Grid, Agent, RandomBrain,
    DIRS, EMPTY, WALL, SMOKE, GUN, SWORD, TRAP_SPIKE, TRAP_STUN, AOE_ACID, AOE_MAGMA
)
from joker_brain import JokerBrain

try:
    from astar_brain import AStarBrain
except ImportError:
    AStarBrain = None

try:
    from sa_brain import SABrain
except ImportError:
    SABrain = None

try:
    from ga_brain import GABrain
except ImportError:
    GABrain = None

GRID_COLS, GRID_ROWS = 32, 18


class SanctumEngine:
    def __init__(self):
        self.grid = Grid(GRID_COLS, GRID_ROWS)
        self.agents = self.create_agents()
        self.joker = JokerBrain(16, 7)
        self.brains = {
            "ASTAR": AStarBrain(),
            "SA": SABrain() if SABrain else RandomBrain(),
            "GA": GABrain() if GABrain else RandomBrain(),
        }
        self.editor_mode = True
        self.turn_count = 0
        self.round_number = 1
        self.current_level_id = 1
        self.winner = None
        self.combat_active = False
        self.speed_multiplier = 1
        self.recent_events = []
        self.magma_tick = 0
        self.dramatic_delay = 0
        self.biomes = []
        self.log = [
            "Citadel Sanctum initialized.",
            "Select level or redesign map to reposition operatives."
        ]

        self.load_custom_level(1)

    def create_agents(self):
        types = ["ASTAR", "SA", "GA"]
        return [
            Agent(i, f"{t}", t, 0, 0, (0, 0))
            for i, t in enumerate(types)
        ]

    def clear_grid_completely(self):
        self.biomes = []
        for y in range(self.grid.rows):
            for x in range(self.grid.cols):
                self.grid.clear_tile(x, y)
        self.full_restart_operatives()

    def reset_agent_brains(self):
        for b in self.brains.values():
            if hasattr(b, 'current_path'):
                b.current_path = []
            if hasattr(b, 'last_target'):
                b.last_target = None
            if hasattr(b, 'position_history'):
                b.position_history = []

    def full_restart_operatives(self):
        """Disarms all operatives, restores all stats, and places them at random open locations."""
        self.reset_agent_brains()
        self.winner = None
        self.combat_active = False
        self.dramatic_delay = 0

        occupied = set()
        if self.joker and self.joker.alive:
            occupied.add((self.joker.x, self.joker.y))

        for agent in self.agents:
            agent.alive = True
            agent.combat_hp = 2
            agent.trap_lives = 3
            agent.is_wounded = False
            agent.fume_slow_turns = 0
            agent.stun_turns = 0
            agent.distracted_turns = 0
            agent.armed = False
            agent.weapon_type = None
            agent.ammo = 5

            # Find random walkable empty tile with spacing
            placed = False
            attempts = 0
            while not placed and attempts < 400:
                attempts += 1
                rx = random.randint(2, GRID_COLS - 3)
                ry = random.randint(2, GRID_ROWS - 3)
                if (rx, ry) not in occupied and self.grid.is_walkable(rx, ry) and self.grid.tiles[ry][rx] == EMPTY:
                    agent.x, agent.y = rx, ry
                    agent.spawn = (rx, ry)
                    occupied.add((rx, ry))
                    placed = True

    def sync_biomes_to_grid(self):
        for b in self.biomes:
            tile_type = AOE_ACID if b["type"] == "acid" else AOE_MAGMA
            for dy in range(b["h"]):
                for dx in range(b["w"]):
                    tx, ty = b["x"] + dx, b["y"] + dy
                    if self.grid.in_bounds(tx, ty) and self.grid.tiles[ty][tx] == EMPTY:
                        self.grid.set_tile(tx, ty, tile_type)

    def add_biome(self, root_x, root_y, b_type):
        if len(self.biomes) >= 3:
            return False
        can_place = True
        for dy in range(2):
            for dx in range(3):
                tx, ty = root_x + dx, root_y + dy
                if not self.grid.in_bounds(tx, ty) or self.grid.tiles[ty][tx] != EMPTY:
                    can_place = False
                    break
        if can_place:
            self.biomes.append({"type": "acid" if b_type == AOE_ACID else "magma", "x": root_x, "y": root_y, "w": 3, "h": 2})
            self.sync_biomes_to_grid()
            return True
        return False

    def place_random_weapons(self, count=3):
        mid_x, mid_y = GRID_COLS // 2, GRID_ROWS // 2
        agent_positions = {(a.x, a.y) for a in self.agents}
        placed = 0
        attempts = 0

        while placed < count and attempts < 400:
            attempts += 1
            rx = random.randint(2, GRID_COLS - 3)
            ry = random.randint(2, GRID_ROWS - 3)
            if self.grid.tiles[ry][rx] == EMPTY and (rx, ry) not in agent_positions and (rx, ry) != (mid_x, mid_y):
                w_type = random.choice([GUN, SWORD])
                self.grid.set_tile(rx, ry, w_type)
                placed += 1

    def load_custom_level(self, level_id: int):
        self.clear_grid_completely()
        self.current_level_id = level_id
        mid_x, mid_y = GRID_COLS // 2, GRID_ROWS // 2
        walls = []
        traps = []

        if level_id == 1:
            level_name = "Courtyard Atrium [TIER 1 - NOVICE]"
            walls = [
                (mid_x - 5, 4), (mid_x - 4, 4), (mid_x + 4, 4), (mid_x + 5, 4),
                (mid_x - 5, 13), (mid_x - 4, 13), (mid_x + 4, 13), (mid_x + 5, 13),
                (8, 8), (9, 8), (22, 8), (23, 8),
                (mid_x, 3), (mid_x, 14)
            ]
            self.biomes = [{"type": "acid", "x": 14, "y": 12, "w": 3, "h": 2}]
            traps = [(11, 8, TRAP_SPIKE), (20, 8, TRAP_STUN)]

        elif level_id == 2:
            level_name = "Twin Sentry Forts [TIER 2 - APPRENTICE]"
            for y in range(4, 14):
                if y not in (6, 11):
                    walls.extend([(7, y), (24, y)])
            walls.extend([(8, 4), (9, 4), (22, 4), (23, 4), (8, 13), (9, 13), (22, 13), (23, 13)])
            self.biomes = [
                {"type": "acid", "x": 10, "y": 7, "w": 3, "h": 2},
                {"type": "magma", "x": 19, "y": 9, "w": 3, "h": 2}
            ]
            traps = [(7, 6, TRAP_SPIKE), (24, 11, TRAP_SPIKE), (mid_x, 5, TRAP_STUN)]

        elif level_id == 3:
            level_name = "Serpent Trench [TIER 3 - MODERATE]"
            for x in range(5, 27, 3):
                walls.extend([(x, 5), (x + 1, 5), (x, 12), (x + 1, 12)])
            walls.extend([(mid_x, 7), (mid_x, 8), (mid_x, 9), (mid_x, 10)])
            self.biomes = [{"type": "acid", "x": 8, "y": 8, "w": 3, "h": 2}]
            traps = [
                (12, 6, TRAP_SPIKE), (19, 6, TRAP_SPIKE),
                (12, 11, TRAP_STUN), (19, 11, TRAP_STUN)
            ]

        elif level_id == 4:
            level_name = "Crossfire Redoubt [TIER 4 - TACTICAL]"
            for ox in [6, 21]:
                for oy in [3, 10]:
                    walls.extend([
                        (ox, oy), (ox + 1, oy), (ox + 2, oy),
                        (ox, oy + 1), (ox, oy + 2), (ox + 3, oy + 2)
                    ])
            walls.extend([(mid_x - 1, 8), (mid_x + 1, 8)])
            self.biomes = [
                {"type": "acid", "x": 9, "y": 7, "w": 3, "h": 2},
                {"type": "magma", "x": 20, "y": 7, "w": 3, "h": 2}
            ]
            traps = [(mid_x - 3, 7, TRAP_STUN), (mid_x + 3, 7, TRAP_STUN), (mid_x, 11, TRAP_SPIKE)]

        elif level_id == 5:
            level_name = "Spikewall Gauntlet [TIER 5 - HAZARDOUS]"
            for x in range(4, 28):
                if x not in (9, 16, 22):
                    walls.extend([(x, 5), (x, 12)])
            walls.extend([(mid_x - 4, 8), (mid_x + 4, 8)])
            self.biomes = [
                {"type": "magma", "x": 7, "y": 8, "w": 3, "h": 2},
                {"type": "magma", "x": 22, "y": 8, "w": 3, "h": 2}
            ]
            traps = [
                (9, 5, TRAP_SPIKE), (22, 5, TRAP_SPIKE),
                (9, 12, TRAP_STUN), (22, 12, TRAP_STUN),
                (16, 7, TRAP_SPIKE), (16, 10, TRAP_SPIKE)
            ]

        elif level_id == 6:
            level_name = "Volcanic Caldera [TIER 6 - INFERNAL]"
            for r in range(4):
                walls.extend([
                    (5 + r, 4), (26 - r, 4),
                    (5 + r, 13), (26 - r, 13),
                    (mid_x - 5, 6 + r), (mid_x + 5, 6 + r)
                ])
            walls.extend([(mid_x - 1, 3), (mid_x + 1, 3), (mid_x - 1, 14), (mid_x + 1, 14)])
            self.biomes = [
                {"type": "magma", "x": 7, "y": 7, "w": 3, "h": 2},
                {"type": "magma", "x": 22, "y": 7, "w": 3, "h": 2}
            ]
            traps = [
                (12, 7, TRAP_SPIKE), (19, 7, TRAP_SPIKE),
                (12, 10, TRAP_STUN), (19, 10, TRAP_STUN),
                (mid_x, 8, TRAP_SPIKE)
            ]

        elif level_id == 7:
            level_name = "Labyrinth of Whispers [TIER 7 - LETHAL]"
            for x in range(4, 28, 4):
                for y in range(2, 16):
                    if (y + x) % 3 != 0:
                        walls.append((x, y))
            for y in (5, 11):
                walls.extend([(mid_x - 2, y), (mid_x + 2, y)])
            self.biomes = [
                {"type": "acid", "x": 9, "y": 6, "w": 3, "h": 2},
                {"type": "acid", "x": 19, "y": 9, "w": 3, "h": 2}
            ]
            traps = [
                (8, 5, TRAP_SPIKE), (16, 5, TRAP_SPIKE), (24, 5, TRAP_SPIKE),
                (8, 11, TRAP_STUN), (16, 11, TRAP_STUN), (24, 11, TRAP_STUN)
            ]

        else:
            level_name = "Sanctum Cataclysm [TIER 8 - APOCALYPSE]"
            for x in range(3, 29, 3):
                walls.extend([(x, 3), (x, 14), (x, 8)])
            for y in range(4, 14, 3):
                walls.extend([(6, y), (25, y)])
            walls.extend([(mid_x - 2, 6), (mid_x + 2, 6), (mid_x - 2, 11), (mid_x + 2, 11)])
            self.biomes = [
                {"type": "magma", "x": 8, "y": 5, "w": 3, "h": 2},
                {"type": "acid", "x": 21, "y": 5, "w": 3, "h": 2},
                {"type": "magma", "x": 14, "y": 10, "w": 3, "h": 2}
            ]
            traps = [
                (5, 4, TRAP_SPIKE), (26, 4, TRAP_SPIKE),
                (5, 13, TRAP_SPIKE), (26, 13, TRAP_SPIKE),
                (mid_x - 3, 9, TRAP_STUN), (mid_x + 3, 9, TRAP_STUN),
                (mid_x, 5, TRAP_SPIKE), (mid_x, 12, TRAP_SPIKE)
            ]

        for wx, wy in walls:
            if self.grid.in_bounds(wx, wy) and (wx, wy) != (mid_x, mid_y):
                self.grid.set_tile(wx, wy, WALL)

        self.sync_biomes_to_grid()

        for tx, ty, t_type in traps:
            if self.grid.in_bounds(tx, ty) and self.grid.tiles[ty][tx] == EMPTY and (tx, ty) != (mid_x, mid_y):
                self.grid.set_tile(tx, ty, t_type)

        self.joker = JokerBrain(mid_x, mid_y)
        self.full_restart_operatives()
        self.place_random_weapons(count=3)
        self.log.append(f"{level_name} deployed. Operatives scattered.")

    def generate_random_sanctum(self):
        chosen_lvl = random.randint(1, 8)
        self.load_custom_level(chosen_lvl)

    def reset_round(self):
        self.full_restart_operatives()
        self.round_number += 1
        self.joker = JokerBrain(GRID_COLS // 2, GRID_ROWS // 2)
        self.dramatic_delay = 0
        self.log.append(f"Cycle {self.round_number} Initiated. Weapons discarded, operatives repositioned.")

    def has_uncollected_weapons(self):
        return any(
            self.grid.tiles[y][x] in (GUN, SWORD)
            for y in range(self.grid.rows)
            for x in range(self.grid.cols)
        )

    def check_combat_ready(self):
        living = [a for a in self.agents if a.alive]
        if not living:
            return True
        return all(a.armed for a in living) or not self.has_uncollected_weapons()

    def visible_agents_for(self, agent):
        seen = []
        for d in DIRS:
            los = self.grid.line_of_sight(agent.x, agent.y, d)
            for other in self.agents:
                if other.id != agent.id and other.alive and (other.x, other.y) in los:
                    seen.append(other)
        return seen

    def is_adjacent(self, a, b):
        return abs(a.x - b.x) + abs(a.y - b.y) == 1

    def distance_to_joker(self, agent):
        return abs(agent.x - self.joker.x) + abs(agent.y - self.joker.y)

    def can_target_joker(self, agent):
        return self.distance_to_joker(agent) <= 2

    def is_backstab_angle(self, shooter, victim):
        opp_face = {"up": "down", "down": "up", "left": "right", "right": "left"}
        return shooter.facing != opp_face.get(victim.facing)

    def check_pool_perimeter_side_effects(self, agent):
        for _, (dx, dy) in DIRS.items():
            nx, ny = agent.x + dx, agent.y + dy
            if self.grid.in_bounds(nx, ny):
                t = self.grid.tiles[ny][nx]
                if t == AOE_ACID:
                    agent.fume_slow_turns = 1
                    brain = self.brains.get(agent.algo_type)
                    if brain and not agent.is_wounded:
                        brain.dialogue = "[ACID FUMES] Noxious vapors burning throat!"
                    return
                elif t == AOE_MAGMA:
                    brain = self.brains.get(agent.algo_type)
                    if brain and not agent.is_wounded:
                        brain.dialogue = "[MAGMA HEAT] Thermal backdraft scorching armor!"
                    return

    def step(self):
        if self.winner or self.editor_mode:
            return

        self.recent_events = []
        self.grid.tick_smoke()
        self.magma_tick = (self.magma_tick + 1) % 3
        self.dramatic_delay = 0

        # Step Joker
        if self.joker.alive:
            j_tile = self.grid.tiles[self.joker.y][self.joker.x]
            if j_tile == TRAP_SPIKE or (j_tile == AOE_MAGMA and self.magma_tick == 0):
                self.joker.take_hit()
                self.log.append(f"HAZARD: Joker took environmental damage! (HP: {self.joker.lives})")
                self.recent_events.append({"type": "spike_hit", "x": self.joker.x, "y": self.joker.y})

            joker_event = self.joker.step(self.grid, self.agents)
            if joker_event:
                self.recent_events.append(joker_event)
                self.dramatic_delay = 2.4
                for ag in self.agents:
                    if ag.id == joker_event["agent_id"]:
                        brain = self.brains[ag.algo_type]
                        brain.dialogue = joker_event["agent_reply"]

        living = [a for a in self.agents if a.alive]
        if len(living) <= 1:
            self.winner = living[0].algo_type if living else "Nobody"
            self.log.append(f"VICTORY: {self.winner} claims sole survival!")
            return

        if not self.combat_active and self.check_combat_ready():
            self.combat_active = True
            self.log.append("STAND-OFF COMMENCED: Weapons claimed! Proximity attacks enabled.")

        can_attack_rivals = self.combat_active and not self.has_uncollected_weapons()

        for agent in self.agents:
            if not agent.alive:
                continue

            if agent.stun_turns > 0:
                agent.stun_turns -= 1
                continue

            if agent.distracted_turns > 0:
                agent.distracted_turns -= 1
                continue

            if agent.fume_slow_turns > 0:
                agent.fume_slow_turns -= 1
                continue

            current_tile = self.grid.tiles[agent.y][agent.x]
            if current_tile == AOE_MAGMA and self.magma_tick == 0:
                agent.take_trap_hit()
                self.log.append(f"BURST: {agent.algo_type} scorched by magma! ({agent.trap_lives}/3 Shields)")
                self.recent_events.append({"type": "magma_blast", "x": agent.x, "y": agent.y})
                if not agent.alive:
                    self.log.append(f"{agent.algo_type} dissolved in molten magma!")
                    continue
            elif current_tile == AOE_ACID:
                agent.take_trap_hit()
                self.log.append(f"ACID BURN: {agent.algo_type} touched toxic pool! ({agent.trap_lives}/3 Shields)")
                if not agent.alive:
                    self.log.append(f"{agent.algo_type} dissolved in caustic acid!")
                    continue

            self.check_pool_perimeter_side_effects(agent)

            visible = self.visible_agents_for(agent)
            active_targets = visible if can_attack_rivals else []
            active_targets.sort(key=lambda v: abs(agent.x - v.x) + abs(agent.y - v.y))

            brain = self.brains[agent.algo_type]
            old_x, old_y = agent.x, agent.y

            if isinstance(brain, (AStarBrain, SABrain, GABrain)):
                action = brain.decide(agent, self.grid, active_targets, self.agents, self.joker)
            else:
                action = brain.decide(agent, self.grid, active_targets)

            if action == "shoot" and agent.armed and agent.ammo > 0:
                joker_in_range = self.joker.alive and self.can_target_joker(agent)
                dist_joker = self.distance_to_joker(agent) if self.joker.alive else 999

                closest_rival = active_targets[0] if active_targets else None
                dist_rival = (abs(agent.x - closest_rival.x) + abs(agent.y - closest_rival.y)) if closest_rival else 999

                attack_performed = False

                if joker_in_range and (dist_joker <= dist_rival):
                    if self.is_backstab_angle(agent, self.joker):
                        agent.ammo -= 1
                        self.joker.alive = False
                        attack_performed = True
                        self.dramatic_delay = 3.2
                        self.log.append(f"ASSASSINATION! {agent.algo_type} eliminated Joker from {dist_joker} grid(s) away!")
                        self.recent_events.append({
                            "type": "joker_killed",
                            "shooter": {"x": agent.x, "y": agent.y},
                            "victim": {"x": self.joker.x, "y": self.joker.y}
                        })
                    else:
                        self.log.append(f"{agent.algo_type}'s strike glanced off Joker's guard!")

                if not attack_performed and closest_rival and can_attack_rivals:
                    if self.is_adjacent(agent, closest_rival):
                        if self.is_backstab_angle(agent, closest_rival):
                            agent.ammo -= 1
                            attack_performed = True
                            if agent.weapon_type == "GUN":
                                closest_rival.take_combat_hit("GUN")
                                self.dramatic_delay = 3.4
                                self.log.append(f"POINT-BLANK EXECUTION! {agent.algo_type} eliminated {closest_rival.algo_type}!")
                                self.recent_events.append({
                                    "type": "shoot",
                                    "shooter": {"x": agent.x, "y": agent.y},
                                    "victim": {"x": closest_rival.x, "y": closest_rival.y},
                                    "weapon": "GUN",
                                    "fatal": True
                                })
                                self.log.append(f"{closest_rival.algo_type} was ELIMINATED!")
                            else:
                                was_already_wounded = closest_rival.is_wounded or closest_rival.combat_hp <= 1
                                closest_rival.take_combat_hit("SWORD")
                                if not was_already_wounded:
                                    self.dramatic_delay = 2.6
                                    self.log.append(f"ADJACENT STAB! {agent.algo_type} sliced {closest_rival.algo_type}! (1 HP remaining)")
                                    self.recent_events.append({
                                        "type": "sword_stab",
                                        "shooter": {"x": agent.x, "y": agent.y},
                                        "victim": {"x": closest_rival.x, "y": closest_rival.y},
                                        "weapon": "SWORD",
                                        "fatal": False
                                    })
                                else:
                                    self.dramatic_delay = 3.4
                                    self.log.append(f"DEATHBLOW! {agent.algo_type} landed fatal stab on {closest_rival.algo_type}!")
                                    self.recent_events.append({
                                        "type": "sword_stab",
                                        "shooter": {"x": agent.x, "y": agent.y},
                                        "victim": {"x": closest_rival.x, "y": closest_rival.y},
                                        "weapon": "SWORD",
                                        "fatal": True
                                    })
                                    self.log.append(f"{closest_rival.algo_type} was ELIMINATED!")
                        else:
                            self.log.append(f"{agent.algo_type}'s strike was parried! Head-on.")

                if not attack_performed and joker_in_range:
                    if self.is_backstab_angle(agent, self.joker):
                        agent.ammo -= 1
                        self.joker.alive = False
                        self.dramatic_delay = 3.2
                        self.log.append(f"ASSASSINATION! {agent.algo_type} eliminated Joker from {dist_joker} grid(s) away!")
                        self.recent_events.append({
                            "type": "joker_killed",
                            "shooter": {"x": agent.x, "y": agent.y},
                            "victim": {"x": self.joker.x, "y": self.joker.y}
                        })

            elif action in DIRS:
                dx, dy = DIRS[action]
                nx, ny = agent.x + dx, agent.y + dy
                agent.facing = action

                too_close_agent = any(a.alive and a.id != agent.id and a.x == nx and a.y == ny for a in self.agents)
                too_close_joker = (self.joker.alive and self.joker.x == nx and self.joker.y == ny)

                if self.grid.is_walkable(nx, ny) and not too_close_agent and not too_close_joker:
                    agent.x, agent.y = nx, ny
                    t = self.grid.tiles[ny][nx]
                    if (nx, ny) != (old_x, old_y):
                        if t == GUN:
                            agent.armed = True
                            agent.weapon_type = "GUN"
                            self.grid.clear_tile(nx, ny)
                            self.log.append(f"{agent.algo_type} acquired the Rifle!")
                            self.recent_events.append({"type": "pickup", "x": nx, "y": ny, "weapon": "GUN"})
                        elif t == SWORD:
                            agent.armed = True
                            agent.weapon_type = "SWORD"
                            self.grid.clear_tile(nx, ny)
                            self.log.append(f"{agent.algo_type} equipped the Sword!")
                            self.recent_events.append({"type": "pickup", "x": nx, "y": ny, "weapon": "SWORD"})
                        elif t == TRAP_SPIKE:
                            agent.take_trap_hit()
                            self.grid.clear_tile(nx, ny)
                            self.log.append(f"TRAP TRIGGERED: {agent.algo_type} hit Spike Pit! ({agent.trap_lives}/3 Shields)")
                            self.recent_events.append({"type": "spike_hit", "x": nx, "y": ny})
                            if not agent.alive:
                                self.log.append(f"{agent.algo_type} succumbed to spikes!")
                        elif t == TRAP_STUN:
                            agent.stun_turns = 2
                            self.grid.clear_tile(nx, ny)
                            self.log.append(f"TRAP TRIGGERED: {agent.algo_type} tripped EMP Drone! (Stunned 2 turns)")
                            self.recent_events.append({"type": "stun_hit", "x": nx, "y": ny})

        self.turn_count += 1
        self.log = self.log[-6:]

    def to_dict(self):
        thoughts = {}
        for a in self.agents:
            if a.alive:
                b = self.brains[a.algo_type]
                thoughts[a.algo_type] = getattr(b, "dialogue", "")

        return {
            "cols": self.grid.cols,
            "rows": self.grid.rows,
            "tiles": self.grid.tiles,
            "biomes": self.biomes,
            "editor_mode": self.editor_mode,
            "turn_count": self.turn_count,
            "round_number": self.round_number,
            "level_id": self.current_level_id,
            "combat_active": self.combat_active,
            "winner": self.winner,
            "speed": self.speed_multiplier,
            "events": self.recent_events,
            "log": self.log,
            "thoughts": thoughts,
            "joker": {
                "x": self.joker.x,
                "y": self.joker.y,
                "facing": self.joker.facing,
                "mode": self.joker.mode,
                "alive": self.joker.alive,
                "lives": self.joker.lives,
                "dialogue": self.joker.dialogue
            },
            "agents": [
                {
                    "id": a.id,
                    "name": a.name,
                    "algo_type": a.algo_type,
                    "x": a.x,
                    "y": a.y,
                    "facing": a.facing,
                    "armed": a.armed,
                    "weapon_type": a.weapon_type,
                    "lives": a.combat_hp,
                    "combat_hp": a.combat_hp,
                    "trap_lives": a.trap_lives,
                    "is_wounded": a.is_wounded,
                    "ammo": a.ammo,
                    "alive": a.alive,
                    "stunned": a.stun_turns > 0,
                    "distracted": a.distracted_turns > 0,
                }
                for a in self.agents
            ]
        }


game = SanctumEngine()
app = FastAPI()
sockets = set()

async def broadcast():
    if not sockets:
        return
    msg = json.dumps(game.to_dict())
    dead = []
    for s in sockets:
        try:
            await s.send_text(msg)
        except Exception:
            dead.append(s)
    for s in dead:
        sockets.remove(s)

@app.get("/")
async def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    sockets.add(ws)
    await ws.send_text(json.dumps(game.to_dict()))
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            act = data.get("type")

            if act == "load_level":
                lvl = int(data.get("level_id", 1))
                game.load_custom_level(lvl)
                await broadcast()

            elif act == "set_tile":
                gx, gy, t = data["x"], data["y"], data["tile"]
                if game.editor_mode and game.grid.in_bounds(gx, gy):
                    occupied = any(a.alive and a.x == gx and a.y == gy for a in game.agents)
                    if not occupied:
                        if t in (AOE_ACID, AOE_MAGMA):
                            game.add_biome(gx, gy, t)
                        elif t == "EMPTY":
                            game.grid.clear_tile(gx, gy)
                        else:
                            cur = game.grid.tiles[gy][gx]
                            game.grid.set_tile(gx, gy, EMPTY if cur == t else t)
                    game.reset_agent_brains()
                await broadcast()

            elif act == "move_agent":
                agent_id = data.get("agent_id")
                gx, gy = data["x"], data["y"]
                if game.editor_mode and game.grid.in_bounds(gx, gy):
                    tile_free = game.grid.tiles[gy][gx] == EMPTY
                    agent_free = not any(a.alive and a.x == gx and a.y == gy for a in game.agents)
                    if tile_free and agent_free:
                        for ag in game.agents:
                            if ag.id == agent_id:
                                ag.alive = True
                                ag.x, ag.y = gx, gy
                                ag.spawn = (gx, gy)
                                break
                    game.reset_agent_brains()
                await broadcast()

            elif act == "remove_agent":
                agent_id = data.get("agent_id")
                if game.editor_mode:
                    for ag in game.agents:
                        if ag.id == agent_id:
                            ag.alive = False
                            ag.x, ag.y = -10, -10
                            break
                    game.reset_agent_brains()
                await broadcast()

            elif act == "set_speed":
                game.speed_multiplier = int(data.get("speed", 1))
                await broadcast()

            elif act == "clear_all":
                if game.editor_mode:
                    game.clear_grid_completely()
                await broadcast()

            elif act == "randomize_map":
                game.generate_random_sanctum()
                await broadcast()

            elif act == "start":
                game.editor_mode = False
                game.log.append("Breach Initiated! Stalk targets from behind.")
                await broadcast()

            elif act == "edit_mode":
                game.editor_mode = True
                await broadcast()

            elif act == "reset":
                game.reset_round()
                await broadcast()

    except WebSocketDisconnect:
        sockets.discard(ws)

async def tick_loop():
    while True:
        base_interval = 1.05
        extra_pause = game.dramatic_delay
        current_sleep = (base_interval / max(game.speed_multiplier, 1)) + extra_pause
        await asyncio.sleep(current_sleep)
        if not game.editor_mode and not game.winner:
            game.step()
            await broadcast()

@app.on_event("startup")
async def on_start():
    asyncio.create_task(tick_loop())

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
