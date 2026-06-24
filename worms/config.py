"""Game-wide constants and data-driven weapon definitions.

All tunable numbers live here so balancing does not require touching logic.
Physics assumes a fixed 60 Hz timestep (see FPS).
"""

# --- Display ---------------------------------------------------------------
WIDTH = 960
HEIGHT = 600
FPS = 60

# --- Physics (per 60 Hz tick) ----------------------------------------------
GRAVITY = 0.30           # downward acceleration, px/tick^2
MAX_FALL = 9.0           # terminal velocity, px/tick
WIND_ACCEL = 0.0025      # horizontal accel per wind-unit per tick
JUMP_VY = -5.0           # initial vertical jump velocity
JUMP_VX = 1.6            # initial horizontal jump velocity (toward facing)
STEP_UP = 6              # max pixels a worm can step/climb while walking
WALK_SPEED = 1           # px per walk tick

# --- Fall damage -----------------------------------------------------------
FALL_DAMAGE_THRESHOLD = 110   # px; falls shorter than this hurt nothing
FALL_DAMAGE_FACTOR = 0.35     # damage per px beyond the threshold

# --- Shooting --------------------------------------------------------------
MAX_SHOT_SPEED = 13.0    # launch speed at 100% power, px/tick
CHARGE_RATE = 1.6        # power gained per frame while charging (0..100)
AIM_RATE = 1.2           # degrees of aim adjustment per frame

# --- Turn flow -------------------------------------------------------------
TURN_TIME_FRAMES = 45 * FPS   # 45 s aiming window
RETREAT_FRAMES = 3 * FPS      # post-shot movement window

# --- Environment -----------------------------------------------------------
WATER_OFFSET = 14        # water surface = HEIGHT - WATER_OFFSET
WIND_RANGE = 10          # wind randomized in [-WIND_RANGE, +WIND_RANGE]

# --- Teams -----------------------------------------------------------------
TEAM_COLORS = [
    (70, 130, 220),   # blue
    (220, 80, 80),    # red
    (90, 200, 120),   # green
    (230, 200, 70),   # yellow
]

# --- Weapons (data-driven; see docs/worms-game-design.md §4.4) -------------
WEAPONS = {
    "bazooka": {
        "id": "bazooka",
        "name": "Bazooka",
        "category": "projectile",
        "damage": 45,
        "blastRadius": 48,
        "affectedByWind": True,
        "fuse": None,         # explodes on contact
        "bounce": False,
        "knockback": 1.0,
    },
    "grenade": {
        "id": "grenade",
        "name": "Grenade",
        "category": "throw",
        "damage": 50,
        "blastRadius": 45,
        "affectedByWind": True,
        "fuse": 3.0,          # seconds until detonation
        "bounce": True,       # bounces off terrain until the fuse ends
        "knockback": 1.1,
    },
}

WEAPON_ORDER = ["bazooka", "grenade"]
