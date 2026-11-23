# Android signing key: custody and rotation

The Android signing key is the permanent identity of the app. A device accepts an
update only if it is signed by the same key, so losing the key means every user
has to uninstall before they can install again, and leaking it means someone else
can ship an update your users' phones will trust.

This page is the procedure. It contains no secrets.

## What is true today (verified 2026-11-16)

| Item | Value |
| --- | --- |
| Keystore | `PRIVATE - Sa6i Link Android release keystore.p12`, 3,470 bytes, in Google Drive |
| Password | `PRIVATE - Sa6i Link Android signing password.txt`, 253 bytes, plaintext, beside the keystore |
| Sharing on either file | owner only — **no `anyoneWithLink` grant, no shared parent folder** |
| Build distribution | the candidate and release ZIPs *are* shared by link, so they are downloadable by anyone who has the URL |
| Consequence | the key is not exposed today; it is protected by exactly one Google account |

So this is a **custody** problem, not an incident. It becomes an incident the day
that account is phished, or an OAuth client with Drive scope is granted and later
misused.

## Do now (≈15 minutes)

1. **Confirm 2FA** on the Google account, and review *Security → Third-party
   access*: remove any app with Drive scope that is not actively used.
2. **Download both files locally**, into a folder outside any synced drive.
3. **Package them encrypted**, password manager entry or an encrypted archive:
   `7z a -p -mhe=on sa6i-signing.7z keystore.p12 password.txt` (7-Zip with
   header encryption; the archive password goes in the password manager, not in
   the same archive).
4. **Record the fingerprints** (public values, safe to keep in the repository):

   ```powershell
   keytool -list -v -storetype PKCS12 -keystore keystore.p12 |
     Select-String "SHA256|Alias|Valid"
   apksigner verify --print-certs app-release.apk
   ```

   Put the SHA-256 fingerprint and the alias in the table below, then delete the
   downloaded plaintext copy from the Downloads folder.
5. **Store two copies**: a password manager entry (keystore + password) and one
   offline medium (USB stick in a drawer, encrypted archive). Two copies, two
   places, both encrypted.
6. **Remove the plaintext password file from Drive** once the password is in the
   password manager. Keep the keystore in Drive only if it is inside an encrypted
   archive — otherwise keep it off Drive entirely.
7. **Wire CI to the secret store**, never to the repository: the build reads
   `SA6I_KEYSTORE_BASE64`, `SA6I_KEYSTORE_PASSWORD`, `SA6I_KEY_ALIAS` from the CI
   secret store.

## Record

| Field | Value |
| --- | --- |
| Alias | *fill in from step 4* |
| Key algorithm / size | *e.g. RSA 4096, validity to 2050* |
| SHA-256 fingerprint | *fill in from step 4* |
| Created | 2025-11-18 (file date) |
| Custody | password manager + offline copy, since 2026-11-16 |

Once filled in, this table is what proves a release was signed by us — anyone can
compare it with `apksigner verify --print-certs`.

## Rotation: when, and what it costs

| Situation | Action |
| --- | --- |
| Key is safe, password is in a manager, 2FA on | **Do not rotate.** Rotation costs every sideloaded user an uninstall |
| Password was shared in chat/email, or a plaintext copy was on a shared drive | **Rotate.** Assume compromise |
| Account shows unfamiliar activity or OAuth grants | **Rotate**, then review all shares |
| Key lost with no backup | Nothing to rotate — new identity; ship as a fresh install with a migration note |
| Publishing through Play later | Play App Signing can rotate the *upload* key without breaking updates; the app signing key stays ours |

Rotation procedure when it is genuinely needed:

1. Generate the new key (`keytool -genkeypair -storetype PKCS12`, RSA 4096,
   validity 25 years, distinct alias).
2. Update CI secrets; keep the old key in the archive (users on old builds still
   exist).
3. Build and publish a transitional release signed with the **old** key whose only
   job is to tell users to reinstall, then ship the new key.
4. Bump the version name so the two lineages are distinguishable in the field.
5. Note the new fingerprint in the table above.

## Never

Never commit the keystore or the password. Never put the password in the same
archive as the keystore. Never reuse the Google account password as the keystore
password. Never let an agent or a script print the password into a log.
