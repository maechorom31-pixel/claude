"""All drawing. Reads game state; never mutates it.

The world (terrain, water, worms, ordnance, particles) is drawn onto an
offscreen surface and blitted with the current screen-shake offset; the HUD
is drawn directly on the screen so it stays steady.
"""

import math

import pygame

from worms.config import WEAPONS, WEAPON_ORDER
from worms.game import AIM, RETREAT, GAME_OVER

SKY = (135, 190, 230)
WATER = (40, 110, 180)


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.world = pygame.Surface((self.w, self.h))
        self.font = pygame.font.SysFont("consolas,monospace", 16)
        self.small = pygame.font.SysFont("consolas,monospace", 13)
        self.big = pygame.font.SysFont("consolas,monospace", 40, bold=True)

    def draw(self, game):
        wf = self.world
        wf.fill(SKY)
        wf.blit(game.terrain.surface, (0, 0))

        # water
        wh = max(0, game.height - game.water_line)
        water = pygame.Surface((game.width, wh), pygame.SRCALPHA)
        water.fill((*WATER, 150))
        wf.blit(water, (0, game.water_line))

        self._draw_mines(wf, game)
        self._draw_drums(wf, game)
        self._draw_crates(wf, game)
        self._draw_rope(wf, game)
        self._draw_worms(wf, game)
        self._draw_sheep(wf, game)
        self._draw_bombs(wf, game)
        self._draw_projectiles(wf, game)
        self._draw_aim(wf, game)
        self._draw_particles(wf, game)

        ox, oy = game.shake.offset()
        self.screen.fill((0, 0, 0))
        self.screen.blit(wf, (ox, oy))

        self._draw_hud(game)
        if game.state == GAME_OVER:
            self._draw_gameover(game)

    # --- world pieces ------------------------------------------------------
    def _draw_worms(self, wf, game):
        active = game.current_worm()
        for team in game.teams:
            for w in team.worms:
                if not w.alive:
                    continue
                cx, cy = int(w.x), int(w.y)
                pygame.draw.circle(wf, team.color, (cx, cy), w.RADIUS)
                pygame.draw.circle(wf, (20, 20, 20), (cx, cy), w.RADIUS, 1)
                pygame.draw.circle(wf, (255, 255, 255), (cx + w.facing * 2, cy - 1), 1)
                if w is active:
                    pygame.draw.circle(wf, (255, 255, 255), (cx, cy), w.RADIUS + 3, 1)
                self._hp_bar(wf, w, cx, cy)

    def _hp_bar(self, wf, w, cx, cy):
        bw, bh = 22, 3
        x = cx - bw // 2
        y = cy - w.RADIUS - 8
        pygame.draw.rect(wf, (0, 0, 0), (x, y, bw, bh))
        frac = max(0.0, w.hp / 100.0)
        col = (90, 200, 90) if frac > 0.5 else (230, 200, 60) if frac > 0.25 else (220, 70, 70)
        pygame.draw.rect(wf, col, (x, y, int(bw * frac), bh))

    def _draw_rope(self, wf, game):
        if game.rope is None:
            return
        r = game.rope
        w = r.worm
        pygame.draw.line(wf, (40, 30, 20), (int(r.ax), int(r.ay)), (int(w.x), int(w.y)), 2)
        pygame.draw.circle(wf, (60, 50, 40), (int(r.ax), int(r.ay)), 3)

    def _draw_projectiles(self, wf, game):
        for p in game.projectiles:
            for (tx, ty) in p.trail:
                pygame.draw.circle(wf, (255, 230, 180), (int(tx), int(ty)), 1)
            pygame.draw.circle(wf, (40, 40, 40), (int(p.x), int(p.y)), 3)

    def _draw_sheep(self, wf, game):
        for s in game.sheep:
            cx, cy = int(s.x), int(s.y)
            pygame.draw.circle(wf, (240, 240, 240), (cx, cy), s.RADIUS)
            pygame.draw.circle(wf, (40, 40, 40), (cx, cy), s.RADIUS, 1)
            pygame.draw.circle(wf, (255, 120, 120), (cx + s.facing * 2, cy - 1), 1)

    def _draw_bombs(self, wf, game):
        for b in game.bombs:
            cx, cy = int(b.x), int(b.y)
            pygame.draw.rect(wf, (180, 40, 40), (cx - 3, cy - 6, 6, 12))
            blink = (b.fuse // 6) % 2 == 0
            pygame.draw.circle(wf, (255, 220, 80) if blink else (120, 100, 40), (cx, cy - 8), 2)

    def _draw_mines(self, wf, game):
        for m in game.mines:
            cx, cy = int(m.x), int(m.y)
            col = (220, 60, 60) if m.armed and (m.fuse // 4) % 2 == 0 else (90, 90, 90)
            pygame.draw.circle(wf, col, (cx, cy), m.RADIUS)
            pygame.draw.circle(wf, (20, 20, 20), (cx, cy), m.RADIUS, 1)

    def _draw_drums(self, wf, game):
        for d in game.drums:
            if not d.alive:
                continue
            cx, cy = int(d.x), int(d.y)
            pygame.draw.rect(wf, (150, 110, 40), (cx - d.RADIUS, cy - d.RADIUS, d.RADIUS * 2, d.RADIUS * 2))
            pygame.draw.rect(wf, (40, 30, 10), (cx - d.RADIUS, cy - d.RADIUS, d.RADIUS * 2, d.RADIUS * 2), 1)
            pygame.draw.line(wf, (40, 30, 10), (cx - d.RADIUS, cy - 2), (cx + d.RADIUS, cy - 2), 1)

    def _draw_crates(self, wf, game):
        for c in game.crates:
            cx, cy = int(c.x), int(c.y)
            if not c.landed:
                pygame.draw.arc(wf, (230, 230, 230),
                                (cx - 12, cy - 20, 24, 20), math.pi, math.tau, 2)
                pygame.draw.line(wf, (230, 230, 230), (cx - 10, cy - 10), (cx, cy - c.RADIUS), 1)
                pygame.draw.line(wf, (230, 230, 230), (cx + 10, cy - 10), (cx, cy - c.RADIUS), 1)
            pygame.draw.rect(wf, (160, 120, 70), (cx - c.RADIUS, cy - c.RADIUS, c.RADIUS * 2, c.RADIUS * 2))
            pygame.draw.rect(wf, (40, 30, 10), (cx - c.RADIUS, cy - c.RADIUS, c.RADIUS * 2, c.RADIUS * 2), 1)
            cross = (90, 220, 90)
            pygame.draw.line(wf, cross, (cx, cy - 4), (cx, cy + 4), 2)
            pygame.draw.line(wf, cross, (cx - 4, cy), (cx + 4, cy), 2)

    def _draw_aim(self, wf, game):
        if game.state != AIM or game.rope is not None:
            return
        w = game.current_worm()
        if w is None:
            return
        rad = math.radians(game.aim_angle)
        dx = math.cos(rad) * w.facing
        dy = -math.sin(rad)
        for i in range(6, 46, 6):
            pygame.draw.circle(wf, (255, 255, 255), (int(w.x + dx * i), int(w.y + dy * i)), 1)

    def _draw_particles(self, wf, game):
        for p in game.particles.particles:
            a = max(0, min(255, int(255 * p.life / p.max_life)))
            col = (*p.color, a)
            s = pygame.Surface((p.size * 2, p.size * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, col, (p.size, p.size), p.size)
            wf.blit(s, (int(p.x - p.size), int(p.y - p.size)))

    # --- HUD ---------------------------------------------------------------
    def _draw_hud(self, game):
        s = self.screen
        team = game.current_team()
        worm = game.current_worm()
        if team and worm:
            txt = f"{team.name}  worm {worm.name}  HP {worm.hp}"
            s.blit(self.font.render(txt, True, team.color), (10, 8))

        secs = max(0, game.timer // 60)
        tcol = (220, 70, 70) if secs <= 5 else (20, 20, 20)
        s.blit(self.font.render(f"{secs:02d}s", True, tcol), (game.width - 56, 8))

        if game.sudden_death:
            sd = self.font.render("SUDDEN DEATH", True, (220, 50, 50))
            s.blit(sd, sd.get_rect(midtop=(game.width // 2, 30)))

        # wind
        cx, wy = game.width // 2, 18
        s.blit(self.small.render("Wind", True, (20, 20, 20)), (cx - 70, 10))
        mag = abs(game.wind)
        if mag:
            d = 1 if game.wind > 0 else -1
            for i in range(mag):
                px = cx + d * (i * 5)
                pygame.draw.line(s, (20, 20, 90), (px, wy), (px + d * 4, wy), 2)
            tip = cx + d * mag * 5
            pygame.draw.polygon(s, (20, 20, 90),
                                [(tip, wy), (tip - d * 5, wy - 3), (tip - d * 5, wy + 3)])

        # weapon + power
        idx = WEAPON_ORDER.index(game.weapon) + 1
        wname = WEAPONS[game.weapon]["name"]
        s.blit(self.font.render(f"[{idx}/{len(WEAPON_ORDER)}] {wname}", True, (20, 20, 20)),
               (10, game.height - 44))
        s.blit(self.small.render("1-9/Tab weapon  F rope  Space fire  Enter jump",
                                 True, (40, 40, 40)), (10, game.height - 24))
        pygame.draw.rect(s, (0, 0, 0), (320, game.height - 42, 204, 14), 1)
        pw = int(200 * game.power / 100.0)
        pcol = (90, 200, 90) if game.power < 60 else (230, 200, 60) if game.power < 85 else (220, 70, 70)
        pygame.draw.rect(s, pcol, (322, game.height - 40, pw, 10))
        if game.rope is not None:
            rope = self.small.render("ROPE: <>/swing  ^v/reel  F or Space release",
                                     True, (120, 60, 20))
            s.blit(rope, (320, game.height - 22))

    def _draw_gameover(self, game):
        s = self.screen
        overlay = pygame.Surface((game.width, game.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        s.blit(overlay, (0, 0))
        if game.winner:
            msg, col = f"{game.winner.name} wins!", game.winner.color
        else:
            msg, col = "Draw!", (240, 240, 240)
        label = self.big.render(msg, True, col)
        s.blit(label, label.get_rect(center=(game.width // 2, game.height // 2 - 20)))
        sub = self.font.render("Press R to restart, Esc to quit", True, (240, 240, 240))
        s.blit(sub, sub.get_rect(center=(game.width // 2, game.height // 2 + 24)))
