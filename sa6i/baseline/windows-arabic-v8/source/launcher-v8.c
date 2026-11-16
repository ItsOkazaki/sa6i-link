#define UNICODE
#define _UNICODE
#include <windows.h>
#include <wchar.h>
static DWORD target_pid, target_tid;
static HMODULE hook_dll;
static HHOOK hook;
static BOOL CALLBACK find_window(HWND hwnd, LPARAM lp) {
 (void)lp; DWORD pid=0, tid=GetWindowThreadProcessId(hwnd,&pid);
 if(pid!=target_pid || !IsWindowVisible(hwnd)) return TRUE;
 if(!hook && tid) {
  HOOKPROC proc=(HOOKPROC)GetProcAddress(hook_dll,"sa6i_hook");
  if(proc) { hook=SetWindowsHookExW(WH_GETMESSAGE,proc,hook_dll,tid); if(hook)target_tid=tid; }
 }
 if(hook && tid==target_tid) PostMessageW(hwnd,WM_NULL,0x53413649,0x4c494e4b);
 return TRUE;
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE prev,PWSTR args,int show) {
 (void)instance;(void)prev;(void)args;(void)show;
 wchar_t dir[32768],exe[32768],dll[32768],command[32768];
 DWORD len=GetModuleFileNameW(NULL,dir,32768); if(!len || len>=32768)return 1;
 wchar_t *slash=wcsrchr(dir,L'\\');if(!slash)return 1;*slash=0;
 if(wcslen(dir)+80>=32768)return 1;
 _snwprintf(exe,32767,L"%ls\\Sa6i-Link-Win7-UI-v8.exe",dir);exe[32767]=0;
 _snwprintf(dll,32767,L"%ls\\sa6i-icon-hook-v4.dll",dir);dll[32767]=0;
 if(GetFileAttributesW(exe)==INVALID_FILE_ATTRIBUTES || GetFileAttributesW(dll)==INVALID_FILE_ATTRIBUTES) {
  MessageBoxW(NULL,L"Put the launcher, the UI-v8 EXE and sa6i-icon-hook-v4.dll together in your working app folder.",L"Sa6i Link",MB_OK|MB_ICONWARNING);return 1;
 }
 hook_dll=LoadLibraryW(dll);
 if(!hook_dll){MessageBoxW(NULL,L"Could not load the Sa6i Link icon helper.",L"Sa6i Link",MB_OK|MB_ICONERROR);return 1;}
 _snwprintf(command,32767,L"\"%ls\"",exe);command[32767]=0;
 STARTUPINFOW si={0};si.cb=sizeof(si);PROCESS_INFORMATION pi={0};
 if(!CreateProcessW(exe,command,NULL,NULL,FALSE,0,NULL,dir,&si,&pi)){
  MessageBoxW(NULL,L"The test app could not start. Check VxKex is enabled for the UI-v8 EXE.",L"Sa6i Link",MB_OK|MB_ICONERROR);FreeLibrary(hook_dll);return 1;}
 target_pid=pi.dwProcessId;
 while(WaitForSingleObject(pi.hProcess,1000)==WAIT_TIMEOUT) EnumWindows(find_window,0);
 if(hook)UnhookWindowsHookEx(hook);FreeLibrary(hook_dll);CloseHandle(pi.hThread);CloseHandle(pi.hProcess);return 0;
}
