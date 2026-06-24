"""Projectiles fired by weapons (bazooka, grenade, ...).

``update`` advances the projectile one tick and returns an event:
  * ("explode", (x, y)) -> caller should detonate at that point
  * ("expire", None)    -> remove silently (fell into water / left the world)
  * (None, None)        -> still in flight
"""

from worms.config import GRAVITY, WIND_ACCEL


class Projectile:
    def __init__(self, x, y, vx, vy, weapon):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.weapon = weapon
        fuse = weapon.get("fuse")
        self.fuse_ticks = int(fuse * 60) if fuse else None
        self.trail = []  # recent positions, for rendering

    def update(self, terrain, wind, width, height):
        w = self.weapon
        if w["affectedByWind"]:
            self.vx += wind * WIND_ACCEL
        self.vy += GRAVITY

        steps = int(max(abs(self.vx), abs(self.vy))) + 1
        sx, sy = self.vx / steps, self.vy / steps
        for _ in range(steps):
            self.x += sx
            self.y += sy

            if self.y >= height:                       # hit the water
                return ("expire", None)
            if self.x < 0 or self.x >= width:
                if w["bounce"]:
                    self.x -= sx
                    self.vx = -self.vx * 0.6
                    break
                return ("expire", None)

            if terrain.solid_at(self.x, self.y):
                if w["bounce"] and self.fuse_ticks and self.fuse_ticks > 0:
                    # Step back out of the terrain and reflect (damped).
                    self.x -= sx
                    self.y -= sy
                    self.vy = -self.vy * 0.5
                    self.vx *= 0.7
                    break
                return ("explode", (self.x, self.y))

        self.trail.append((self.x, self.y))
        if len(self.trail) > 12:
            self.trail.pop(0)

        if self.fuse_ticks is not None:
            self.fuse_ticks -= 1
            if self.fuse_ticks <= 0:
                return ("explode", (self.x, self.y))
        return (None, None)
