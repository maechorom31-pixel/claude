"""Game-wide constants and data-driven weapon definitions.

All tunable numbers live here so balancing does not require touching logic.
Physics assumes a fixed 60 Hz timestep (see FPS).
"""

# --- Display ---------------------------------------------------------------
WIDTH = 960
HEIGHT = 600
FPS = 60

# --- Physics (per 60 Hz tick) ----------------------------------------------
GRAVITY = 0.30
MAX_FALL = 9.0
WIND_ACCEL = 0.0025
JUMP_VY = -5.0
JUMP_VX = 1.6
STEP_UP = 6
WALK_SPEED = 1

# --- Fall damage -----------------------------------------------------------
FALL_DAMAGE_THRESHOLD = 110
FALL_DAMAGE_FACTOR = 0.35

# --- Shooting --------------------------------------------------------------
MAX_SHOT_SPEED = 13.0
CHARGE_RATE = 1.6
AIM_RATE = 1.2

# --- Ninja Rope (the centerpiece movement tool) ----------------------------
ROPE_MAX_LENGTH = 240     # max grapple reach, px
ROPE_MIN_LENGTH = 14      # fully reeled-in length
ROPE_REEL_SPEED = 1.6     # px per frame while reeling
ROPE_SWING_ACCEL = 0.16   # horizontal accel per frame while swinging
ROPE_DAMPING = 0.996      # velocity retention along the constraint

# --- Turn flow -------------------------------------------------------------
TURN_TIME_FRAMES = 45 * FPS
RETREAT_FRAMES = 3 * FPS

# --- Environment -----------------------------------------------------------
WATER_OFFSET = 14
WIND_RANGE = 10
MINE_COUNT = 4
MINE_TRIGGER = 20         # worm proximity that arms a mine, px
MINE_FUSE = 0.8           # seconds after arming
OILDRUM_COUNT = 3
CRATE_EVERY = 3           # drop a supply crate every N turns
CRATE_HEAL = 30           # health restored by a health crate

# --- Sudden death ----------------------------------------------------------
SUDDEN_DEATH_ROUND = 8    # full rounds before sudden death triggers
WATER_RISE = 5            # px the water climbs each turn during sudden death

# --- Teams -----------------------------------------------------------------
TEAM_COLORS = [
    (70, 130, 220),
    (220, 80, 80),
    (90, 200, 120),
    (230, 200, 70),
]

# --- Weapons (data-driven; see docs/worms-game-design.md §4) ---------------
# mode determines firing behaviour:
#   projectile  -> arcing shot (power+angle); fuse/bounce/clusters honoured
#   hitscan     -> instant ray (angle only)
#   placed      -> dropped timed bomb at the worm
#   melee       -> instant short-range hit in front of the worm
#   sheep       -> spawns a walking sheep bomb (power+angle lob)
#   airstrike   -> calls a salvo of missiles from the sky toward a target
WEAPONS = {
    "bazooka": {
        "name": "Bazooka", "mode": "projectile", "damage": 45, "blastRadius": 48,
        "affectedByWind": True, "fuse": None, "bounce": False, "knockback": 1.0,
        "clusters": 0,
    },
    "grenade": {
        "name": "Grenade", "mode": "projectile", "damage": 50, "blastRadius": 45,
        "affectedByWind": True, "fuse": 3.0, "bounce": True, "knockback": 1.1,
        "clusters": 0,
    },
    "cluster": {
        "name": "Cluster Bomb", "mode": "projectile", "damage": 28, "blastRadius": 34,
        "affectedByWind": True, "fuse": 3.0, "bounce": True, "knockback": 0.9,
        "clusters": 5,
    },
    "shotgun": {
        "name": "Shotgun", "mode": "hitscan", "damage": 28, "blastRadius": 12,
        "affectedByWind": False, "fuse": None, "bounce": False, "knockback": 0.6,
        "clusters": 0, "range": 320,
    },
    "dynamite": {
        "name": "Dynamite", "mode": "placed", "damage": 65, "blastRadius": 60,
        "affectedByWind": False, "fuse": 4.0, "bounce": False, "knockback": 1.4,
        "clusters": 0,
    },
    "firepunch": {
        "name": "Fire Punch", "mode": "melee", "damage": 32, "blastRadius": 0,
        "affectedByWind": False, "fuse": None, "bounce": False, "knockback": 2.0,
        "clusters": 0, "range": 26,
    },
    "sheep": {
        "name": "Sheep", "mode": "sheep", "damage": 55, "blastRadius": 55,
        "affectedByWind": False, "fuse": 5.0, "bounce": False, "knockback": 1.2,
        "clusters": 0,
    },
    "airstrike": {
        "name": "Air Strike", "mode": "airstrike", "damage": 38, "blastRadius": 36,
        "affectedByWind": True, "fuse": None, "bounce": False, "knockback": 0.9,
        "clusters": 0, "salvo": 5,
    },
    "holy": {
        "name": "Holy Hand Grenade", "mode": "projectile", "damage": 90, "blastRadius": 85,
        "affectedByWind": True, "fuse": 4.0, "bounce": True, "knockback": 1.8,
        "clusters": 0,
    },
}

# Player-selectable order (maps to number keys 1..9 and Tab cycling).
WEAPON_ORDER = [
    "bazooka", "grenade", "cluster", "shotgun", "dynamite",
    "firepunch", "sheep", "airstrike", "holy",
]

# Internal weapon defs spawned by other weapons / the world (not selectable).
CLUSTER_CHILD = {
    "name": "Cluster", "mode": "projectile", "damage": 22, "blastRadius": 26,
    "affectedByWind": True, "fuse": None, "bounce": False, "knockback": 0.8,
    "clusters": 0,
}
AIRSTRIKE_MISSILE = {
    "name": "Missile", "mode": "projectile", "damage": 38, "blastRadius": 36,
    "affectedByWind": True, "fuse": None, "bounce": False, "knockback": 0.9,
    "clusters": 0,
}
OILDRUM_BLAST = {
    "name": "Oil Drum", "mode": "projectile", "damage": 55, "blastRadius": 58,
    "affectedByWind": False, "fuse": None, "bounce": False, "knockback": 1.3,
    "clusters": 0,
}
