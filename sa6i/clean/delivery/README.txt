SA6I CLEAN - BRANDING PATCH (EXPERIMENTAL, NOT A RELEASE)

The cleaner shipped inside Sa6i Link was built by someone else and still says
so: its own tabs point at that author's payment page and mailbox, its sidebar
and About panel carry that author's name, and Windows shows that author's
product name in the file's details. This patch removes those tabs, replaces
the name and logo with Sa6i Clean, and makes Sa6i Link accept the result.

WHAT TO DO

Everything happens in your "Sa6i Link Hardened Candidate" folder, which
contains sa6i-link.exe and a "Sa6i Clean" subfolder.

1. Close Sa6i Link (tray menu: Quit) and close any open Sa6i Clean window.

2. THE CLEANER. Copy the three files inside
   "1 - into the Sa6i Clean folder" into the "Sa6i Clean" folder, beside
   "Sa6i Clean Integration.exe" and its "resources" folder:

     Install-Sa6i-Clean-Patch.ps1
     Apply Sa6i Clean Patch.cmd
     app.asar                      <- beside the exe, NOT inside resources

   Then, in that folder, double-click "Apply Sa6i Clean Patch.cmd" and wait
   for "Done.". The window stays open and writes patch-log.txt.

   It copies app.asar into resources itself; dropping it there by hand would
   leave the executable pointing at a bundle it cannot verify.

3. SA6I LINK. Copy the two files inside "2 - into the candidate folder" into
   the candidate folder itself, beside sa6i-link.exe:

     Retarget-Sa6i-Clean-Digests.ps1
     Retarget Sa6i Clean.cmd

   Then double-click "Retarget Sa6i Clean.cmd" and wait for "Done.".

   Sa6i Link never starts a cleaner it has not identified: it hashes the
   cleaner's exe and bundle and compares them with two digests compiled into
   sa6i-link.exe. Step 2 changed both files, so without this step the
   Sa6i Clean tab refuses to start it. This step is also the one that packs
   the whole candidate folder into

     Sa6i-Link-Integrated-Candidate.zip

   beside the candidate folder, and prints that ZIP's SHA-256. Backups are
   left as .bak files, and .bak files and logs are kept out of the archive.

If either step stops with an ERROR line, send me its log (patch-log.txt or
retarget-log.txt): the line names the exact check that failed, and nothing is
changed when it stops.

Windows may warn that the scripts are unsigned; allow them, or right-click and
choose Run with PowerShell. They need nothing installed: they run on the
PowerShell Windows 7 already has (2.0) and pack with the ZIP support built
into Windows.

WHAT THE BUNDLE CHANGES

* The Support/Tip and Feedback navigation entries are removed.
* The name is Sa6i Clean in the sidebar, the About panel, the window title and
  the application name, including the lowercase spelling the app used.
* The inline sparkle logo is replaced with the Sa6i Clean emblem.
* The tip checkout address and the author's contact address are replaced with
  an unresolvable placeholder, so nothing can open their pages or mail them.
* The junction/symlink cache-root guard is applied, so cleaning refuses a
  cache root reached through a redirect.

WHAT DID NOT CHANGE

Cleanup behaviour: the categories, the selections and the confirmation step
are untouched. That also means cleanup can still permanently delete files and
empty the Recycle Bin; it has not been safety-validated. Use it on a
disposable machine only.

The file icon shown by Explorer and the taskbar still comes from the original
executable's icon resource; replacing that means rebuilding the executable,
which this patch deliberately does not attempt.

HASHES

app.asar (1,420,960 bytes), SHA-256:
  2d163de5f5f862da2087579d8920796c970528a08d8bad9b682697f79050d2e9
debranded bundle header hash (written into the exe by step 2):
  653f05e211811d173cd943c6fc44aecb6c9318a3091010abafcb4abca87e5a0a

Step 2 reads the installer's own bundle hash rather than trusting a fixed
value, so it works with any cleaner build; it stops only if the executable
does not store that hash, which means that build verifies its bundle some
other way.
