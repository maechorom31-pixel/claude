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

Single player:  python main.py --cpu          (you = Team 1, rest = CPU)
                python main.py --teams 3 --humans 1   (Team 1 human, 2 & 3 CPU)
"""

import argparse

import pygame

from worms.config import WIDTH, HEIGHT, FPS
from worms.game import Game, AIM, RETREAT, GAME_OVER
from worms.render import Renderer
from worms.ai import AIController

_NUM_KEYS = {
    pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3, pygame.K_5: 4,
    pygame.K_6: 5, pygame.K_7: 6, pygame.K_8: 7, pygame.K_9: 8,
}


def main():
    ap = argparse.ArgumentParser(description="Worms")
    ap.add_argument("--teams", type=int, default=2)
    ap.add_argument("--worms", type=int, default=3, help="worms per team")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--humans", type=int, default=None,
                    help="number of human-controlled teams (rest are CPU)")
    ap.add_argument("--cpu", action="store_true",
                    help="single player: Team 1 human, all others CPU")
    args = ap.parse_args()

    human_count = args.teams
    if args.cpu:
        human_count = 1
    if args.humans is not None:
        human_count = max(0, min(args.teams, args.humans))
    ai_teams = set(range(human_count, args.teams))

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Worms")
    clock = pygame.time.Clock()

    game = Game(WIDTH, HEIGHT)
    game.new_game(teams=args.teams, worms_per_team=args.worms, seed=args.seed,
                  ai_teams=ai_teams)
    ai = AIController()
    renderer = Renderer(screen)

    def cpu_turn():
        return game.current_team() is not None and game.current_team().is_ai

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r and game.state == GAME_OVER:
                    game.new_game(teams=args.teams, worms_per_team=args.worms,
                                  seed=args.seed, ai_teams=ai_teams)
                elif cpu_turn():
                    pass  # ignore player input on the CPU's turn
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
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE and not cpu_turn():
                    if game.rope is not None:
                        game.release_rope()
                    else:
                        game.fire()

        if cpu_turn():
            ai.update(game)

        keys = pygame.key.get_pressed()
        if cpu_turn():
            pass
        elif game.rope is not None:
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
