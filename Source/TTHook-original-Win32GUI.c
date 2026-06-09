#include <windows.h>

// ── Python imports (resolved at inject time) ──────────────────────────
typedef int  (*PyRun_SimpleString_t)(const char*);
typedef void (*PyEval_EvalCodeEx_t)(void*,void*,void*,void*,int,void*,int,void*,int,void*);

PyRun_SimpleString_t  real_PyRun_SimpleString  = NULL;
PyEval_EvalCodeEx_t   real_PyEval_EvalCodeEx   = NULL;

// ── Globals ───────────────────────────────────────────────────────────
#define INPUT_BUF_SIZE  (1024 * 1024)

static HINSTANCE g_hInst       = NULL;
static HWND      g_hWnd        = NULL;
static HWND      g_hInput      = NULL;
static HWND      g_hLog        = NULL;
static HWND      g_hBtnSubmit  = NULL;
static HWND      g_hBtnClear   = NULL;

static char g_inputBuf[INPUT_BUF_SIZE];
static char g_pendingCode[INPUT_BUF_SIZE];
static BOOL g_hasPending = FALSE;

static BYTE g_origBytes[5];

// ── Console log (pure Win32, no CRT) ─────────────────────────────────
void Log(const char* fmt, ...) {
    char buf[1024];
    char line[1100];
    va_list args;
    SYSTEMTIME st;

    va_start(args, fmt);
    wvsprintfA(buf, fmt, args);
    va_end(args);

    GetLocalTime(&st);
    wsprintfA(line, "[%02d:%02d:%02d] %s\r\n",
              st.wHour, st.wMinute, st.wSecond, buf);

    if (g_hLog) {
        int len = GetWindowTextLengthA(g_hLog);
        SendMessageA(g_hLog, EM_SETSEL, len, len);
        SendMessageA(g_hLog, EM_REPLACESEL, FALSE, (LPARAM)line);
        SendMessageA(g_hLog, WM_VSCROLL, SB_BOTTOM, 0);
    }
    OutputDebugStringA(line);
}

// ── Hook stub ─────────────────────────────────────────────────────────
void __cdecl HookStub(void* co, void* globals, void* locals) {
    if (g_hasPending) {
        g_hasPending = FALSE;
        Log("Executing queued code...");
        int result = real_PyRun_SimpleString(g_pendingCode);
        if (result == 0)
            Log("OK");
        else
            Log("Error: PyRun_SimpleString returned %d", result);
    }
    real_PyEval_EvalCodeEx(co, globals, locals,
                           NULL,0, NULL,0, NULL,0, NULL);
}

// ── Install hook ──────────────────────────────────────────────────────
static BOOL InstallHook(void) {
    // python24.dll first, then fallback to newer versions
    HMODULE hPy = GetModuleHandleA("python24.dll");
    if (!hPy) hPy = GetModuleHandleA("python25.dll");
    if (!hPy) hPy = GetModuleHandleA("python26.dll");
    if (!hPy) hPy = GetModuleHandleA("python27.dll");
    if (!hPy) {
        Log("ERROR: No python2x.dll found in process");
        return FALSE;
    }

    // log which one we found
    char modName[64];
    GetModuleFileNameA(hPy, modName, sizeof(modName));
    Log("Found: %s", modName);

    void* pEvalCode = GetProcAddress(hPy, "PyEval_EvalCode");
    if (!pEvalCode) {
        Log("ERROR: PyEval_EvalCode not found");
        return FALSE;
    }

    real_PyRun_SimpleString = (PyRun_SimpleString_t)
                               GetProcAddress(hPy, "PyRun_SimpleString");
    real_PyEval_EvalCodeEx  = (PyEval_EvalCodeEx_t)
                               GetProcAddress(hPy, "PyEval_EvalCodeEx");

    if (!real_PyRun_SimpleString || !real_PyEval_EvalCodeEx) {
        Log("ERROR: Could not resolve Python functions");
        return FALSE;
    }

    DWORD oldProt;
    VirtualProtect(pEvalCode, 5, PAGE_EXECUTE_READWRITE, &oldProt);
    memcpy(g_origBytes, pEvalCode, 5);

    DWORD rel = (DWORD)HookStub - (DWORD)pEvalCode - 5;
    ((BYTE*)pEvalCode)[0] = 0xE9;
    memcpy((BYTE*)pEvalCode + 1, &rel, 4);

    VirtualProtect(pEvalCode, 5, oldProt, &oldProt);

    Log("Hook installed @ 0x%08X", (DWORD)pEvalCode);
    Log("PyRun_SimpleString @ 0x%08X", (DWORD)real_PyRun_SimpleString);
    Log("Ready — type code and hit Submit");
    return TRUE;
}

// ── Submit handler ────────────────────────────────────────────────────
static void OnSubmit(void) {
    int len = GetWindowTextLengthA(g_hInput);
    if (len == 0) {
        Log("Nothing to submit");
        return;
    }
    GetWindowTextA(g_hInput, g_inputBuf, INPUT_BUF_SIZE);

    // strip \r
    int out = 0;
    for (int i = 0; g_inputBuf[i] && i < INPUT_BUF_SIZE - 1; i++) {
        if (g_inputBuf[i] != '\r')
            g_pendingCode[out++] = g_inputBuf[i];
    }
    g_pendingCode[out] = '\0';

    g_hasPending = TRUE;
    Log("Queued %d bytes — waiting for next eval tick", out);
}

// ── Window proc ───────────────────────────────────────────────────────
#define ID_BTN_SUBMIT  1
#define ID_BTN_CLEAR   2

LRESULT CALLBACK WndProc(HWND hWnd, UINT msg,
                          WPARAM wParam, LPARAM lParam) {
    switch (msg) {
    case WM_CREATE: {
        HFONT hMono = CreateFontA(14, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                                  ANSI_CHARSET, OUT_DEFAULT_PRECIS,
                                  CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY,
                                  FIXED_PITCH | FF_MODERN, "Consolas");

        g_hInput = CreateWindowExA(WS_EX_CLIENTEDGE, "EDIT", "",
            WS_CHILD | WS_VISIBLE | WS_VSCROLL |
            ES_MULTILINE | ES_AUTOVSCROLL | ES_WANTRETURN,
            5, 5, 490, 180, hWnd, (HMENU)3, g_hInst, NULL);
        SendMessageA(g_hInput, WM_SETFONT, (WPARAM)hMono, TRUE);
        SetWindowTextA(g_hInput, "# Python 2.4 — no parens on print\r\nprint \"hello world\"");

        g_hBtnSubmit = CreateWindowExA(0, "BUTTON", "Submit",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
            5, 192, 100, 28, hWnd, (HMENU)ID_BTN_SUBMIT, g_hInst, NULL);

        g_hBtnClear = CreateWindowExA(0, "BUTTON", "Clear Log",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
            112, 192, 100, 28, hWnd, (HMENU)ID_BTN_CLEAR, g_hInst, NULL);

        g_hLog = CreateWindowExA(WS_EX_CLIENTEDGE, "EDIT", "",
            WS_CHILD | WS_VISIBLE | WS_VSCROLL |
            ES_MULTILINE | ES_AUTOVSCROLL | ES_READONLY,
            5, 228, 490, 220, hWnd, (HMENU)4, g_hInst, NULL);
        SendMessageA(g_hLog, WM_SETFONT, (WPARAM)hMono, TRUE);

        Log("=== Toontown Python Injector ===");
        InstallHook();
        return 0;
    }

    case WM_COMMAND:
        switch (LOWORD(wParam)) {
        case ID_BTN_SUBMIT:
            OnSubmit();
            break;
        case ID_BTN_CLEAR:
            SetWindowTextA(g_hLog, "");
            Log("Log cleared");
            break;
        }
        return 0;

    case WM_SIZE: {
        int w = LOWORD(lParam);
        int h = HIWORD(lParam);
        int inputH = (h - 44) * 45 / 100;
        int logH   = (h - 44) * 55 / 100;
        int btnY   = inputH + 8;
        int logY   = btnY + 32;
        MoveWindow(g_hInput,     5,   5,    w-10, inputH, TRUE);
        MoveWindow(g_hBtnSubmit, 5,   btnY, 100,  28,     TRUE);
        MoveWindow(g_hBtnClear,  112, btnY, 100,  28,     TRUE);
        MoveWindow(g_hLog,       5,   logY, w-10, logH,   TRUE);
        return 0;
    }

    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcA(hWnd, msg, wParam, lParam);
}

// ── UI thread ─────────────────────────────────────────────────────────
static DWORD WINAPI UIThread(LPVOID unused) {
    WNDCLASSEXA wc = {0};
    wc.cbSize        = sizeof(wc);
    wc.style         = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc   = WndProc;
    wc.hInstance     = g_hInst;
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    wc.lpszClassName = "TTInjector";
    wc.hCursor       = LoadCursorA(NULL, IDC_ARROW);
    RegisterClassExA(&wc);

    g_hWnd = CreateWindowExA(
        WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
        "TTInjector", "Toontown Python Injector",
        WS_OVERLAPPEDWINDOW,
        100, 100, 510, 490,
        NULL, NULL, g_hInst, NULL);

    ShowWindow(g_hWnd, SW_SHOW);
    UpdateWindow(g_hWnd);

    MSG msg;
    while (GetMessageA(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageA(&msg);
    }
    return 0;
}

// ── DllMain ───────────────────────────────────────────────────────────
BOOL WINAPI DllMain(HINSTANCE hInst, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hInst);
        g_hInst = hInst;
        CreateThread(NULL, 0, UIThread, NULL, 0, NULL);
    }
    return TRUE;
}
