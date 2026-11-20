// SPDX-License-Identifier: GPL-3.0-or-later
// Standalone Windows-only hosting experiment. NOT integrated into Sa6i Link.
// Launches only the adjacent restricted Sa6i Clean test executable on request.
#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wincrypt.h>

// Zig's Windows linker forces this symbol even for a freestanding executable.
// This probe does not use thread-local storage.
unsigned long _tls_index;

// Exact restricted fixture only. These checks prevent accidentally hosting the
// unrestricted cleaner; they are not an authenticity or anti-tamper guarantee.
#ifdef WIN7_HEADER_PROBE
#define CLEAN_EXE_NAME L"\\Sa6i Clean Win7 Probe.exe"
static const BYTE expected_exe[32] = {
    0x88,0x39,0x33,0x44,0x9d,0x34,0x3d,0xec,0x59,0x25,0xe9,0x06,0x8c,0x7e,0x81,0x05,
    0x26,0x78,0xa1,0x86,0xaf,0x71,0x8f,0xf6,0xa0,0x7c,0x15,0xd6,0xbb,0xb3,0x8a,0xbe
};
#else
#define CLEAN_EXE_NAME L"\\Sa6i Clean.exe"
static const BYTE expected_exe[32] = {
    0xca,0x53,0x9c,0x30,0x6d,0x32,0x92,0x1f,0x9c,0xaa,0x9b,0x55,0xe2,0xfd,0x8e,0xe7,
    0x7e,0x0b,0x44,0xfb,0xf3,0xcf,0xd8,0x1c,0x70,0x66,0x3a,0x20,0x5e,0x99,0x30,0x49
};
#endif
static const BYTE expected_asar[32] = {
    0x33,0x62,0x40,0x3c,0x15,0xda,0xee,0x28,0x46,0xc5,0x9d,0xc4,0x80,0xb4,0x55,0xa3,
    0xe3,0xfa,0x3c,0x24,0x19,0xa5,0xb5,0xa0,0x89,0xff,0x6b,0x85,0xfe,0x38,0xda,0x44
};

#define ID_HOME 100
#define ID_CLEAN 101
#define TIMER_DISCOVER 1
#define TIMER_INTERVAL 100
#define WAIT_TICKS 150

static HWND host, panel, banner, home_button, clean_button, child;
static PROCESS_INFORMATION process_info;
static BOOL clean_active;
static unsigned int ticks;
static wchar_t folder[32768], executable[32768], asar[32768], command_line[32768];
static BYTE hash_buffer[65536];

static void clear_bytes(void *pointer, unsigned int count) {
    BYTE *bytes = (BYTE *)pointer;
    while (count--) *bytes++ = 0;
}

static void message(const wchar_t *text) {
    SetWindowTextW(banner, text);
}

static BOOL verify_file(const wchar_t *path, const BYTE expected[32]) {
    HCRYPTPROV provider = 0;
    HCRYPTHASH hash = 0;
    HANDLE file = INVALID_HANDLE_VALUE;
    BOOL ok = FALSE;
    BYTE digest[32];
    DWORD n = 0, len = sizeof(digest);
    if (!CryptAcquireContextW(&provider, NULL, NULL, PROV_RSA_AES, CRYPT_VERIFYCONTEXT)) goto done;
    if (!CryptCreateHash(provider, CALG_SHA_256, 0, 0, &hash)) goto done;
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) goto done;
    for (;;) {
        if (!ReadFile(file, hash_buffer, sizeof(hash_buffer), &n, NULL)) goto done;
        if (!n) break;
        if (!CryptHashData(hash, hash_buffer, n, 0)) goto done;
    }
    if (!CryptGetHashParam(hash, HP_HASHVAL, digest, &len, 0) || len != sizeof(digest)) goto done;
    ok = TRUE;
    for (unsigned int i = 0; i < sizeof(digest); ++i) {
        if (digest[i] != expected[i]) { ok = FALSE; break; }
    }
 done:
    if (file != INVALID_HANDLE_VALUE) CloseHandle(file);
    if (hash) CryptDestroyHash(hash);
    if (provider) CryptReleaseContext(provider, 0);
    return ok;
}

static BOOL CALLBACK find_process_window(HWND window, LPARAM ignored) {
    DWORD pid = 0;
    (void)ignored;
    GetWindowThreadProcessId(window, &pid);
    if (pid != process_info.dwProcessId || !IsWindowVisible(window) || GetWindow(window, GW_OWNER))
        return TRUE;
    child = window;
    return FALSE;
}

static void layout(void) {
    RECT bounds;
    if (!host || !panel || !banner || !home_button || !clean_button) return;
    if (!GetClientRect(host, &bounds)) return;
    int width = bounds.right, height = bounds.bottom;
    MoveWindow(home_button, 12, 12, 110, 30, TRUE);
    MoveWindow(clean_button, 130, 12, 140, 30, TRUE);
    MoveWindow(banner, 282, 13, width > 294 ? width - 294 : 0, 28, TRUE);
    MoveWindow(panel, 0, 50, width, height > 50 ? height - 50 : 0, TRUE);
    if (child && IsWindow(child)) {
        RECT area;
        GetClientRect(panel, &area);
        MoveWindow(child, 0, 0, area.right, area.bottom, TRUE);
    }
}

static void stop_tracking(void) {
    KillTimer(host, TIMER_DISCOVER);
    if (process_info.hThread) CloseHandle(process_info.hThread);
    if (process_info.hProcess) CloseHandle(process_info.hProcess);
    clear_bytes(&process_info, sizeof(process_info));
    child = NULL;
}

static void launch_cleaner(void) {
    if (process_info.hProcess) {
        clean_active = TRUE;
        if (child && IsWindow(child)) ShowWindow(child, SW_SHOW);
        return;
    }
    if (lstrlenW(folder) + 32 >= 32768) {
        message(L"Path is too long.");
        return;
    }
    lstrcpyW(executable, folder);
    lstrcatW(executable, CLEAN_EXE_NAME);
    lstrcpyW(asar, folder);
    lstrcatW(asar, L"\\resources\\app.asar");
    if (!verify_file(executable, expected_exe) || !verify_file(asar, expected_asar)) {
        message(L"Restricted test files missing or different; nothing was launched.");
        return;
    }
    lstrcpyW(command_line, L"\"");
    lstrcatW(command_line, executable);
    lstrcatW(command_line, L"\"");
    STARTUPINFOW startup;
    clear_bytes(&startup, sizeof(startup));
    startup.cb = sizeof(startup);
    if (!CreateProcessW(executable, command_line, NULL, NULL, FALSE, 0, NULL, folder, &startup, &process_info)) {
        DWORD error = GetLastError();
        wchar_t detail[1024], system_text[768];
        system_text[0] = 0;
        FormatMessageW(FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
                       NULL, error, 0, system_text, 768, NULL);
        wsprintfW(detail, L"Windows error %lu.\n\n%ls\nNo cleaner process was launched."
                  L"\nPlease report this error code and message.", error,
                  system_text[0] ? system_text : L"No Windows description available.");
        message(L"Cleaner did not start. See the Windows error dialog.");
        MessageBoxW(host, detail, L"Sa6i Clean host - launch error", MB_OK | MB_ICONERROR);
        return;
    }
    clean_active = TRUE;
    ticks = 0;
    message(L"Waiting for test cleaner window...");
    SetTimer(host, TIMER_DISCOVER, TIMER_INTERVAL, NULL);
}

static void discover(void) {
    if (!process_info.hProcess) return;
    if (WaitForSingleObject(process_info.hProcess, 0) == WAIT_OBJECT_0) {
        stop_tracking();
        message(L"Test cleaner exited. Click Clean to retry.");
        return;
    }
    if (child && IsWindow(child)) return;
    child = NULL;
    EnumWindows(find_process_window, 0);
    if (!child) {
        if (++ticks >= WAIT_TICKS) {
            // Do not terminate an unknown or slow process; leave it independent.
            stop_tracking();
            message(L"Window was not found; cleaner may still be running separately.");
        }
        return;
    }
    LONG_PTR old_style = GetWindowLongPtrW(child, GWL_STYLE);
    SetLastError(0);
    if (!SetWindowLongPtrW(child, GWL_STYLE, (old_style & ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME)) | WS_CHILD) && GetLastError()) {
        child = NULL;
        stop_tracking();
        message(L"Could not change the cleaner window style; it remains separate.");
        return;
    }
    SetLastError(0);
    HWND previous_parent = SetParent(child, panel);
    if (!previous_parent && GetLastError()) {
        SetWindowLongPtrW(child, GWL_STYLE, old_style);
        SetWindowPos(child, NULL, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED);
        child = NULL;
        stop_tracking();
        message(L"Could not embed the cleaner; it remains separate.");
        return;
    }
    SetWindowPos(child, NULL, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED);
    layout();
    ShowWindow(child, clean_active ? SW_SHOW : SW_HIDE);
    message(L"Integration probe only; not Sa6i Link or a release.");
}

static LRESULT CALLBACK window_proc(HWND window, UINT msg, WPARAM wparam, LPARAM lparam) {
    switch (msg) {
    case WM_SIZE:
        layout();
        return 0;
    case WM_COMMAND:
        if (LOWORD(wparam) == ID_HOME) {
            clean_active = FALSE;
            if (child && IsWindow(child)) ShowWindow(child, SW_HIDE);
            message(L"Home placeholder. Your real Sa6i Link is unchanged.");
        } else if (LOWORD(wparam) == ID_CLEAN) {
            launch_cleaner();
        }
        return 0;
    case WM_TIMER:
        if (wparam == TIMER_DISCOVER) discover();
        return 0;
    case WM_CLOSE:
        if (child && IsWindow(child)) PostMessageW(child, WM_CLOSE, 0, 0);
        stop_tracking();
        DestroyWindow(window);
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    default:
        return DefWindowProcW(window, msg, wparam, lparam);
    }
}

void WINAPI main_entry(void) {
    HINSTANCE instance = GetModuleHandleW(NULL);
    DWORD size = GetModuleFileNameW(NULL, folder, 32768);
    if (!size || size >= 32768) ExitProcess(1);
    wchar_t *slash = NULL;
    for (DWORD i = 0; i < size; ++i) if (folder[i] == L'\\') slash = &folder[i];
    if (!slash) ExitProcess(1);
    *slash = 0;
    WNDCLASSW cls;
    clear_bytes(&cls, sizeof(cls));
    cls.lpfnWndProc = window_proc;
    cls.hInstance = instance;
    cls.hCursor = LoadCursorW(NULL, IDC_ARROW);
    cls.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    cls.lpszClassName = L"Sa6iCleanIntegrationProbe";
    if (!RegisterClassW(&cls)) ExitProcess(1);
    host = CreateWindowExW(0, cls.lpszClassName, L"Sa6i Clean - host experiment", WS_OVERLAPPEDWINDOW,
                           CW_USEDEFAULT, CW_USEDEFAULT, 1280, 820, NULL, NULL, instance, NULL);
    if (!host) ExitProcess(1);
    home_button = CreateWindowExW(0, L"BUTTON", L"Home", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                                  0, 0, 0, 0, host, (HMENU)(INT_PTR)ID_HOME, instance, NULL);
    clean_button = CreateWindowExW(0, L"BUTTON", L"Sa6i Clean", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                                   0, 0, 0, 0, host, (HMENU)(INT_PTR)ID_CLEAN, instance, NULL);
    banner = CreateWindowExW(0, L"STATIC", L"Home placeholder. Your real Sa6i Link is unchanged.", WS_CHILD | WS_VISIBLE,
                             0, 0, 0, 0, host, NULL, instance, NULL);
    panel = CreateWindowExW(0, L"STATIC", L"", WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN,
                            0, 0, 0, 0, host, NULL, instance, NULL);
    if (!home_button || !clean_button || !banner || !panel) ExitProcess(1);
    layout();
    ShowWindow(host, SW_SHOWNORMAL);
    UpdateWindow(host);
    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    ExitProcess(0);
}
