const DEFAULT_STATE = {
  currentPet: null,
  collection: [],
  stats: {
    poemsRead: 0,
    songsListened: 0,
    daylightOutdoorCount: 0,
    sunsetMeets: 0,
    nightMeets: 0,
    totalMissionsCompleted: 0,
    photoUploads: 0,
    missionsByCategory: {
      sensing: 0, stillness: 0, literature_music: 0,
      body: 0, creation: 0, connection: 0,
      doing_nothing: 0, useless_play: 0, visual_pause: 0
    }
  },
  season: 1,
  unlockedSpecials: [],
  metSpecials: [],
  metSeason2: [],
  settings: {
    position: null,
    opacity: 0.92,
    soundOn: false
  },
  firstRunDone: false,
  session: {
    recentMissionIds: [],
    lastMissionCompletedAt: null,
    declinesThisCycle: 0,
    pendingMissionId: null
  }
};

let state = null;
let saveTimer = null;

async function load() {
  const raw = await window.spiritAPI.loadState();
  state = mergeWithDefault(raw);
  return state;
}

function mergeWithDefault(raw) {
  if (!raw) return structuredClone(DEFAULT_STATE);
  const merged = structuredClone(DEFAULT_STATE);
  Object.assign(merged, raw);
  merged.stats = { ...DEFAULT_STATE.stats, ...(raw.stats || {}) };
  merged.stats.missionsByCategory = {
    ...DEFAULT_STATE.stats.missionsByCategory,
    ...((raw.stats && raw.stats.missionsByCategory) || {})
  };
  merged.settings = { ...DEFAULT_STATE.settings, ...(raw.settings || {}) };
  merged.session = { ...DEFAULT_STATE.session, ...(raw.session || {}) };
  return merged;
}

function get() {
  return state;
}

function save() {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => window.spiritAPI.saveState(state), 200);
}

function saveNow() {
  if (saveTimer) clearTimeout(saveTimer);
  return window.spiritAPI.saveState(state);
}

function patch(updater) {
  updater(state);
  save();
}

export { load, get, save, saveNow, patch };
