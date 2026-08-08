# Toontown Python Injector

Python injector for Toontown Sunrise.

> ⚠️ **Only works with [Toontown Sunrise](https://sunrise.games).** Not intended for any server where client modifications are prohibited.

---

Injects Python source directly into the running interpreter via `Py_AddPendingCall`. No DLL, no code patching.

The original **TeamFD injector** patched `PyEval_EvalCode` in `python24.dll` and carried its own Win32 GUI. That approach is retired here. A decompiled and updated copy of that DLL lives in `src/decompiled TeamFD Injector/` with screenshots. It still works standalone if you'd rather inject it yourself with something like RemoteDLL32.

`TTsunriseInjector.exe` opens the Toontown launcher, waits for the game, attaches, and opens the dashboard. It reattaches on its own if the game restarts.

---

## Setup

**Requirements:** Windows 10/11 64-bit, Administrator

1. Download `TTsunriseInjector.7z` from [Releases](../../releases/latest)
2. Copy `toonbot\` and `TaskBot\` into your Toontown install directory. Both are required:
   ```
   ToontownOnline\
   ├── toonbot\
   │   ├── ToonBot.py
   │   ├── scripts\
   │   ├── libs\
   │   └── Injectables\
   └── TaskBot\
   ```
3. Run `TTsunriseInjector.exe`. It asks for Administrator on launch.

### Build from source

```
pip install pyinstaller pyqt5
pyinstaller --onefile --windowed --uac-admin --icon src/toontown.ico src/app.py -n TTsunriseInjector
```

Copy `toonbot\` and `TaskBot\` into your install directory as above.

---

## Usage

Run exe, and login to the game. The console shows `[+] bridge live on :8888` when ready. Write or load a script and press **EXECUTE SCRIPT** or **Ctrl+Enter**.

You can also have the game already open. It attaches either way.

| Panel | Description |
|-------|-------------|
| **Scripts sidebar** | Browses `toonbot\Injectables\`, double-click a `.py` / `.txt` to load |
| **Editor** | Python 2.4 code, runs inside the game |
| **Console** | Green `[done]` on success, red `[error]` plus traceback on failure |

![Screenshot of injector UI](https://raw.githubusercontent.com/SSalem00/assets/main/wCzkbBxsuc.png)

![Screenshot of injector UI](https://raw.githubusercontent.com/SSalem00/assets/main/znPmTwvKPH.png)

---

## Included Scripts

Ships with [ToonBot](https://github.com/freshollie/ToonBot) and TaskBot: boss battles, gag training, ToonTasks, and more. `toonbot\scripts\` is kept as a reference to build from.

`toonbot\Injectables\` holds the scripts shown in the sidebar. Drop your own `.txt` in there. More at the [Scrap repo](https://github.com/ttcloopy/Scrap).

| Bundled Example | What it does |
|--------|-------------|
| `ToonTask-Autoer.py` | freshollie task autoer, needs the TaskBot folder |
| `SalemsButtons.txt` | A few buttons |
| `SpikesButtons.txt` | A larger button set |
| `CheckBeans.txt` | Prints your bean count |
| `UnstuckSELF.txt` | Teleports to Donald's Dreamland if stuck |
| `pumpkinHEAD.txt` / `snowmanHEAD.txt` | Cosmetic head |

---

## Credits

- **Original DLL injector:** TeamFD
- **ToonBot:** [freshollie](https://github.com/freshollie/ToonBot)
- **Rewrite, dashboard, script fixes:** SSalem00
