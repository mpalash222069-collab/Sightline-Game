"""
Sightline — Core Engine (Fixed In-Place Damage)
"""

EMPTY = "EMPTY"
WALL = "WALL"
SMOKE = "SMOKE"
GUN = "GUN"
SWORD = "SWORD"
TRAP_SPIKE = "TRAP_SPIKE"
TRAP_STUN = "TRAP_STUN"
AOE_ACID = "AOE_ACID"
AOE_MAGMA = "AOE_MAGMA"
WEAPON = GUN

DIRS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

VALID_ACTIONS = {"up", "down", "left", "right", "shoot", "stay"}

class Grid:
    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.tiles = [[EMPTY for _ in range(cols)] for _ in range(rows)]
        self.smoke_timer = {}

    def in_bounds(self, x, y):
        return 0 <= x < self.cols and 0 <= y < self.rows

    def is_walkable(self, x, y):
        return self.in_bounds(x, y) and self.tiles[y][x] != WALL

    def line_of_sight(self, x, y, direction, max_range=None):
        dx, dy = DIRS[direction]
        visible = []
        cx, cy = x + dx, y + dy
        steps = 0
        while self.in_bounds(cx, cy):
            if self.tiles[cy][cx] in (WALL, SMOKE):
                break
            visible.append((cx, cy))
            cx += dx
            cy += dy
            steps += 1
            if max_range and steps >= max_range:
                break
        return visible

    def set_tile(self, x, y, tile_type, smoke_duration=5):
        if not self.in_bounds(x, y):
            return
        self.tiles[y][x] = tile_type
        if tile_type == SMOKE:
            self.smoke_timer[(x, y)] = smoke_duration

    def clear_tile(self, x, y):
        if self.in_bounds(x, y):
            self.tiles[y][x] = EMPTY
            self.smoke_timer.pop((x, y), None)

    def tick_smoke(self):
        expired = []
        for pos, remaining in self.smoke_timer.items():
            remaining -= 1
            if remaining <= 0:
                expired.append(pos)
            else:
                self.smoke_timer[pos] = remaining
        for (x, y) in expired:
            self.clear_tile(x, y)

class Agent:
    def __init__(self, agent_id, name, algo_type, x, y, spawn):
        self.id = agent_id
        self.name = name
        self.algo_type = algo_type
        self.x, self.y = x, y
        self.spawn = spawn
        self.facing = "down"
        self.armed = False
        self.weapon_type = None  # "GUN" or "SWORD"
        # Combat health: 2 HP (1 gunshot kills immediately, 2 sword stabs kill)
        self.combat_hp = 2
        # Environmental lifelines: 3 lives strictly for traps and dangerous areas
        self.trap_lives = 3
        self.is_wounded = False
        self.ammo = 5
        self.alive = True
        self.stun_turns = 0
        self.distracted_turns = 0

    @property
    def lives(self):
        return self.combat_hp

    @lives.setter
    def lives(self, val):
        self.combat_hp = val

    def reset_to_spawn(self):
        self.x, self.y = self.spawn
        self.armed = False
        self.weapon_type = None
        self.stun_turns = 0
        self.distracted_turns = 0
        self.is_wounded = False

    def take_combat_hit(self, weapon_type="SWORD"):
        """Combat damage: 1 shot = 2 dmg (instant kill), 1 stab = 1 dmg (survives & adapts), 2 stabs = death.
        Never reverts back to spawn; adapts in-place."""
        if weapon_type == "GUN":
            self.combat_hp = 0
            self.alive = False
        else:  # SWORD
            self.combat_hp -= 1
            if self.combat_hp <= 0:
                self.alive = False
            else:
                self.is_wounded = True

    def take_trap_hit(self):
        """Environmental damage: Uses one of 3 lifelines reserved strictly for traps/hazards."""
        self.trap_lives -= 1
        if self.trap_lives <= 0:
            self.alive = False

    def take_hit(self, lethal_reset=False):
        """Backwards-compatible hit decrement without teleporting."""
        self.take_trap_hit()

class Brain:
    def decide(self, agent, grid, visible_agents):
        raise NotImplementedError

class RandomBrain(Brain):
    def decide(self, agent, grid, visible_agents):
        import random
        if visible_agents and agent.armed and agent.ammo > 0:
            return "shoot"
        return random.choice(["up", "down", "left", "right", "stay"])