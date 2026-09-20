import random

from sightline_core import Brain, DIRS, SWORD
from ga1 import GAEncodingMixin, manhattan


class GATrainingMixin:

    ga_population_size = 18
    ga_generations = 14
    ga_mutation_rate = 0.15
    ga_elite_fraction = 0.5

    def _random_genome(self):
        return [random.randrange(len(self._MOVE_LIST)) for _ in range(self.GA_GENOME_LENGTH)]

    def _crossover(self, g1, g2):
        if self.GA_GENOME_LENGTH < 2:
            return list(g1)
        point = random.randrange(1, self.GA_GENOME_LENGTH)
        return g1[:point] + g2[point:]

    def _mutate(self, genome):
        return [
            random.randrange(len(self._MOVE_LIST)) if random.random() < self.ga_mutation_rate else gene
            for gene in genome
        ]

    def genetic_algorithm_search(self, start, goal, grid, joker_pos=None, joker_alive=True):
        if start == goal:
            return []

        population = [self._random_genome() for _ in range(self.ga_population_size)]
        elite_count = max(2, int(self.ga_population_size * self.ga_elite_fraction))

        best_genome = None
        best_score = float('inf')

        for _ in range(self.ga_generations):
            scored = [
                (self._fitness(g, start, goal, grid, joker_pos, joker_alive), g)
                for g in population
            ]
            scored.sort(key=lambda pair: pair[0])
            self.nodes_expanded += len(population)

            if scored[0][0] < best_score:
                best_score = scored[0][0]
                best_genome = scored[0][1]

            survivors = [g for _, g in scored[:elite_count]]

            children = []
            while len(survivors) + len(children) < self.ga_population_size:
                parent_a = random.choice(survivors)
                parent_b = random.choice(survivors)
                children.append(self._mutate(self._crossover(parent_a, parent_b)))

            population = survivors + children

        if best_genome is None:
            return []
        return self._simulate_genome(best_genome, start, goal, grid)


class GABrain(Brain, GAEncodingMixin, GATrainingMixin):
    def __init__(self):
        self.current_path = []
        self.last_target = None
        self.nodes_expanded = 0
        self.dialogue = "Evolving a route..."
        self.swap_cooldown = 0
        self.last_target_id = None

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

        shot = self.check_immediate_shot(
            agent, joker_alive, joker_pos, joker_facing, dist_to_joker, closest_rival, closest_rival_dist
        )
        if shot:
            return shot

        action_type, target_pos = self.evaluate_optimal_target(agent, grid, all_agents, joker)

        if action_type == "UPGRADE_GUN":
            drop_pos = self.find_empty_adjacent_tile(agent, grid)
            if drop_pos:
                grid.set_tile(drop_pos[0], drop_pos[1], SWORD)
                agent.armed = False
                agent.weapon_type = None
                self.current_path = []
                self.last_target = None
            else:
                action_type, target_pos = ("HUNT_AGENT", target_pos)

        if not target_pos:
            target_pos = (grid.cols // 2, grid.rows // 2)

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
            self.current_path = self.genetic_algorithm_search(pos, target_pos, grid, joker_pos, joker_alive)

        if self.current_path:
            next_step = self.current_path.pop(0)
            for act, (dx, dy) in DIRS.items():
                if (agent.x + dx, agent.y + dy) == next_step:
                    return act

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
