const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { buildWindowOptions } = require('./windowConfig');

const isDev = !app.isPackaged;
let mainWindow = null;

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
  mainWindow = new BrowserWindow(buildWindowOptions());
  mainWindow.setAlwaysOnTop(true, 'floating');

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', '..', 'dist', 'renderer', 'index.html'));
  }

  mainWindow.on('closed', () => { mainWindow = null; });
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

ipcMain.on('window:drag', (_event, { dx, dy }) => {
  if (!mainWindow) return;
  const [x, y] = mainWindow.getPosition();
  mainWindow.setPosition(x + dx, y + dy);
});

ipcMain.on('window:setOpacity', (_event, value) => {
  if (!mainWindow) return;
  mainWindow.setOpacity(Math.max(0.3, Math.min(1, value)));
});

ipcMain.on('window:quit', () => app.quit());

function formatTimestamp(d) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
