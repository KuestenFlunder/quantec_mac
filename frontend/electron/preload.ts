import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  onBackendReady: (callback: () => void) => ipcRenderer.on('backend-ready', callback),
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
});
