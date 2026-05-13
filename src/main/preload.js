const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('spiritAPI', {
  loadState: () => ipcRenderer.invoke('state:load'),
  saveState: (state) => ipcRenderer.invoke('state:save', state),
  loadPets: () => ipcRenderer.invoke('data:pets'),
  loadMissions: () => ipcRenderer.invoke('data:missions'),
  pickPhoto: (petType) => ipcRenderer.invoke('photo:pick', { petType }),
  readPhoto: (filename) => ipcRenderer.invoke('photo:read', filename),
  dragWindow: (dx, dy) => ipcRenderer.send('window:drag', { dx, dy }),
  setOpacity: (v) => ipcRenderer.send('window:setOpacity', v),
  hide: () => ipcRenderer.send('window:hide'),
  quit: () => ipcRenderer.send('window:quit')
});
