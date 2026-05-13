import { get, patch } from './storage.js';

let petsConfig = null;
function setPetsConfig(cfg) { petsConfig = cfg; }

function allSeason1Pets() {
  if (!petsConfig) return [];
  return [...petsConfig.season1.common, ...petsConfig.season1.special];
}

function eligibleSeason1() {
  if (!petsConfig) return [];
  const s = get();
  const seen = new Set(s.collection.map(c => c.type));
  const metSpecial = new Set(s.metSpecials || []);
  const result = [];
  for (const p of petsConfig.season1.common) {
    if (seen.has(p.type)) continue;
    result.push(p);
  }
  for (const p of petsConfig.season1.special) {
    if (seen.has(p.type)) continue;
    if (!checkUnlock(p.unlock, s)) continue;
    if (metSpecial.has(p.type)) continue;
    result.push(p);
  }
  return result;
}

function eligibleSeason2() {
  if (!petsConfig) return [];
  const s = get();
  const seen = new Set(s.collection.map(c => c.type));
  const met = new Set(s.metSeason2 || []);
  return petsConfig.season2.filter(p =>
    !seen.has(p.type) && !met.has(p.type) && checkUnlock(p.unlock, s)
  );
}

function checkUnlock(unlock, s) {
  if (!unlock) return true;
  switch (unlock.kind) {
    case 'starter':
      return true;
    case 'stat':
      return (s.stats[unlock.stat] || 0) >= unlock.threshold;
    case 'category':
      return (s.stats.missionsByCategory[unlock.category] || 0) >= unlock.threshold;
    case 'photos':
      return (s.stats.photoUploads || 0) >= unlock.threshold;
    case 'categoryRepeat': {
      const counts = Object.values(s.stats.missionsByCategory || {});
      return counts.some(c => c >= unlock.threshold);
    }
    default:
      return false;
  }
}

function pickNextPet() {
  const s = get();
  const season1Done = isSeason1Complete();
  if (season1Done && s.season < 2) {
    patch(st => { st.season = 2; });
  }
  if (s.season === 2 || season1Done) {
    const pool = eligibleSeason2();
    if (pool.length > 0) return pool[Math.floor(Math.random() * pool.length)];
  }
  const pool = eligibleSeason1();
  if (pool.length > 0) {
    const specials = pool.filter(p => petsConfig.season1.special.some(sp => sp.type === p.type));
    if (specials.length > 0 && Math.random() < 0.7) {
      return specials[Math.floor(Math.random() * specials.length)];
    }
    return pool[Math.floor(Math.random() * pool.length)];
  }
  return null;
}

function isSeason1Complete() {
  const s = get();
  if (!petsConfig) return false;
  const allTypes = allSeason1Pets().map(p => p.type);
  const collected = new Set(s.collection.map(c => c.type));
  return allTypes.every(t => collected.has(t));
}

function markMet(type) {
  patch(st => {
    if (petsConfig && petsConfig.season2.some(p => p.type === type)) {
      st.metSeason2 = Array.from(new Set([...(st.metSeason2 || []), type]));
    } else {
      st.metSpecials = Array.from(new Set([...(st.metSpecials || []), type]));
    }
  });
}

export { setPetsConfig, pickNextPet, eligibleSeason1, eligibleSeason2, isSeason1Complete, markMet, checkUnlock };
