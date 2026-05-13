import * as Storage from './modules/storage.js';
import * as Growth from './modules/growth.js';
import * as Unlock from './modules/unlockTrigger.js';
import * as Pet from './modules/petState.js';
import * as Collection from './modules/collection.js';
import * as MissionPool from './modules/missionPool.js';
import { completeMission } from './modules/missionLifecycle.js';
import { softenOnClick, refreshMoodFromTime, touchSeen } from './modules/moodSystem.js';
import * as PetView from './components/PetView.js';
import * as MissionCard from './components/MissionCard.js';
import * as Timer from './components/Timer.js';
import * as CooldownView from './components/CooldownView.js';
import * as CollectionView from './components/Collection.js';
import * as SettingsPanel from './components/SettingsPanel.js';
import { chime } from './modules/sound.js';

const els = {};
let petsConfig = null;
let panelOpen = false;
let cooldownTicker = null;

async function boot() {
  els.app = document.getElementById('app');
  els.stage = document.getElementById('pet-stage');
  els.hint = document.getElementById('hint');
  els.card = document.getElementById('card-slot');
  els.panel = document.getElementById('panel-slot');
  els.dragHandle = document.getElementById('drag-handle');
  els.btnCollection = document.getElementById('open-collection');
  els.btnSettings = document.getElementById('open-settings');
  els.btnHide = document.getElementById('hide-window');
  els.btnQuit = document.getElementById('quit');

  await Storage.load();
  petsConfig = await window.spiritAPI.loadPets();
  const missions = await window.spiritAPI.loadMissions();
  Growth.setPetsConfig(petsConfig);
  Unlock.setPetsConfig(petsConfig);
  Pet.setPetsConfig(petsConfig);
  Collection.setPetsConfig(petsConfig);
  MissionPool.setMissions(missions);

  refreshMoodFromTime();
  Pet.ensureCurrentPet();
  renderPet();
  bindEvents();
  startCooldownTicker();
  applyOpacityFromState();
  maybeShowIntro();
}

function applyOpacityFromState() {
  const v = Storage.get().settings.opacity;
  if (typeof v === 'number') window.spiritAPI.setOpacity(v);
}

function maybeShowIntro() {
  if (Storage.get().firstRunDone) return;
  els.hint.innerHTML = '<span class="intro">정령을 살짝 클릭해보세요 ↑</span>';
  Storage.patch(st => { st.firstRunDone = true; });
}

function renderPet() {
  PetView.render(els.stage);
  const pet = Pet.getCurrent();
  if (!pet) {
    els.hint.textContent = '안개 너머에서 정령이 다가오는 중…';
  } else if (!pet.revealed) {
    els.hint.textContent = '클릭하면 첫 만남이 시작됩니다';
  } else {
    els.hint.textContent = MissionPool.inCooldown()
      ? ''
      : '정령을 살짝 누르면 카드 한 장을 건네줘요';
  }
}

function bindEvents() {
  els.stage.addEventListener('click', onPetClick);
  els.btnCollection.addEventListener('click', toggleCollection);
  els.btnSettings.addEventListener('click', toggleSettings);
  els.btnHide.addEventListener('click', () => window.spiritAPI.hide());
  els.btnQuit.addEventListener('click', () => window.spiritAPI.quit());
  setupDrag();
}

function setupDrag() {
  let dragging = false;
  let last = { x: 0, y: 0 };
  els.dragHandle.addEventListener('mousedown', (e) => {
    dragging = true;
    last = { x: e.screenX, y: e.screenY };
  });
  window.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    const dx = e.screenX - last.x;
    const dy = e.screenY - last.y;
    last = { x: e.screenX, y: e.screenY };
    window.spiritAPI.dragWindow(dx, dy);
  });
  window.addEventListener('mouseup', () => { dragging = false; });
}

async function onPetClick() {
  if (panelOpen) return;
  const pet = Pet.getCurrent();
  if (!pet) {
    Pet.summonNewPet();
    renderPet();
    return;
  }
  if (!pet.revealed) {
    Pet.revealPet();
    renderPet();
    els.hint.textContent = `${getPetDef(pet.type).name}이(가) 나타났어요`;
    setTimeout(() => offerCard(), 800);
    return;
  }
  softenOnClick();
  touchSeen();
  if (MissionPool.inCooldown()) {
    renderPet();
    CooldownView.render(els.card);
    return;
  }
  offerCard();
}

function offerCard() {
  const mission = MissionPool.offerMission();
  if (!mission) {
    els.card.innerHTML = '<div class="card empty">지금은 카드가 없어요…</div>';
    return;
  }
  const canDecline = (Storage.get().session.declinesThisCycle || 0) < 1;
  MissionCard.render(els.card, mission, {
    onComplete: handleComplete,
    onDecline: handleDecline,
    canDecline,
    onPickPhoto: handleComplete,
    onStartTimer: handleStartTimer
  });
}

async function handleComplete(mission) {
  const result = await completeMission(mission.id);
  if (!result.ok) {
    if (result.reason === 'no_photo') {
      els.hint.textContent = '사진을 고르지 않았어요';
    }
    return;
  }
  celebrate();
  chime();
  els.card.innerHTML = '';
  renderPet();
  if (result.completedPet) {
    setTimeout(() => {
      els.hint.textContent = '정령이 책장으로 자리잡았어요';
      Pet.summonNewPet();
      renderPet();
    }, 1400);
  } else {
    els.hint.textContent = '잘 쉬었어요. 60분 후에 다시 만나요';
  }
}

function handleDecline() {
  const r = MissionPool.declinePending();
  if (!r.ok) {
    els.hint.textContent = '오늘 사이클에선 한 번만 다른 카드를 받을 수 있어요';
    return;
  }
  offerCard();
}

function handleStartTimer(mission) {
  Timer.render(els.card, mission, {
    onFinish: () => handleComplete(mission),
    onCancel: () => {
      els.card.innerHTML = '';
      MissionPool.clearPending();
      els.hint.textContent = '괜찮아요, 다음에 다시 만나요';
    }
  });
}

function celebrate() {
  const img = els.stage.querySelector('.pet-img');
  if (!img) return;
  img.classList.remove('celebrate');
  void img.offsetWidth;
  img.classList.add('celebrate');
}

function toggleCollection() {
  if (panelOpen) {
    els.panel.innerHTML = '';
    panelOpen = false;
    return;
  }
  panelOpen = true;
  CollectionView.render(els.panel, {
    onClose: closePanel,
    onSelect: () => {}
  });
}

function toggleSettings() {
  if (panelOpen) {
    closePanel();
    return;
  }
  panelOpen = true;
  SettingsPanel.render(els.panel, { onClose: closePanel });
}

function closePanel() {
  els.panel.innerHTML = '';
  panelOpen = false;
}

function getPetDef(type) {
  if (!petsConfig) return null;
  const all = [
    ...petsConfig.season1.common,
    ...petsConfig.season1.special,
    ...petsConfig.season2
  ];
  return all.find(p => p.type === type) || { name: '정령' };
}

let lastCooldownState = false;
function startCooldownTicker() {
  lastCooldownState = MissionPool.inCooldown();
  cooldownTicker = setInterval(() => {
    if (panelOpen) return;
    const cd = MissionPool.inCooldown();
    if (cd) {
      const slot = els.card.firstElementChild;
      if (slot && slot.classList.contains('cooldown-card')) {
        CooldownView.render(els.card);
      }
    } else {
      const slot = els.card.firstElementChild;
      if (slot && slot.classList.contains('cooldown-card')) {
        els.card.innerHTML = '';
        els.hint.textContent = '쉬는 시간이 끝났어요. 정령을 다시 만나보세요';
      }
    }
    if (cd !== lastCooldownState) {
      renderPet();
      lastCooldownState = cd;
    }
  }, 1000);
}

boot().catch(err => {
  console.error(err);
  document.body.innerHTML = `<pre style="padding:20px;color:#a44">${err.stack || err.message}</pre>`;
});
