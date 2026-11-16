#define UNICODE
#define _UNICODE
#include <windows.h>
/* Thread-specific Windows hook: loads icon in the target process, avoiding
   cross-process HICON misuse. Only responds to our private WM_NULL marker. */
static HINSTANCE module;
static HICON large_icon,small_icon;
BOOL WINAPI DllMain(HINSTANCE h,DWORD why,LPVOID reserved) { (void)reserved; if(why==DLL_PROCESS_ATTACH){module=h; DisableThreadLibraryCalls(h);} return TRUE; }
__declspec(dllexport) LRESULT CALLBACK sa6i_hook(int code,WPARAM wp,LPARAM lp) {
 if (code>=0 && lp) {
  MSG *m=(MSG*)lp;
  if(m->message==WM_NULL && m->wParam==0x53413649 && m->lParam==0x4c494e4b && IsWindow(m->hwnd)) {
   if(!small_icon) small_icon=(HICON)LoadImageW(module,MAKEINTRESOURCEW(101),IMAGE_ICON,16,16,LR_DEFAULTCOLOR);
   if(!large_icon) large_icon=(HICON)LoadImageW(module,MAKEINTRESOURCEW(101),IMAGE_ICON,32,32,LR_DEFAULTCOLOR);
   if(small_icon) SendMessageW(m->hwnd,WM_SETICON,ICON_SMALL,(LPARAM)small_icon);
   if(large_icon) SendMessageW(m->hwnd,WM_SETICON,ICON_BIG,(LPARAM)large_icon);
  }
 }
 return CallNextHookEx(NULL,code,wp,lp);
}
