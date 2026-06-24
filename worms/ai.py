"""Single-player AI — a computer opponent for a team.

Strategy: pick the nearest living enemy, then find a firing solution by
*simulating* candidate shots. For each (weapon, angle, power) candidate the AI
flies a throwaway projectile through the real terrain/wind (Projectile.update
mutates nothing) and scores the blast point by how close it lands to the target
— penalising self-damage and friendly fire. The best candidate is fired, with a
little aim/power noise so the CPU is beatable.

The controller is frame-driven: ``update(game)`` is called every frame from the
main loop. On the CPU's turn it waits a short "thinking" delay (for watchability)
and then commits its shot exactly once.
"""

import math
import random

from worms.config import WEAPONS, MAX_SHOT_SPEED
from worms.projectile import Projectile

# Weapons the AI knows how to aim (all simple arcing shots).
_AI_WEAPONS = ["bazooka", "grenade", "holy"]

_ANGLES = list(range(12, 81, 4))
_POWERS = list(range(35, 101, 5))


def choose_target(game, worm):
    enemies = [w for w in game.all_worms()
               if w.alive and w.team_idx != worm.team_idx]
    if not enemies:
        return None
    return min(enemies, key=lambda e: math.hypot(e.x - worm.x, e.y - worm.y))


def _simulate(game, worm, weapon, angle, power, facing):
    """Fly a candidate shot; return the blast point or None if it fizzles."""
    speed = power / 100.0 * MAX_SHOT_SPEED
    rad = math.radians(angle)
    vx = math.cos(rad) * speed * facing
    vy = -math.sin(rad) * speed
    px = worm.x + facing * (worm.RADIUS + 3)
    proj = Projectile(px, worm.y, vx, vy, weapon)
    for _ in range(800):
        event, pos = proj.update(game.terrain, game.wind, game.width, game.height)
        if event == "explode":
            return pos
        if event == "expire":
            return None
    return None


def best_shot(game, worm, target):
    """Search candidates; return dict(weapon, angle, power, facing, impact, dist)."""
    facing = 1 if target.x >= worm.x else -1
    friends = [w for w in game.all_worms()
               if w.alive and w.team_idx == worm.team_idx and w is not worm]
    best = None
    for wid in _AI_WEAPONS:
        weapon = WEAPONS[wid]
        blast = weapon["blastRadius"]
        for angle in _ANGLES:
            for power in _POWERS:
                impact = _simulate(game, worm, weapon, angle, power, facing)
                if impact is None:
                    continue
                d = math.hypot(impact[0] - target.x, impact[1] - target.y)
                score = d
                if math.hypot(impact[0] - worm.x, impact[1] - worm.y) < blast * 1.1:
                    score += 500  # don't blow yourself up
                for f in friends:
                    if math.hypot(impact[0] - f.x, impact[1] - f.y) < blast:
                        score += 200
                # Prefer a stronger weapon only when it actually lands on target.
                if d > blast:
                    score += {"bazooka": 0, "grenade": 4, "holy": 8}[wid]
                cand = {"weapon": wid, "angle": angle, "power": power,
                        "facing": facing, "impact": impact, "dist": d, "score": score}
                if best is None or cand["score"] < best["score"]:
                    best = cand
    return best


class AIController:
    def __init__(self, seed=None, aim_noise=4.0, power_noise=6.0, think_frames=45):
        self.rng = random.Random(seed)
        self.aim_noise = aim_noise
        self.power_noise = power_noise
        self.think_frames = think_frames
        self._turn_id = None
        self._think = 0

    def update(self, game):
        from worms.game import AIM
        if game.state != AIM:
            return
        team = game.current_team()
        if team is None or not team.is_ai:
            return
        if self._turn_id != game.turns_taken:   # new CPU turn
            self._turn_id = game.turns_taken
            self._think = 0
        if self._think < self.think_frames:
            self._think += 1
            return
        if game.fired:
            return
        self.act(game)

    def act(self, game):
        """Plan and fire immediately (also usable headlessly in tests)."""
        worm = game.current_worm()
        if worm is None:
            return
        target = choose_target(game, worm)
        if target is None:
            # Nothing to shoot at: fire harmlessly so the turn ends.
            game.select_weapon("bazooka")
            game.power = 30
            game.fire()
            return
        plan = best_shot(game, worm, target)
        if plan is None:
            game.select_weapon("bazooka")
            worm.facing = 1 if target.x >= worm.x else -1
            game.aim_angle = 45
            game.power = 60
            game.fire()
            return
        worm.facing = plan["facing"]
        game.select_weapon(plan["weapon"])
        game.aim_angle = max(1.0, min(89.0, plan["angle"] + self.rng.gauss(0, self.aim_noise)))
        game.power = max(10.0, min(100.0, plan["power"] + self.rng.gauss(0, self.power_noise)))
        game.fire()
