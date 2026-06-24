"""Game state and turn manager — the rules engine tying everything together.

State machine per turn:
    AIM     -> active worm may move / aim / use the ninja rope / charge a shot
    BUSY    -> the worm's ordnance is resolving (projectiles/sheep/bombs live)
    RETREAT -> post-shot movement window; ends once timer hits 0 and world settles
    GAME_OVER

The main loop feeds input via the public command methods and calls update()
once per frame; rendering reads the public attributes.
"""

import math
import random

from worms.config import (
    WEAPONS, WEAPON_ORDER, CLUSTER_CHILD, AIRSTRIKE_MISSILE, OILDRUM_BLAST,
    TEAM_COLORS, WATER_OFFSET, WIND_RANGE, MAX_SHOT_SPEED, CHARGE_RATE, AIM_RATE,
    TURN_TIME_FRAMES, RETREAT_FRAMES, MINE_COUNT, MINE_TRIGGER, MINE_FUSE,
    OILDRUM_COUNT, CRATE_EVERY, CRATE_HEAL, SUDDEN_DEATH_ROUND, WATER_RISE,
)
from worms.terrain import Terrain
from worms.worm import Worm
from worms.projectile import Projectile
from worms.rope import NinjaRope
from worms.entities import Sheep, TimedBomb, Mine, OilDrum, Crate
from worms.particles import ParticleSystem, ScreenShake

AIM = "aim"
BUSY = "busy"
RETREAT = "retreat"
GAME_OVER = "over"

_EXPLOSION_COLORS = [(255, 220, 120), (255, 170, 60), (230, 90, 40), (90, 90, 90)]


class Team:
    def __init__(self, idx, color, name, is_ai=False):
        self.idx = idx
        self.color = color
        self.name = name
        self.is_ai = is_ai
        self.worms = []
        self.active = -1

    def alive_worms(self):
        return [w for w in self.worms if w.alive]

    def advance_worm(self):
        n = len(self.worms)
        for i in range(1, n + 1):
            j = (self.active + i) % n
            if self.worms[j].alive:
                self.active = j
                return


class Game:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.state = GAME_OVER
        self.teams = []
        self.terrain = Terrain(width, height)
        self.water_line = height - WATER_OFFSET
        self.rng = random.Random()
        self.particles = ParticleSystem()
        self.shake = ScreenShake()
        self._reset_runtime()

    def _reset_runtime(self):
        self.projectiles = []
        self.sheep = []
        self.bombs = []
        self.mines = []
        self.drums = []
        self.crates = []
        self.rope = None
        self.weapon = "bazooka"
        self.wind = 0
        self.power = 0.0
        self.aim_angle = 45.0
        self.fired = False
        self.timer = 0
        self.turn_team = -1
        self.turns_taken = 0
        self.sudden_death = False
        self.winner = None

    # --- setup -------------------------------------------------------------
    def new_game(self, teams=2, worms_per_team=3, seed=None, ai_teams=None):
        self.rng = random.Random(seed)
        self.terrain = Terrain(self.width, self.height)
        self.terrain.generate(self.rng.randint(0, 10 ** 6))
        self.water_line = self.height - WATER_OFFSET
        self.particles = ParticleSystem()
        self.shake = ScreenShake()
        self._reset_runtime()

        ai_teams = set(ai_teams or ())
        self.teams = []
        slots = teams * worms_per_team
        spacing = self.width // (slots + 1)
        slot = 1
        for ti in range(teams):
            is_ai = ti in ai_teams
            label = f"Team {ti + 1}" + (" [CPU]" if is_ai else "")
            team = Team(ti, TEAM_COLORS[ti % len(TEAM_COLORS)], label, is_ai=is_ai)
            for wi in range(worms_per_team):
                x = spacing * slot
                slot += 1
                y = self.terrain.surface_y(x) - 12
                team.worms.append(Worm(x, y, ti, f"{ti + 1}-{wi + 1}"))
            self.teams.append(team)

        self._spawn_world_objects()
        self.start_turn()

    def _spawn_world_objects(self):
        for _ in range(MINE_COUNT):
            x = self.rng.randint(40, self.width - 40)
            y = self.terrain.surface_y(x) - 4
            if y < self.water_line:
                self.mines.append(Mine(x, y, MINE_TRIGGER, MINE_FUSE))
        for _ in range(OILDRUM_COUNT):
            x = self.rng.randint(40, self.width - 40)
            y = self.terrain.surface_y(x) - OilDrum.RADIUS
            if y < self.water_line:
                self.drums.append(OilDrum(x, y))

    # --- turn flow ---------------------------------------------------------
    def start_turn(self):
        self.turns_taken += 1
        for _ in range(len(self.teams)):
            self.turn_team = (self.turn_team + 1) % len(self.teams)
            team = self.teams[self.turn_team]
            if team.alive_worms():
                team.advance_worm()
                break

        # Sudden death bookkeeping.
        n = max(1, len(self.teams))
        round_no = (self.turns_taken - 1) // n
        if round_no >= SUDDEN_DEATH_ROUND and not self.sudden_death:
            self._trigger_sudden_death()
        if self.sudden_death:
            self.water_line = max(self.height // 3, self.water_line - WATER_RISE)

        # Periodic supply crate from the sky.
        if self.turns_taken % CRATE_EVERY == 0:
            cx = self.rng.randint(40, self.width - 40)
            self.crates.append(Crate(cx, -10, CRATE_HEAL))

        self.rope = None
        self.wind = self.rng.randint(-WIND_RANGE, WIND_RANGE)
        self.power = 0.0
        self.aim_angle = 45.0
        self.fired = False
        self.timer = TURN_TIME_FRAMES
        self.state = AIM

    def _trigger_sudden_death(self):
        self.sudden_death = True
        for w in self.all_worms():
            if w.alive:
                w.hp = min(w.hp, 1)

    def end_turn(self):
        if self.alive_team_count() <= 1:
            self._finish()
            return
        self.start_turn()

    def _finish(self):
        self.state = GAME_OVER
        self.rope = None
        alive = [t for t in self.teams if t.alive_worms()]
        self.winner = alive[0] if alive else None

    # --- queries -----------------------------------------------------------
    def all_worms(self):
        return [w for t in self.teams for w in t.worms]

    def alive_team_count(self):
        return sum(1 for t in self.teams if t.alive_worms())

    def current_worm(self):
        if not self.teams:
            return None
        team = self.teams[self.turn_team]
        if 0 <= team.active < len(team.worms):
            w = team.worms[team.active]
            return w if w.alive else None
        return None

    def current_team(self):
        return self.teams[self.turn_team] if self.teams else None

    def ordnance_active(self):
        return bool(self.projectiles or self.sheep or self.bombs)

    def settled(self):
        worms_ok = all(w.on_ground or not w.alive for w in self.all_worms())
        mines_ok = not any(m.armed for m in self.mines)
        return worms_ok and mines_ok and not self.ordnance_active()

    # --- player commands ---------------------------------------------------
    def can_control(self):
        return self.state in (AIM, RETREAT) and self.current_worm() is not None

    def walk(self, direction):
        if self.can_control() and self.rope is None:
            self.current_worm().walk(direction, self.terrain)

    def jump(self):
        if self.can_control() and self.rope is None:
            self.current_worm().jump()

    def adjust_aim(self, delta):
        if self.state == AIM and self.rope is None:
            self.aim_angle = max(0.0, min(90.0, self.aim_angle + delta * AIM_RATE))

    def charge(self):
        if self.state == AIM and not self.fired and self.rope is None:
            self.power = min(100.0, self.power + CHARGE_RATE)

    def select_weapon(self, weapon_id):
        if weapon_id in WEAPONS and self.state == AIM and not self.fired:
            self.weapon = weapon_id

    def select_weapon_index(self, i):
        if 0 <= i < len(WEAPON_ORDER):
            self.select_weapon(WEAPON_ORDER[i])

    def cycle_weapon(self, step=1):
        if self.state == AIM and not self.fired:
            i = WEAPON_ORDER.index(self.weapon)
            self.weapon = WEAPON_ORDER[(i + step) % len(WEAPON_ORDER)]

    # --- ninja rope --------------------------------------------------------
    def fire_rope(self):
        if not self.can_control() or self.rope is not None:
            return
        worm = self.current_worm()
        rope = NinjaRope.fire(worm, self.aim_angle, self.terrain)
        if rope is not None:
            self.rope = rope

    def release_rope(self):
        if self.rope is not None:
            self.rope.worm.on_ground = False
            self.rope = None

    def rope_swing(self, direction):
        if self.rope is not None:
            self.rope.swing(direction)

    def rope_reel(self, direction):
        if self.rope is not None:
            self.rope.reel(direction)

    # --- firing dispatch ---------------------------------------------------
    def fire(self):
        if self.state != AIM or self.fired:
            return
        worm = self.current_worm()
        if worm is None:
            return
        weapon = WEAPONS[self.weapon]
        mode = weapon["mode"]

        if mode == "projectile":
            if self.power <= 1:
                return
            self._fire_projectile(worm, weapon)
        elif mode == "hitscan":
            self._fire_hitscan(worm, weapon)
        elif mode == "placed":
            self._fire_placed(worm, weapon)
        elif mode == "melee":
            self._fire_melee(worm, weapon)
        elif mode == "sheep":
            self._fire_sheep(worm, weapon)
        elif mode == "airstrike":
            self._fire_airstrike(worm, weapon)
        else:
            return

        self.rope = None
        self.fired = True
        self.power = 0.0
        self.state = BUSY

    def _launch_velocity(self, worm):
        speed = self.power / 100.0 * MAX_SHOT_SPEED
        rad = math.radians(self.aim_angle)
        return (math.cos(rad) * speed * worm.facing, -math.sin(rad) * speed)

    def _fire_projectile(self, worm, weapon):
        vx, vy = self._launch_velocity(worm)
        px = worm.x + worm.facing * (worm.RADIUS + 3)
        self.projectiles.append(Projectile(px, worm.y, vx, vy, weapon))

    def _fire_hitscan(self, worm, weapon):
        rad = math.radians(self.aim_angle)
        dx = math.cos(rad) * worm.facing
        dy = -math.sin(rad)
        rng = weapon.get("range", 300)
        targets = self.all_worms()
        for step in range(8, rng):
            x = worm.x + dx * step
            y = worm.y + dy * step
            if x < 0 or x >= self.width or y < 0 or y >= self.height:
                return
            for t in targets:
                if t is not worm and t.alive and math.hypot(t.x - x, t.y - y) <= t.RADIUS + 2:
                    t.damage(weapon["damage"])
                    t.apply_knockback(dx * 4 * weapon["knockback"], dy * 4 - 1)
                    self.particles.burst(x, y, 10, _EXPLOSION_COLORS, 3, 14)
                    self.shake.add(3)
                    return
            if self.terrain.solid_at(x, y):
                self.terrain.destroy(x, y, weapon["blastRadius"])
                self.particles.burst(x, y, 12, _EXPLOSION_COLORS, 3, 16)
                self.shake.add(3)
                return

    def _fire_melee(self, worm, weapon):
        rng = weapon.get("range", 26)
        for t in self.all_worms():
            if t is worm or not t.alive:
                continue
            dx = t.x - worm.x
            if dx * worm.facing <= 0:
                continue  # must be in front
            if abs(dx) <= rng and abs(t.y - worm.y) <= rng:
                t.damage(weapon["damage"])
                t.apply_knockback(worm.facing * 4.5 * weapon["knockback"], -4.5)
        self.particles.burst(worm.x + worm.facing * 10, worm.y, 8, [(255, 120, 40), (255, 200, 80)], 2.5, 12)
        self.shake.add(2)

    def _fire_placed(self, worm, weapon):
        self.bombs.append(TimedBomb(worm.x, worm.y, weapon["fuse"], weapon))

    def _fire_sheep(self, worm, weapon):
        sx = worm.x + worm.facing * (worm.RADIUS + Sheep.RADIUS + 1)
        self.sheep.append(Sheep(sx, worm.y, worm.facing, weapon["fuse"]))

    def _fire_airstrike(self, worm, weapon):
        target_x = worm.x + worm.facing * 130
        salvo = weapon.get("salvo", 5)
        for i in range(salvo):
            offset = (i - (salvo - 1) / 2) * 22
            px = target_x + offset
            self.projectiles.append(Projectile(px, -10, worm.facing * 0.5, 3.0, AIRSTRIKE_MISSILE))

    # --- detonation (with chain reactions & clusters) ----------------------
    def detonate(self, x, y, weapon):
        queue = [(x, y, weapon)]
        guard = 0
        while queue and guard < 64:
            guard += 1
            cx, cy, w = queue.pop()
            self._blast(cx, cy, w, queue)

    def _blast(self, x, y, weapon, queue):
        r = weapon["blastRadius"]
        self.terrain.destroy(x, y, r)
        self.particles.burst(x, y, int(r * 0.7), _EXPLOSION_COLORS, r * 0.12, int(r * 0.5))
        self.shake.add(r * 0.16)

        for worm in self.all_worms():
            if not worm.alive:
                continue
            d = math.hypot(worm.x - x, worm.y - y)
            if d > r:
                continue
            frac = 1.0 - d / r
            worm.damage(weapon["damage"] * frac)
            kb = weapon["knockback"] * frac * 6.0
            if d > 0.1:
                worm.apply_knockback((worm.x - x) / d * kb, (worm.y - y) / d * kb - 2.0)
            else:
                worm.apply_knockback(0.0, -4.0)

        for drum in self.drums:
            if not drum.alive:
                continue
            d = math.hypot(drum.x - x, drum.y - y)
            if d <= r + drum.RADIUS:
                drum.hp -= weapon["damage"] * (1.0 - min(1.0, d / (r + drum.RADIUS)))
                if drum.hp <= 0:
                    drum.alive = False
                    queue.append((drum.x, drum.y, OILDRUM_BLAST))

        for _ in range(weapon.get("clusters", 0)):
            ang = self.rng.uniform(-2.4, -0.7)
            spd = self.rng.uniform(3.0, 6.0)
            self.projectiles.append(
                Projectile(x, y - 2, math.cos(ang) * spd, math.sin(ang) * spd, CLUSTER_CHILD))

    # --- per-frame update --------------------------------------------------
    def update(self):
        if self.state == GAME_OVER:
            self.particles.update()
            self.shake.update()
            return

        roped = self.rope.worm if self.rope else None
        for worm in self.all_worms():
            if worm is roped:
                self.rope.update(self.terrain)
            else:
                worm.update(self.terrain)
            if worm.alive and worm.y > self.water_line:
                worm.drown()
                if worm is roped:
                    self.rope = None
                    roped = None

        for p in list(self.projectiles):
            event, pos = p.update(self.terrain, self.wind, self.width, self.height)
            if event == "explode":
                self.detonate(pos[0], pos[1], p.weapon)
                self.projectiles.remove(p)
            elif event == "expire":
                self.projectiles.remove(p)

        for s in list(self.sheep):
            if s.update(self.terrain):
                self.detonate(s.x, s.y, WEAPONS["sheep"])
                self.sheep.remove(s)

        for b in list(self.bombs):
            if b.update(self.terrain):
                self.detonate(b.x, b.y, b.weapon)
                self.bombs.remove(b)

        alive_worms = [w for w in self.all_worms() if w.alive]
        for m in list(self.mines):
            if m.update(alive_worms):
                self.detonate(m.x, m.y, {"damage": 45, "blastRadius": 46, "knockback": 1.2, "clusters": 0})
                self.mines.remove(m)

        for c in list(self.crates):
            c.update(self.terrain)
            for w in alive_worms:
                if math.hypot(w.x - c.x, w.y - c.y) <= w.RADIUS + c.RADIUS:
                    w.hp = min(100, w.hp + c.heal)
                    c.alive = False
                    self.particles.burst(c.x, c.y, 10, [(120, 230, 120)], 2.5, 16)
                    break
            if not c.alive:
                self.crates.remove(c)

        self.particles.update()
        self.shake.update()

        if self.state == AIM:
            self.timer -= 1
            if self.timer <= 0:
                self.end_turn()
                return
        elif self.state == BUSY:
            if not self.ordnance_active():
                self.state = RETREAT
                self.timer = RETREAT_FRAMES
        elif self.state == RETREAT:
            self.timer -= 1
            if self.timer <= 0 and self.settled():
                self.end_turn()
                return

        if self.alive_team_count() <= 1:
            self._finish()
