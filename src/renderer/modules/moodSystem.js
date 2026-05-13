import { get, patch } from './storage.js';

const DAY = 24 * 60 * 60 * 1000;

function daysSinceSeen() {
  const s = get();
  if (!s.currentPet || !s.currentPet.lastSeenAt) return 0;
  return (Date.now() - new Date(s.currentPet.lastSeenAt).getTime()) / DAY;
}

function computeMood() {
  const days = daysSinceSeen();
  if (days >= 7) return 'wilted2';
  if (days >= 3) return 'wilted1';
  return 'normal';
}

function refreshMoodFromTime() {
  patch(st => {
    if (!st.currentPet) return;
    const days = daysSinceSeen();
    if (days >= 7) st.currentPet.mood = 'wilted2';
    else if (days >= 3) st.currentPet.mood = 'wilted1';
  });
}

function softenOnClick() {
  patch(st => {
    if (!st.currentPet) return;
    if (st.currentPet.mood === 'wilted2') st.currentPet.mood = 'wilted1';
    else if (st.currentPet.mood === 'wilted1') st.currentPet.mood = 'recovering';
  });
}

function restoreOnMission() {
  patch(st => {
    if (!st.currentPet) return;
    st.currentPet.mood = 'normal';
    st.currentPet.lastSeenAt = new Date().toISOString();
  });
}

function touchSeen() {
  patch(st => {
    if (!st.currentPet) return;
    st.currentPet.lastSeenAt = new Date().toISOString();
  });
}

export { computeMood, refreshMoodFromTime, softenOnClick, restoreOnMission, touchSeen, daysSinceSeen };
