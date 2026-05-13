import { get, patch } from '../modules/storage.js';

function render(container, { onClose }) {
  const s = get();
  container.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.className = 'panel settings-panel';
  wrap.innerHTML = `
    <div class="panel-header">
      <span class="title">설정</span>
      <button class="ghost close">닫기</button>
    </div>
    <div class="setting-row">
      <label>위젯 투명도</label>
      <input type="range" min="0.4" max="1" step="0.02" value="${s.settings.opacity}" id="opacity-slider"/>
      <span class="value" id="opacity-value">${Math.round(s.settings.opacity * 100)}%</span>
    </div>
    <div class="setting-row toggle">
      <label for="sound-toggle">완료 시 작은 소리</label>
      <input type="checkbox" id="sound-toggle" ${s.settings.soundOn ? 'checked' : ''}/>
    </div>
    <div class="setting-help">
      <p>창 위쪽 작은 점을 잡으면 위젯을 옮길 수 있어요.</p>
      <p>잠시 숨기려면 ⊖ 버튼이나 트레이 아이콘을 사용하세요.</p>
    </div>
  `;
  wrap.querySelector('.close').onclick = onClose;
  const slider = wrap.querySelector('#opacity-slider');
  const valEl = wrap.querySelector('#opacity-value');
  slider.addEventListener('input', () => {
    const v = parseFloat(slider.value);
    valEl.textContent = `${Math.round(v * 100)}%`;
    window.spiritAPI.setOpacity(v);
    patch(st => { st.settings.opacity = v; });
  });
  const sound = wrap.querySelector('#sound-toggle');
  sound.addEventListener('change', () => {
    patch(st => { st.settings.soundOn = sound.checked; });
  });
  container.appendChild(wrap);
}

export { render };
