const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { autoUpdater } = require('electron-updater');
const { spawn } = require('child_process');
const dgram = require('dgram');

const ENV_PATH = app.isPackaged 
  ? path.join(app.getPath('userData'), '.env')
  : path.join(__dirname, '..', '.env');
const OLD_ENV_PATH = app.isPackaged 
  ? path.join(process.resourcesPath, '.env') 
  : path.join(__dirname, '..', '.env');

let overlayWindow = null;
let udpServer = null;

function createOverlay() {
  if (overlayWindow) return;
  
  const { screen } = require('electron');
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;
  const WIN_W = 320;
  const WIN_H = 320;

  overlayWindow = new BrowserWindow({
    width: WIN_W,
    height: WIN_H,
    x: width - WIN_W - 10,
    y: Math.round((height - WIN_H) / 2),
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    focusable: false,
    skipTaskbar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  overlayWindow.setIgnoreMouseEvents(true, { forward: true });
  const uiPath = app.isPackaged
    ? path.join(process.resourcesPath, 'jarvis_ui_side.html')
    : path.join(__dirname, '..', 'jarvis_ui_side.html');
  overlayWindow.loadFile(uiPath);

  if (!udpServer) {
    udpServer = dgram.createSocket('udp4');
    udpServer.on('message', (msg) => {
      const state = msg.toString().trim();
      if (overlayWindow) {
        overlayWindow.webContents.send('ui-state', state);
      }
    });
    udpServer.bind(49152);
  }
}

function destroyOverlay() {
  if (overlayWindow) {
    overlayWindow.close();
    overlayWindow = null;
  }
  if (udpServer) {
    udpServer.close();
    udpServer = null;
  }
}

const ENV_EXAMPLE_PATH = app.isPackaged 
  ? path.join(process.resourcesPath, '.env.example')
  : path.join(__dirname, '..', '.env.example');

// Migrate old .env from resources path to userData if it exists (for users updating to this version)
if (app.isPackaged) {
  if (fs.existsSync(OLD_ENV_PATH) && !fs.existsSync(ENV_PATH)) {
    try {
      fs.copyFileSync(OLD_ENV_PATH, ENV_PATH);
    } catch (e) {
      console.error('Failed to migrate .env', e);
    }
  }
}

function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1000,
    height: 800,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    },
    icon: path.join(__dirname, 'icon.ico')
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    require('electron').shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.loadFile('index.html');

  // Auto Updater logic
  autoUpdater.forceDevUpdateConfig = true;
  
  autoUpdater.on('checking-for-update', () => {
    mainWindow.webContents.send('update-message', 'Checking for updates...');
  });
  
  autoUpdater.on('update-available', (info) => {
    mainWindow.webContents.send('update-message', `Version ${info.version} update available! Downloading...`);
  });
  
  autoUpdater.on('update-not-available', (info) => {
    mainWindow.webContents.send('update-message', 'Up to date.');
  });
  
  autoUpdater.on('error', (err) => {
    mainWindow.webContents.send('update-message', 'Update error. ' + err.message);
  });
  
  autoUpdater.on('download-progress', (progressObj) => {
    mainWindow.webContents.send('update-progress', progressObj.percent);
  });
  
  autoUpdater.on('update-downloaded', (info) => {
    mainWindow.webContents.send('update-message', 'Update downloaded! Restarting...');
    setTimeout(() => {
      autoUpdater.quitAndInstall();
    }, 3000);
  });

  // Check for updates after the window is loaded
  mainWindow.webContents.on('did-finish-load', async () => {
    try {
      if (app.isPackaged) {
        await autoUpdater.checkForUpdatesAndNotify();
      }
    } catch (error) {
      let msg = error.message;
      if (msg.includes('404')) msg = 'Unable to fetch latest release from server.';
      mainWindow.webContents.send('update-message', 'Update error: ' + msg);
    }
  });
}

ipcMain.handle('check-for-updates', async () => {
  try {
    await autoUpdater.checkForUpdatesAndNotify();
    return { status: 'success' };
  } catch (error) {
    let msg = error.message;
    if (msg.includes('404')) msg = 'Unable to fetch latest release from server.';
    BrowserWindow.getAllWindows()[0].webContents.send('update-message', 'Update error: ' + msg);
    return { status: 'error', message: msg };
  }
});


app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});


app.on('before-quit', () => {
  if (casperProcess) {
    // Kill the cmd process and all its children (the python engine) on Windows
    const { exec } = require('child_process');
    exec(`taskkill /pid ${casperProcess.pid} /T /F`);
  }
});

ipcMain.handle('read-env', () => {
  let content = '';
  if (fs.existsSync(ENV_PATH)) {
    content = fs.readFileSync(ENV_PATH, 'utf-8');
  } else if (fs.existsSync(ENV_EXAMPLE_PATH)) {
    content = fs.readFileSync(ENV_EXAMPLE_PATH, 'utf-8');
  }

  const config = {};
  // Normalize line endings before splitting
  const lines = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  lines.forEach(line => {
    const trimmed = line.trim();
    if (trimmed.includes('=') && !trimmed.startsWith('#')) {
      const eqIdx = trimmed.indexOf('=');
      const key = trimmed.substring(0, eqIdx).trim();
      const val = trimmed.substring(eqIdx + 1).trim();
      config[key] = val;
    }
  });
  return config;
});

ipcMain.handle('save-env', (event, data) => {
  try {
    let content = '';
    if (fs.existsSync(ENV_PATH)) {
      content = fs.readFileSync(ENV_PATH, 'utf-8');
    } else if (fs.existsSync(ENV_EXAMPLE_PATH)) {
      content = fs.readFileSync(ENV_EXAMPLE_PATH, 'utf-8');
    }

    // Detect original line ending style
    const lineEnding = content.includes('\r\n') ? '\r\n' : '\n';

    // Normalize to \n for processing
    const lines = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
    const envDict = { ...data };
    const newLines = [];
    const updatedKeys = new Set();

    lines.forEach(line => {
      const trimmed = line.trim();
      if (trimmed.includes('=') && !trimmed.startsWith('#')) {
        const key = trimmed.split('=')[0].trim();
        if (key in envDict && envDict[key] !== undefined && envDict[key] !== null) {
          newLines.push(`${key}=${envDict[key]}`);
          updatedKeys.add(key);
        } else {
          newLines.push(line.replace(/\r$/, ''));
        }
      } else {
        newLines.push(line.replace(/\r$/, ''));
      }
    });

    for (const key in envDict) {
      if (!updatedKeys.has(key) && envDict[key]) {
        newLines.push(`${key}=${envDict[key]}`);
      }
    }

    // Write back using original line ending style
    fs.writeFileSync(ENV_PATH, newLines.join(lineEnding));
    return { status: 'success', message: 'Settings saved to Casper matrix!' };
  } catch (error) {
    return { status: 'error', message: error.message };
  }
});

let casperProcess = null;
let isIntentionalStop = false;

ipcMain.handle('start-casper', () => {
  try {
    if (casperProcess) {
      return { status: 'error', message: 'Casper is already online.' };
    }

    const backendDir = app.isPackaged
      ? process.resourcesPath
      : path.join(__dirname, '..');
      
    // Try to launch the compiled executable first (for portable distribution)
    const exePath = path.join(backendDir, 'dist', 'casper_backend', 'casper_backend.exe');
    
    let command, args, cwdToUse;
    
    const logPath = path.join(app.getPath('userData'), 'casper.log');
    
    if (fs.existsSync(exePath)) {
        command = exePath;
        args = ['console'];
        cwdToUse = path.join(backendDir, 'dist', 'casper_backend');
    } else {
        // Fallback to virtual environment (development mode)
        command = path.join(backendDir, '.venv', 'Scripts', 'python.exe');
        args = ['agent.py', 'console'];
        cwdToUse = backendDir;
    }

    // Read .env from userData and inject it so agent.py can access it
    const envVars = { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8', DISABLE_PYSIDE_UI: '1', USER_DATA_PATH: app.getPath('userData') };
    try {
      if (fs.existsSync(ENV_PATH)) {
        const content = fs.readFileSync(ENV_PATH, 'utf-8');
        const lines = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
        lines.forEach(line => {
          const trimmed = line.trim();
          if (trimmed.includes('=') && !trimmed.startsWith('#')) {
            const eqIdx = trimmed.indexOf('=');
            const key = trimmed.substring(0, eqIdx).trim();
            const val = trimmed.substring(eqIdx + 1).trim();
            envVars[key] = val;
          }
        });
      }
    } catch (e) {
      console.error('Failed to parse .env', e);
    }

    // Write log file from Node.js side instead of shell redirection
    const logStream = fs.createWriteStream(logPath, { flags: 'w' });

    casperProcess = spawn(command, args, {
      cwd: cwdToUse,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
      env: envVars
    });

    // Pipe stdout and stderr to the log file
    if (casperProcess.stdout) casperProcess.stdout.pipe(logStream);
    if (casperProcess.stderr) casperProcess.stderr.pipe(logStream);
    
    isIntentionalStop = false;
    casperProcess.on('exit', (code) => {
      casperProcess = null;
      destroyOverlay();
      if (!isIntentionalStop && code !== 0 && code !== null) {
        // Use the globally defined logPath
        if (fs.existsSync(logPath)) {
          const logContent = fs.readFileSync(logPath, 'utf8');
          const lines = logContent.split('\n').filter(l => l.trim() !== '');
          const lastLines = lines.slice(-10).join('\n');
          const win = BrowserWindow.getAllWindows()[0];
          if (win) {
            win.webContents.send('casper-error', 'Casper Engine exited unexpectedly (Code ' + code + ').\n\nLog Details:\n' + lastLines);
          }
        }
      }
    });

    createOverlay();

    return { status: 'success' };
  } catch (error) {
    return { status: 'error', message: error.message };
  }
});

ipcMain.handle('stop-casper', () => {
  try {
    if (casperProcess) {
      isIntentionalStop = true;
      const { exec } = require('child_process');
      exec(`taskkill /pid ${casperProcess.pid} /T /F`);
      casperProcess = null;
    }
    destroyOverlay();
    return { status: 'success', message: 'Casper terminated.' };
  } catch (error) {
    return { status: 'error', message: error.message };
  }
});

ipcMain.handle('check-casper-status', () => {
  return casperProcess !== null;
});
