"""
Single-process entry point for the Toontown bot.

Merges the launcher (process watch + DLL injection + bridge bootstrap) and the
PyQt5 dashboard into ONE process: the dashboard owns the main/UI thread, and the
boot sequence runs on a background QThread, streaming progress into the
dashboard's console. Build into a windowed EXE with PyInstaller (see bottom).
"""

import subprocess
import sys
import time
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication

import launcher as L
from dashboard import Dashboard

SCRIPTS_ROOT = Path(
    r"C:\Program Files (x86)\Disney\Disney Online\ToontownOnline\toonbot\Injectables"
)


def _inject_and_bootstrap(pid: int, log_fn) -> bool:
    """Inject the DLL and start ToonBot.py in an already-running game process."""
    if L.INJECT_DLL.exists():
        last_err = None
        for _ in range(20):
            try:
                L.inject(pid, str(L.INJECT_DLL))
                log_fn("system", f"[+] injected {L.INJECT_DLL.name}")
                break
            except OSError as e:
                last_err = e
                time.sleep(0.25)
        else:
            log_fn("warn", f"[~] DLL inject failed (non-fatal): {last_err}")
    else:
        log_fn("warn", f"[~] {L.INJECT_DLL} not found")

    if not L.TOONBOT_PY.exists():
        log_fn("error", f"[!] {L.TOONBOT_PY} not found — bridge won't start")
        return False

    bootstrap = "execfile(r'{}')".format(str(L.TOONBOT_PY))
    try:
        L._queue_python_code(pid, bootstrap)
        log_fn("system", "[+] bridge bootstrap queued")
    except OSError as e:
        log_fn("error", f"[!] queue failed: {e}")
        return False

    for i in range(20):
        time.sleep(0.5)
        if L._bridge_is_up():
            log_fn("system", f"[+] bridge live on 127.0.0.1:8888 after ~{(i + 1) * 0.5:.0f}s")
            return True

    log_fn("warn", "[!] bridge not responding — check in-game for a ToonBot.py error")
    return False


class BootWorker(QThread):
    """Runs the launch/inject/bootstrap sequence off the UI thread."""
    log   = pyqtSignal(str, str)  # (severity, message)
    ready = pyqtSignal(int)       # emits game PID once bridge is confirmed live

    def run(self):
        try:
            self._run()
        except Exception as e:  # noqa: BLE001
            self.log.emit("error", f"[!] boot error: {e.__class__.__name__}: {e}")

    def _run(self):
        game_pid = L.find_pid_by_name(L.GAME_EXE_NAME)
        if game_pid:
            self.log.emit("system", f"[*] {L.GAME_EXE_NAME} already running (pid {game_pid})")
        else:
            if not L.LAUNCHER_EXE.exists():
                self.log.emit("error", f"[!] missing {L.LAUNCHER_EXE}")
                return
            self.log.emit("system", "[*] starting login launcher — log in to continue…")
            subprocess.Popen([str(L.LAUNCHER_EXE)], cwd=str(L.LAUNCHER_EXE.parent))
            game_pid = L.wait_for_game(L.WATCH_TIMEOUT_SEC, L.POLL_INTERVAL_SEC)
            if not game_pid:
                self.log.emit("error", f"[!] timed out waiting for {L.GAME_EXE_NAME}")
                return
            self.log.emit(
                "system",
                f"[+] detected pid {game_pid} — waiting {int(L.PRE_INJECT_DELAY_SEC)}s for load…",
            )
            time.sleep(L.PRE_INJECT_DELAY_SEC)

        if _inject_and_bootstrap(game_pid, self.log.emit):
            self.ready.emit(game_pid)


class WatchdogWorker(QThread):
    """Watches for the game to crash and re-injects when it relaunches."""
    log = pyqtSignal(str, str)

    def __init__(self, initial_pid: int, parent=None):
        super().__init__(parent)
        self._pid = initial_pid

    def run(self):
        while True:
            # Wait for the known PID to disappear
            while True:
                pid = L.find_pid_by_name(L.GAME_EXE_NAME)
                if pid != self._pid:
                    break
                time.sleep(2)

            self.log.emit("warn", "[~] game process ended — watching for relaunch…")

            # Wait for a new Toontown.exe to appear
            while True:
                pid = L.find_pid_by_name(L.GAME_EXE_NAME)
                if pid:
                    self._pid = pid
                    self.log.emit(
                        "system",
                        f"[+] game back (pid {pid}) — waiting {int(L.PRE_INJECT_DELAY_SEC)}s for load…",
                    )
                    break
                time.sleep(2)

            time.sleep(L.PRE_INJECT_DELAY_SEC)

            try:
                _inject_and_bootstrap(self._pid, self.log.emit)
            except Exception as e:  # noqa: BLE001
                self.log.emit("error", f"[!] re-inject error: {e.__class__.__name__}: {e}")


def main():
    SCRIPTS_ROOT.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    win = Dashboard(SCRIPTS_ROOT)
    win.show()

    worker = BootWorker()
    worker.log.connect(win.console.append_log)

    def _on_boot_ready(pid: int):
        watchdog = WatchdogWorker(pid, win)
        watchdog.log.connect(win.console.append_log)
        win._watchdog = watchdog
        watchdog.start()

    worker.ready.connect(_on_boot_ready)
    win._boot_worker = worker
    worker.start()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
