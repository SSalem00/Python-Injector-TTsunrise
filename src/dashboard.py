"""
Toontown Python Dashboard - external PyQt5 control panel.

Protocol (localhost:8888):
    [4-byte big-endian length][utf-8 payload]
The game-side hook reads the frame, exec()s it, and streams stdout/stderr
back over the same socket until it closes the connection.

Also tails the game's own log file (toontown-*.log in the install dir) so
in-game warnings, errors, and crash tracebacks show up in the GAME LOG tab
without digging through .txt files by hand.
"""

import os
import re
import socket
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QRect, QSize, Qt, QThread, pyqtSignal
from PyQt5.QtGui import (
    QColor,
    QFont,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextFormat,
)
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QShortcut,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from launcher import ROOT as GAME_LOG_DIR

GAME_LOG_GLOB = "toontown-*.log"


# Python syntax highlighting
class PythonHighlighter(QSyntaxHighlighter):
    """Lightweight regex highlighter tuned for the in-game Python 2.4 scripts."""

    KEYWORDS = (
        "False None True and as assert break class continue def del elif else "
        "except exec finally for from global if import in is lambda not or "
        "pass print raise return try while with yield"
    ).split()

    BUILTINS = (
        "abs apply bool callable chr cmp dict dir enumerate eval execfile "
        "filter float getattr globals hasattr hash hex id int isinstance "
        "issubclass iter len list locals long map max min object open ord "
        "range raw_input reduce reload repr round setattr sorted str sum "
        "super tuple type unicode vars xrange zip __import__"
    ).split()

    def __init__(self, document):
        super().__init__(document)

        def fmt(color, bold=False, italic=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Bold)
            if italic:
                f.setFontItalic(True)
            return f

        self._fmt_keyword   = fmt("#c792ea", bold=True)
        self._fmt_builtin   = fmt("#82aaff")
        self._fmt_self      = fmt("#f78c6c", italic=True)
        self._fmt_defname   = fmt("#ffcb6b", bold=True)
        self._fmt_decorator = fmt("#ffcb6b")
        self._fmt_number    = fmt("#f78c6c")
        self._fmt_string    = fmt("#c3e88d")
        self._fmt_comment   = fmt("#67608a", italic=True)

        self._rules = [
            (re.compile(r"\b(?:%s)\b" % "|".join(self.KEYWORDS)), self._fmt_keyword),
            (re.compile(r"\b(?:%s)\b" % "|".join(self.BUILTINS)), self._fmt_builtin),
            (re.compile(r"\bself\b"), self._fmt_self),
            (re.compile(r"\b(?:def|class)\s+(\w+)"), self._fmt_defname),
            (re.compile(r"@\w+(?:\.\w+)*"), self._fmt_decorator),
            (re.compile(r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[LljJ]?\b"), self._fmt_number),
            (re.compile(r"[rRbBuU]{0,2}'(?:\\.|[^'\\\n])*'"
                        r"|[rRbBuU]{0,2}\"(?:\\.|[^\"\\\n])*\""), self._fmt_string),
        ]

    def highlightBlock(self, text):
        for pattern, f in self._rules:
            for m in pattern.finditer(text):
                if m.groups():
                    self.setFormat(m.start(1), m.end(1) - m.start(1), f)
                else:
                    self.setFormat(m.start(), m.end() - m.start(), f)

        # first # outside a string
        quote = None
        i = 0
        while i < len(text):
            ch = text[i]
            if quote:
                if ch == "\\":
                    i += 1
                elif ch == quote:
                    quote = None
            elif ch in "'\"":
                quote = ch
            elif ch == "#":
                self.setFormat(i, len(text) - i, self._fmt_comment)
                break
            i += 1

        self._highlight_triple_quotes(text)

    def _highlight_triple_quotes(self, text):
        NONE, SINGLE, DOUBLE = 0, 1, 2
        state = self.previousBlockState()
        pos = 0

        if state in (SINGLE, DOUBLE):
            delim = "'''" if state == SINGLE else '"""'
            end = text.find(delim)
            if end == -1:
                self.setFormat(0, len(text), self._fmt_string)
                self.setCurrentBlockState(state)
                return
            self.setFormat(0, end + 3, self._fmt_string)
            pos = end + 3

        self.setCurrentBlockState(NONE)
        while True:
            s1 = text.find("'''", pos)
            s2 = text.find('"""', pos)
            starts = [(s, d, st) for s, d, st in
                      ((s1, "'''", SINGLE), (s2, '"""', DOUBLE)) if s != -1]
            if not starts:
                return
            s, delim, st = min(starts)
            e = text.find(delim, s + 3)
            if e == -1:
                self.setFormat(s, len(text) - s, self._fmt_string)
                self.setCurrentBlockState(st)
                return
            self.setFormat(s, e + 3 - s, self._fmt_string)
            pos = e + 3


# Line number gutter
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

        self._highlighter = PythonHighlighter(self.document())

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


# IPC worker thread
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
                self.log.emit("system", f"[+] sent {len(body)} bytes - awaiting output...")

                sock.settimeout(30)
                buf = b""
                while True:
                    try:
                        chunk = sock.recv(4096)
                    except socket.timeout:
                        self.log.emit("warn", "[~] recv timed out - script may still be running")
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
                f"[!] connection refused - is the in-game hook listening on "
                f"{self.host}:{self.port}?",
            )
        except socket.timeout:
            self.log.emit("error", "[!] connection timed out.")
        except OSError as e:
            self.log.emit("error", f"[!] socket error: {e.__class__.__name__}: {e}")
        except Exception as e:
            self.log.emit("error", f"[!] unexpected: {e.__class__.__name__}: {e}")
        finally:
            self.finished_run.emit()


# Game log watcher
class GameLogWatcher(QThread):
    """Tails the newest toontown-*.log, switching files when the game relaunches."""
    line = pyqtSignal(str, str)      # (severity, message)
    switched = pyqtSignal(str)       # path now being tailed

    _RE_EXC_TAIL = re.compile(r"^\w+(?:Error|Exception|Warning)\b")

    def __init__(self, log_dir: Path = GAME_LOG_DIR, pattern: str = GAME_LOG_GLOB,
                 parent=None):
        super().__init__(parent)
        self.log_dir = Path(log_dir)
        self.pattern = pattern
        self._stop = False

    def stop(self):
        self._stop = True

    # internals
    def _newest_log(self):
        try:
            logs = list(self.log_dir.glob(self.pattern))
        except OSError:
            return None
        if not logs:
            return None
        return max(logs, key=lambda p: p.stat().st_mtime)

    def _sleep(self, seconds: float):
        end = time.monotonic() + seconds
        while not self._stop and time.monotonic() < end:
            time.sleep(0.1)

    @classmethod
    def classify(cls, line: str, in_traceback: bool):
        """Return (severity, still_in_traceback) for one raw log line."""
        if line.startswith("Traceback (most recent call last):"):
            return "error", True
        if in_traceback:
            if line.startswith((" ", "\t")):
                return "error", True
            # unindented "Error: msg" ends the traceback
            return "error", False
        if "(error)" in line:
            return "error", False
        if cls._RE_EXC_TAIL.match(line):
            return "error", False
        if "Exception exit" in line or "Handling Python exception" in line:
            return "error", False
        if "(warning)" in line:
            return "warn", False
        return "game", False

    def run(self):
        current = None
        pos = 0
        in_tb = False
        said_missing = False
        first_attach = True

        while not self._stop:
            newest = self._newest_log()
            if newest is None:
                if not said_missing:
                    self.line.emit(
                        "system",
                        f"[*] no {self.pattern} found in {self.log_dir} yet - waiting...",
                    )
                    said_missing = True
                self._sleep(2.0)
                continue

            if newest != current:
                current = newest
                in_tb = False
                try:
                    # old logs: start at end. new logs: start at top.
                    pos = current.stat().st_size if first_attach else 0
                except OSError:
                    pos = 0
                first_attach = False
                self.line.emit("system", f"[*] tailing game log: {current.name}")
                self.switched.emit(str(current))

            try:
                size = current.stat().st_size
                if size < pos:          # truncated/replaced in place
                    pos = 0
                if size > pos:
                    with open(current, "rb") as fp:
                        fp.seek(pos)
                        data = fp.read(size - pos)
                    last_nl = data.rfind(b"\n")
                    if last_nl != -1:
                        complete, pos = data[:last_nl], pos + last_nl + 1
                        for raw in complete.decode("utf-8", errors="replace").splitlines():
                            sev, in_tb = self.classify(raw, in_tb)
                            if sev == "error" and "Exception exit" in raw:
                                self.line.emit("error", raw)
                                self.line.emit(
                                    "error",
                                    "[!] game exited with a Python exception - "
                                    "see traceback above",
                                )
                                continue
                            self.line.emit(sev, raw)
            except OSError:
                pass  # file vanished mid-read; next poll re-resolves it

            self._sleep(0.5)


# Console
class LogConsole(QTextEdit):
    COLORS = {
        "system": "#9d7bff",
        "info":   "#e8d8ff",
        "print":  "#c9b3ff",
        "warn":   "#ffcf6b",
        "error":  "#ff7090",
        "done":   "#5fff87",
        "game":   "#9c8cc4",
    }
    TIMESTAMP_COLOR = "#574a7a"
    MAX_BLOCKS = 5000

    def __init__(self, parent=None, timestamps: bool = True):
        super().__init__(parent)
        self.setReadOnly(True)
        self._timestamps = timestamps
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.document().setMaximumBlockCount(self.MAX_BLOCKS)

    def append_log(self, severity: str, message: str):
        color = self.COLORS.get(severity, "#d4d4d4")
        safe = (
            message.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
        )
        html = f'<span style="color:{color};white-space:pre;">{safe}</span>'
        if self._timestamps:
            ts = datetime.now().strftime("%H:%M:%S")
            html = (
                f'<span style="color:{self.TIMESTAMP_COLOR};white-space:pre;">'
                f"{ts} </span>" + html
            )

        sb = self.verticalScrollBar()
        stick = sb.value() >= sb.maximum() - 4   # only autoscroll if at bottom
        self.append(html)
        if stick:
            sb.setValue(sb.maximum())


class GameLogConsole(LogConsole):
    """Console with an errors-only filter backed by a replayable buffer."""
    VISIBLE_FILTERED = ("system", "warn", "error")

    def __init__(self, parent=None):
        super().__init__(parent, timestamps=False)
        self._buffer = deque(maxlen=self.MAX_BLOCKS)
        self._errors_only = True

    def _passes(self, severity: str) -> bool:
        return (not self._errors_only) or severity in self.VISIBLE_FILTERED

    def append_log(self, severity: str, message: str):
        self._buffer.append((severity, message))
        if self._passes(severity):
            super().append_log(severity, message)

    def set_errors_only(self, enabled: bool):
        self._errors_only = enabled
        self.clear()
        for severity, message in self._buffer:
            if self._passes(severity):
                super().append_log(severity, message)

    def clear_all(self):
        self._buffer.clear()
        self.clear()


# Main window
class Dashboard(QMainWindow):
    def __init__(self, scripts_root: Path, host: str = "127.0.0.1", port: int = 8888,
                 game_log_dir: Path = GAME_LOG_DIR):
        super().__init__()
        self.scripts_root = scripts_root
        self.host, self.port = host, port
        self.game_log_dir = Path(game_log_dir)

        self._current_path = None        # script currently open in the editor
        self._current_game_log = None    # log file currently tailed
        self._unread_game_errors = 0

        self.setWindowTitle("Toontown Python Dashboard")
        self.resize(1280, 820)
        self._build_ui()
        self._apply_theme()

        self.console.append_log("system", f"[*] scripts root  : {self.scripts_root}")
        self.console.append_log("system", f"[*] ipc target    : {self.host}:{self.port}")
        self.console.append_log("system", "[*] ready.  Ctrl+Enter to execute, Ctrl+S to save.")

        self._start_log_watcher()

    # ui scaffolding
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
        self.editor.document().modificationChanged.connect(self._refresh_title)

        self.host_label = QLabel(f"target  {self.host}:{self.port}")
        self.host_label.setObjectName("hostLabel")

        self.file_label = QLabel("unsaved buffer")
        self.file_label.setObjectName("fileLabel")

        self.save_btn = QPushButton("save")
        self.save_btn.setObjectName("ghostBtn")
        self.save_btn.setToolTip("Save to the opened script (Ctrl+S)")
        self.save_btn.clicked.connect(self._on_save)
        QShortcut("Ctrl+S", self, activated=self._on_save)

        self.run_btn = QPushButton("EXECUTE SCRIPT")
        self.run_btn.setObjectName("runBtn")
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setShortcut("Ctrl+Return")
        self.run_btn.clicked.connect(self._on_execute)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.host_label)
        toolbar.addSpacing(16)
        toolbar.addWidget(self.file_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self.save_btn)
        toolbar.addSpacing(8)
        toolbar.addWidget(self.run_btn)

        editor_header = QLabel("  EDITOR")
        editor_header.setObjectName("panelHeader")
        editor_panel = QWidget()
        ep = QVBoxLayout(editor_panel)
        ep.setContentsMargins(8, 6, 8, 8)
        ep.addWidget(editor_header)
        ep.addLayout(toolbar)
        ep.addWidget(self.editor, 1)

        # console tabs: bridge output | game log
        self.console = LogConsole()                  # bridge / injector output
        clear_btn = QPushButton("clear")
        clear_btn.setObjectName("ghostBtn")
        clear_btn.clicked.connect(self.console.clear)

        bridge_row = QHBoxLayout()
        bridge_row.addStretch(1)
        bridge_row.addWidget(clear_btn)

        bridge_page = QWidget()
        bp = QVBoxLayout(bridge_page)
        bp.setContentsMargins(0, 6, 0, 0)
        bp.setSpacing(4)
        bp.addLayout(bridge_row)
        bp.addWidget(self.console, 1)

        self.game_console = GameLogConsole()

        self.errors_only_cb = QCheckBox("errors && warnings only")
        self.errors_only_cb.setChecked(True)
        self.errors_only_cb.toggled.connect(self.game_console.set_errors_only)

        open_log_btn = QPushButton("open log file")
        open_log_btn.setObjectName("ghostBtn")
        open_log_btn.setToolTip("Open the current game log in your text editor")
        open_log_btn.clicked.connect(self._on_open_game_log)

        game_clear_btn = QPushButton("clear")
        game_clear_btn.setObjectName("ghostBtn")
        game_clear_btn.clicked.connect(self.game_console.clear_all)

        game_row = QHBoxLayout()
        game_row.addWidget(self.errors_only_cb)
        game_row.addStretch(1)
        game_row.addWidget(open_log_btn)
        game_row.addSpacing(6)
        game_row.addWidget(game_clear_btn)

        game_page = QWidget()
        gp = QVBoxLayout(game_page)
        gp.setContentsMargins(0, 6, 0, 0)
        gp.setSpacing(4)
        gp.addLayout(game_row)
        gp.addWidget(self.game_console, 1)

        self.tabs = QTabWidget()
        self.tabs.addTab(bridge_page, "CONSOLE")
        self.tabs.addTab(game_page, "GAME LOG")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        console_panel = QWidget()
        cp = QVBoxLayout(console_panel)
        cp.setContentsMargins(8, 4, 8, 8)
        cp.addWidget(self.tabs)

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

        QTabWidget::pane { border: none; }
        QTabBar::tab {
            background: transparent;
            color: #a892c9;
            font-weight: bold;
            letter-spacing: 1px;
            padding: 5px 16px;
            border: 1px solid rgba(124, 77, 255, 0.20);
            border-bottom: none;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            margin-right: 4px;
        }
        QTabBar::tab:selected { background: #140e23; color: #b388ff; }
        QTabBar::tab:hover    { color: #e8d8ff; }

        QCheckBox { color: #a892c9; spacing: 6px; }
        QCheckBox::indicator {
            width: 13px; height: 13px;
            border: 1px solid rgba(124, 77, 255, 0.40);
            border-radius: 4px;
            background: #140e23;
        }
        QCheckBox::indicator:checked { background: #7c4dff; }
        QCheckBox::indicator:hover   { border-color: #b388ff; }

        QLabel#panelHeader {
            color: #b388ff;
            font-weight: bold;
            padding: 4px 2px;
            letter-spacing: 1px;
        }
        QLabel#hostLabel { color: #a892c9; }
        QLabel#fileLabel { color: #7a6aa0; }

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

        QToolTip {
            background: #1f1638;
            color: #e8d8ff;
            border: 1px solid #7c4dff;
            padding: 4px;
        }

        QScrollBar:vertical           { background: transparent; width: 12px; }
        QScrollBar::handle:vertical   { background: #3a2a5e; border-radius: 6px; min-height: 30px; }
        QScrollBar::handle:vertical:hover { background: #7c4dff; }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical { height: 0; }
        """)

    # game log watcher
    def _start_log_watcher(self):
        self._log_watcher = GameLogWatcher(self.game_log_dir, parent=self)
        self._log_watcher.line.connect(self._on_game_log_line)
        self._log_watcher.switched.connect(self._on_game_log_switched)
        self._log_watcher.start()

    def _on_game_log_line(self, severity: str, message: str):
        self.game_console.append_log(severity, message)
        if severity in ("warn", "error") and self.tabs.currentIndex() != 1:
            self._unread_game_errors += 1
            self.tabs.setTabText(1, f"GAME LOG ({self._unread_game_errors})")

    def _on_game_log_switched(self, path: str):
        self._current_game_log = path

    def _on_tab_changed(self, index: int):
        if index == 1 and self._unread_game_errors:
            self._unread_game_errors = 0
            self.tabs.setTabText(1, "GAME LOG")

    def _on_open_game_log(self):
        target = self._current_game_log or str(self.game_log_dir)
        try:
            os.startfile(target)
        except OSError as e:
            self.console.append_log("error", f"[!] could not open {target}: {e}")

    def closeEvent(self, event):
        watcher = getattr(self, "_log_watcher", None)
        if watcher is not None:
            watcher.stop()
            watcher.wait(2000)
        super().closeEvent(event)

    # handlers
    def _refresh_title(self, *_):
        name = os.path.basename(self._current_path) if self._current_path else None
        dirty = "* " if self.editor.document().isModified() else ""
        if name:
            self.setWindowTitle(f"Toontown Python Dashboard - {dirty}{name}")
            self.file_label.setText(f"{dirty}{name}")
        else:
            self.setWindowTitle("Toontown Python Dashboard")
            self.file_label.setText(f"{dirty}unsaved buffer")

    def _on_tree_open(self, index):
        path = self.fs_model.filePath(index)
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as fp:
                self.editor.setPlainText(fp.read())
            self._current_path = path
            self.editor.document().setModified(False)
            rel = os.path.relpath(path, self.scripts_root)
            self.console.append_log("system", f"[*] loaded  {rel}")
            self._refresh_title()
        except OSError as e:
            self.console.append_log("error", f"[!] could not open {path}: {e}")

    def _on_save(self):
        if not self._current_path:
            self.console.append_log(
                "warn", "[~] no file open - double-click a script in the sidebar first."
            )
            return
        try:
            with open(self._current_path, "w", encoding="utf-8") as fp:
                fp.write(self.editor.toPlainText())
            self.editor.document().setModified(False)
            rel = os.path.relpath(self._current_path, self.scripts_root)
            self.console.append_log("system", f"[*] saved  {rel}")
            self.statusBar().showMessage(f"saved {rel}", 3000)
            self._refresh_title()
        except OSError as e:
            self.console.append_log("error", f"[!] could not save {self._current_path}: {e}")

    def _on_execute(self):
        payload = self.editor.toPlainText()
        if not payload.strip():
            self.console.append_log("warn", "[~] editor is empty.")
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("RUNNING...")
        self.statusBar().showMessage("sending...")
        self.tabs.setCurrentIndex(0)
        self.console.append_log("system", "-" * 60)

        self._bridge = IPCBridge(self.host, self.port, payload, self)
        self._bridge.log.connect(self.console.append_log)
        self._bridge.finished_run.connect(self._on_run_done)
        self._bridge.start()

    def _on_run_done(self):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("EXECUTE SCRIPT")
        self.statusBar().showMessage("idle")


# entry point
def main():
    try:
        scripts_root = GAME_LOG_DIR / "toonbot" / "Injectables"
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
