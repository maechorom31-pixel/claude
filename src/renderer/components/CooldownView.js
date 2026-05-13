import { cooldownRemainingMs } from '../modules/missionPool.js';

function fmt(ms) {
  const s = Math.ceil(ms / 1000);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}분 ${String(r).padStart(2, '0')}초`;
}

function render(container) {
  const ms = cooldownRemainingMs();
  container.innerHTML = `
    <div class="card cooldown-card">
      <div class="z">zZ</div>
      <div class="msg">아직 쉬는 중이야, 잠시 후에 봐</div>
      <div class="sub">${fmt(ms)} 후 다시 만나요</div>
    </div>
  `;
}

export { render };
