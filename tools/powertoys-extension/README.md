# Sa6i Link PowerToys Command Palette / PowerToys Run Extension (`sa6i-link-ptrun`)

`sa6i-link-ptrun` is a standalone, zero-dependency Rust helper that connects Windows launcher tools (PowerToys Command Palette, PowerToys Run, Flow Launcher, Raycast for Windows) to Sa6i Link's [Local Authenticated API](../../docs/api.md).

## Building

```powershell
cargo build --release --manifest-path tools/powertoys-extension/Cargo.toml
```

## Prerequisites

1. Open **Sa6i Link → Settings → Local automation API** and turn on **Enable local automation API**.
2. Sa6i Link writes `%LOCALAPPDATA%\Sa6iLink\api-token.json` containing the loopback port (`53320`) and a 256-bit Bearer token.

## Usage

### Querying Palette Items

```powershell
sa6i-link-ptrun query ""
sa6i-link-ptrun query "ring"
sa6i-link-ptrun query "https://example.com"
```

Outputs a JSON array of palette commands (`send-clipboard`, `ring`, `camera` `photo`/`scan`, `send-url`, `send-text`, plus recent timeline items).

### Invoking an Action

```powershell
sa6i-link-ptrun invoke ring
sa6i-link-ptrun invoke send-clipboard
sa6i-link-ptrun invoke camera photo
sa6i-link-ptrun invoke camera scan
sa6i-link-ptrun invoke send-url "https://example.com"
sa6i-link-ptrun invoke send-text "Copied from PowerToys"
sa6i-link-ptrun invoke send-file "C:\Users\Alice\Desktop\notes.pdf"
```
