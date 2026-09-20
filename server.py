"""
Sightline — Server Engine (Procedural Redesign & Cinematic Dramatic Timing)
==========================================================================
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

GRID_COLS, GRID_ROWS = 32, 18

class SanctumEngine:
    def __init__(self):
        self.grid = Grid(GRID_COLS, GRID_ROWS)
        self.agents = self.create_agents()
        self.joker = JokerBrain(16, 7)
        self.brains = {
            "ASTAR": AStarBrain(),
            "SA": RandomBrain(),
            "GA": RandomBrain(),
        }
        self.editor_mode = True
        self.turn_count = 0
        self.round_number = 1
        self.winner = None
        self.combat_active = False
        self.speed_multiplier = 1
        self.recent_events = []
        self.magma_tick = 0
        self.dramatic_delay = 0

        self.biomes = []
        self.log = [
            "The Joker Sanctum awakens.",
            "Click REDESIGN to generate a unique tactical citadel layout!"
        ]

        self.generate_random_sanctum()

    def create_agents(self):
        spawns = [(2, 2), (GRID_COLS - 3, 2), (GRID_COLS // 2, GRID_ROWS - 3)]
        types = ["ASTAR", "SA", "GA"]
        return [
            Agent(i, f"{t}", t, sx, sy, (sx, sy))
            for i, (t, (sx, sy)) in enumerate(zip(types, spawns))
        ]

    def clear_grid_completely(self):
        self.biomes = []
        for y in range(self.grid.rows):
            for x in range(self.grid.cols):
                self.grid.clear_tile(x, y)

    def generate_random_sanctum(self):
        """Procedurally crafts a unique, balanced tactical dungeon."""
        self.clear_grid_completely()

        # 1. Outer corner and corridor bastions
        wall_patterns = []
        # Random labyrinth wings
        mid_x = GRID_COLS // 2
        mid_y = GRID_ROWS // 2

        # Symmetrical aesthetic clusters
        cluster_style = random.choice(["ruins", "pillars", "citadel", "arena"])

        if cluster_style == "citadel":
            for ox in [5, 23]:
                for oy in [3, 11]:
                    wall_patterns.extend([
                        (ox, oy), (ox + 1, oy), (ox + 2, oy),
                        (ox, oy + 1), (ox, oy + 2), (ox + 3, oy + 2)
                    ])
            wall_patterns.extend([
                (mid_x - 3, 6), (mid_x + 3, 6),
                (mid_x - 3, 11), (mid_x + 3, 11),
                (mid_x - 1, 3), (mid_x, 3), (mid_x + 1, 3),
                (mid_x - 1, 14), (mid_x, 14), (mid_x + 1, 14)
            ])
        elif cluster_style == "pillars":
            for x in range(4, GRID_COLS - 4, 4):
                for y in range(3, GRID_ROWS - 3, 4):
                    wall_patterns.extend([(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)])
        elif cluster_style == "arena":
            wall_patterns.extend([
                (7, 4), (8, 4), (9, 4), (10, 4), (7, 5), (7, 6),
                (21, 4), (22, 4), (23, 4), (24, 4), (24, 5), (24, 6),
                (7, 11), (7, 12), (8, 13), (9, 13), (10, 13),
                (24, 11), (24, 12), (23, 13), (22, 13), (21, 13),
                (mid_x - 4, mid_y), (mid_x - 3, mid_y),
                (mid_x + 3, mid_y), (mid_x + 4, mid_y)
            ])
        else:  # ruins
            for _ in range(7):
                rx = random.randint(4, GRID_COLS - 8)
                ry = random.randint(3, GRID_ROWS - 6)
                length = random.randint(3, 6)
                horizontal = random.choice([True, False])
                for step in range(length):
                    wx = rx + (step if horizontal else 0)
                    wy = ry + (0 if horizontal else step)
                    wall_patterns.append((wx, wy))

        for wx, wy in wall_patterns:
            if self.grid.in_bounds(wx, wy):
                # Never place walls on agent spawns or center bonfire
                if not any(a.spawn == (wx, wy) for a in self.agents) and (wx, wy) != (mid_x, mid_y):
                    self.grid.set_tile(wx, wy, WALL)

        # 2. Procedural Hazard Biomes (1 Acid, 1 Magma)
        b_types = ["acid", "magma"]
        for b_type in b_types:
            placed = False
            attempts = 0
            while not placed and attempts < 50:
                attempts += 1
                bx = random.randint(5, GRID_COLS - 8)
                by = random.randint(3, GRID_ROWS - 5)
                # Check 3x2 space is completely free
                can_fit = True
                for dy in range(2):
                    for dx in range(3):
                        tx, ty = bx + dx, by + dy
                        if not self.grid.in_bounds(tx, ty) or self.grid.tiles[ty][tx] != EMPTY or (tx, ty) == (mid_x, mid_y):
                            can_fit = False
                            break
                if can_fit:
                    self.biomes.append({"type": b_type, "x": bx, "y": by, "w": 3, "h": 2})
                    placed = True
        self.sync_biomes_to_grid()

        # 3. Procedural Weapon Placement (Always separated in different sectors)
        weapon_sectors = [
            (random.randint(6, mid_x - 2), random.randint(3, GRID_ROWS - 4)),
            (random.randint(mid_x + 2, GRID_COLS - 6), random.randint(3, GRID_ROWS - 4))
        ]
        random.shuffle(weapon_sectors)
        w_types = [GUN, SWORD]
        for w_type, (tx, ty) in zip(w_types, weapon_sectors):
            while self.grid.tiles[ty][tx] != EMPTY:
                tx = (tx + 1) % (GRID_COLS - 4) + 2
                ty = (ty + 1) % (GRID_ROWS - 4) + 2
            self.grid.set_tile(tx, ty, w_type)

        # 4. Traps (2 Spikes, 2 EMP Shocks)
        for t_type in [TRAP_SPIKE, TRAP_SPIKE, TRAP_STUN, TRAP_STUN]:
            placed = False
            attempts = 0
            while not placed and attempts < 40:
                attempts += 1
                tx = random.randint(3, GRID_COLS - 4)
                ty = random.randint(2, GRID_ROWS - 3)
                if self.grid.tiles[ty][tx] == EMPTY and (tx, ty) != (mid_x, mid_y):
                    self.grid.set_tile(tx, ty, t_type)
                    placed = True

        # Reset Joker position
        self.joker = JokerBrain(mid_x, mid_y)
        self.log.append(f"Architect re-forged the Sanctum! [Theme: {cluster_style.upper()}]")

    def sync_biomes_to_grid(self):
        for b in self.biomes:
            tile_type = AOE_ACID if b["type"] == "acid" else AOE_MAGMA
            for dy in range(b["h"]):
                for dx in range(b["w"]):
                    tx, ty = b["x"] + dx, b["y"] + dy
                    if self.grid.in_bounds(tx, ty) and self.grid.tiles[ty][tx] == EMPTY:
                        self.grid.set_tile(tx, ty, tile_type)

    def add_biome(self, root_x, root_y, b_type):
        if len(self.biomes) >= 2:
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

    def reset_round(self):
        for a in self.agents:
            a.alive = True
            a.combat_hp = 2
            a.trap_lives = 3
            a.is_wounded = False
            a.reset_to_spawn()
            a.ammo = 5
        self.editor_mode = True
        self.winner = None
        self.combat_active = False
        self.round_number += 1
        self.joker = JokerBrain(GRID_COLS // 2, GRID_ROWS // 2)
        self.dramatic_delay = 0
        self.log.append(f"Cycle {self.round_number} Edit Phase. Re-arm or Redesign the Sanctum.")

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

    def step(self):
        if self.winner or self.editor_mode:
            return

        self.recent_events = []
        self.grid.tick_smoke()
        self.magma_tick = (self.magma_tick + 1) % 3
        self.dramatic_delay = 0

        # 1. Step Joker Boss
        if self.joker.alive:
            j_tile = self.grid.tiles[self.joker.y][self.joker.x]
            if j_tile == TRAP_SPIKE or (j_tile == AOE_MAGMA and self.magma_tick == 0):
                self.joker.take_hit()
                self.log.append(f"HAZARD: Joker took environmental damage! (HP: {self.joker.lives})")
                self.recent_events.append({"type": "spike_hit", "x": self.joker.x, "y": self.joker.y})

            joker_event = self.joker.step(self.grid, self.agents)
            if joker_event:
                self.recent_events.append(joker_event)
                self.dramatic_delay = 2.2  # Generous reading pause for comical banter
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

        # 2. Step Operatives
        for agent in self.agents:
            if not agent.alive:
                continue

            if agent.stun_turns > 0:
                agent.stun_turns -= 1
                continue

            if agent.distracted_turns > 0:
                agent.distracted_turns -= 1
                continue

            current_tile = self.grid.tiles[agent.y][agent.x]
            if current_tile == AOE_MAGMA and self.magma_tick == 0:
                agent.take_trap_hit()
                self.log.append(f"BURST: {agent.algo_type} burned by magma! ({agent.trap_lives}/3 Trap Lifelines remaining)")
                self.recent_events.append({"type": "magma_blast", "x": agent.x, "y": agent.y})
                if not agent.alive:
                    self.log.append(f"{agent.algo_type} was consumed by molten magma!")
                    continue

            visible = self.visible_agents_for(agent)
            active_targets = visible if can_attack_rivals else []
            active_targets.sort(key=lambda v: abs(agent.x - v.x) + abs(agent.y - v.y))

            brain = self.brains[agent.algo_type]
            old_x, old_y = agent.x, agent.y

            if isinstance(brain, AStarBrain):
                action = brain.decide(agent, self.grid, active_targets, self.agents, self.joker)
            else:
                action = brain.decide(agent, self.grid, active_targets)

            # Proximity Combat Gate with Prioritized Targets & Dramatic Pauses
            if action == "shoot" and agent.armed and agent.ammo > 0:
                joker_in_range = self.joker.alive and self.can_target_joker(agent)
                dist_joker = self.distance_to_joker(agent) if self.joker.alive else 999

                closest_rival = active_targets[0] if active_targets else None
                dist_rival = (abs(agent.x - closest_rival.x) + abs(agent.y - closest_rival.y)) if closest_rival else 999

                attack_performed = False

                # Target Joker if closest threat within 2 grids
                if joker_in_range and (dist_joker <= dist_rival):
                    if self.is_backstab_angle(agent, self.joker):
                        agent.ammo -= 1
                        self.joker.alive = False
                        attack_performed = True
                        self.dramatic_delay = 3.2  # Slowed down for cinematic focus
                        self.log.append(f"ASSASSINATION! {agent.algo_type} eliminated Joker from {dist_joker} grid(s) away!")
                        self.recent_events.append({
                            "type": "joker_killed",
                            "shooter": {"x": agent.x, "y": agent.y},
                            "victim": {"x": self.joker.x, "y": self.joker.y}
                        })
                    else:
                        self.log.append(f"{agent.algo_type}'s strike glanced off Joker's front guard!")

                # Otherwise prioritize closest rival
                if not attack_performed and closest_rival and can_attack_rivals:
                    if self.is_adjacent(agent, closest_rival):
                        if self.is_backstab_angle(agent, closest_rival):
                            agent.ammo -= 1
                            attack_performed = True
                            if agent.weapon_type == "GUN":
                                closest_rival.take_combat_hit("GUN")
                                self.dramatic_delay = 3.4  # Slowed down execution
                                self.log.append(f"POINT-BLANK EXECUTION! {agent.algo_type} eliminated {closest_rival.algo_type} from behind!")
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
                                    self.dramatic_delay = 2.6  # Flesh wound adaptation pause
                                    self.log.append(f"ADJACENT STAB! {agent.algo_type} sliced {closest_rival.algo_type}! ({closest_rival.algo_type} survives with 1 HP)")
                                    self.recent_events.append({
                                        "type": "sword_stab",
                                        "shooter": {"x": agent.x, "y": agent.y},
                                        "victim": {"x": closest_rival.x, "y": closest_rival.y},
                                        "weapon": "SWORD",
                                        "fatal": False
                                    })
                                else:
                                    self.dramatic_delay = 3.4  # Fatal deathblow strike pause
                                    self.log.append(f"DEATHBLOW! {agent.algo_type} landed fatal adjacent stab on {closest_rival.algo_type}!")
                                    self.recent_events.append({
                                        "type": "sword_stab",
                                        "shooter": {"x": agent.x, "y": agent.y},
                                        "victim": {"x": closest_rival.x, "y": closest_rival.y},
                                        "weapon": "SWORD",
                                        "fatal": True
                                    })
                                    self.log.append(f"{closest_rival.algo_type} was ELIMINATED!")
                        else:
                            self.log.append(f"{agent.algo_type}'s strike was parried! {closest_rival.algo_type} faced head-on.")
                    else:
                        self.log.append(f"{agent.algo_type} held fire: Target out of reach!")

                # Secondary fallback if rival wasn't adjacent but Joker is in range
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
                            self.log.append(f"{agent.algo_type} hit Caltrop Spikes! ({agent.trap_lives}/3 Trap Lifelines remaining)")
                            self.recent_events.append({"type": "spike_hit", "x": nx, "y": ny})
                            if not agent.alive:
                                self.log.append(f"{agent.algo_type} succumbed to lethal trap spikes!")
                        elif t == TRAP_STUN:
                            agent.stun_turns = 2
                            self.grid.clear_tile(nx, ny)
                            self.log.append(f"{agent.algo_type} hit an EMP Shock Drone! (Stunned 2 turns)")
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

            if act == "set_tile":
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
                await broadcast()

            elif act == "remove_agent":
                agent_id = data.get("agent_id")
                if game.editor_mode:
                    for ag in game.agents:
                        if ag.id == agent_id:
                            ag.alive = False
                            ag.x, ag.y = -10, -10
                            break
                await broadcast()

            elif act == "set_speed":
                game.speed_multiplier = int(data.get("speed", 1))
                await broadcast()

            elif act == "clear_all":
                if game.editor_mode:
                    game.clear_grid_completely()
                await broadcast()

            elif act == "randomize_map":
                if game.editor_mode or game.winner:
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
        base_interval = 1.05  # More comfortable observation pacing
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