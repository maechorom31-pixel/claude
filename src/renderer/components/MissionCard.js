const CATEGORY_LABEL = {
  sensing: '감각',
  stillness: '호흡과 멈춤',
  literature_music: '문학과 음악',
  body: '몸',
  creation: '작은 창작',
  connection: '연결',
  doing_nothing: '무위',
  useless_play: '무용한 장난',
  visual_pause: '시각적 멈춤'
};

function render(container, mission, { onComplete, onDecline, canDecline, onPickPhoto, onStartTimer }) {
  container.innerHTML = '';
  if (!mission) {
    container.innerHTML = '<div class="card empty">지금은 카드가 없어요…</div>';
    return;
  }
  const card = document.createElement('div');
  card.className = 'card mission-card';
  card.innerHTML = `
    <div class="cat">${CATEGORY_LABEL[mission.category] || ''}</div>
    <div class="title">${mission.title}</div>
    <div class="actions"></div>
  `;
  const actions = card.querySelector('.actions');
  if (mission.verify === 'timer') {
    const btn = document.createElement('button');
    btn.className = 'primary';
    btn.textContent = `${Math.round(mission.duration / 60)}분 같이 있기`;
    btn.onclick = () => onStartTimer(mission);
    actions.appendChild(btn);
  } else if (mission.verify === 'photo') {
    const btn = document.createElement('button');
    btn.className = 'primary';
    btn.textContent = '사진 한 장 건네기';
    btn.onclick = () => onPickPhoto(mission);
    actions.appendChild(btn);
  } else {
    const btn = document.createElement('button');
    btn.className = 'primary';
    btn.textContent = '다 했어요';
    btn.onclick = () => onComplete(mission);
    actions.appendChild(btn);
  }
  if (canDecline) {
    const dec = document.createElement('button');
    dec.className = 'ghost';
    dec.textContent = '다른 카드';
    dec.onclick = () => onDecline(mission);
    actions.appendChild(dec);
  }
  container.appendChild(card);
}

export { render };
