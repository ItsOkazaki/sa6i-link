// SPDX-License-Identifier: GPL-3.0-or-later
// Inert Electron fixture: no cleaner code, deletion, external URLs or IPC.
const { app, BrowserWindow } = require('electron')

app.disableHardwareAcceleration()
app.commandLine.appendSwitch('disable-gpu')
app.whenReady().then(() => {
  // Approximate the packaged cleaner's window geometry and title-bar options;
  // this is still an inert app and not the cleaner or its renderer.
  const window = new BrowserWindow({
    width: 1320, height: 840, minWidth: 1120, minHeight: 740,
    show: false, backgroundColor: '#101720', titleBarStyle: 'hidden',
    titleBarOverlay: { color: '#00000000', symbolColor: '#ffffff', height: 44 },
    webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false }
  })
  window.once('ready-to-show', () => window.show())
  window.loadURL('data:text/html,<title>Inert Electron Test</title><h1>Sa6i integration test fixture</h1>')
})
app.on('window-all-closed', () => app.quit())
