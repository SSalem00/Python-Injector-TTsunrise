"""
Toontown auto-injecting launcher.

Spawns ToontownLauncher.exe so the user can log in, watches for Toontown.exe
to appear, injects inject.dll via CreateRemoteThread(LoadLibraryA), then opens
the dashboard. One click instead of three programs.
"""

import ctypes
import os
import struct
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

# ---- paths -----------------------------------------------------------------
ROOT          = Path(r"C:\Program Files (x86)\Disney\Disney Online\ToontownOnline")
LAUNCHER_EXE  = ROOT / "ToontownLauncher.exe"
GAME_EXE_NAME = "Toontown.exe"


def _bundled_or_install(*parts):
    """Prefer a copy bundled inside the PyInstaller onefile (sys._MEIPASS);
    fall back to the on-disk install location when run as a plain script."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = Path(base).joinpath(*parts)
        if p.exists():
            return p
    return ROOT.joinpath(*parts)


INJECT_DLL    = _bundled_or_install("TTInjector", "TTHook.dll")
# Anchored to the install dir (not __file__) so paths stay correct when frozen
# into a PyInstaller onefile EXE, whose __file__ lives in a temp extract dir.
TOONBOT_PY    = ROOT / "toonbot" / "ToonBot.py"
DASHBOARD     = ROOT / "toonbot" / "dashboard.py"

WATCH_TIMEOUT_SEC    = 600     # 10 minutes to log in
POLL_INTERVAL_SEC    = 0.5
PRE_INJECT_DELAY_SEC = 15.0    # wait this long after Toontown.exe is detected

# ---- win32 -----------------------------------------------------------------
PROCESS_ALL_ACCESS      = 0x1F0FFF
MEM_COMMIT_RESERVE      = 0x1000 | 0x2000
PAGE_READWRITE          = 0x04
PAGE_EXECUTE_READWRITE  = 0x40
INFINITE                = 0xFFFFFFFF
LIST_MODULES_32BIT      = 0x01
LIST_MODULES_64BIT      = 0x02
DETACHED_PROCESS        = 0x00000008
CREATE_NO_WINDOW        = 0x08000000
TH32CS_SNAPPROCESS      = 0x00000002
INVALID_HANDLE_VALUE    = ctypes.c_void_p(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize",              wintypes.DWORD),
        ("cntUsage",            wintypes.DWORD),
        ("th32ProcessID",       wintypes.DWORD),
        ("th32DefaultHeapID",   ctypes.c_void_p),
        ("th32ModuleID",        wintypes.DWORD),
        ("cntThreads",          wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase",      wintypes.LONG),
        ("dwFlags",             wintypes.DWORD),
        ("szExeFile",           wintypes.WCHAR * 260),
    ]

k32   = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi",    use_last_error=True)

k32.OpenProcess.argtypes      = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype       = wintypes.HANDLE
k32.CloseHandle.argtypes      = [wintypes.HANDLE]
k32.CloseHandle.restype       = wintypes.BOOL
k32.VirtualAllocEx.argtypes   = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
k32.VirtualAllocEx.restype    = ctypes.c_void_p
k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.restype  = wintypes.BOOL
k32.ReadProcessMemory.argtypes  = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.restype   = wintypes.BOOL
k32.CreateRemoteThread.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
k32.CreateRemoteThread.restype  = wintypes.HANDLE
k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
k32.WaitForSingleObject.restype  = wintypes.DWORD
k32.IsWow64Process.argtypes     = [wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
k32.IsWow64Process.restype      = wintypes.BOOL
k32.GetModuleHandleW.argtypes   = [wintypes.LPCWSTR]
k32.GetModuleHandleW.restype    = wintypes.HMODULE
k32.GetProcAddress.argtypes     = [wintypes.HMODULE, wintypes.LPCSTR]
k32.GetProcAddress.restype      = ctypes.c_void_p

psapi.EnumProcessModulesEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
psapi.EnumProcessModulesEx.restype  = wintypes.BOOL
psapi.GetModuleBaseNameW.argtypes   = [wintypes.HANDLE, ctypes.c_void_p, wintypes.LPWSTR, wintypes.DWORD]
psapi.GetModuleBaseNameW.restype    = wintypes.DWORD

k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
k32.CreateToolhelp32Snapshot.restype  = wintypes.HANDLE
k32.Process32FirstW.argtypes          = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
k32.Process32FirstW.restype           = wintypes.BOOL
k32.Process32NextW.argtypes           = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
k32.Process32NextW.restype            = wintypes.BOOL


def find_pid_by_name(name: str):
    """Return the first PID whose executable name matches (case-insensitive)."""
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        return None
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if not k32.Process32FirstW(snap, ctypes.byref(entry)):
            return None
        target = name.lower()
        while True:
            if entry.szExeFile.lower() == target:
                return entry.th32ProcessID
            if not k32.Process32NextW(snap, ctypes.byref(entry)):
                return None
    finally:
        k32.CloseHandle(snap)


def _is_target_wow64(h_proc) -> bool:
    out = wintypes.BOOL()
    if not k32.IsWow64Process(h_proc, ctypes.byref(out)):
        return False
    return bool(out.value)


def _rpm(h_proc, addr, size):
    buf = (ctypes.c_ubyte * size)()
    n = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h_proc, addr, buf, size, ctypes.byref(n)):
        raise OSError(f"ReadProcessMemory @ 0x{addr:x} failed")
    return bytes(buf[: n.value])


def _find_remote_module(h_proc, dll_name: str, want_32bit: bool):
    flag = LIST_MODULES_32BIT if want_32bit else LIST_MODULES_64BIT
    needed = wintypes.DWORD()
    psapi.EnumProcessModulesEx(h_proc, None, 0, ctypes.byref(needed), flag)
    if needed.value == 0:
        return None
    arr = (ctypes.c_void_p * (needed.value // ctypes.sizeof(ctypes.c_void_p)))()
    if not psapi.EnumProcessModulesEx(h_proc, arr, needed.value, ctypes.byref(needed), flag):
        return None
    name = ctypes.create_unicode_buffer(260)
    want = dll_name.lower()
    for mod in arr:
        if not mod:
            continue
        psapi.GetModuleBaseNameW(h_proc, mod, name, 260)
        if name.value.lower() == want:
            return mod
    return None


def _find_remote_kernel32(h_proc, want_32bit: bool):
    return _find_remote_module(h_proc, "kernel32.dll", want_32bit)


def _find_export_rva(h_proc, base, symbol: str):
    dos = _rpm(h_proc, base, 0x40)
    e_lfanew = struct.unpack_from("<I", dos, 0x3C)[0]
    nt = _rpm(h_proc, base + e_lfanew, 0x108)
    magic = struct.unpack_from("<H", nt, 24)[0]            # 0x10b = PE32, 0x20b = PE32+
    dd_off = 24 + (96 if magic == 0x10b else 112)
    exp_rva, _ = struct.unpack_from("<II", nt, dd_off)
    if not exp_rva:
        return None

    exp = _rpm(h_proc, base + exp_rva, 40)
    n_names = struct.unpack_from("<I", exp, 24)[0]
    af_rva, an_rva, ao_rva = struct.unpack_from("<III", exp, 28)

    names    = _rpm(h_proc, base + an_rva, n_names * 4)
    ordinals = _rpm(h_proc, base + ao_rva, n_names * 2)
    funcs_rva_table_base = base + af_rva

    want = symbol.encode("ascii")
    for i in range(n_names):
        rva = struct.unpack_from("<I", names, i * 4)[0]
        s = _rpm(h_proc, base + rva, 256).split(b"\x00", 1)[0]
        if s == want:
            ord_i = struct.unpack_from("<H", ordinals, i * 2)[0]
            return struct.unpack_from("<I", _rpm(h_proc, funcs_rva_table_base + ord_i * 4, 4), 0)[0]
    return None


def _loadlibrary_addr(h_proc):
    """Address of LoadLibraryA inside the target, regardless of bitness mismatch."""
    self_is_64   = struct.calcsize("P") == 8
    target_is_32 = _is_target_wow64(h_proc) or not self_is_64

    if self_is_64 == (not target_is_32):
        # bitness matches — kernel32 lives at the same base in both processes
        h = k32.GetModuleHandleW("kernel32.dll")
        return k32.GetProcAddress(h, b"LoadLibraryA")

    # 64-bit Python injecting into 32-bit target: walk the target's 32-bit kernel32.
    base = _find_remote_kernel32(h_proc, want_32bit=True)
    if not base:
        raise OSError("32-bit kernel32 not found in target (loader not ready?)")
    rva = _find_export_rva(h_proc, base, "LoadLibraryA")
    if not rva:
        raise OSError("LoadLibraryA export not found in target kernel32")
    return base + rva


def inject(pid: int, dll_path: str):
    h = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not h:
        raise OSError(f"OpenProcess({pid}) failed — try running as administrator")
    try:
        addr = _loadlibrary_addr(h)
        payload = dll_path.encode("utf-8") + b"\x00"
        remote = k32.VirtualAllocEx(h, None, len(payload), MEM_COMMIT_RESERVE, PAGE_READWRITE)
        if not remote:
            raise OSError("VirtualAllocEx failed")
        written = ctypes.c_size_t(0)
        if not k32.WriteProcessMemory(h, remote, payload, len(payload), ctypes.byref(written)):
            raise OSError("WriteProcessMemory failed")
        tid = wintypes.DWORD(0)
        th = k32.CreateRemoteThread(h, None, 0, addr, remote, 0, ctypes.byref(tid))
        if not th:
            raise OSError("CreateRemoteThread failed")
        k32.WaitForSingleObject(th, INFINITE)
        k32.CloseHandle(th)
    finally:
        k32.CloseHandle(h)


def _queue_python_code(pid: int, code: str):
    """
    Thread-safe Python injection via Py_AddPendingCall.

    Calling PyRun_SimpleString directly from a foreign thread is unsafe:
    the thread has no Python thread state, and importing 'threading' inside
    the code enables the GIL mid-execution — the thread then exits without
    releasing it, deadlocking the game.

    Py_AddPendingCall IS thread-safe (no GIL needed).  It enqueues a
    (func, arg) pair that the main interpreter thread drains on the next
    bytecode tick.  We queue (PyRun_SimpleString, code_ptr) using a tiny
    20-byte x86 shellcode stub, then our remote thread exits immediately
    without ever touching the GIL.
    """
    h = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not h:
        raise OSError(f"OpenProcess({pid}) failed — try running as administrator")
    try:
        base = _find_remote_module(h, "python24.dll", want_32bit=True)
        if not base:
            raise OSError("python24.dll not loaded in target (game still booting?)")

        pyrun_rva = _find_export_rva(h, base, "PyRun_SimpleString")
        if not pyrun_rva:
            raise OSError("PyRun_SimpleString not found in python24.dll")
        pyrun_addr = base + pyrun_rva

        papc_rva = _find_export_rva(h, base, "Py_AddPendingCall")
        if not papc_rva:
            raise OSError("Py_AddPendingCall not found in python24.dll")
        papc_addr = base + papc_rva

        # Write the Python code string (ASCII) into readable target memory.
        payload = code.encode("ascii") + b"\x00"
        code_mem = k32.VirtualAllocEx(
            h, None, len(payload), MEM_COMMIT_RESERVE, PAGE_READWRITE
        )
        if not code_mem:
            raise OSError("VirtualAllocEx (code) failed")
        written = ctypes.c_size_t(0)
        k32.WriteProcessMemory(h, code_mem, payload, len(payload), ctypes.byref(written))

        # x86 shellcode (called as stdcall LPTHREAD_START_ROUTINE by CreateRemoteThread):
        #   push  code_mem        ; arg  → PyRun_SimpleString receives this
        #   push  pyrun_addr      ; func → PyRun_SimpleString
        #   mov   eax, papc_addr
        #   call  eax             ; Py_AddPendingCall(PyRun_SimpleString, code_mem)
        #   add   esp, 8          ; cdecl caller-cleanup (2 args × 4 bytes)
        #   xor   eax, eax        ; return 0  (DWORD thread exit code)
        #   ret   4               ; stdcall epilogue — pop lpParameter pushed by CRT
        shellcode = (
            b"\x68" + struct.pack("<I", code_mem)    # push code_mem
            + b"\x68" + struct.pack("<I", pyrun_addr) # push pyrun_addr
            + b"\xB8" + struct.pack("<I", papc_addr)  # mov eax, papc_addr
            + b"\xFF\xD0"                              # call eax
            + b"\x83\xC4\x08"                          # add esp, 8
            + b"\x31\xC0"                              # xor eax, eax
            + b"\xC2\x04\x00"                          # ret 4
        )

        sc_mem = k32.VirtualAllocEx(
            h, None, len(shellcode), MEM_COMMIT_RESERVE, PAGE_EXECUTE_READWRITE
        )
        if not sc_mem:
            raise OSError("VirtualAllocEx (shellcode) failed")
        k32.WriteProcessMemory(h, sc_mem, shellcode, len(shellcode), ctypes.byref(written))

        tid = wintypes.DWORD(0)
        th = k32.CreateRemoteThread(h, None, 0, sc_mem, None, 0, ctypes.byref(tid))
        if not th:
            raise OSError("CreateRemoteThread failed")
        k32.WaitForSingleObject(th, INFINITE)
        k32.CloseHandle(th)
    finally:
        k32.CloseHandle(h)


def _bridge_is_up(host="127.0.0.1", port=8888, timeout=0.5) -> bool:
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_game(timeout: float, poll: float):
    """Block until Toontown.exe appears in the process list. Returns its PID."""
    deadline = time.monotonic() + timeout
    last_log = 0.0
    while time.monotonic() < deadline:
        pid = find_pid_by_name(GAME_EXE_NAME)
        if pid:
            return pid
        now = time.monotonic()
        if now - last_log >= 5:
            remaining = int(deadline - now)
            print(f"[*] still waiting for {GAME_EXE_NAME}… ({remaining}s left)")
            last_log = now
        time.sleep(poll)
    return None


def main():
    if not LAUNCHER_EXE.exists():
        sys.exit(f"missing: {LAUNCHER_EXE}")
    if not INJECT_DLL.exists():
        sys.exit(f"missing: {INJECT_DLL}")

    existing = find_pid_by_name(GAME_EXE_NAME)
    if existing:
        print(f"[*] {GAME_EXE_NAME} already running (pid {existing}) — skipping launcher.")
        game_pid = existing
    else:
        print(f"[*] starting login launcher: {LAUNCHER_EXE}")
        subprocess.Popen([str(LAUNCHER_EXE)], cwd=str(LAUNCHER_EXE.parent))
        print(f"[*] log in, then wait — watching for {GAME_EXE_NAME} to appear.")
        game_pid = wait_for_game(WATCH_TIMEOUT_SEC, POLL_INTERVAL_SEC)
        if not game_pid:
            sys.exit(f"[!] timed out after {WATCH_TIMEOUT_SEC}s waiting for {GAME_EXE_NAME}")
        print(f"[+] detected {GAME_EXE_NAME} pid {game_pid} — "
              f"waiting {PRE_INJECT_DELAY_SEC:.0f}s for game to finish loading…")
        for remaining in range(int(PRE_INJECT_DELAY_SEC), 0, -5):
            print(f"    {remaining}s")
            time.sleep(5)
        # finish any sub-5s remainder
        leftover = PRE_INJECT_DELAY_SEC - (int(PRE_INJECT_DELAY_SEC) // 5) * 5
        if leftover > 0:
            time.sleep(leftover)

    # Step 1: inject.dll — opens the manual REPL window in-game (optional).
    last_err = None
    for attempt in range(20):
        try:
            inject(game_pid, str(INJECT_DLL))
            print(f"[+] injected {INJECT_DLL.name}")
            break
        except OSError as e:
            last_err = e
            time.sleep(0.25)
    else:
        print(f"[~] inject.dll failed (non-fatal): {last_err}")

    # Step 2: queue ToonBot.py on the main interpreter thread via Py_AddPendingCall.
    # Our shellcode returns immediately — no GIL touched, no crash.
    if TOONBOT_PY.exists():
        # Pure ASCII bootstrap — no imports, no threading, safe to send as const char*.
        bootstrap = "execfile(r'{}')".format(str(TOONBOT_PY))
        print(f"[*] queuing {TOONBOT_PY.name} via Py_AddPendingCall…")
        try:
            _queue_python_code(game_pid, bootstrap)
            print("[+] queued — ToonBot.py will run on next interpreter tick")
        except OSError as e:
            sys.exit(f"[!] queue failed: {e}")

        print("[*] probing 127.0.0.1:8888…")
        for i in range(20):
            time.sleep(0.5)
            if _bridge_is_up():
                print(f"[+] bridge live on :8888 after ~{(i + 1) * 0.5:.0f}s")
                break
        else:
            print("[!] bridge not responding — check in-game for a ToonBot.py error.")
    else:
        print(f"[~] {TOONBOT_PY} not found — dashboard bridge won't start.")

    if DASHBOARD.exists():
        print(f"[+] opening dashboard: {DASHBOARD}")
        # Launch with pythonw (no console) and no extra window — the dashboard
        # GUI is the only window the user should see.
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        interpreter = str(pythonw) if pythonw.exists() else sys.executable
        subprocess.Popen(
            [interpreter, str(DASHBOARD)],
            cwd=str(DASHBOARD.parent),
            creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
            close_fds=True,
        )
    else:
        print(f"[~] dashboard not found at {DASHBOARD}, skipping")

    print("[*] launcher done. Game and dashboard are running independently.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit…")
