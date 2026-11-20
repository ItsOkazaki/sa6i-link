// SPDX-License-Identifier: GPL-3.0-or-later
// Inert Electron fixture: no cleaner code, deletion, external URLs or IPC.
const { app, BrowserWindow } = require('electron')

app.disableHardwareAcceleration()
app.commandLine.appendSwitch('disable-gpu')
app.whenReady().then(() => {
  const window = new BrowserWindow({ width: 800, height: 600, show: true })
  window.loadURL('data:text/html,<title>Inert Electron Test</title><h1>Sa6i integration test fixture</h1>')
})
app.on('window-all-closed', () => app.quit())
