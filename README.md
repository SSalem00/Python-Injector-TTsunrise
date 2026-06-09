# Toontown Python Injector

Python injector for Toontown Sunrise Games.

> ⚠️ **This tool only works with [Toontown Sunrise](https://sunrise.games).** It will not work on other servers and is not intended for use on any server where client modifications are prohibited.

---

Uses the same DLL hook as the original **TeamFD injector** — patching `PyEval_EvalCode` in `python24.dll` to intercept the game's Python interpreter. The original Win32 GUI has been replaced with a new PyQt5 dashboard with a working debug console.

`ModdedLauncher.exe` is the injector — it launches Toontown, waits for the game to load, and automatically injects and opens the dashboard. No extra steps needed.

---

## Setup

### Requirements
- Toontown Sunrise installed at:  
  `C:\Program Files (x86)\Disney\Disney Online\ToontownOnline\`
- Windows
- Run as **Administrator**

### Installation

1. Download `ModdedLauncher.7z` from the [Releases](../../releases/latest) page
2. Extract the archive — it contains `ModdedLauncher.exe`, `toonbot\`, and `TaskBot\`
3. Copy `toonbot\` and `TaskBot\` into your Toontown install directory (**both folders are required**):
   ```
   ToontownOnline\
   ├── toonbot\
   │   ├── ToonBot.py
   │   ├── scripts\
   │   ├── libs\
   │   └── Injectables\
   └── TaskBot\
   ```
4. Place `ModdedLauncher.exe` anywhere and run as Administrator

### Building from source

```
pip install pyinstaller pyqt5
pyinstaller --onefile --windowed --add-data "Source/TTHook.dll;TTInjector" Source/app.py -n ModdedLauncher
```

Copy `game\toonbot\` and `game\TaskBot\` into your Toontown install directory as above.

---

## Usage

1. **Run `ModdedLauncher.exe` as Administrator**
2. Log in through the Toontown launcher normally
3. The injector waits ~15 seconds for the game to load, then injects and opens the dashboard
4. Console will show `[+] bridge live on :8888` when ready
5. Write or load a script in the editor and press **Ctrl+Enter** to run it in-game

### Dashboard

| Panel | Description |
|-------|-------------|
| **Scripts sidebar** | Browses `toonbot\Injectables\` — double-click any `.py` / `.txt` to load it |
| **Editor** | Write Python 2.4 code to execute inside the running game |
| **Console** | Live output — green `[done]` on success, red `[error]` + full traceback on failure |
---
![Screenshot of injector UI](https://raw.githubusercontent.com/SSalem00/assets/main/wCzkbBxsuc.png)


## Included Scripts

The install includes [ToonBot](https://github.com/freshollie/ToonBot) and its TaskBot — a collection of automation scripts for boss battles, gag training, ToonTasks, and more. The `toonbot\scripts\` folder is left in as a reference and base to build from.

### `toonbot\Injectables\` — Dashboard scripts

These appear in the dashboard sidebar. A few example scripts are included — you can add your own `.txt` files here to quickly load and run any injector code copy and pasting it each time. For more scripts, browse the [Scrap repo](https://github.com/ttcloopy/Scrap).

| Script | What it does |
|--------|-------------|
| `ToonTask-Autoer.py` | freshollie task autoer, requires TaskBot folder in main game folder. |
| `SalemsSimpleButtons.txt` | A few buttons |
| `pumpkinHEAD.txt` / `snowmanHEAD.txt` | Cosmetic head swaps |

---

## Credits

- **Original DLL hook**: TeamFD
- **ToonBot** (in-game GUI framework): [freshollie](https://github.com/freshollie/ToonBot)
- **Rewrite & dashboard**: SSalem00
