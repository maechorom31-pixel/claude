const { app, BrowserWindow, ipcMain, dialog, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');
const { buildWindowOptions } = require('./windowConfig');

const isDev = !app.isPackaged;
let mainWindow = null;
let tray = null;

function resolveAssetPath(...parts) {
  if (isDev) return path.join(__dirname, '..', '..', 'assets', ...parts);
  return path.join(process.resourcesPath, 'assets', ...parts);
}

function userDataPath(...parts) {
  return path.join(app.getPath('userData'), ...parts);
}

function ensurePhotoDir() {
  const dir = userDataPath('photos');
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function statePath() {
  return userDataPath('state.json');
}

function resolveDataFile(name) {
  if (isDev) return path.join(__dirname, '..', '..', 'data', name);
  return path.join(process.resourcesPath, 'data', name);
}

function createWindow() {
  const opts = buildWindowOptions();
  opts.icon = resolveAssetPath('icons', 'app.png');
  mainWindow = new BrowserWindow(opts);
  mainWindow.setAlwaysOnTop(true, 'floating');

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', '..', 'dist', 'renderer', 'index.html'));
  }

  mainWindow.on('close', (e) => {
    if (!app.isQuiting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
  mainWindow.on('closed', () => { mainWindow = null; });
}

function createTray() {
  const iconPath = resolveAssetPath('icons', 'tray.png');
  const image = nativeImage.createFromPath(iconPath);
  tray = new Tray(image);
  tray.setToolTip('작은 정령들');
  const menu = Menu.buildFromTemplate([
    { label: '정령 보기', click: () => showWindow() },
    { label: '잠시 숨기기', click: () => mainWindow && mainWindow.hide() },
    { type: 'separator' },
    { label: '종료', click: () => { app.isQuiting = true; app.quit(); } }
  ]);
  tray.setContextMenu(menu);
  tray.on('click', () => {
    if (!mainWindow) return;
    if (mainWindow.isVisible()) mainWindow.hide();
    else showWindow();
  });
}

function showWindow() {
  if (!mainWindow) return;
  mainWindow.show();
  mainWindow.setAlwaysOnTop(true, 'floating');
}

ipcMain.handle('state:load', async () => {
  try {
    const raw = fs.readFileSync(statePath(), 'utf-8');
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
});

ipcMain.handle('state:save', async (_event, state) => {
  fs.writeFileSync(statePath(), JSON.stringify(state, null, 2), 'utf-8');
  return true;
});

ipcMain.handle('data:pets', async () => {
  return JSON.parse(fs.readFileSync(resolveDataFile('pets.json'), 'utf-8'));
});

ipcMain.handle('data:missions', async () => {
  return JSON.parse(fs.readFileSync(resolveDataFile('missions.json'), 'utf-8'));
});

ipcMain.handle('photo:pick', async (_event, { petType }) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [{ name: 'Images', extensions: ['jpg', 'jpeg', 'png', 'gif', 'webp'] }]
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  const src = result.filePaths[0];
  const ext = path.extname(src).toLowerCase().replace('.', '') || 'jpg';
  const ts = formatTimestamp(new Date());
  const filename = `${ts}_${petType}.${ext}`;
  const dest = path.join(ensurePhotoDir(), filename);
  fs.copyFileSync(src, dest);
  return { filename, fullPath: dest };
});

ipcMain.handle('photo:read', async (_event, filename) => {
  const full = path.join(ensurePhotoDir(), filename);
  if (!fs.existsSync(full)) return null;
  const buf = fs.readFileSync(full);
  const ext = path.extname(filename).toLowerCase().replace('.', '');
  const mime = ext === 'png' ? 'image/png' : ext === 'gif' ? 'image/gif' : ext === 'webp' ? 'image/webp' : 'image/jpeg';
  return `data:${mime};base64,${buf.toString('base64')}`;
});

ipcMain.on('window:setOpacity', (_event, value) => {
  if (!mainWindow) return;
  mainWindow.setOpacity(Math.max(0.3, Math.min(1, value)));
});

ipcMain.on('window:resize', (_event, { width, height }) => {
  if (!mainWindow) return;
  const [x, y] = mainWindow.getPosition();
  const [oldW, oldH] = mainWindow.getSize();
  const newX = x + oldW - width;
  const newY = y + oldH - height;
  mainWindow.setBounds({
    x: Math.max(0, newX),
    y: Math.max(0, newY),
    width,
    height
  }, true);
});

ipcMain.on('window:quit', () => { app.isQuiting = true; app.quit(); });
ipcMain.on('window:hide', () => { if (mainWindow) mainWindow.hide(); });

function formatTimestamp(d) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (!mainWindow.isVisible()) mainWindow.show();
      mainWindow.focus();
    }
  });
  app.whenReady().then(() => {
    createWindow();
    createTray();
  });
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
