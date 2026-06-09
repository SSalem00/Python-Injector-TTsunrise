"""
Toontown Python Dashboard — external PyQt5 control panel.

Protocol (localhost:8888):
    [4-byte big-endian length][utf-8 payload]
The game-side hook reads the frame, exec()s it, and streams stdout/stderr
back over the same socket until it closes the connection.
"""

import os
import socket
import sys
from pathlib import Path

from PyQt5.QtCore import QRect, QSize, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QTextFormat
from PyQt5.QtWidgets import (
    QApplication,
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


# ---------- Line number gutter ----------------------------------------------

class _Gutter(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.gutter_width(), 0)

    def paintEvent(self, event):
        self._editor.paint_gutter(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._gutter = _Gutter(self)

        self.blockCountChanged.connect(lambda _: self._update_gutter_width())
        self.updateRequest.connect(self._on_update_request)
        self.cursorPositionChanged.connect(self._highlight_current_line)

        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))

        self._update_gutter_width()
        self._highlight_current_line()

    def gutter_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_gutter_width(self):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _on_update_request(self, rect, dy):
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._gutter.setGeometry(
            QRect(cr.left(), cr.top(), self.gutter_width(), cr.height())
        )

    def _highlight_current_line(self):
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor("#1f1638"))
        sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.setExtraSelections([sel])

    def paint_gutter(self, event):
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), QColor("#120c20"))
        painter.setPen(QColor("#7a6aa0"))

        block = self.firstVisibleBlock()
        top = round(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + round(self.blockBoundingRect(block).height())
        n = block.blockNumber()
        h = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0, top,
                    self._gutter.width() - 8, h,
                    Qt.AlignRight,
                    str(n + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            n += 1


# ---------- IPC worker thread -----------------------------------------------

class IPCBridge(QThread):
    """Sends a payload to the in-game hook and streams response lines back."""
    log = pyqtSignal(str, str)       # (severity, message)
    finished_run = pyqtSignal()

    def __init__(self, host: str, port: int, payload: str, parent=None):
        super().__init__(parent)
        self.host, self.port, self.payload = host, port, payload

    def run(self):
        try:
            with socket.create_connection((self.host, self.port), timeout=3) as sock:
                self.log.emit("system", f"[+] connected to {self.host}:{self.port}")
                body = self.payload.encode("utf-8")
                sock.sendall(len(body).to_bytes(4, "big") + body)
                self.log.emit("system", f"[+] sent {len(body)} bytes — awaiting output…")

                sock.settimeout(30)
                buf = b""
                while True:
                    try:
                        chunk = sock.recv(4096)
                    except socket.timeout:
                        self.log.emit("warn", "[~] recv timed out — script may still be running")
                        break
                    if not chunk:
                        break
                    buf += chunk

                for raw in buf.decode("utf-8", errors="replace").splitlines():
                    if raw.startswith("[done"):
                        sev = "done"
                    elif raw.startswith(("[error", "Traceback", "Error", "Exception", "  File ")):
                        sev = "error"
                    else:
                        sev = "print"
                    self.log.emit(sev, raw)

        except ConnectionRefusedError:
            self.log.emit(
                "error",
                f"[!] connection refused — is the in-game hook listening on "
                f"{self.host}:{self.port}?",
            )
        except socket.timeout:
            self.log.emit("error", "[!] connection timed out.")
        except OSError as e:
            self.log.emit("error", f"[!] socket error: {e.__class__.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            self.log.emit("error", f"[!] unexpected: {e.__class__.__name__}: {e}")
        finally:
            self.finished_run.emit()


# ---------- Console ---------------------------------------------------------

class LogConsole(QTextEdit):
    COLORS = {
        "system": "#9d7bff",
        "info":   "#e8d8ff",
        "print":  "#c9b3ff",
        "warn":   "#ffcf6b",
        "error":  "#ff7090",
        "done":   "#5fff87",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)

    def append_log(self, severity: str, message: str):
        color = self.COLORS.get(severity, "#d4d4d4")
        safe = (
            message.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
        )
        self.append(f'<span style="color:{color};white-space:pre;">{safe}</span>')


# ---------- Main window -----------------------------------------------------

class Dashboard(QMainWindow):
    def __init__(self, scripts_root: Path, host: str = "127.0.0.1", port: int = 8888):
        super().__init__()
        self.scripts_root = scripts_root
        self.host, self.port = host, port

        self.setWindowTitle("Toontown Python Dashboard")
        self.resize(1280, 820)
        self._build_ui()
        self._apply_theme()

        self.console.append_log("system", f"[*] scripts root  : {self.scripts_root}")
        self.console.append_log("system", f"[*] ipc target    : {self.host}:{self.port}")
        self.console.append_log("system", "[*] ready.  Ctrl+Enter to execute.")

    # ----- ui scaffolding ---------------------------------------------------

    def _build_ui(self):
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(str(self.scripts_root))
        self.fs_model.setNameFilters(["*.py", "*.txt"])
        self.fs_model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.setModel(self.fs_model)
        self.tree.setRootIndex(self.fs_model.index(str(self.scripts_root)))
        for col in (1, 2, 3):
            self.tree.hideColumn(col)
        self.tree.setHeaderHidden(True)
        self.tree.doubleClicked.connect(self._on_tree_open)

        sidebar_header = QLabel("  SCRIPTS")
        sidebar_header.setObjectName("panelHeader")
        sidebar = QWidget()
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(0, 6, 0, 0)
        sl.setSpacing(2)
        sl.addWidget(sidebar_header)
        sl.addWidget(self.tree, 1)

        self.editor = CodeEditor()
        self.editor.setPlaceholderText(
            "# write Python here, or double-click a script in the sidebar"
        )

        self.host_label = QLabel(f"target  {self.host}:{self.port}")
        self.host_label.setObjectName("hostLabel")

        self.run_btn = QPushButton("▶  EXECUTE SCRIPT")
        self.run_btn.setObjectName("runBtn")
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setShortcut("Ctrl+Return")
        self.run_btn.clicked.connect(self._on_execute)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.host_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self.run_btn)

        editor_header = QLabel("  EDITOR")
        editor_header.setObjectName("panelHeader")
        editor_panel = QWidget()
        ep = QVBoxLayout(editor_panel)
        ep.setContentsMargins(8, 6, 8, 8)
        ep.addWidget(editor_header)
        ep.addLayout(toolbar)
        ep.addWidget(self.editor, 1)

        self.console = LogConsole()
        clear_btn = QPushButton("clear")
        clear_btn.setObjectName("ghostBtn")
        clear_btn.clicked.connect(self.console.clear)

        console_header_row = QHBoxLayout()
        c_header = QLabel("  CONSOLE")
        c_header.setObjectName("panelHeader")
        console_header_row.addWidget(c_header)
        console_header_row.addStretch(1)
        console_header_row.addWidget(clear_btn)

        console_panel = QWidget()
        cp = QVBoxLayout(console_panel)
        cp.setContentsMargins(8, 4, 8, 8)
        cp.addLayout(console_header_row)
        cp.addWidget(self.console, 1)

        right = QSplitter(Qt.Vertical)
        right.addWidget(editor_panel)
        right.addWidget(console_panel)
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)
        right.setSizes([520, 260])

        root = QSplitter(Qt.Horizontal)
        root.addWidget(sidebar)
        root.addWidget(right)
        root.setSizes([260, 1020])
        root.setStretchFactor(0, 0)
        root.setStretchFactor(1, 1)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("idle")

    def _apply_theme(self):
        self.setStyleSheet("""
        QMainWindow {
            background: qradialgradient(
                cx:0.5, cy:0, radius:1.1, fx:0.5, fy:0,
                stop:0 #1a1030, stop:0.7 #0c0814
            );
        }
        QWidget {
            background: transparent;
            color: #e8d8ff;
            font-family: Consolas, "Courier New", monospace;
        }
        QTreeView {
            background: #140e23;
            border: 1px solid rgba(124, 77, 255, 0.20);
            border-radius: 12px;
            padding: 4px;
            outline: 0;
        }
        QTreeView::item { padding: 3px 4px; border-radius: 6px; }
        QTreeView::item:selected { background: #7c4dff; color: #fff; }
        QTreeView::item:hover    { background: rgba(124, 77, 255, 0.22); }

        QPlainTextEdit, QTextEdit {
            background: #140e23;
            color: #e8d8ff;
            border: 1px solid rgba(124, 77, 255, 0.20);
            border-radius: 12px;
            selection-background-color: #7c4dff;
            selection-color: #ffffff;
        }

        QSplitter::handle           { background: #1a1030; }
        QSplitter::handle:horizontal { width: 3px; }
        QSplitter::handle:vertical   { height: 3px; }

        QStatusBar { background: #7c4dff; color: #ffffff; }

        QLabel#panelHeader {
            color: #b388ff;
            font-weight: bold;
            padding: 4px 2px;
            letter-spacing: 1px;
        }
        QLabel#hostLabel { color: #a892c9; }

        QPushButton#runBtn {
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1, stop:0 #8a5bff, stop:1 #7c4dff
            );
            color: #ffffff;
            font-weight: bold;
            border: none;
            padding: 6px 22px;
            border-radius: 10px;
        }
        QPushButton#runBtn:hover {
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1, stop:0 #a07bff, stop:1 #8a5bff
            );
        }
        QPushButton#runBtn:pressed  { background: #6a3fe0; }
        QPushButton#runBtn:disabled { background: #2a2140; color: #6a5a85; }

        QPushButton#ghostBtn {
            background: transparent;
            color: #a892c9;
            border: 1px solid rgba(124, 77, 255, 0.25);
            padding: 2px 10px;
            border-radius: 8px;
        }
        QPushButton#ghostBtn:hover { color: #e8d8ff; border-color: #b388ff; }

        QScrollBar:vertical           { background: transparent; width: 12px; }
        QScrollBar::handle:vertical   { background: #3a2a5e; border-radius: 6px; min-height: 30px; }
        QScrollBar::handle:vertical:hover { background: #7c4dff; }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical { height: 0; }
        """)

    # ----- handlers ---------------------------------------------------------

    def _on_tree_open(self, index):
        path = self.fs_model.filePath(index)
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as fp:
                self.editor.setPlainText(fp.read())
            rel = os.path.relpath(path, self.scripts_root)
            self.console.append_log("system", f"[*] loaded  {rel}")
            self.setWindowTitle(
                f"Toontown Python Dashboard — {os.path.basename(path)}"
            )
        except OSError as e:
            self.console.append_log("error", f"[!] could not open {path}: {e}")

    def _on_execute(self):
        payload = self.editor.toPlainText()
        if not payload.strip():
            self.console.append_log("warn", "[~] editor is empty.")
            return

        self.run_btn.setEnabled(False)
        self.statusBar().showMessage("sending…")
        self.console.append_log("system", "─" * 60)

        self._bridge = IPCBridge(self.host, self.port, payload, self)
        self._bridge.log.connect(self.console.append_log)
        self._bridge.finished_run.connect(self._on_run_done)
        self._bridge.start()

    def _on_run_done(self):
        self.run_btn.setEnabled(True)
        self.statusBar().showMessage("idle")


# ---------- entry point -----------------------------------------------------

def main():
    try:
        scripts_root = Path(
            r"C:\Program Files (x86)\Disney\Disney Online\ToontownOnline\toonbot\Injectables"
        )
        scripts_root.mkdir(parents=True, exist_ok=True)

        sample = scripts_root / "hello.py"
        if not sample.exists():
            sample.write_text(
                'print("hello from the embedded interpreter")\n', encoding="utf-8"
            )

        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        win = Dashboard(scripts_root)
        win.show()
        sys.exit(app.exec_())

    except Exception:
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")  # keeps the window open so you can read it


if __name__ == "__main__":
    main()
