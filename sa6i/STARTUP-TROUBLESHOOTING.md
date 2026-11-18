# Startup troubleshooting

## `CoIncrementMTAUsage` / `ole32.dll`

A startup error was reported on Windows 7. The v8 app executable imports `CoIncrementMTAUsage` from `ole32.dll`; this function is not provided by the original Windows 7 `ole32.dll`. VxKex provides compatibility for this API in some versions, but whether it is active and working on the affected PC has not yet been verified. Other compatibility issues may also remain.

**Do not download or replace `ole32.dll`, or copy DLLs into Windows system folders.** Keep the previous working version and back up shared preferences and pairings.

## Patcher and original folder

The original folder included v1–v3 patchers. Their source shows that they create separate patched executables from one exact original binary; they do not enable VxKex. The v8 executable already contains the v3 patch's relevant byte changes. Both the original v5 and v8 executables still import `CoIncrementMTAUsage`, so running the old patcher again is not a demonstrated fix for this error and could create a different executable without the v8 changes.

The released v8 executable, launcher, `cldapi.dll` and v4 icon helper match the supplied archive byte-for-byte. An archive comparison also found that the shared DLL, QML and translation files match; the older `sa6i-icon-hook.dll` was omitted, while v8's launcher uses the included `sa6i-icon-hook-v4.dll`. The user reports that the original folder's `Start Sa6i Link v8.exe` opens the app on the same PC, but the assembled release does not. The files on that PC have not been independently compared, and these static checks do not identify the cause.

The user confirmed that VxKex 1.2.1.2229 is enabled for `Sa6i-Link-Win7-UI-v8.exe` in the working original folder, while the checkbox for the extracted release executable does not stay enabled. The source for that VxKex version supports path-specific configuration and provides `CoIncrementMTAUsage`. It can use an on-demand scheduled task to apply settings without a prompt; the lack of a prompt alone is not proof of failure. Whether that task failed or the path configuration caused the issue is unknown. Do not change or delete the working installation while investigating.

For a read-only check, open **Task Scheduler → Task Scheduler Library** and look for **VxKex Configuration Elevation Task**. Note its **Last Run Time** and **Last Run Result**, if present. Do not run, disable or delete it. A missing or older task result is not proof of a cause.

## VxKex transaction error and the renamed package

A screenshot of VxKex 1.2.1.2229 showed a failure to apply settings to
`Sa6i Link.exe`, with a French message saying the name is reserved by another
transaction. The VxKex configuration tool uses a Windows registry transaction;
the error suggests a transaction conflict, but the screenshot does not identify
its cause. A restart may clear a transient conflict; this has not been verified.
Do not delete registry keys, reset transactional logs, reinstall VxKex, or change
the working installation to troubleshoot this without further evidence.

In the separately packaged candidate, `Sa6i Link.exe` is the small launcher,
not the actual app: the launcher starts `Sa6i Link App.exe`. On Windows 7, apply
VxKex to **`Sa6i Link App.exe`**, in the extracted folder, then launch
`Sa6i Link.exe`. Do not rename either file: the launcher uses that exact app
filename. Close all VxKex property dialogs and Sa6i Link windows before trying;
if the conflict persists, restart Windows once and retry. Reopen the target's
properties to check whether the setting stayed enabled. If it fails again,
record the exact error and whether the target or launcher was selected. Keep
using the original working folder until the candidate is confirmed working.
VxKex in this setup targets Windows 7; the candidate's separate Windows 11
window change still needs testing and does not establish compatibility for all
versions of Windows.

## Check the VxKex setting for the original v8 filenames

1. Extract the whole app ZIP to a normal folder first; don't run it inside the ZIP. Keep it separate from the previous installation.
2. In the extracted folder, right-click **`Sa6i-Link-Win7-UI-v8.exe`** (the application, not `Start Sa6i Link v8.exe` or a shortcut) and open **Properties → VxKex**.
3. Enable VxKex, click **Apply**, approve any administrator permission prompt, then click **OK**. Reopen the properties of that same file and check whether the setting stayed enabled. VxKex settings can depend on the executable's full path, so repeat this if the folder is moved or the app is extracted again.
4. If the setting remains enabled, launch `Start Sa6i Link v8.exe`. If it does not, note any error or administrator prompt; do not edit registry settings by hand.
5. Some VxKex versions provide **Run with VxKex enabled** on the executable's Shift + right-click menu. If this option is available, try it once on `Sa6i-Link-Win7-UI-v8.exe`. This starts the app directly and may bypass the icon helper; it is a diagnostic test, not a confirmed fix. The menu and behaviour vary between versions.

If it still fails, record the exact error text, the executable used, the VxKex version, and whether the setting stayed enabled or the one-time menu worked. Do not share pairing data or personal settings. The assembled v8 folder has not been verified on the affected machine.
