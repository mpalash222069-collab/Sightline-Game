import random
from sightline_core import (
    DIRS, GUN, SWORD, TRAP_SPIKE, TRAP_STUN, AOE_ACID, AOE_MAGMA
)


class JokerMovementMixin:
    def find_prized_weapon(self, grid):
        for y in range(grid.rows):
            for x in range(grid.cols):
                if grid.tiles[y][x] == GUN:
                    return (x, y)
        for y in range(grid.rows):
            for x in range(grid.cols):
                if grid.tiles[y][x] == SWORD:
                    return (x, y)
        return (grid.cols // 2, grid.rows // 2)

    def is_safe_for_joker(self, nx, ny, grid):
        if not grid.is_walkable(nx, ny):
            return False
        tile = grid.tiles[ny][nx]
        if tile in (TRAP_SPIKE, TRAP_STUN, AOE_ACID, AOE_MAGMA, GUN, SWORD):
            return False
        return True

    def take_hit(self):
        self.lives -= 1
        if self.lives <= 0:
            self.alive = False

    def resolve_movement(self, target_dest, grid, agents):
        dx = 1 if target_dest[0] > self.x else (-1 if target_dest[0] < self.x else 0)
        dy = 1 if target_dest[1] > self.y else (-1 if target_dest[1] < self.y else 0)

        moves = []
        if dx != 0 and self.is_safe_for_joker(self.x + dx, self.y, grid):
            moves.append((dx, 0, "right" if dx > 0 else "left"))
        if dy != 0 and self.is_safe_for_joker(self.x, self.y + dy, grid):
            moves.append((0, dy, "down" if dy > 0 else "up"))

        if moves:
            mx, my, fac = random.choice(moves)
            nx, ny = self.x + mx, self.y + my
            occupied_agent = any(a.alive and a.x == nx and a.y == ny for a in agents)
            if not occupied_agent:
                self.x, self.y = nx, ny
                self.facing = fac
