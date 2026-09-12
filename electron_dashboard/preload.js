const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  readEnv: () => ipcRenderer.invoke('read-env'),
  saveEnv: (data) => ipcRenderer.invoke('save-env', data),
  startCasper: () => ipcRenderer.invoke('start-casper'),
  stopCasper: () => ipcRenderer.invoke('stop-casper'),
  checkCasperStatus: () => ipcRenderer.invoke('check-casper-status'),
  checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
  onUpdateMessage: (callback) => ipcRenderer.on('update-message', (event, msg) => callback(msg)),
  onUpdateProgress: (callback) => ipcRenderer.on('update-progress', (event, percent) => callback(percent)),
  onCasperError: (callback) => ipcRenderer.on('casper-error', (event, msg) => callback(msg))
});

contextBridge.exposeInMainWorld('electronAPI', {
  onUIState: (callback) => ipcRenderer.on('ui-state', (event, state) => callback(state))
});
