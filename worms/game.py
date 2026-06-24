"""Game state and turn manager — the rules engine tying everything together.

State machine per turn:
    AIM     -> active worm may walk/jump/aim/charge; ticking turn timer
    BUSY    -> a shot is resolving (projectiles in flight)
    RETREAT -> post-shot movement window; ends once timer hits 0 and worms settle
    GAME_OVER

The main loop feeds input via the public command methods and calls update()
once per frame; rendering reads the public attributes.
"""

import math
import random

from worms.config import (
    WEAPONS, WEAPON_ORDER, TEAM_COLORS, WATER_OFFSET, WIND_RANGE,
    MAX_SHOT_SPEED, CHARGE_RATE, AIM_RATE,
    TURN_TIME_FRAMES, RETREAT_FRAMES,
)
from worms.terrain import Terrain
from worms.worm import Worm
from worms.projectile import Projectile

AIM = "aim"
BUSY = "busy"
RETREAT = "retreat"
GAME_OVER = "over"


class Team:
    def __init__(self, idx, color, name):
        self.idx = idx
        self.color = color
        self.name = name
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
        self.projectiles = []
        self.terrain = Terrain(width, height)
        self.water_line = height - WATER_OFFSET
        self.rng = random.Random()
        self.weapon = "bazooka"
        self.wind = 0
        self.power = 0.0
        self.aim_angle = 45.0
        self.fired = False
        self.timer = 0
        self.turn_team = -1
        self.winner = None

    # --- setup -------------------------------------------------------------
    def new_game(self, teams=2, worms_per_team=3, seed=None):
        self.rng = random.Random(seed)
        self.terrain = Terrain(self.width, self.height)
        self.terrain.generate(self.rng.randint(0, 10 ** 6))
        self.water_line = self.height - WATER_OFFSET
        self.teams = []
        slots = teams * worms_per_team
        spacing = self.width // (slots + 1)
        slot = 1
        for ti in range(teams):
            team = Team(ti, TEAM_COLORS[ti % len(TEAM_COLORS)], f"Team {ti + 1}")
            for wi in range(worms_per_team):
                x = spacing * slot
                slot += 1
                y = self.terrain.surface_y(x) - 12
                team.worms.append(Worm(x, y, ti, f"{ti + 1}-{wi + 1}"))
            self.teams.append(team)
        self.projectiles = []
        self.turn_team = -1
        self.weapon = "bazooka"
        self.winner = None
        self.start_turn()

    # --- turn flow ---------------------------------------------------------
    def start_turn(self):
        for _ in range(len(self.teams)):
            self.turn_team = (self.turn_team + 1) % len(self.teams)
            team = self.teams[self.turn_team]
            if team.alive_worms():
                team.advance_worm()
                break
        self.wind = self.rng.randint(-WIND_RANGE, WIND_RANGE)
        self.power = 0.0
        self.aim_angle = 45.0
        self.fired = False
        self.timer = TURN_TIME_FRAMES
        self.state = AIM

    def end_turn(self):
        if self.alive_team_count() <= 1:
            self._finish()
            return
        self.start_turn()

    def _finish(self):
        self.state = GAME_OVER
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

    def settled(self):
        return all(w.on_ground or not w.alive for w in self.all_worms())

    # --- player commands ---------------------------------------------------
    def can_control(self):
        return self.state in (AIM, RETREAT) and self.current_worm() is not None

    def walk(self, direction):
        if self.can_control():
            self.current_worm().walk(direction, self.terrain)

    def jump(self):
        if self.can_control():
            self.current_worm().jump()

    def adjust_aim(self, delta):
        if self.state == AIM:
            self.aim_angle = max(0.0, min(90.0, self.aim_angle + delta * AIM_RATE))

    def charge(self):
        if self.state == AIM and not self.fired:
            self.power = min(100.0, self.power + CHARGE_RATE)

    def select_weapon(self, weapon_id):
        if weapon_id in WEAPONS and self.state == AIM and not self.fired:
            self.weapon = weapon_id

    def cycle_weapon(self):
        if self.state == AIM and not self.fired:
            i = WEAPON_ORDER.index(self.weapon)
            self.weapon = WEAPON_ORDER[(i + 1) % len(WEAPON_ORDER)]

    def fire(self):
        if self.state != AIM or self.fired:
            return
        worm = self.current_worm()
        if worm is None or self.power <= 1:
            return
        weapon = WEAPONS[self.weapon]
        speed = self.power / 100.0 * MAX_SHOT_SPEED
        rad = math.radians(self.aim_angle)
        vx = math.cos(rad) * speed * worm.facing
        vy = -math.sin(rad) * speed
        px = worm.x + worm.facing * (worm.RADIUS + 3)
        py = worm.y
        self.projectiles.append(Projectile(px, py, vx, vy, weapon))
        self.fired = True
        self.power = 0.0
        self.state = BUSY

    # --- detonation --------------------------------------------------------
    def explode(self, x, y, weapon):
        r = weapon["blastRadius"]
        self.terrain.destroy(x, y, r)
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

    # --- per-frame update --------------------------------------------------
    def update(self):
        if self.state == GAME_OVER:
            return

        for worm in self.all_worms():
            worm.update(self.terrain)
            if worm.alive and worm.y > self.water_line:
                worm.drown()

        for p in list(self.projectiles):
            event, pos = p.update(self.terrain, self.wind, self.width, self.height)
            if event == "explode":
                self.explode(pos[0], pos[1], p.weapon)
                self.projectiles.remove(p)
            elif event == "expire":
                self.projectiles.remove(p)

        if self.state == AIM:
            self.timer -= 1
            if self.timer <= 0:
                self.end_turn()
                return
        elif self.state == BUSY:
            if not self.projectiles:
                self.state = RETREAT
                self.timer = RETREAT_FRAMES
        elif self.state == RETREAT:
            self.timer -= 1
            if self.timer <= 0 and self.settled() and not self.projectiles:
                self.end_turn()
                return

        if self.alive_team_count() <= 1:
            self._finish()
