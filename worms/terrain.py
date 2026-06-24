"""Destructible terrain backed by a pixel mask.

The terrain is a single SRCALPHA surface: solid pixels are opaque, empty
pixels are fully transparent. A pygame mask derived from that surface gives
fast point collision queries. Explosions simply erase a transparent circle
and rebuild the mask.
"""

import math
import random

import pygame


class Terrain:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.surface = pygame.Surface((width, height), pygame.SRCALPHA)
        self.mask = pygame.mask.from_surface(self.surface)

    # --- construction ------------------------------------------------------
    def _rebuild_mask(self):
        # Alpha >= 127 counts as solid (opaque terrain), < 127 is empty.
        self.mask = pygame.mask.from_surface(self.surface)

    def generate(self, seed=0):
        """Procedural rolling hills from a sum of sine waves."""
        rng = random.Random(seed)
        self.surface.fill((0, 0, 0, 0))
        base = self.height * 0.55
        amp1 = self.height * 0.12
        amp2 = self.height * 0.06
        f1 = rng.uniform(0.004, 0.008)
        f2 = rng.uniform(0.010, 0.020)
        p1 = rng.uniform(0, math.tau)
        p2 = rng.uniform(0, math.tau)
        for x in range(self.width):
            top = int(base + amp1 * math.sin(x * f1 + p1) + amp2 * math.sin(x * f2 + p2))
            top = max(0, min(self.height - 1, top))
            # grass cap then dirt down to the bottom
            pygame.draw.line(self.surface, (90, 170, 70, 255), (x, top), (x, top + 3))
            pygame.draw.line(self.surface, (130, 95, 60, 255), (x, top + 4), (x, self.height))
        self._rebuild_mask()

    def flat_ground(self, y):
        """Fill a solid slab from row ``y`` to the bottom (used by tests)."""
        self.surface.fill((0, 0, 0, 0))
        pygame.draw.rect(self.surface, (130, 95, 60, 255), (0, y, self.width, self.height - y))
        self._rebuild_mask()

    # --- queries -----------------------------------------------------------
    def solid_at(self, x, y):
        xi, yi = int(x), int(y)
        if xi < 0 or xi >= self.width or yi < 0 or yi >= self.height:
            return False  # outside the world is empty (water/sky handled elsewhere)
        return self.mask.get_at((xi, yi)) != 0

    def surface_y(self, x):
        """First solid row from the top at column ``x`` (spawn helper)."""
        xi = int(max(0, min(self.width - 1, x)))
        for y in range(self.height):
            if self.mask.get_at((xi, y)) != 0:
                return y
        return self.height

    # --- mutation ----------------------------------------------------------
    def destroy(self, cx, cy, r):
        """Erase a circular crater. Drawing color (0,0,0,0) clears alpha."""
        pygame.draw.circle(self.surface, (0, 0, 0, 0), (int(cx), int(cy)), int(r))
        self._rebuild_mask()
