# Sa6i Clean: experimental packaged-binary rebrand

> **Current status (2026-11-16):** the packaged cleaner is now traceable to the public Cleanly v0.2.0 source. Rebuilding commit `b62bef4` and applying the documented Sa6i patches reproduces every packaged file byte for byte (`verify_upstream_equivalence.py`). Cleanup safety is still unvalidated: `SAFETY-REVIEW.md` records how deletion works and one containment gap for redirected cache roots, and `RELEASE-READINESS.md` is the go/no-go summary. Run `node sa6i/clean/tests/probe_upstream_cleanup.mjs SOURCE` for the isolated guard check; nothing in it touches real files outside a temporary fixture.


The user confirmed they have permission from the Cleanly rights holder to modify and redistribute the supplied build. This work is separate from Sa6i Link. It patches the supplied **Cleanly 0.2.0 Windows x64 packaged application**, not a full source project. Original input archives are not changed. This is not a production release.

## What is changed

`build_candidate.py` checks SHA-256 hashes for both exact inputs and refuses an existing output path. It copies the runtime, removes the original uninstaller, renames the executable, changes application package name/product name and selected visible titles, repacks `app.asar`, updates the embedded ASAR integrity hash, and replaces the executable icon in its existing PE resource slots. A new UI icon and cleanup warnings are included. It keeps Cleanly attribution, the Electron/Chromium license files, and the upstream tip/feedback services; the Support Cleanly title identifies those as for the original developer. Windows file metadata, some Cleanly messages, network behavior, and the cleaning code remain unchanged. Application data isolation is intended by the renamed Electron package/product name but has not been checked on Windows. See `SAFETY-REVIEW.md` for the limited static cleanup review.

## Safety and limitations

- The user reported that the experimental candidate works on Windows 7 using VxKex. The scope of their test is unknown; data separation, cleanup safety, and individual features remain unverified. No production or public release has been made.
- Some cleanup code uses direct file deletion (`unlink`), not the Recycle Bin. Other operations use the system Trash. This has not been fully audited. Do not run cleanup, uninstallation or startup-management actions on a real system based on this candidate.
- The executable specifies Windows 10.0 as its minimum OS version, and upstream documents Windows 10/11. The user reports the candidate works on their Windows 7 machine with VxKex, but that does not establish native or full Windows 7 compatibility.
- The app is unsigned. The original executable has no Authenticode certificate table, and this patch does not add a signature.
- Tip and feedback features still reach the original developer's endpoints. AI features retain the original third-party provider integrations; avoid entering personal data or API keys during initial inspection.
- A full source project and platform-specific testing are recommended before further modifications, particularly cleanup safety and a complete rebrand. Attribution and applicable third-party licenses must be retained.

## Reproduce

With Python 3, Node.js and npm available, combine the two provided 7-Zip volumes and extract the single `Cleanly.zip` containing `Cleanly.exe`. Supply that ZIP and `clean.zip` (the runtime archive) to:

```sh
python3 sa6i/clean/build_candidate.py /path/to/clean.zip /path/to/Cleanly.zip '/path/to/new/Sa6i Clean'
```

The script obtains `@electron/asar@4.3.2` through npx. The version-locked inputs and exact string replacement counts prevent silently patching a different build. An output folder is created only after successful staging, and an existing output is never replaced.

Static checks performed on the first candidate: packaged JS syntax checks, original-versus-patched ASAR file inventory, verification that the executable differs only by its embedded ASAR header hash, and byte hashes of the other bundled runtime files. The second branding preview additionally changes PE icon resource bytes and size metadata. These checks do not demonstrate launch or safe behavior.
