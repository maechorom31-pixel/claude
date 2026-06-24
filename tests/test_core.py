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
from worms.rope import NinjaRope           # noqa: E402
from worms.entities import Sheep, Mine, OilDrum, Crate  # noqa: E402
from worms.game import Game, Team, AIM, BUSY, GAME_OVER  # noqa: E402
from worms.config import WEAPONS, WEAPON_ORDER  # noqa: E402


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
    g.detonate(150, 190, WEAPONS["bazooka"])
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


# --- new systems -----------------------------------------------------------
def test_ninja_rope_attaches_to_ceiling_and_misses_open_sky():
    import pygame as _pg
    # Open sky above the worm: a straight-up shot finds nothing.
    t = Terrain(300, 300)
    t.flat_ground(250)
    w = Worm(150, 200, 0, "x")
    assert NinjaRope.fire(w, 90, t) is None

    # Ceiling slab above the worm: a straight-up shot grapples it.
    t2 = Terrain(300, 300)
    _pg.draw.rect(t2.surface, (130, 95, 60, 255), (0, 0, 300, 60))
    t2._rebuild_mask()
    w2 = Worm(150, 200, 0, "x")
    rope = NinjaRope.fire(w2, 90, t2)
    assert rope is not None
    assert rope.length > 0
    assert t2.solid_at(rope.ax, rope.ay)


def test_rope_swing_changes_velocity_and_release():
    t = Terrain(300, 300)
    import pygame as _pg
    _pg.draw.rect(t.surface, (130, 95, 60, 255), (0, 0, 300, 50))
    t._rebuild_mask()
    w = Worm(150, 200, 0, "x")
    rope = NinjaRope.fire(w, 90, t)
    assert rope is not None
    rope.swing(1)
    assert w.vx > 0
    for _ in range(30):
        rope.update(t)
    # worm stays within rope length of the anchor
    import math
    assert math.hypot(w.x - rope.ax, w.y - rope.ay) <= rope.length + 1.5


def test_sheep_walks_and_explodes():
    t = Terrain(300, 200)
    t.flat_ground(150)
    s = Sheep(50, 145, 1, fuse_seconds=0.2)  # ~12 frames
    exploded = False
    start_x = s.x
    for _ in range(20):
        if s.update(t):
            exploded = True
            break
    assert exploded
    assert s.x > start_x            # it moved forward


def test_cluster_bomb_spawns_children():
    g = Game(400, 300)
    g.terrain.flat_ground(200)
    g.teams = [Team(0, (0, 0, 0), "T")]
    g.teams[0].worms.append(Worm(380, 190, 0, "z"))  # far from blast
    g.detonate(100, 150, WEAPONS["cluster"])
    assert len(g.projectiles) == WEAPONS["cluster"]["clusters"]


def test_oil_drum_chain_reaction():
    g = Game(400, 300)
    g.terrain.flat_ground(200)
    g.teams = [Team(0, (0, 0, 0), "T")]
    g.teams[0].worms.append(Worm(390, 190, 0, "z"))
    drum = OilDrum(120, 190)
    g.drums = [drum]
    g.detonate(110, 190, WEAPONS["dynamite"])  # near drum -> destroys it -> chain
    assert not drum.alive


def test_supply_crate_heals_worm():
    g = Game(400, 300)
    g.new_game(teams=2, worms_per_team=1, seed=3)
    worm = g.teams[0].worms[0]
    worm.hp = 40
    g.crates.append(Crate(worm.x, worm.y, heal=30))
    g.update()
    assert worm.hp >= 70
    assert len(g.crates) == 0


def test_sudden_death_triggers_and_caps_hp():
    g = Game(400, 300)
    g.new_game(teams=2, worms_per_team=1, seed=5)
    # Fast-forward many turns until sudden death is reached.
    for _ in range(200):
        if g.sudden_death:
            break
        g.timer = 1
        g.update()
    assert g.sudden_death
    for w in g.all_worms():
        if w.alive:
            assert w.hp <= 1


def test_ai_chooses_nearest_enemy():
    from worms.ai import choose_target
    g = Game(640, 400)
    g.new_game(teams=2, worms_per_team=1, seed=2, ai_teams={1})
    shooter = g.teams[1].worms[0]
    target = choose_target(g, shooter)
    assert target is not None
    assert target.team_idx != shooter.team_idx


def test_ai_best_shot_lands_near_target_on_flat_ground():
    from worms.ai import best_shot
    from worms.game import Team
    g = Game(800, 400)
    g.terrain.flat_ground(300)
    g.wind = 0
    shooter = Worm(120, 290, 1, "cpu")
    target = Worm(600, 290, 0, "you")
    g.teams = [Team(0, (0, 0, 0), "you"), Team(1, (0, 0, 0), "cpu", is_ai=True)]
    g.teams[0].worms.append(target)
    g.teams[1].worms.append(shooter)
    plan = best_shot(g, shooter, target)
    assert plan is not None
    assert plan["facing"] == 1
    assert plan["dist"] <= 40          # simulated blast lands close to the target


def test_ai_takes_its_turn():
    from worms.ai import AIController
    g = Game(800, 400)
    g.new_game(teams=2, worms_per_team=1, seed=4, ai_teams={1})
    # Make team 1 (CPU) the active team.
    while not g.current_team().is_ai:
        g.timer = 1
        g.update()
    ai = AIController(seed=1, think_frames=0)
    ai.update(g)
    assert g.fired                     # the CPU committed a shot
    assert g.state == BUSY


def test_all_weapons_fire_without_error():
    for wid in WEAPON_ORDER:
        g = Game(640, 400)
        g.new_game(teams=2, worms_per_team=1, seed=11)
        g.select_weapon(wid)
        g.aim_angle = 35
        g.power = 80
        g.fire()
        assert g.state in (BUSY,)  # turn consumed
        for _ in range(400):       # let the shot fully resolve
            g.update()
            if g.state in (AIM, GAME_OVER):
                break
