"""All drawing. Reads game state; never mutates it."""

import math

import pygame

from worms.config import WEAPONS
from worms.game import AIM, RETREAT, GAME_OVER

SKY = (135, 190, 230)
WATER = (40, 110, 180)


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas,monospace", 16)
        self.big = pygame.font.SysFont("consolas,monospace", 40, bold=True)

    def draw(self, game):
        s = self.screen
        s.fill(SKY)
        s.blit(game.terrain.surface, (0, 0))

        # water
        water = pygame.Surface((game.width, game.height - game.water_line), pygame.SRCALPHA)
        water.fill((*WATER, 150))
        s.blit(water, (0, game.water_line))

        self._draw_worms(game)
        self._draw_projectiles(game)
        self._draw_aim(game)
        self._draw_hud(game)
        if game.state == GAME_OVER:
            self._draw_gameover(game)

    # --- pieces ------------------------------------------------------------
    def _draw_worms(self, game):
        s = self.screen
        active = game.current_worm()
        for team in game.teams:
            for w in team.worms:
                if not w.alive:
                    continue
                cx, cy = int(w.x), int(w.y)
                pygame.draw.circle(s, team.color, (cx, cy), w.RADIUS)
                pygame.draw.circle(s, (20, 20, 20), (cx, cy), w.RADIUS, 1)
                # facing eye
                pygame.draw.circle(s, (255, 255, 255), (cx + w.facing * 2, cy - 1), 1)
                if w is active:
                    pygame.draw.circle(s, (255, 255, 255), (cx, cy), w.RADIUS + 3, 1)
                self._hp_bar(w, cx, cy)

    def _hp_bar(self, w, cx, cy):
        bw, bh = 22, 3
        x = cx - bw // 2
        y = cy - w.RADIUS - 8
        pygame.draw.rect(self.screen, (0, 0, 0), (x, y, bw, bh))
        frac = max(0.0, w.hp / 100.0)
        col = (90, 200, 90) if frac > 0.5 else (230, 200, 60) if frac > 0.25 else (220, 70, 70)
        pygame.draw.rect(self.screen, col, (x, y, int(bw * frac), bh))

    def _draw_projectiles(self, game):
        s = self.screen
        for p in game.projectiles:
            for i, (tx, ty) in enumerate(p.trail):
                a = int(60 * i / max(1, len(p.trail)))
                pygame.draw.circle(s, (255, 230, 180), (int(tx), int(ty)), 1)
            pygame.draw.circle(s, (40, 40, 40), (int(p.x), int(p.y)), 3)

    def _draw_aim(self, game):
        if game.state != AIM:
            return
        w = game.current_worm()
        if w is None:
            return
        rad = math.radians(game.aim_angle)
        dx = math.cos(rad) * w.facing
        dy = -math.sin(rad)
        x0, y0 = w.x, w.y
        for i in range(6, 46, 6):  # dotted aim line
            pygame.draw.circle(self.screen, (255, 255, 255),
                               (int(x0 + dx * i), int(y0 + dy * i)), 1)

    def _draw_hud(self, game):
        s = self.screen
        team = game.current_team()
        worm = game.current_worm()

        # active team / worm
        if team and worm:
            txt = f"{team.name}  worm {worm.name}  HP {worm.hp}"
            s.blit(self.font.render(txt, True, team.color), (10, 8))

        # timer
        secs = max(0, game.timer // 60)
        tcol = (220, 70, 70) if secs <= 5 else (20, 20, 20)
        timer = self.font.render(f"{secs:02d}s", True, tcol)
        s.blit(timer, (game.width - 60, 8))

        # wind indicator
        cx, wy = game.width // 2, 18
        s.blit(self.font.render("Wind", True, (20, 20, 20)), (cx - 60, 8))
        mag = abs(game.wind)
        if mag:
            d = 1 if game.wind > 0 else -1
            for i in range(mag):
                px = cx + d * (i * 5)
                pygame.draw.line(s, (20, 20, 90), (px, wy), (px + d * 4, wy), 2)
            pygame.draw.polygon(s, (20, 20, 90), [
                (cx + d * mag * 5, wy),
                (cx + d * mag * 5 - d * 5, wy - 3),
                (cx + d * mag * 5 - d * 5, wy + 3),
            ])

        # weapon + power
        wname = WEAPONS[game.weapon]["name"]
        s.blit(self.font.render(f"Weapon: {wname}  (1/2 or Tab)", True, (20, 20, 20)),
               (10, game.height - 26))
        pygame.draw.rect(s, (0, 0, 0), (220, game.height - 24, 204, 14), 1)
        pw = int(200 * game.power / 100.0)
        pcol = (90, 200, 90) if game.power < 60 else (230, 200, 60) if game.power < 85 else (220, 70, 70)
        pygame.draw.rect(s, pcol, (222, game.height - 22, pw, 10))

    def _draw_gameover(self, game):
        s = self.screen
        overlay = pygame.Surface((game.width, game.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        s.blit(overlay, (0, 0))
        if game.winner:
            msg = f"{game.winner.name} wins!"
            col = game.winner.color
        else:
            msg = "Draw!"
            col = (240, 240, 240)
        label = self.big.render(msg, True, col)
        s.blit(label, label.get_rect(center=(game.width // 2, game.height // 2 - 20)))
        sub = self.font.render("Press R to restart, Esc to quit", True, (240, 240, 240))
        s.blit(sub, sub.get_rect(center=(game.width // 2, game.height // 2 + 24)))
