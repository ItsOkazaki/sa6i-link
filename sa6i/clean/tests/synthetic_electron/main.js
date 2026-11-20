// SPDX-License-Identifier: GPL-3.0-or-later
// Inert Electron fixture: no cleaner code, deletion, external URLs or IPC.
const { app, BrowserWindow } = require('electron')
const fs = require('fs')
const path = require('path')

// Exercise Chromium's default rendering path too. The real cleaner does not
// disable GPU acceleration, so a software-only smoke test cannot represent it.
// This flag is test-only and still does not make this the real cleaner.
if (process.env.SA6I_SYNTHETIC_SOFTWARE === '1') {
  app.disableHardwareAcceleration()
  app.commandLine.appendSwitch('disable-gpu')
}
app.whenReady().then(() => {
  // Record only the synthetic app's actual profile path, for this CI test.
  const profile = app.getPath('userData')
  fs.writeFileSync(path.join(profile, 'synthetic-profile-path.txt'), profile)
  const theme = process.argv.includes('--sa6i-theme-dark') ? 'dark'
    : process.argv.includes('--sa6i-theme-light') ? 'light' : 'system'
  fs.writeFileSync(path.join(profile, 'synthetic-theme.txt'), theme)
  // Approximate the packaged cleaner's window geometry and title-bar options;
  // this is still an inert app and not the cleaner or its renderer.
  const window = new BrowserWindow({
    width: 1320, height: 840, minWidth: 1120, minHeight: 740,
    show: false, backgroundColor: '#101720', frame: false,
    webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false }
  })
  window.once('ready-to-show', () => window.show())
  window.loadURL('data:text/html,<title>Inert Electron Test</title><h1>Sa6i integration test fixture</h1>')
})
app.on('window-all-closed', () => app.quit())
