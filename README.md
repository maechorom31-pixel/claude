# Worms MVP

A turn-based 2D artillery game in the style of *Worms* — destructible terrain,
parabolic aiming with wind, and per-turn team combat. Built with Python + Pygame.

This repo implements **Milestones M1–M3**: the playable core loop, a full
nine-weapon arsenal, the **Ninja Rope** swing tool, environmental hazards,
sudden death, and visual juice (particles + screen shake). See
[`docs/worms-game-design.md`](docs/worms-game-design.md) for the design doc and
the M4 roadmap.

## Run

```bash
pip install -r requirements.txt
python main.py                 # 2 teams x 3 worms
python main.py --teams 3 --worms 4 --seed 42
```

## Controls

| Key | Action |
|-----|--------|
| ← / → | walk *(swing while on the rope)* |
| ↑ / ↓ | aim angle *(reel rope in / out)* |
| Space (hold) | charge power, release to fire *(release rope)* |
| Enter | jump |
| **F** | **fire / release the ninja rope** |
| 1–9 / Tab | select weapon |
| R | restart (after game over) |
| Esc | quit |

### Weapons

| # | Weapon | Behaviour |
|---|--------|-----------|
| 1 | Bazooka | wind-affected arc, impact detonation |
| 2 | Grenade | fuse + bounce |
| 3 | Cluster Bomb | bursts into 5 sub-bomblets |
| 4 | Shotgun | instant hitscan ray |
| 5 | Dynamite | dropped, 4 s fuse, big blast (run away!) |
| 6 | Fire Punch | short-range melee with heavy knockback |
| 7 | Sheep | walks forward, then explodes |
| 8 | Air Strike | missile salvo from the sky |
| 9 | Holy Hand Grenade | massive blast |

## Ninja Rope (the centerpiece)

Press **F** to fire a grapple along your aim line; it anchors to the first
terrain it hits. While attached you hang as a pendulum — **← →** add swing,
**↑ ↓** reel in/out, and releasing (**F**/**Space**) keeps all your momentum,
so a well-timed release launches you across the map. Using the rope does **not**
end your turn, so you can rope into position and *then* fire.

## What's implemented

- **Destructible terrain** — pixel-mask terrain; explosions carve craters.
- **Worm physics** — gravity, slope walking, jumping, knockback, fall damage, drowning.
- **Ninja Rope** — grapple + pendulum swing + reel + momentum release.
- **9 weapons** across projectile / hitscan / placed / melee / sheep / airstrike modes,
  with cluster splits and chain reactions.
- **Environment** — proximity mines, explosive oil drums (chain reactions),
  parachuting health supply crates.
- **Sudden death** — after N rounds, worm HP is capped to 1 and the water rises each turn.
- **Turn manager** — round-robin teams, 45 s timer, post-shot retreat window, win check.
- **Juice** — explosion particles and screen shake.
- **HUD** — team/worm/HP, wind, timer, weapon list, power gauge, rope hints.

## Project layout

```
main.py              # entry point + input loop
worms/
  config.py          # constants + data-driven weapon definitions
  terrain.py         # destructible pixel-mask terrain
  worm.py            # worm entity + movement physics
  projectile.py      # projectile flight, bounce, fuse
  rope.py            # ninja rope grapple + pendulum physics
  entities.py        # sheep, dynamite, mines, oil drums, supply crates
  particles.py       # particle system + screen shake
  game.py            # game state, turn machine, firing dispatch, detonations
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

14 headless tests cover terrain destruction, worm physics, projectile flight,
blast damage, the rope (attach + swing constraint), sheep, cluster splits, oil
drum chains, supply crates, sudden death, the turn/win cycle, and firing every
weapon end-to-end.

## Roadmap (M4)

Optional next steps: networked multiplayer (deterministic lockstep), replays,
a map editor, single-player AI bots, and sound effects.
