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
  const pet = Pet.getCurrent();
  const allCollected = !pet && Unlock.isSeason1Complete() && allSeason2Done();
  PetView.render(els.stage, { allCollected });
  if (!pet) {
    els.hint.textContent = allCollected
      ? '컬렉션 ❉ 에서 정령들과 다시 만나보세요'
      : '안개 너머에서 정령이 다가오는 중…';
  } else if (!pet.revealed) {
    els.hint.textContent = '클릭하면 첫 만남이 시작됩니다';
  } else {
    els.hint.textContent = MissionPool.inCooldown()
      ? ''
      : '정령을 살짝 누르면 카드 한 장을 건네줘요';
  }
}

function allSeason2Done() {
  if (!petsConfig) return false;
  const required = petsConfig.season2.map(p => p.type);
  const have = new Set(Storage.get().collection.map(c => c.type));
  return required.every(t => have.has(t));
}

function bindEvents() {
  els.stage.addEventListener('click', onPetClick);
  els.btnCollection.addEventListener('click', toggleCollection);
  els.btnSettings.addEventListener('click', toggleSettings);
  els.btnHide.addEventListener('click', () => window.spiritAPI.hide());
  els.btnQuit.addEventListener('click', () => window.spiritAPI.quit());
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && panelOpen) closePanel();
  });
}

async function onPetClick() {
  if (panelOpen) return;
  const pet = Pet.getCurrent();
  if (!pet) {
    const summoned = Pet.summonNewPet();
    renderPet();
    if (!summoned) toggleCollection();
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
    refreshOverlay();
    return;
  }
  offerCard();
}

function offerCard() {
  const mission = MissionPool.offerMission();
  if (!mission) {
    els.card.innerHTML = '<div class="card empty">지금은 카드가 없어요…</div>';
    refreshOverlay();
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
  refreshOverlay();
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
  refreshOverlay();
  if (result.completedPet) {
    els.hint.textContent = '정령이 책장으로 자리잡았어요';
    setTimeout(() => {
      Pet.summonNewPet();
      renderPet();
    }, 1400);
  } else {
    setTimeout(() => renderPet(), 700);
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
      refreshOverlay();
      els.hint.textContent = '괜찮아요, 다음에 다시 만나요';
    }
  });
  refreshOverlay();
}

function celebrate() {
  const img = els.stage.querySelector('.pet-img');
  if (!img) return;
  img.classList.remove('celebrate');
  void img.offsetWidth;
  img.classList.add('celebrate');
}

const COMPACT_SIZE = { w: 320, h: 420 };
const PANEL_SIZE = { w: 540, h: 780 };

function expandWindow() {
  window.spiritAPI.resize(PANEL_SIZE.w, PANEL_SIZE.h);
}
function shrinkWindow() {
  window.spiritAPI.resize(COMPACT_SIZE.w, COMPACT_SIZE.h);
}

function refreshOverlay() {
  const hasCard = !!els.card.firstElementChild;
  const hasPanel = !!els.panel.firstElementChild;
  els.app.classList.toggle('has-overlay', hasCard || hasPanel);
}

function toggleCollection() {
  if (panelOpen) {
    closePanel();
    return;
  }
  panelOpen = true;
  expandWindow();
  CollectionView.render(els.panel, {
    onClose: closePanel,
    onSelect: () => {}
  });
  refreshOverlay();
}

function toggleSettings() {
  if (panelOpen) {
    closePanel();
    return;
  }
  panelOpen = true;
  expandWindow();
  SettingsPanel.render(els.panel, { onClose: closePanel });
  refreshOverlay();
}

function closePanel() {
  els.panel.innerHTML = '';
  panelOpen = false;
  shrinkWindow();
  refreshOverlay();
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
    const slot = els.card.firstElementChild;
    const showingCooldown = slot && slot.classList.contains('cooldown-card');
    if (cd && showingCooldown) {
      CooldownView.updateTime(els.card);
    } else if (!cd && showingCooldown) {
      els.card.innerHTML = '';
      refreshOverlay();
      els.hint.textContent = '쉬는 시간이 끝났어요. 정령을 다시 만나보세요';
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
