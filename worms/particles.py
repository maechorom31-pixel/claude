"""Cosmetic particle system and screen shake.

Purely visual — never affects the simulation, so it may use its own RNG.
"""

import math
import random

_rng = random.Random(1234)


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "gravity")

    def __init__(self, x, y, vx, vy, life, color, size=2, gravity=True):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.gravity = gravity

    def update(self):
        if self.gravity:
            self.vy += 0.16
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        return self.life <= 0


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def burst(self, x, y, n, colors, speed, life, gravity=True, size=2):
        for _ in range(n):
            ang = _rng.uniform(0, math.tau)
            spd = _rng.uniform(0.2, 1.0) * speed
            self.particles.append(Particle(
                x, y, math.cos(ang) * spd, math.sin(ang) * spd - speed * 0.3,
                int(life * _rng.uniform(0.6, 1.0)), _rng.choice(colors),
                size=size, gravity=gravity,
            ))

    def update(self):
        self.particles = [p for p in self.particles if not p.update()]


class ScreenShake:
    def __init__(self):
        self.mag = 0.0
        self.t = 0

    def add(self, amount):
        self.mag = min(24.0, self.mag + amount)

    def update(self):
        self.t += 1
        self.mag *= 0.85
        if self.mag < 0.4:
            self.mag = 0.0

    def offset(self):
        if self.mag <= 0:
            return (0, 0)
        return (int(math.sin(self.t * 1.3) * self.mag),
                int(math.cos(self.t * 1.7) * self.mag))
