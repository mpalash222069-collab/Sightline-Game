import random
from joker_movement import JokerMovementMixin

JOKER_BANTERS = [
    ("HA-HA! Freeze, hero!", "Calculating detour..."),
    ("Bananas are radioactive! Fun fact!", "Unnecessary cost penalty detected."),
    ("Rifle is MINE! Finders keepers!", "Re-evaluating target priority."),
    ("Dance with me, pathfinder!", "Distance violation detected."),
    ("Why so serious?", "Heuristics prioritize your demise."),
    ("Can you calculate this chaos?!", "Deterministic prediction failure."),
    ("Catch me if you can!", "Pursuit vectors optimized.")
]


class JokerBehaviorMixin:
    def decide_target(self, grid, agents):
        living = [a for a in agents if a.alive and not a.armed]
        armed_hunter = next((a for a in agents if a.alive and a.armed and a.weapon_type == "GUN"), None)
        nearest_agent = None
        min_dist = 999

        for a in living:
            d = abs(a.x - self.target_weapon[0]) + abs(a.y - self.target_weapon[1])
            if d < min_dist:
                min_dist = d
                nearest_agent = a

        target_dest = self.target_weapon
        event = None

        if armed_hunter:
            self.mode = "EVADE"
            self.dialogue = "Whoa! Put the gun down!"
            dx = 1 if armed_hunter.x < self.x else -1
            dy = 1 if armed_hunter.y < self.y else -1
            target_dest = (max(2, min(grid.cols - 3, self.x + dx * 2)),
                           max(2, min(grid.rows - 3, self.y + dy * 2)))
        elif nearest_agent and min_dist <= 7:
            agent_dist = abs(nearest_agent.x - self.x) + abs(nearest_agent.y - self.y)
            if agent_dist <= 2 and self.confront_cooldown <= 0:
                self.mode = "HERD"
                j_line, a_line = random.choice(JOKER_BANTERS)
                self.dialogue = j_line
                self.confront_cooldown = 10
                nearest_agent.distracted_turns = 1
                event = {
                    "type": "joker_taunt",
                    "x": self.x,
                    "y": self.y,
                    "agent_id": nearest_agent.id,
                    "agent_reply": a_line,
                    "joker_line": j_line
                }
                target_dest = (nearest_agent.x, nearest_agent.y)
            else:
                self.mode = "INTERCEPT"
                mid_x = (self.target_weapon[0] + nearest_agent.x) // 2
                mid_y = (self.target_weapon[1] + nearest_agent.y) // 2
                target_dest = (mid_x, mid_y)
        else:
            self.mode = "GUARD"
            target_dest = self.target_weapon

        return target_dest, event


class JokerBrain(JokerMovementMixin, JokerBehaviorMixin):
    def __init__(self, x=16, y=7):
        self.x = x
        self.y = y
        self.facing = "down"
        self.mode = "GUARD"
        self.target_weapon = None
        self.alive = True
        self.lives = 3
        self.dialogue = ""
        self.confront_cooldown = 0

    def step(self, grid, agents):
        if not self.alive:
            return None

        if self.confront_cooldown > 0:
            self.confront_cooldown -= 1

        self.target_weapon = self.find_prized_weapon(grid)
        target_dest, event = self.decide_target(grid, agents)
        self.resolve_movement(target_dest, grid, agents)

        return event
