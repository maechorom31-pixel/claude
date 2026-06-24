"""Worms MVP — entry point.

Controls
  Left / Right .... walk
  Up / Down ....... aim angle
  Space (hold) .... charge power, release to fire
  Enter ........... jump
  1 / 2 / Tab ..... select weapon (Bazooka / Grenade)
  R ............... restart (after game over)
  Esc ............. quit
"""

import argparse

import pygame

from worms.config import WIDTH, HEIGHT, FPS
from worms.game import Game, AIM, RETREAT, GAME_OVER
from worms.render import Renderer


def main():
    ap = argparse.ArgumentParser(description="Worms MVP")
    ap.add_argument("--teams", type=int, default=2)
    ap.add_argument("--worms", type=int, default=3, help="worms per team")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Worms MVP")
    clock = pygame.time.Clock()

    game = Game(WIDTH, HEIGHT)
    game.new_game(teams=args.teams, worms_per_team=args.worms, seed=args.seed)
    renderer = Renderer(screen)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_1:
                    game.select_weapon("bazooka")
                elif event.key == pygame.K_2:
                    game.select_weapon("grenade")
                elif event.key == pygame.K_TAB:
                    game.cycle_weapon()
                elif event.key == pygame.K_RETURN:
                    game.jump()
                elif event.key == pygame.K_r and game.state == GAME_OVER:
                    game.new_game(teams=args.teams, worms_per_team=args.worms, seed=args.seed)
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    game.fire()

        keys = pygame.key.get_pressed()
        if game.state in (AIM, RETREAT):
            if keys[pygame.K_LEFT]:
                game.walk(-1)
            if keys[pygame.K_RIGHT]:
                game.walk(1)
        if game.state == AIM:
            if keys[pygame.K_UP]:
                game.adjust_aim(+1)
            if keys[pygame.K_DOWN]:
                game.adjust_aim(-1)
            if keys[pygame.K_SPACE]:
                game.charge()

        game.update()
        renderer.draw(game)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
