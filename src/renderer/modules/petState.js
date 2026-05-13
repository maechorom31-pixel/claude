import { get, patch } from './storage.js';
import { calcStage, isComplete } from './growth.js';
import { pickNextPet, markMet } from './unlockTrigger.js';

let petsConfig = null;
function setPetsConfig(cfg) { petsConfig = cfg; }

function getPetDef(type) {
  if (!petsConfig) return null;
  const all = [
    ...petsConfig.season1.common,
    ...petsConfig.season1.special,
    ...petsConfig.season2
  ];
  return all.find(p => p.type === type) || null;
}

function ensureCurrentPet() {
  const s = get();
  if (s.currentPet) return s.currentPet;
  return summonNewPet();
}

function summonNewPet() {
  const next = pickNextPet();
  if (!next) return null;
  const fresh = {
    type: next.type,
    growthStage: 0,
    restPoints: 0,
    lastSeenAt: new Date().toISOString(),
    mood: 'fog',
    startedAt: new Date().toISOString(),
    photos: [],
    revealed: false
  };
  patch(st => { st.currentPet = fresh; });
  markMet(next.type);
  return fresh;
}

function revealPet() {
  patch(st => {
    if (st.currentPet) {
      st.currentPet.revealed = true;
      st.currentPet.mood = 'normal';
    }
  });
}

function addRestPoint() {
  patch(st => {
    if (!st.currentPet) return;
    st.currentPet.restPoints += 1;
    st.currentPet.growthStage = calcStage(st.currentPet.restPoints);
    st.currentPet.lastSeenAt = new Date().toISOString();
    if (!st.currentPet.revealed) st.currentPet.revealed = true;
  });
}

function attachPhoto(filename) {
  patch(st => {
    if (!st.currentPet) return;
    st.currentPet.photos = [...(st.currentPet.photos || []), filename];
  });
}

function completeAndMoveToCollection() {
  patch(st => {
    if (!st.currentPet) return;
    if (!isComplete(st.currentPet.restPoints)) return;
    const entry = {
      type: st.currentPet.type,
      completedAt: new Date().toISOString(),
      photos: st.currentPet.photos || [],
      memos: [],
      startedAt: st.currentPet.startedAt
    };
    st.collection.push(entry);
    st.currentPet = null;
  });
}

function getCurrent() {
  return get().currentPet;
}

export {
  setPetsConfig, getPetDef, ensureCurrentPet, summonNewPet, revealPet,
  addRestPoint, attachPhoto, completeAndMoveToCollection, getCurrent
};
