import { getSlots } from '../modules/collection.js';
import { renderGallery } from './PhotoUpload.js';

function petAssetPath(type, stage = 4) {
  return `pets/${type}/stage${stage}.svg`;
}

function render(container, { onClose, onSelect }) {
  container.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.className = 'panel collection-panel';
  wrap.innerHTML = `
    <div class="panel-header">
      <span class="title">컬렉션</span>
      <button class="ghost close">닫기</button>
    </div>
    <div class="shelves"></div>
    <div class="memo-area"></div>
  `;
  const close = wrap.querySelector('.close');
  close.onclick = onClose;
  const shelves = wrap.querySelector('.shelves');
  const memoArea = wrap.querySelector('.memo-area');
  const slots = getSlots();
  const byShelf = new Map();
  for (const slot of slots) {
    if (!byShelf.has(slot.shelf)) byShelf.set(slot.shelf, []);
    byShelf.get(slot.shelf).push(slot);
  }
  for (const [shelfNum, list] of byShelf) {
    const shelf = document.createElement('div');
    shelf.className = 'shelf';
    shelf.innerHTML = `<div class="shelf-label">시즌 ${shelfNum}</div>`;
    const row = document.createElement('div');
    row.className = 'shelf-row';
    for (const slot of list) {
      const cell = document.createElement('div');
      cell.className = `slot ${slot.entry ? 'filled' : 'empty'}`;
      if (slot.entry) {
        cell.innerHTML = `<img src="${petAssetPath(slot.def.type, 4)}" alt=""/>`;
        cell.title = slot.def.name;
        cell.onclick = () => openMemo(memoArea, slot);
      } else {
        cell.innerHTML = `<div class="slot-placeholder"></div>`;
      }
      row.appendChild(cell);
    }
    shelf.appendChild(row);
    shelves.appendChild(shelf);
  }
  container.appendChild(wrap);
}

async function openMemo(area, slot) {
  area.innerHTML = `
    <div class="memo">
      <div class="memo-title">${slot.def.name}</div>
      <div class="memo-line">${slot.def.tagline}</div>
      <div class="memo-photos"></div>
    </div>
  `;
  await renderGallery(area.querySelector('.memo-photos'), slot.entry.photos);
}

export { render };
