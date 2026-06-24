"""Headless smoke tests for the core simulation.

Run with: SDL_VIDEODRIVER=dummy python -m pytest tests/ -q
(pygame needs to be initialized, but no real window is opened.)
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
pygame.init()

from worms.terrain import Terrain          # noqa: E402
from worms.worm import Worm                # noqa: E402
from worms.projectile import Projectile    # noqa: E402
from worms.game import Game, AIM, GAME_OVER  # noqa: E402
from worms.config import WEAPONS           # noqa: E402


def test_terrain_destroy_clears_pixels():
    t = Terrain(200, 200)
    t.flat_ground(150)
    assert t.solid_at(100, 160)
    t.destroy(100, 160, 20)
    assert not t.solid_at(100, 160)          # crater center cleared
    assert t.solid_at(100, 199)              # far below still solid


def test_worm_falls_and_rests_on_ground():
    t = Terrain(200, 200)
    t.flat_ground(150)
    w = Worm(100, 40, 0, "t")
    for _ in range(400):
        w.update(t)
    assert w.on_ground
    assert 142 <= w.feet() <= 152            # resting on the surface (~150)


def test_projectile_flies_then_explodes_on_terrain():
    t = Terrain(400, 300)
    t.flat_ground(250)
    p = Projectile(40, 120, 6.0, -2.0, WEAPONS["bazooka"])
    event = pos = None
    for _ in range(600):
        event, pos = p.update(t, 0, 400, 300)
        if event:
            break
    assert event == "explode"
    assert pos[1] >= 240                     # detonated at/near the ground


def test_explosion_damages_nearby_worm():
    g = Game(300, 300)
    g.terrain.flat_ground(200)
    from worms.game import Team
    team = Team(0, (0, 0, 0), "T")
    worm = Worm(150, 190, 0, "x")
    team.worms.append(worm)
    g.teams = [team]
    before = worm.hp
    g.explode(150, 190, WEAPONS["bazooka"])
    assert worm.hp < before                  # took blast damage
    assert worm.hp <= before - 40            # near direct hit


def test_full_turn_cycle_and_win_condition():
    g = Game(640, 400)
    g.new_game(teams=2, worms_per_team=1, seed=7)
    assert g.state == AIM
    # Kill team 2's only worm -> team 1 should win.
    for w in g.teams[1].worms:
        w.drown()
    g.update()
    assert g.state == GAME_OVER
    assert g.winner is g.teams[0]


def test_drowning_below_water_line():
    g = Game(300, 300)
    g.new_game(teams=2, worms_per_team=1, seed=1)
    victim = g.teams[0].worms[0]
    victim.on_ground = False
    victim.y = g.water_line + 5
    g.update()
    assert not victim.alive
