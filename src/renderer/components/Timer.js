function render(container, mission, { onFinish, onCancel }) {
  container.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.className = 'card timer-card';
  wrap.innerHTML = `
    <div class="cat">${mission.title}</div>
    <div class="breathing"><div class="circle"></div></div>
    <div class="time-left"></div>
    <div class="actions">
      <button class="ghost cancel">그만</button>
    </div>
  `;
  const timeEl = wrap.querySelector('.time-left');
  const cancelBtn = wrap.querySelector('.cancel');
  let remaining = mission.duration;
  let running = true;
  function fmt(s) {
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m}:${String(r).padStart(2, '0')}`;
  }
  timeEl.textContent = fmt(remaining);
  const interval = setInterval(() => {
    if (!running) return;
    remaining -= 1;
    timeEl.textContent = fmt(Math.max(0, remaining));
    if (remaining <= 0) {
      running = false;
      clearInterval(interval);
      onFinish();
    }
  }, 1000);
  cancelBtn.onclick = () => {
    running = false;
    clearInterval(interval);
    onCancel();
  };
  container.appendChild(wrap);
}

export { render };
