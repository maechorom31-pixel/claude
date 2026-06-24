# Worms MVP

A turn-based 2D artillery game in the style of *Worms* — destructible terrain,
parabolic aiming with wind, and per-turn team combat. Built with Python + Pygame.

This repo currently implements **Milestone M1 (playable core loop)** plus a
bonus grenade. See [`docs/worms-game-design.md`](docs/worms-game-design.md) for
the full game design document and roadmap (M1–M4).

## Run

```bash
pip install -r requirements.txt
python main.py                 # 2 teams x 3 worms
python main.py --teams 3 --worms 4 --seed 42
```

## Controls

| Key | Action |
|-----|--------|
| ← / → | walk |
| ↑ / ↓ | aim angle |
| Space (hold) | charge power, release to fire |
| Enter | jump |
| 1 / 2 / Tab | select weapon (Bazooka / Grenade) |
| R | restart (after game over) |
| Esc | quit |

## What's implemented (M1)

- **Destructible terrain** — pixel-mask terrain; explosions carve craters.
- **Worm physics** — gravity, walking up slopes, jumping, knockback, fall damage.
- **Turn manager** — round-robin teams, 45 s turn timer, post-shot retreat window.
- **Weapons** — Bazooka (wind-affected, impact detonation) and Grenade (fuse + bounce).
- **Aiming** — angle + charge-to-power launch with a parabolic trajectory.
- **Hazards** — falling into the water below the water line is instant death.
- **Win condition** — last team with a living worm wins.
- **HUD** — active team/worm/HP, wind indicator, turn timer, weapon, power gauge.

## Project layout

```
main.py              # entry point + input loop
worms/
  config.py          # constants + data-driven weapon definitions
  terrain.py         # destructible pixel-mask terrain
  worm.py            # worm entity + movement physics
  projectile.py      # projectile flight, bounce, fuse
  game.py            # game state + turn/state machine + explosions
  render.py          # all drawing (reads state, never mutates)
tests/
  test_core.py       # headless smoke tests for the simulation
docs/
  worms-game-design.md
```

## Tests

```bash
SDL_VIDEODRIVER=dummy python -m pytest tests/ -q
```

The tests run headless (no window) and cover terrain destruction, worm
gravity/landing, projectile flight, blast damage, the turn/win cycle and drowning.

## Roadmap

Next milestones from the GDD: more MVP weapons (shotgun, dynamite, melee),
supply crates / mines / oil drums, sudden death, particles & sound (M2–M3),
and optional networked multiplayer (M4).
