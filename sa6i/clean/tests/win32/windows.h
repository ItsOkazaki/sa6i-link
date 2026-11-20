// Test-only minimal Win32 shim. Not used in Windows builds.
#ifndef FAKE_WINDOWS_H
#define FAKE_WINDOWS_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <wchar.h>
#define WINAPI
#define CALLBACK
#define TRUE 1
#define FALSE 0
typedef int BOOL;
typedef unsigned char BYTE;
typedef uint32_t DWORD;
typedef intptr_t LONG_PTR;
typedef intptr_t LPARAM;
typedef void *HANDLE;
typedef void *HWND;
typedef const wchar_t *LPCWSTR;
typedef wchar_t *LPWSTR;
typedef struct { long left, top, right, bottom; } RECT;
typedef struct { DWORD cb; } STARTUPINFOW;
typedef struct { HANDLE hProcess; HANDLE hThread; DWORD dwProcessId, dwThreadId; } PROCESS_INFORMATION;
#define ZeroMemory(x,n) memset((x),0,(n))
#define INVALID_HANDLE_VALUE ((HANDLE)(intptr_t)-1)
#define MAX_PATH 260
#define GENERIC_READ 0x80000000u
#define FILE_SHARE_READ 1u
#define OPEN_EXISTING 3u
#define FILE_ATTRIBUTE_NORMAL 128u
#define ERROR_NOT_ENOUGH_MEMORY 8u
#define ERROR_INVALID_PARAMETER 87u
#define ERROR_INVALID_DATA 13u
#define ERROR_GEN_FAILURE 31u
#define ERROR_ALREADY_EXISTS 183u
#define ERROR_ACCESS_DENIED 5u
#define ERROR_INVALID_WINDOW_HANDLE 1400u
#define ERROR_TIMEOUT 1460u
#define WAIT_OBJECT_0 0u
#define WAIT_TIMEOUT 258u
#define WAIT_FAILED 0xffffffffu
#define SW_HIDE 0
#define SW_SHOWNA 8
#define SWP_NOZORDER 4u
#define SWP_NOACTIVATE 16u
#define SWP_NOSIZE 1u
#define SWP_NOMOVE 2u
#define SWP_FRAMECHANGED 32u
#define SWP_ASYNCWINDOWPOS 0x4000u
#define SWP_SHOWWINDOW 0x0040u
#define SWP_HIDEWINDOW 0x0080u
#define GWL_STYLE (-16)
#define WS_POPUP 0x80000000L
#define WS_CAPTION 0x00c00000L
#define WS_THICKFRAME 0x00040000L
#define WS_CHILD 0x40000000L
#define WS_CLIPCHILDREN 0x02000000L
#define GW_OWNER 4
#define WM_CLOSE 16

BOOL IsWindow(HWND);
BOOL IsWindowVisible(HWND);
HWND GetWindow(HWND, unsigned int);
HWND GetParent(HWND);
DWORD GetWindowThreadProcessId(HWND, DWORD *);
DWORD WaitForSingleObject(HANDLE, DWORD);
BOOL GetClientRect(HWND, RECT *);
HWND CreateWindowExW(DWORD, LPCWSTR, LPCWSTR, DWORD, int, int, int, int, HWND, HANDLE, HANDLE, void *);
BOOL DestroyWindow(HWND);
BOOL SetWindowPos(HWND, HWND, int, int, int, int, unsigned int);
BOOL ShowWindowAsync(HWND, int);
DWORD GetTempPathW(DWORD, LPWSTR);
DWORD GetCurrentProcessId(void);
BOOL CreateDirectoryW(LPCWSTR, void *);
HANDLE CreateFileW(LPCWSTR, DWORD, DWORD, void *, DWORD, DWORD, HANDLE);
BOOL ReadFile(HANDLE, void *, DWORD, DWORD *, void *);
BOOL CloseHandle(HANDLE);
BOOL CreateProcessW(LPCWSTR, LPWSTR, void *, void *, BOOL, DWORD, void *, LPCWSTR, STARTUPINFOW *, PROCESS_INFORMATION *);
int lstrlenW(LPCWSTR);
LPWSTR lstrcpyW(LPWSTR, LPCWSTR);
LPWSTR lstrcatW(LPWSTR, LPCWSTR);
BOOL EnumWindows(BOOL (CALLBACK *)(HWND, LPARAM), LPARAM);
LONG_PTR GetWindowLongPtrW(HWND, int);
LONG_PTR SetWindowLongPtrW(HWND, int, LONG_PTR);
HWND SetParent(HWND, HWND);
void SetLastError(DWORD);
DWORD GetLastError(void);
BOOL PostMessageW(HWND, unsigned int, uintptr_t, intptr_t);
#endif
