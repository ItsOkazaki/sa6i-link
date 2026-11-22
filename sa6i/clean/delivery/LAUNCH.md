# How Sa6i Link has to be started, and why

Three separate things look like "the app won't start". They are different
problems, and only the first is about the executable.

## 1. The executable needs a launch contract

`Sa6i Link.exe` does nothing when double-clicked. That is not a symptom of the
rebranding: it is how this build is started. `Start Sa6i Link Candidate.cmd`
supplies:

| Item | Value |
| --- | --- |
| `--data-dir` | `%LOCALAPPDATA%\Sa6i-Link-Candidate-46ed96159a09abaa958e0c99` (profile) |
| `--sa6i-clean-header-clearance` | clearance the app needs before it draws its window |
| `--sa6i-clean-test-dir` | the candidate's own `Sa6i Clean` folder |
| `SA6I_CLEAN_WIN7_COMPAT` | `1` |
| `SA6I_CLEAN_WIN7_SOFTWARE`, `QT_QUICK_BACKEND` | empty |

Without `--data-dir` the app has no profile and exits before drawing anything,
which is indistinguishable from a broken executable. Defaulting these inside
the binary would mean rebuilding the application, so the batch file stays as
the single definition of the contract, and `Make Sa6i Link Shortcut.cmd` builds
a shortcut to a generated `.vbs` that runs that batch file with no window.

## 2. The profile is tied to the product name

The app stores a device key in its profile, encrypted by Windows with material
derived from the application's identity. A profile created **before** the
product name was rewritten cannot be unlocked afterwards:

```
storage error: cannot unlock device key: Donnees non valides. (0x8007000B)
```

`0x8007000B` is `ERROR_BAD_FORMAT`, the error a failed integrity check returns.
The fix is a new profile, not a repair: `Reset Sa6i Link Profile.cmd` rewrites
`SA6I_DATA` in the batch file to a fresh path (`…-p2`) and leaves the old folder
alone. The old folder cannot simply be moved while the app is running - it is
held open - which is why the path is changed instead.

Pairing the phone again is part of that, because the pairing lives in the
profile.

## 3. The executable was locked while being rewritten

Writing to a running executable fails outright. The retarget script therefore
tests the file for writing before it starts, and asks the process to close if it
cannot. Sa6i Link lives in the notification area, so "closed" is easy to get
wrong: quitting from the tray icon is what actually releases the file.

## What is still original

The icon inside the executable. `Retarget Sa6i Clean.cmd` replaces it by
walking the resource section and writing into the slots the existing images
occupy; that step has not completed on the user's machine. It is isolated on
purpose: it runs as a child process with a four minute limit, and `-NoIcon`
skips it, so it can never stop the archive from being produced.
