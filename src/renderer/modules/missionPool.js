import { get, patch } from './storage.js';
import { isMissionAvailable } from './timeFilter.js';

let missions = [];
const RECENT_AVOID = 5;
const COOLDOWN_MS = 60 * 60 * 1000;

function setMissions(list) { missions = list; }

function getById(id) { return missions.find(m => m.id === id); }

function cooldownRemainingMs() {
  const s = get();
  const last = s.session.lastMissionCompletedAt;
  if (!last) return 0;
  const elapsed = Date.now() - new Date(last).getTime();
  return Math.max(0, COOLDOWN_MS - elapsed);
}

function inCooldown() { return cooldownRemainingMs() > 0; }

function pickMission(now = new Date()) {
  const s = get();
  const recent = new Set(s.session.recentMissionIds || []);
  let pool = missions.filter(m => isMissionAvailable(m, now) && !recent.has(m.id));
  if (pool.length === 0) {
    pool = missions.filter(m => isMissionAvailable(m, now));
  }
  if (pool.length === 0) return null;
  return pool[Math.floor(Math.random() * pool.length)];
}

function offerMission(now = new Date()) {
  const s = get();
  if (s.session.pendingMissionId) {
    const existing = getById(s.session.pendingMissionId);
    if (existing) return existing;
  }
  const m = pickMission(now);
  if (m) {
    patch(st => { st.session.pendingMissionId = m.id; });
  }
  return m;
}

function declinePending() {
  const s = get();
  if (s.session.declinesThisCycle >= 1) return { ok: false, reason: 'limit' };
  const previousId = s.session.pendingMissionId;
  patch(st => {
    st.session.declinesThisCycle = (st.session.declinesThisCycle || 0) + 1;
    st.session.pendingMissionId = null;
  });
  const next = pickMission();
  if (next) {
    patch(st => { st.session.pendingMissionId = next.id; });
  }
  return { ok: true, mission: next, previousId };
}

function clearPending() {
  patch(st => { st.session.pendingMissionId = null; });
}

function markRecent(missionId) {
  patch(st => {
    const list = st.session.recentMissionIds || [];
    const next = [missionId, ...list.filter(id => id !== missionId)].slice(0, RECENT_AVOID);
    st.session.recentMissionIds = next;
  });
}

function startCooldown() {
  patch(st => {
    st.session.lastMissionCompletedAt = new Date().toISOString();
    st.session.declinesThisCycle = 0;
    st.session.pendingMissionId = null;
  });
}

export {
  setMissions, getById, pickMission, offerMission, declinePending,
  clearPending, markRecent, startCooldown, inCooldown, cooldownRemainingMs
};
