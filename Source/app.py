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


class BootWorker(QThread):
    """Runs the launch/inject/bootstrap sequence off the UI thread."""
    log = pyqtSignal(str, str)  # (severity, message)

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

        # Step 1: inject the DLL.
        if L.INJECT_DLL.exists():
            last_err = None
            for _ in range(20):
                try:
                    L.inject(game_pid, str(L.INJECT_DLL))
                    self.log.emit("system", f"[+] injected {L.INJECT_DLL.name}")
                    break
                except OSError as e:
                    last_err = e
                    time.sleep(0.25)
            else:
                self.log.emit("warn", f"[~] DLL inject failed (non-fatal): {last_err}")
        else:
            self.log.emit("warn", f"[~] {L.INJECT_DLL} not found")

        # Step 2: queue ToonBot.py on the game's main interpreter thread.
        if not L.TOONBOT_PY.exists():
            self.log.emit("error", f"[!] {L.TOONBOT_PY} not found — bridge won't start")
            return
        bootstrap = "execfile(r'{}')".format(str(L.TOONBOT_PY))
        try:
            L._queue_python_code(game_pid, bootstrap)
            self.log.emit("system", "[+] bridge bootstrap queued")
        except OSError as e:
            self.log.emit("error", f"[!] queue failed: {e}")
            return

        for i in range(20):
            time.sleep(0.5)
            if L._bridge_is_up():
                self.log.emit("system", f"[+] bridge live on 127.0.0.1:8888 after ~{(i + 1) * 0.5:.0f}s")
                return
        self.log.emit("warn", "[!] bridge not responding — check in-game for a ToonBot.py error")


def main():
    SCRIPTS_ROOT.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    win = Dashboard(SCRIPTS_ROOT)
    win.show()

    worker = BootWorker()
    worker.log.connect(win.console.append_log)
    win._boot_worker = worker  # keep a reference so it isn't garbage-collected
    worker.start()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
