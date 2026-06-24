"""World/weapon entities: Sheep, TimedBomb, Mine, OilDrum, Crate.

Each exposes a simple update(...) returning whether it should detonate / is
consumed this frame, so the Game can drive them uniformly.
"""

import math

from worms.config import GRAVITY, MAX_FALL


class Sheep:
    """A bomb that walks/hops in its facing direction, then explodes on fuse."""
    RADIUS = 5

    def __init__(self, x, y, facing, fuse_seconds):
        self.x = float(x)
        self.y = float(y)
        self.vx = 1.5 * facing
        self.vy = 0.0
        self.facing = facing
        self.fuse = int(fuse_seconds * 60)
        self.alive = True

    def update(self, terrain):
        self.vy = min(self.vy + GRAVITY, MAX_FALL)
        # horizontal walk with small step-climb / wall bounce
        nx = self.x + self.vx
        if 0 < nx < terrain.width and not terrain.solid_at(nx, self.y + self.RADIUS - 1):
            self.x = nx
        elif 0 < nx < terrain.width:
            climbed = False
            for up in range(1, 7):
                if not terrain.solid_at(nx, self.y + self.RADIUS - 1 - up):
                    self.x = nx
                    self.y -= up
                    climbed = True
                    break
            if not climbed:
                self.vx = -self.vx
                self.facing = -self.facing
        # vertical fall / land
        if not terrain.solid_at(self.x, self.y + self.RADIUS + self.vy):
            self.y += self.vy
        else:
            while self.vy > 0 and not terrain.solid_at(self.x, self.y + self.RADIUS + 1):
                self.y += 1
            self.vy = 0.0
        self.fuse -= 1
        if self.fuse <= 0:
            self.alive = False
            return True
        return False


class TimedBomb:
    """Dropped dynamite: sits in place and detonates when the fuse expires."""
    RADIUS = 4

    def __init__(self, x, y, fuse_seconds, weapon):
        self.x = float(x)
        self.y = float(y)
        self.fuse = int(fuse_seconds * 60)
        self.weapon = weapon
        self.alive = True

    def update(self, terrain):
        self.fuse -= 1
        if self.fuse <= 0:
            self.alive = False
            return True
        return False


class Mine:
    """Proximity mine: arms when a worm gets close, then detonates on a fuse."""
    RADIUS = 4

    def __init__(self, x, y, trigger, fuse_seconds):
        self.x = float(x)
        self.y = float(y)
        self.trigger = trigger
        self.fuse_frames = int(fuse_seconds * 60)
        self.armed = False
        self.fuse = 0
        self.alive = True

    def update(self, worms):
        if not self.armed:
            for w in worms:
                if w.alive and math.hypot(w.x - self.x, w.y - self.y) < self.trigger:
                    self.armed = True
                    self.fuse = self.fuse_frames
                    break
            return False
        self.fuse -= 1
        if self.fuse <= 0:
            self.alive = False
            return True
        return False


class OilDrum:
    """Explosive barrel: takes blast damage and chain-detonates when destroyed."""
    RADIUS = 9

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.hp = 20
        self.alive = True


class Crate:
    """Supply crate that parachutes down; a worm touching it gets healed."""
    RADIUS = 7

    def __init__(self, x, y, heal):
        self.x = float(x)
        self.y = float(y)
        self.vy = 0.0
        self.heal = heal
        self.landed = False
        self.alive = True

    def update(self, terrain):
        if self.landed:
            return
        self.vy = min(self.vy + GRAVITY * 0.35, 2.5)  # slow, parachute-like
        if terrain.solid_at(self.x, self.y + self.RADIUS + self.vy):
            self.landed = True
        else:
            self.y += self.vy
