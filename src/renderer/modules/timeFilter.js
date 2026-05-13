function currentTimeBand(now = new Date()) {
  const h = now.getHours();
  if (h >= 9 && h < 17) return 'day';
  if (h >= 18 && h < 20) return 'sunset';
  if (h >= 22 || h < 1) return 'night';
  return 'general';
}

function isMissionAvailable(mission, now = new Date()) {
  if (!mission.timeOfDay) return true;
  const band = currentTimeBand(now);
  if (mission.timeOfDay === 'day') return band === 'day';
  if (mission.timeOfDay === 'sunset') return band === 'sunset';
  if (mission.timeOfDay === 'night') return band === 'night';
  return true;
}

export { currentTimeBand, isMissionAvailable };
