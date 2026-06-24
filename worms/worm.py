"""The worm entity: position, health and pixel-based movement physics.

Two movement regimes:
  * Grounded  -> keyboard ``walk`` snaps the worm along the surface (handles
    small slopes/steps), ``jump`` launches it into the air.
  * Airborne  -> ``update`` integrates velocity (gravity, knockback, jump
    arc) with per-pixel collision against the terrain mask.
"""

from worms.config import (
    GRAVITY, MAX_FALL, JUMP_VY, JUMP_VX, STEP_UP, WALK_SPEED,
    FALL_DAMAGE_THRESHOLD, FALL_DAMAGE_FACTOR,
)


class Worm:
    HEIGHT = 8        # body height in px (head to feet)
    RADIUS = 4        # collision/visual radius

    def __init__(self, x, y, team_idx, name):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.hp = 100
        self.alive = True
        self.team_idx = team_idx
        self.name = name
        self.facing = 1           # +1 right, -1 left
        self.on_ground = False
        self.fall_from = None     # y at which the current fall began

    # --- helpers -----------------------------------------------------------
    @property
    def radius(self):
        return self.RADIUS

    def feet(self):
        return self.y + self.RADIUS

    def damage(self, amount):
        if not self.alive:
            return
        self.hp -= int(amount)
        if self.hp <= 0:
            self.hp = 0
            self.alive = False

    def drown(self):
        self.hp = 0
        self.alive = False

    # --- grounded movement -------------------------------------------------
    def walk(self, direction, terrain):
        self.facing = 1 if direction >= 0 else -1
        if not self.on_ground:
            return
        nx = self.x + WALK_SPEED * self.facing
        if nx < self.RADIUS or nx >= terrain.width - self.RADIUS:
            return
        feet = int(self.feet())
        # Look for the nearest walkable surface within the climb window.
        for dy in range(-STEP_UP, STEP_UP + 1):
            fy = feet + dy
            if fy <= 0 or fy >= terrain.height:
                continue
            if terrain.solid_at(nx, fy) and not terrain.solid_at(nx, fy - 1):
                head = fy - self.HEIGHT
                if not terrain.solid_at(nx, head):       # head clearance
                    self.x = nx
                    self.y = fy - self.RADIUS - 1         # rest just above ground
                    return
                return                                    # blocked by ceiling
        # No ground within reach -> step off the ledge and start falling.
        if not terrain.solid_at(nx, self.y) and not terrain.solid_at(nx, self.feet()):
            self.x = nx
            self._go_airborne()

    def jump(self):
        if not self.on_ground:
            return
        self.vy = JUMP_VY
        self.vx = JUMP_VX * self.facing
        self._go_airborne()

    def apply_knockback(self, kvx, kvy):
        self.vx += kvx
        self.vy += kvy
        self._go_airborne()

    def _go_airborne(self):
        if self.on_ground or self.fall_from is None:
            self.fall_from = self.y
        self.on_ground = False

    # --- per-frame update --------------------------------------------------
    def update(self, terrain):
        if not self.alive:
            return
        if self.on_ground:
            # Ground may have been blown away beneath us.
            if not terrain.solid_at(self.x, self.feet() + 1):
                self._go_airborne()
            return

        self.vy = min(self.vy + GRAVITY, MAX_FALL)
        self._move_axis(terrain, self.vx, 0.0)
        self._move_axis(terrain, 0.0, self.vy)

        if self.vy >= 0 and terrain.solid_at(self.x, self.feet() + 1):
            self._land()

    def _move_axis(self, terrain, dx, dy):
        steps = int(max(abs(dx), abs(dy))) + 1
        sx, sy = dx / steps, dy / steps
        for _ in range(steps):
            nx, ny = self.x + sx, self.y + sy
            if self._blocked(terrain, nx, ny):
                if dx:
                    self.vx = 0.0
                if dy:
                    self.vy = 0.0
                return
            self.x, self.y = nx, ny

    def _blocked(self, terrain, x, y):
        return terrain.solid_at(x, y - self.RADIUS) or terrain.solid_at(x, y + self.RADIUS)

    def _land(self):
        if self.fall_from is not None:
            dist = self.y - self.fall_from
            if dist > FALL_DAMAGE_THRESHOLD:
                self.damage((dist - FALL_DAMAGE_THRESHOLD) * FALL_DAMAGE_FACTOR)
        self.fall_from = None
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = True
