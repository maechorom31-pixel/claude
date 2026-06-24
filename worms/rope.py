"""Ninja Rope — the signature movement tool.

Fire a grapple along the aim direction; it anchors to the first terrain pixel
it hits. While attached, the worm hangs as a pendulum: gravity pulls it down,
a distance constraint keeps it within the rope length, the player swings by
adding tangential velocity and reels the rope in/out. Releasing keeps all
momentum, so a well-timed release launches the worm across the map.
"""

import math

from worms.config import (
    GRAVITY, ROPE_MAX_LENGTH, ROPE_MIN_LENGTH, ROPE_REEL_SPEED,
    ROPE_SWING_ACCEL, ROPE_DAMPING,
)


class NinjaRope:
    def __init__(self, worm, anchor, length):
        self.worm = worm
        self.ax, self.ay = anchor
        self.length = length

    @classmethod
    def fire(cls, worm, aim_angle, terrain):
        """Raycast from the worm along the aim direction; attach on first hit."""
        rad = math.radians(aim_angle)
        dx = math.cos(rad) * worm.facing
        dy = -math.sin(rad)
        for step in range(8, ROPE_MAX_LENGTH + 1):
            px = worm.x + dx * step
            py = worm.y + dy * step
            if py < 0 or px < 0 or px >= terrain.width:
                return None
            if terrain.solid_at(px, py):
                length = math.hypot(px - worm.x, py - worm.y)
                worm.on_ground = False
                worm.fall_from = None
                return cls(worm, (px, py), max(ROPE_MIN_LENGTH, length))
        return None

    def reel(self, direction):
        # direction < 0 shortens (climb up), > 0 lengthens (drop down)
        self.length = max(ROPE_MIN_LENGTH,
                          min(ROPE_MAX_LENGTH, self.length + direction * ROPE_REEL_SPEED))

    def swing(self, direction):
        self.worm.facing = 1 if direction >= 0 else -1
        self.worm.vx += direction * ROPE_SWING_ACCEL

    def update(self, terrain):
        w = self.worm
        w.vy += GRAVITY
        w.x += w.vx
        w.y += w.vy

        dx = w.x - self.ax
        dy = w.y - self.ay
        dist = math.hypot(dx, dy) or 1e-6
        if dist > self.length:
            # Snap back onto the constraint circle and kill the radial velocity.
            rx, ry = dx / dist, dy / dist
            w.x = self.ax + rx * self.length
            w.y = self.ay + ry * self.length
            radial = w.vx * rx + w.vy * ry
            w.vx -= radial * rx
            w.vy -= radial * ry
            w.vx *= ROPE_DAMPING
            w.vy *= ROPE_DAMPING

        # Don't tunnel through terrain while swinging into a slope.
        if terrain.solid_at(w.x, w.feet()):
            if w.vy > 0:
                w.vy = 0
            w.y -= 1
