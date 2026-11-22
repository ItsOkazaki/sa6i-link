SA6I CLEAN - DEBRANDED BUNDLE (EXPERIMENTAL, NOT A RELEASE)

This removes the original developer's Tip and Feedback tabs from the cleaner
that ships inside Sa6i Link, so no part of the window points at or pays the
author of the cleaner it was built from.

WHAT TO DO

1. Close Sa6i Link (tray menu: Quit).
2. Copy all four files of this package into your existing
   "Sa6i Link Integrated Candidate\Sa6i Clean" folder, next to
   "Sa6i Clean Integration.exe" and its "resources" folder:
     Install-Sa6i-Clean-Patch.ps1
     Apply Sa6i Clean Patch.cmd
     README.txt
     app.asar        <- beside the exe, NOT inside resources
   The script copies app.asar into resources itself; dropping it there by
   hand would leave the executable pointing at a bundle it cannot verify.
3. There, double-click "Apply Sa6i Clean Patch.cmd". It keeps the window
   open and writes everything it prints to patch-log.txt, so nothing flashes
   past. If Windows asks about running a script, allow it.
4. Start Sa6i Link as usual.

The script does two things and reports each one:

  Step 1  patches the cleaner, so the Tip and Feedback tabs are gone.
  Step 2  packs the whole "Sa6i Link Integrated Candidate" folder into
          "Sa6i-Link-Integrated-Candidate.zip", written next to that folder.
          That ZIP is the assembled candidate, ready to keep or move to
          another machine.

So the same double-click both applies the patch and produces the packaged
candidate. Step 2 takes a couple of minutes and prints the ZIP's SHA-256 when
it finishes. If it fails, the patch is still applied; the log then suggests
packing the folder by hand with right-click, Send to, Compressed (zipped)
folder.

If the patch stops with an ERROR line, send me patch-log.txt: it names the
exact check that failed, and nothing is changed when it stops.

The script backs up "Sa6i Clean Integration.exe" and "resources\app.asar"
as .bak before changing anything. Windows may warn that the script is
unsigned; it only edits those two files and then packs the folder. Re-running
it is safe: it notices the bundle is already installed and goes straight to
packing.

WHAT CHANGED IN THE BUNDLE

* The Support/Tip and Feedback navigation entries are removed.
* "Cleanly" is now "Sa6i Clean" throughout the interface and the prompts.
* The tip checkout address and the author's contact address are replaced with
  an unresolvable placeholder, so nothing can open their pages or mail them.
* The junction/symlink cache-root guard is applied, so cleaning refuses a
  cache root reached through a redirect.

WHAT DID NOT CHANGE

Cleanup behaviour: the categories, the selections and the confirmation step
are untouched. That also means cleanup can still permanently delete files and
empty the Recycle Bin; it has not been safety-validated. Use it on a
disposable machine only.

HASHES

app.asar SHA-256:
  ea12336539260cfda7c409882bda14bbe9704f55c66c916db34fbe7b0d7f0fac
debranded bundle header hash (written into the exe by the script):
  8e6ee85e794723de784eb1adc1baedf28a612f968e7b88970297f91053e37fb9

The script no longer needs to be told which build you have: it reads the hash
of the bundle that is installed and finds that same text inside the exe. It
stops only if the exe does not contain it, which means that build checks its
bundle differently.
