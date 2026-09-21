# Sightline

**AI Lab Project — CSE 3812 / CSI 342, Artificial Intelligence Laboratory**
**Track:** Algorithm-Based Project

A grid-based game where three AI-controlled agents — one powered by
**A\* Search**, one by **Simulated Annealing**, and one by a **Genetic
Algorithm** — race for weapons, avoid ambushes, and fight for survival
on a battlefield the player actively designs. Same map, same rules,
three fundamentally different ways of deciding what to do next.

---

## The Game

The player never controls an agent directly — they're the **architect**,
not a fighter. Each round, the player places weapons, walls, traps, and
smoke, then watches the three AI "brains" navigate the consequences.

### Phase 1 — The Weapon Race
- All three agents start unarmed at their spawn points.
- The player places exactly 3 weapons on the grid before the round begins.
- An armed agent that reaches an unarmed one costs that agent a life and
  resets it to its spawn point.
- An agent that loses all 3 lives while still unarmed is eliminated
  immediately.
- Phase 1 ends once every surviving agent is armed.

### Phase 2 — The Armed Standoff
- **Line of sight** is a ray-cast in an agent's facing direction, blocked
  by the first wall or smoke tile it hits.
- Two agents facing **opposite** directions (approaching each other) pass
  with no shot.
- If one agent sees another **in front of it, facing the same direction**
  (an ambush — trailing behind, not approaching), it may shoot.
- Each agent has **5 shots total for the whole game** — not per round.
- **3 shared lives** per agent, covering both phases.
- A round ends the instant any agent is shot. Positions stay; only the
  environment (walls/traps/smoke) resets between rounds.
- **Traps** reveal a rough directional hint (not an exact location) to
  the other agents for a few turns when triggered.
- The game ends when only one agent remains standing.

### The Three Brains

| Agent | Algorithm | Personality |
|---|---|---|
| **A\*** | A* Search | *The Predictable Hunter* — always takes the shortest path, no risk-awareness. Efficient, but exploitable. |
| **SA** | Simulated Annealing | *The Cautious Opportunist* — balances distance against exposure risk; explores early, settles into safer routes as it "cools." |
| **GA** | Genetic Algorithm | *The Evolved Strategist* — trained across generations of simulated self-play before ever facing the player. |

---

## Comparative Analysis

Every rubric evaluation criterion maps to a concrete, logged metric:

| Criterion | A\* (baseline) | Simulated Annealing | Genetic Algorithm |
|---|---|---|---|
| Execution time | Decision time per replan | Decision time per turn | Decision time per turn (post-training) |
| Solution quality | Path optimality | Survival time, escape success | Elimination count, survival rate |
| Efficiency | Nodes expanded ÷ path length | Cost-function evaluations | Generations to fitness plateau |
| Convergence | Nodes expanded per replan, across a round | Cost value decreasing within a round | Fitness improving across training generations |

---

## Repository Structure

```
sightline_core.py        Shared contract — Grid, Agent, Brain interface.
                          Every algorithm and the frontend import from this file.
sightline_engine.py       Game engine — Phase 1/2 rules, combat, lives, ammo, traps.
sightline_frontend.py    Pygame rendering + player map editor.
test_your_brain.py       Standalone Brain tester — validate an algorithm with no pygame needed.

sa_costfunction.py       SA — cost function (distance + exposure risk).
sa_annealing.py          SA — annealing search + live decision integration.

astar_brain.py            A* — pathfinding, replanning, nodes-expanded metric.        [ in progress ]
ga_encoding.py             GA — genome encoding + fitness function.                     [ in progress ]
ga_training.py             GA — selection, crossover, mutation, self-play training.     [ in progress ]
```

---

## Team & Contributions

| Member | Branch | Owns | Status |
|---|---|---|---|
| [Name] | `main` (shared) | Framework — `sightline_core.py`, `sightline_engine.py` | ✅ Built & tested |
| [Name] | `main` (shared) | Frontend — `sightline_frontend.py`, map editor, visual theme | ✅ Built & tested |
| [Name] | `sa_costfunction_<id>` | SA Dev 1 — cost function (distance + exposure risk) | ✅ Built & tested |
| [Name] | `sa_annealing_<id>` | SA Dev 2 — annealing search + live integration | ✅ Built & tested |
| Md. Rayhan Islam Showrav | `astar_<id>` | A\* Developer — pathfinding, replanning, metrics | ⏳ In progress |
| [Name] | `ga_encoding_<id>` | GA Dev 1 — genome encoding, fitness function | ⏳ In progress |
| [Name] | `ga_training_<id>` | GA Dev 2 — selection, crossover, mutation, training loop | ⏳ In progress |

*(Replace `[Name]` with actual team member names as branches land.)*

### Simulated Annealing — what's already validated

- Stress-tested across 30 random seeds: **0 failures**, ~13.5 turns
  average to reach a goal.
- Full 3-agent engine simulation confirms correct arming, hunting,
  ambushing, and survival behavior.
- Two real bugs were caught and fixed during testing — see the
  docstrings in `sa_annealing.py` and `sa_costfunction.py` for details
  (returning the wrong search result, and a risk-weight imbalance that
  caused permanent stalling). Worth reading before tuning either file
  further.

---

## Running the Game

```bash
pip install pygame
python sightline_frontend.py
```

- **Editor mode:** click tiles to place weapons/walls/traps/smoke
  (keys `1`–`4` to switch tool), `Enter` to start the round.
- **Auto-play mode:** turns advance automatically; `Space` to pause,
  `R` to return to the editor.

## Testing an Algorithm Standalone

```bash
python test_your_brain.py
```

Edit the `CONFIG` section at the top of that file to point at your own
`Brain` subclass. No pygame or other teammates' code required.

---

## Git Workflow

- `sightline_core.py` is the single source of truth for `Grid`, `Agent`,
  and `Brain` — nobody redefines these elsewhere.
- One branch per algorithm piece (see table above). Pull Requests into
  `main`, reviewed by at least one teammate outside the pair, before
  merging.
- Branch naming avoids numeric-only names per course requirements
  (e.g. `astar_2021304`, not just `2021304`).
