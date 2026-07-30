/*
 * Build (MinGW 32-bit, must match the 32-bit Toontown process):
 *   gcc -m32 -O2 -shared -o TTHook.dll TTHook.c -lkernel32
 * Or with MSVC (x86):
 *   cl /LD /Fe:TTHook.dll TTHook.c
 */

#include <windows.h>

//Python function pointer types
typedef int  (*PyRun_SimpleString_t)(const char*);
typedef void (*PyEval_EvalCodeEx_t)(void*,void*,void*,void*,int,
                                    void*,int,void*,int,void*);

static PyRun_SimpleString_t  real_PyRun_SimpleString = NULL;
static PyEval_EvalCodeEx_t   real_PyEval_EvalCodeEx  = NULL;

//Pending-code queue (set via WriteProcessMemory from the launcher)
#define CODE_BUF_SIZE (1024 * 1024)

static char g_pendingCode[CODE_BUF_SIZE];
static BOOL g_hasPending = FALSE;
static BYTE g_origBytes[5];

//Debug log (OutputDebugString only – no UI)
static void Log(const char* fmt, ...) {
    char buf[1024];
    char line[1100];
    va_list args;
    SYSTEMTIME st;

    va_start(args, fmt);
    wvsprintfA(buf, fmt, args);
    va_end(args);

    GetLocalTime(&st);
    wsprintfA(line, "[TTHook %02d:%02d:%02d] %s\r\n",
              st.wHour, st.wMinute, st.wSecond, buf);
    OutputDebugStringA(line);
}

//Hook stub (replaces PyEval_EvalCode entry point)
void __cdecl HookStub(void* co, void* globals, void* locals) {
    if (g_hasPending) {
        g_hasPending = FALSE;
        Log("Executing queued code");
        int r = real_PyRun_SimpleString(g_pendingCode);
        Log(r == 0 ? "OK" : "PyRun_SimpleString returned %d", r);
    }
    real_PyEval_EvalCodeEx(co, globals, locals,
                           NULL, 0, NULL, 0, NULL, 0, NULL);
}

// Install the 5-byte JMP detour
static BOOL InstallHook(void) {
    HMODULE hPy = GetModuleHandleA("python24.dll");
    if (!hPy) hPy = GetModuleHandleA("python25.dll");
    if (!hPy) hPy = GetModuleHandleA("python26.dll");
    if (!hPy) hPy = GetModuleHandleA("python27.dll");
    if (!hPy) {
        Log("ERROR: no python2x.dll found in process");
        return FALSE;
    }

    char name[MAX_PATH];
    GetModuleFileNameA(hPy, name, sizeof(name));
    Log("Found %s", name);

    void* pEvalCode = (void*)GetProcAddress(hPy, "PyEval_EvalCode");
    if (!pEvalCode) { Log("ERROR: PyEval_EvalCode not found"); return FALSE; }

    real_PyRun_SimpleString = (PyRun_SimpleString_t)
                               GetProcAddress(hPy, "PyRun_SimpleString");
    real_PyEval_EvalCodeEx  = (PyEval_EvalCodeEx_t)
                               GetProcAddress(hPy, "PyEval_EvalCodeEx");

    if (!real_PyRun_SimpleString || !real_PyEval_EvalCodeEx) {
        Log("ERROR: could not resolve Python exports");
        return FALSE;
    }

    DWORD oldProt;
    VirtualProtect(pEvalCode, 5, PAGE_EXECUTE_READWRITE, &oldProt);
    memcpy(g_origBytes, pEvalCode, 5);

    DWORD rel = (DWORD)HookStub - (DWORD)pEvalCode - 5;
    ((BYTE*)pEvalCode)[0] = 0xE9;
    memcpy((BYTE*)pEvalCode + 1, &rel, 4);

    VirtualProtect(pEvalCode, 5, oldProt, &oldProt);

    Log("Hook installed @ 0x%08X → HookStub", (DWORD)pEvalCode);
    Log("PyRun_SimpleString @ 0x%08X", (DWORD)real_PyRun_SimpleString);
    return TRUE;
}

//DLL entry
BOOL WINAPI DllMain(HINSTANCE hInst, DWORD reason, LPVOID reserved) {
    (void)hInst; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hInst);
        InstallHook();
    }
    return TRUE;
}
