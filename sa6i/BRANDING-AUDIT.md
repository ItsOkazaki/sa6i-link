# Branding audit: portable Windows ZIP and Android APK

This is a static inspection, not a complete visual or runtime test. The user
reported that the Windows package works. Keep that working package unchanged;
the artwork candidate is a separate ZIP.

## Windows

Inspected public release `Sa6i.Link.zip`, SHA-256
`4cfcb2227ba61f6d54282dfb2513ae9c8dda5faceda2ce11979e4a4237f602d9`.
`Assets/Square150x150Logo.png` and `Assets/Square44x44Logo.png` contained the
old NectarLink mark. The artwork candidate replaces only those two PNG entries
with sizes derived from the supplied Sa6i Link ICO. A complete decompressed
entry-by-entry comparison verifies all other ZIP entries have unchanged bytes;
the ZIP passes `testzip()`. The candidate has not been run on Windows. The
executable, launcher, icon hook, settings, and updater are unchanged.

The loose `AppxManifest.xml` still contains upstream display strings, identity,
publisher and executable references. Its role in the portable package has not
been verified. It was intentionally not modified because changing package
identity or executable references may affect Windows integration. Translation
filenames and `nectarlink_vcam.dll` also contain the upstream name and are kept
because they may be referenced by the executable. Licence and copyright notices
are preserved. No claim of a complete trace-free Windows build is made.

Candidate SHA-256:
`623d5f4f71a190e37d5d885addd3665bb3fa9482434af6304d098fcd74566a60`.
Generator: `sa6i/tools/package_windows_assets.py` (checks the full input hash,
assets, ZIP integrity and unchanged entries; refuses overwrite).

## Android

Inspected public release `Sa6i.Link.apk`, SHA-256
`86913c1ab9ac5f1aac060b966708a0fc4442fd56e02df7cbc2dc4a4a1d92b5b1`.
Androguard reports package `app.sa6ilink.test`, label `Sa6i Link`, version
`0.1.5`. Its compiled string resources contain the existing destination
`Download/Nectarlink` in file-transfer guidance for English, Arabic, German,
Turkish and Chinese; those strings match the old storage path. Blindly changing
only the displayed text would be misleading.

DEX strings contain upstream references including `NectarLink PC media`,
`NectarLink Virtual Gamepad`, `NectarLink Virtual Keyboard`,
`Phone speaker (NectarLink)`, an upstream update API/release feed and internal
package/class names. String presence alone does not establish where or when each
one appears. Native library files also retain the name `libnectarlink_ffi.so`.
APK signing and device behavior were not tested. The existing APK has not been
changed, rebuilt, signed, or replaced; Android source-string edits in the
workspace are not present in this APK. The separate source update-string edits
must not be confused with the APK's already compiled values.

A safe future Android candidate needs exact-binary patching or a reproducible
matching source build, careful path migration, updater configuration, proper
signing, and phone testing. Internal identifiers and required attribution
cannot simply be replaced without risking breakage or licence compliance.
Docker is not required for testing on a physical phone.

### Separate Android branding candidate

A separate candidate was produced from the exact APK above with
`sa6i/tools/package_android_branding_candidate.py`. It changes six DEX strings:
PC media, virtual keyboard, virtual gamepad, phone-speaker, shared-file label,
and invalid-pairing-code message. The compiled resources, manifest, native
libraries and all other non-signature ZIP entries match the original bytes;
DEX class names and string differences were checked. Stored ZIP entries are
aligned, and apksigner verified the candidate's v2 and v3 signatures.

Candidate SHA-256:
`64208e3e96a02807cb5e9fda1b3a93abaa579a0fddcd60e558b1443feeff82a4`.
Its test signer certificate SHA-256 is
`3e93339b6791095180c3aa76988bb4e199c3b2253f171b719350bd3df3d05331`,
different from the original
`a42d20a27bf4f16871c0acc170b9e46aaeed312afe80b0e982979387e7653fc1`.
The test key was discarded: it is not a release signing key and cannot be reused
for updates. The user reported that this branding test worked on their phone.

The same package ID and different signer mean Android will not install it over
the original, nor will the original update it. Uninstalling can delete app data,
settings and pairing keys; backing up received files alone is not a complete
backup of app data. Do not uninstall unless this loss is acceptable. Prefer a
spare Android device for testing. The destination `Download/Nectarlink`, old
updater endpoints, native library and internal references remain unchanged.
Do not use the in-app updater, and do not publish this test candidate as a final
release. The original public APK remains untouched.

### Separately signed release candidate (awaiting phone test)

`sa6i/tools/package_android_release_candidate.py` patches the exact original
APK, not the modified source. It applies the six display-name changes above,
changes the two compiled receive-storage paths to `Sa6i Link`, updates the ten
localized guidance strings, and adds a FileProvider entry for the new path while
retaining the legacy path. Existing files are not migrated or deleted by the
patch. On Android 8–9 the app uses its app-specific external Downloads directory;
uninstall can remove that directory, so copy any files out before uninstalling.
On later Android versions the app uses MediaStore. These paths and old-file
access still need device testing.

The upstream updater's check, update, automatic installation and lookup entry
points are disabled in DEX, and its settings UI entry points are hidden. This
is manual Sa6i release updating, not an automatic updater. The upstream endpoints
and internal identifiers still exist in the code; no blanket trace-removal claim
is made. Updates using the same durable signing key should be compatible with
this candidate, subject to versioning and device testing, but not with either
previously signed same-package APK.

SHA-256 `f6ea8e025325b70f49c8bcb773bfe3b808b6e17569f327e20ea920423f4fa504`.
Signer certificate SHA-256
`070f72049765be9cbebdb839279948317c72ad9628727bba06183ff539ac01fa`.
The signing key and password are stored separately in the owner's private Drive;
they must remain private and be backed up securely. Losing the key prevents
future in-place updates. No secrets belong in the repository or release.

Verified: apksigner v2/v3, ZIP integrity and alignment; package, version and SDK
metadata unchanged; all other non-signature ZIP payloads unchanged. Apktool
re-decoding showed only the intended five resource XML files and FileProvider
paths changed; all DEX class names matched and the eight changed smali files
matched the intended instructions. The original resource table string pool is
modified in place structurally, preserving resource indexes and file references;
a wholesale Apktool-rebuilt table would incorrectly reference renamed resource
files. These checks are static. The user reported the signed candidate worked
on their phone and uploaded it to the public release; the published asset's
SHA-256 matches the candidate. Original and branding test APKs remain intact.
