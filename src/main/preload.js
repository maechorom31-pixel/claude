const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('spiritAPI', {
  loadState: () => ipcRenderer.invoke('state:load'),
  saveState: (state) => ipcRenderer.invoke('state:save', state),
  loadPets: () => ipcRenderer.invoke('data:pets'),
  loadMissions: () => ipcRenderer.invoke('data:missions'),
  pickPhoto: (petType) => ipcRenderer.invoke('photo:pick', { petType }),
  readPhoto: (filename) => ipcRenderer.invoke('photo:read', filename),
  setOpacity: (v) => ipcRenderer.send('window:setOpacity', v),
  resize: (width, height) => ipcRenderer.send('window:resize', { width, height }),
  hide: () => ipcRenderer.send('window:hide'),
  quit: () => ipcRenderer.send('window:quit')
});
