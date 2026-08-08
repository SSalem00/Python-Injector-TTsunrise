"""
Entry point. Launcher and dashboard in one process.

The dashboard owns the UI thread; boot runs on a QThread and logs to its console.
"""

import subprocess
import sys
import time
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication

import launcher as L
from dashboard import Dashboard

SCRIPTS_ROOT = L.ROOT / "toonbot" / "Injectables"


class BootWorker(QThread):
    """Boot sequence, off the UI thread."""
    log   = pyqtSignal(str, str)  # (severity, message)
    ready = pyqtSignal(int)       # game PID

    def run(self):
        try:
            self._run()
        except Exception as e:
            self.log.emit("error", f"[!] boot error: {e.__class__.__name__}: {e}")

    def _run(self):
        game_pid = L.find_pid_by_name(L.GAME_EXE_NAME)
        if game_pid:
            self.log.emit("system", f"[*] {L.GAME_EXE_NAME} already running (pid {game_pid})")
        else:
            if not L.LAUNCHER_EXE.exists():
                self.log.emit("error", f"[!] missing {L.LAUNCHER_EXE}")
                return
            self.log.emit("system", "[*] starting login launcher - log in to continue...")
            subprocess.Popen([str(L.LAUNCHER_EXE)], cwd=str(L.LAUNCHER_EXE.parent))
            game_pid = L.wait_for_game(L.WATCH_TIMEOUT_SEC, L.POLL_INTERVAL_SEC)
            if not game_pid:
                self.log.emit("error", f"[!] timed out waiting for {L.GAME_EXE_NAME}")
                return
            self.log.emit(
                "system",
                f"[+] detected pid {game_pid} - waiting {int(L.PRE_INJECT_DELAY_SEC)}s for load...",
            )
            time.sleep(L.PRE_INJECT_DELAY_SEC)

        if L.inject_and_bootstrap(game_pid, self.log.emit):
            self.ready.emit(game_pid)


class WatchdogWorker(QThread):
    """Reattaches when the game relaunches."""
    log = pyqtSignal(str, str)

    def __init__(self, initial_pid: int, parent=None):
        super().__init__(parent)
        self._pid = initial_pid

    def run(self):
        while True:
            while True:
                pid = L.find_pid_by_name(L.GAME_EXE_NAME)
                if pid != self._pid:
                    break
                time.sleep(2)

            self.log.emit("warn", "[~] game process ended - watching for relaunch...")

            while True:
                pid = L.find_pid_by_name(L.GAME_EXE_NAME)
                if pid:
                    self._pid = pid
                    self.log.emit(
                        "system",
                        f"[+] game back (pid {pid}) - waiting {int(L.PRE_INJECT_DELAY_SEC)}s for load...",
                    )
                    break
                time.sleep(2)

            time.sleep(L.PRE_INJECT_DELAY_SEC)

            try:
                L.inject_and_bootstrap(self._pid, self.log.emit)
            except Exception as e:
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
