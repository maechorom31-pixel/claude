"""Worms — entry point.

Controls
  Left / Right ........ walk  (or swing while on the rope)
  Up / Down ........... aim   (or reel the rope in / out)
  Space (hold) ........ charge power, release to fire  (release rope if attached)
  Enter ............... jump
  F ................... fire the ninja rope / release it
  1-9 / Tab ........... select weapon
  R ................... restart (after game over)
  Esc ................. quit

Weapons: 1 Bazooka  2 Grenade  3 Cluster  4 Shotgun  5 Dynamite
         6 Fire Punch  7 Sheep  8 Air Strike  9 Holy Hand Grenade
"""

import argparse

import pygame

from worms.config import WIDTH, HEIGHT, FPS
from worms.game import Game, AIM, RETREAT, GAME_OVER
from worms.render import Renderer

_NUM_KEYS = {
    pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3, pygame.K_5: 4,
    pygame.K_6: 5, pygame.K_7: 6, pygame.K_8: 7, pygame.K_9: 8,
}


def main():
    ap = argparse.ArgumentParser(description="Worms")
    ap.add_argument("--teams", type=int, default=2)
    ap.add_argument("--worms", type=int, default=3, help="worms per team")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Worms")
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
                elif event.key in _NUM_KEYS:
                    game.select_weapon_index(_NUM_KEYS[event.key])
                elif event.key == pygame.K_TAB:
                    game.cycle_weapon(-1 if (event.mod & pygame.KMOD_SHIFT) else 1)
                elif event.key == pygame.K_RETURN:
                    game.jump()
                elif event.key == pygame.K_f:
                    if game.rope is not None:
                        game.release_rope()
                    else:
                        game.fire_rope()
                elif event.key == pygame.K_r and game.state == GAME_OVER:
                    game.new_game(teams=args.teams, worms_per_team=args.worms, seed=args.seed)
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    if game.rope is not None:
                        game.release_rope()
                    else:
                        game.fire()

        keys = pygame.key.get_pressed()
        if game.rope is not None:
            if keys[pygame.K_LEFT]:
                game.rope_swing(-1)
            if keys[pygame.K_RIGHT]:
                game.rope_swing(1)
            if keys[pygame.K_UP]:
                game.rope_reel(-1)   # shorten / climb
            if keys[pygame.K_DOWN]:
                game.rope_reel(1)    # lengthen / drop
        else:
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
