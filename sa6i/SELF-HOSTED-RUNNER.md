# Free alternative: attach the release assets with a self-hosted runner

GitHub-hosted runners are currently blocked by this account's
**Billing & plans** spending-limit / failed-payment state, so every hosted job
(including CI) fails before starting with:

> *The job was not started because recent account payments have failed or your
> spending limit needs to be increased.*

A **self-hosted runner is free**: it does not consume billed Actions minutes,
and it runs on your own network, where `uploads.github.com` is reachable. The
helper workflow `.github/workflows/sa6i-release-assets.yml` now uses
`runs-on: self-hosted` and uploads the two vendored files from
`sa6i/fallback/` to release `447714019` using `curl` + the job's own
`GITHUB_TOKEN`. No `gh` CLI, no `jq`, no payment method needed.

## 1. Register a runner (in your browser)

1. Open <https://github.com/ItsOkazaki/sa6i-link/settings/actions/runners/new>.
2. Pick the OS + architecture of the machine that will host it.
   **Use Windows 10/11, Linux, or macOS — not Windows 7.** The current
   GitHub Actions runner does not support Windows 7. (Your Win7 machine can stay
   the target for testing the app; the runner just needs a different PC.)
3. GitHub shows a **registration token** (valid ~1 hour) and the exact
   download/config commands. Copy them; do not paste the token into chat.
4. On that machine, extract the runner and run the config command, e.g.:
   - Linux/macOS: `./config.sh --url https://github.com/ItsOkazaki/sa6i-link --token <TOKEN>`
   - Windows: `.\config.cmd --url https://github.com/ItsOkazaki/sa6i-link --token <TOKEN>`
   Accept the default labels (`self-hosted` is included) and give it a name
   such as `sa6i-upload`.
5. Start it: `./run.sh` (Linux/macOS) or `.\run.cmd` (Windows). Leave the
   window open.
6. Back on <https://github.com/ItsOkazaki/sa6i-link/settings/actions/runners>,
   the runner should show **Idle**. That is the signal that the upload job can
   run.

Requirements on that machine: `bash` and `curl` (Git for Windows supplies both
on Windows), outbound HTTPS to `github.com`, `api.github.com` and
`uploads.github.com`.

## 2. Let the job run

- If the workflow was already triggered by a push to `main`, the job is
  **queued** waiting for a `self-hosted` runner; it starts as soon as yours is
  Idle.
- Or click **Run workflow** on
  <https://github.com/ItsOkazaki/sa6i-link/actions/workflows/sa6i-release-assets.yml>
  after the runner is online.
- The job checks out the repo, confirms both files exist, and POSTs them to the
  release's asset endpoint. It does not change the release title, notes,
  prerelease flag, or any application code.

## 3. Verify

After it succeeds, the release page
<https://github.com/ItsOkazaki/sa6i-link/releases/tag/sa6i-windows-arabic-v8-test>
must list:

- `Sa6i-Link-Windows-Arabic-v8-Reviewed-TEST.zip` (15,336,199 bytes)
- `SHA256SUMS.txt` (1,900 bytes)

Download both, extract the ZIP beside the checksum file, and run
`sha256sum -c SHA256SUMS.txt` → 14 `OK`. ZIP SHA-256:
`78da55255ee39c31df9064258b550fbb638e47f60b5daff80142a8b29e750cad`.

Tell the agent when the runner is Idle / the job is done and it will confirm the
assets and checksums from GitHub.

## 4. If you'd rather not set up a runner

Nothing here requires money: just drag the same two files onto the release edit
page from your browser, or use the free Google Drive / repo raw links already in
the release notes. The manual route takes about 30 seconds and needs no runner.
