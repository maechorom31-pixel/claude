import { get, patch } from './storage.js';
import { markRecent, startCooldown, clearPending, getById } from './missionPool.js';
import { addRestPoint, attachPhoto, completeAndMoveToCollection } from './petState.js';
import { restoreOnMission } from './moodSystem.js';
import { isComplete } from './growth.js';
import { currentTimeBand } from './timeFilter.js';

function applyStatBonuses(mission, now = new Date()) {
  patch(st => {
    st.stats.totalMissionsCompleted = (st.stats.totalMissionsCompleted || 0) + 1;
    st.stats.missionsByCategory[mission.category] = (st.stats.missionsByCategory[mission.category] || 0) + 1;
    if (mission.statBonus && st.stats[mission.statBonus] !== undefined) {
      st.stats[mission.statBonus] += 1;
    }
    const band = currentTimeBand(now);
    if (band === 'sunset') st.stats.sunsetMeets = (st.stats.sunsetMeets || 0) + 1;
    if (band === 'night') st.stats.nightMeets = (st.stats.nightMeets || 0) + 1;
  });
}

async function attachPhotoIfAny(mission) {
  if (mission.verify !== 'photo') return null;
  const current = get().currentPet;
  if (!current) return null;
  const picked = await window.spiritAPI.pickPhoto(current.type);
  if (!picked) return null;
  attachPhoto(picked.filename);
  patch(st => { st.stats.photoUploads = (st.stats.photoUploads || 0) + 1; });
  return picked.filename;
}

async function completeMission(missionId) {
  const mission = getById(missionId);
  if (!mission) return { ok: false };
  let photoFilename = null;
  if (mission.verify === 'photo') {
    photoFilename = await attachPhotoIfAny(mission);
    if (!photoFilename) return { ok: false, reason: 'no_photo' };
  }
  applyStatBonuses(mission);
  addRestPoint();
  restoreOnMission();
  markRecent(missionId);
  startCooldown();
  clearPending();
  let completed = false;
  if (isComplete(get().currentPet.restPoints)) {
    completeAndMoveToCollection();
    completed = true;
  }
  return { ok: true, completedPet: completed, photoFilename };
}

export { completeMission };
