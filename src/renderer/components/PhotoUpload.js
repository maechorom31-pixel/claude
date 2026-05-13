async function loadThumb(filename) {
  if (!filename) return '';
  return await window.spiritAPI.readPhoto(filename);
}

async function renderGallery(container, photoFilenames) {
  container.innerHTML = '';
  if (!photoFilenames || photoFilenames.length === 0) {
    container.innerHTML = '<div class="empty">아직 사진이 없어요</div>';
    return;
  }
  const grid = document.createElement('div');
  grid.className = 'photo-grid';
  for (const fn of photoFilenames) {
    const dataUrl = await loadThumb(fn);
    if (!dataUrl) continue;
    const img = document.createElement('img');
    img.src = dataUrl;
    img.className = 'photo-thumb';
    grid.appendChild(img);
  }
  container.appendChild(grid);
}

export { renderGallery };
