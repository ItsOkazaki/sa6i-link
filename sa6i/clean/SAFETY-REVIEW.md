# Cleanly 0.2.0 cleanup review (static, incomplete)

This review concerns the exact packaged app identified by `build_candidate.py`, not an arbitrary Cleanly version. It is based on reading bundled/minified JavaScript, not a source audit or execution on Windows. It is not a safety certification.

## Findings

- The cleanup implementation has separate paths. For ordinary cleanup categories, `SS` calls `S1`, which calls `dS` and ultimately `lS`, which uses `fs.unlink` for files and `fs.rmdir` for directories. This is **permanent deletion**, not a Recycle Bin operation. The code attempts root containment and rejects symlinks, and some categories have age/exclusion rules; this is not proof that every selection or race condition is safe.
- Selecting the Recycle Bin invokes PowerShell `Clear-RecycleBin -Force`, which permanently empties the bin. Its availability and behavior on Windows 7 with VxKex have not been tested. Because errors may be suppressed, the result should not be considered reliable without testing.
- Old Downloads and the separate file/duplicate removal flow call Electron `shell.trashItem`. The success, restore behavior and capacity limits have not been tested on Windows 7. Moving something to the bin is not a backup.
- The Smart Scan selects categories marked `safe` and can clean from its dashboard. The UI has a confirmation option which users can disable; the keyboard Enter shortcut can also trigger its action. Do not interpret the label `safe` as a guarantee.
- Startup management can change startup entries; the applications section can run uninstallers. Those actions are outside the cleanup review and have not been validated.
- The tip and feedback features retain external Cleanly developer destinations; AI features retain Anthropic/OpenAI integration. The exact data sent and configurations need further privacy and security review.

## This candidate's changes

The second branding preview adds a visible warning on the Cleanup screen and replaces an overconfident dashboard sentence. It **does not change the deletion implementation, categories, selections, or confirmation behavior**, and it must not be used as evidence of safety. It remains an experimental, unsigned binary patch.

## Before any production release

Obtain the matching source project where possible; review cleanup roots, exclusions, junction/symlink and race-condition handling, privileged actions, default selections, confirmation bypass, rollback, network traffic and third-party licenses. Test in disposable Windows 7 + VxKex and Windows 10/11 environments using synthetic files and verified backups, including locked files, junctions and edge paths. Verify that application data, shell integration and the original Cleanly installation are isolated. A qualified reviewer should evaluate the results; never perform these experiments on a production machine.
