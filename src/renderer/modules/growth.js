import { get } from './storage.js';

let petsConfig = null;

function setPetsConfig(cfg) { petsConfig = cfg; }

function thresholds() {
  return (petsConfig && petsConfig.growth && petsConfig.growth.pointsPerStage) || [0, 13, 25, 38, 50];
}

function calcStage(restPoints) {
  const t = thresholds();
  for (let i = t.length - 1; i >= 0; i--) {
    if (restPoints >= t[i]) return Math.min(i, 4);
  }
  return 0;
}

function isComplete(restPoints) {
  const t = thresholds();
  return restPoints >= t[t.length - 1];
}

function pointsToNext(restPoints) {
  const t = thresholds();
  const stage = calcStage(restPoints);
  if (stage >= 4) return 0;
  return Math.max(0, t[stage + 1] - restPoints);
}

export { setPetsConfig, calcStage, isComplete, pointsToNext, thresholds };
