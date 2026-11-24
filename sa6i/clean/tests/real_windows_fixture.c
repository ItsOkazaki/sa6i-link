// SPDX-License-Identifier: GPL-3.0-or-later
// Inert synthetic window for native embedding CI. This is NOT the cleaner.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static LRESULT CALLBACK window_proc(HWND window, UINT message, WPARAM wp, LPARAM lp)
{
    if (message == WM_CLOSE) {
        DestroyWindow(window);
        return 0;
    }
    if (message == WM_DESTROY) {
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(window, message, wp, lp);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command, int show)
{
    (void)previous; (void)command; (void)show;
    WNDCLASSW wc = {0};
    wc.lpfnWndProc = window_proc;
    wc.hInstance = instance;
    wc.lpszClassName = L"Sa6iSyntheticCleanerWindow";
    if (!RegisterClassW(&wc)) return 1;
    HWND window = CreateWindowExW(0, wc.lpszClassName, L"Synthetic test window",
        WS_OVERLAPPEDWINDOW, 100, 100, 400, 300, NULL, NULL, instance, NULL);
    if (!window) return 2;
    ShowWindow(window, SW_SHOW);
    MSG msg;
    int result;
    while ((result = GetMessageW(&msg, NULL, 0, 0)) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    return result < 0 ? 3 : 0;
}
