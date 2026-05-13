import { get } from './storage.js';

let petsConfig = null;
function setPetsConfig(cfg) { petsConfig = cfg; }

function getSlots() {
  const s = get();
  const slots = [];
  const season1 = [
    ...petsConfig.season1.common,
    ...petsConfig.season1.special
  ];
  for (const def of season1) {
    const found = s.collection.find(c => c.type === def.type);
    slots.push({ shelf: 1, def, entry: found || null });
  }
  for (const def of petsConfig.season2) {
    const found = s.collection.find(c => c.type === def.type);
    slots.push({ shelf: 2, def, entry: found || null });
  }
  return slots;
}

function isSeason1Done(s) {
  if (!petsConfig) return false;
  const required = [...petsConfig.season1.common, ...petsConfig.season1.special].map(p => p.type);
  const have = new Set(s.collection.map(c => c.type));
  return required.every(t => have.has(t));
}

function petDefByType(type) {
  if (!petsConfig) return null;
  const all = [...petsConfig.season1.common, ...petsConfig.season1.special, ...petsConfig.season2];
  return all.find(p => p.type === type) || null;
}

export { setPetsConfig, getSlots, isSeason1Done, petDefByType };
