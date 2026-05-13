import { getCurrent } from '../modules/petState.js';
import { computeMood } from '../modules/moodSystem.js';
import { inCooldown } from '../modules/missionPool.js';

function petAssetPath(type, stage) {
  return `pets/${type}/stage${Math.min(4, Math.max(1, stage + 1))}.svg`;
}

function render(container, opts = {}) {
  const pet = getCurrent();
  container.innerHTML = '';
  if (!pet) {
    if (opts.allCollected) {
      container.innerHTML = '<div class="pet-empty">모든 정령과 함께한 한 시기가 지나갔어요.<br/>책장을 천천히 열어보세요.</div>';
    } else {
      container.innerHTML = '<div class="pet-empty">새 정령이 안개 속에서 다가오는 중…</div>';
    }
    return;
  }
  const mood = computeMood();
  const stage = pet.revealed ? pet.growthStage : 0;
  const sleeping = pet.revealed && inCooldown();
  const wrap = document.createElement('div');
  wrap.className = `pet-view mood-${mood}`;
  if (!pet.revealed) wrap.classList.add('unrevealed');
  if (sleeping) wrap.classList.add('sleeping');
  wrap.innerHTML = `
    <div class="pet-aura"></div>
    <img class="pet-img" src="${petAssetPath(pet.type, stage)}" alt="" draggable="false"/>
    ${sleeping ? '<div class="pet-zz"><span>z</span><span>z</span><span>Z</span></div>' : ''}
    <div class="pet-cheek">${moodHint(mood, pet.revealed, sleeping)}</div>
  `;
  container.appendChild(wrap);
}

function moodHint(mood, revealed, sleeping) {
  if (!revealed) return '안개 너머 무언가가…';
  if (sleeping) return '쉬는 중…';
  switch (mood) {
    case 'wilted2': return '한참 못 봤네…';
    case 'wilted1': return '조금 쓸쓸해 보여요';
    case 'recovering': return '조금씩 풀려요';
    default: return '';
  }
}

export { render };
