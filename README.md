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
as for changing names of file and constant updating we will upload this part at the end of the project
```


## Team & Contributions

| Member | Branch | Owns | Status |
|---|---|---|---|
| Abdullah Zabir Elhan, Syed Tazammul Haque Tazeem| `main` (shared) | Framework — `sightline_core.py`, `sightline_engine.py` | 
| Md. Rayhan Islam Showrav | `main` (shared) | Frontend — `index.html` using PIXI js, map editor, visual theme, UI | 
| Abdullah Zabir Elhan | SA Dev 1
| Syed Tazammul Haque Tazeem  | SA Dev 2  
| Md. Rayhan Islam Showrav | `astar_0112230810` | A\* Developer — pathfinding, replanning, metrics | 
| Ziaul Islam Palash | `GA-1<011222069>` | GA Dev 1 — genome encoding, fitness function |
| Sadia Islam Prova  | `ga_training_<id>` | GA Dev 2 — selection, crossover, mutation, training loop |
| Ziaul Islam Palash, Sadia Islam Prova | Game testing. i.e if any redesign or any problem arrives the redesign is needed they will announce it | in progress......

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
