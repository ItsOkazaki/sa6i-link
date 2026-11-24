# SPDX-License-Identifier: GPL-3.0-or-later
# ASCII only, on purpose: Windows PowerShell 5.1 reads a script with no BOM in
# the local ANSI code page, so a single em dash breaks the parser - its UTF-8
# bytes land on cp1252 characters, one of which is a double quote that ends
# the string early.
<#
.SYNOPSIS
    Runs M1's six exit criteria on this machine and writes down what happened.

.DESCRIPTION
    M1 has never been compiled, let alone run: no Rust toolchain, no Qt, and no
    Windows were available where it was written. This script is the other half of
    that sentence. It builds the CLI, takes the two readings the plan asks for,
    checks the JSON contract, runs the privacy test, and writes a markdown record
    to target/m1-verification.md that can be pasted back.

    It does not replace scripts/check.ps1, which owns formatting, clippy, the
    whole test suite and the dependency policy. Run that one first if you want an
    unfiltered list of everything that is broken; run this one to answer M1's own
    question: do the numbers match Task Manager, and does the sampler hold 1 Hz?

    Criteria 3 and 5 cannot be automated and are recorded as such: Windows 7
    needs a second machine, and "no admin prompt" needs a human to watch for a
    UAC shield.

.PARAMETER Samples
    How many one-second samples the accuracy run takes. 60 is the plan's minute.

.PARAMETER IntervalMs
    The sampling interval. 1000 is the plan's 1 Hz.

.PARAMETER BudgetSamples
    Samples for the budget run. 1800 at 1 Hz is the half hour.

.PARAMETER Budget
    Also run the half-hour budget check. It takes half an hour.

.PARAMETER Yes
    Do not ask before starting the half-hour run.

.PARAMETER OutFile
    Where to write the record. Defaults to target/m1-verification.md.

.EXAMPLE
    ./scripts/verify-m1.ps1
    ./scripts/verify-m1.ps1 -Budget
    ./scripts/verify-m1.ps1 -Budget -Yes -Samples 60 -BudgetSamples 1800
#>
param(
    [int]$Samples = 60,
    [int]$IntervalMs = 1000,
    [int]$BudgetSamples = 1800,
    [switch]$Budget,
    [switch]$Yes,
    [string]$OutFile = ""
)
$ErrorActionPreference = "Stop"

# Where am I? $PSScriptRoot is the usual answer and was empty on the machine that
# first ran this, so ask it four ways and then look for the repository instead of
# assuming a layout: whichever candidate sits above a Cargo.toml wins.
function Find-RepositoryRoot {
    param([string[]]$Starts)
    foreach ($start in $Starts) {
        if (-not $start) { continue }
        $dir = $start
        while ($dir) {
            if (Test-Path -LiteralPath (Join-Path $dir "Cargo.toml")) { return $dir }
            $parent = Split-Path -Parent $dir
            if (-not $parent -or $parent -eq $dir) { break }
            $dir = $parent
        }
    }
    return $null
}

$candidates = @()
if ($PSScriptRoot) { $candidates += $PSScriptRoot }
if ($PSCommandPath) { $candidates += (Split-Path -Parent $PSCommandPath) }
if ($MyInvocation.MyCommand.Path) { $candidates += (Split-Path -Parent $MyInvocation.MyCommand.Path) }
$candidates += (Get-Location).Path

$root = Find-RepositoryRoot -Starts $candidates
if (-not $root) {
    Write-Host ""
    Write-Host "  could not find the repository from here:" -ForegroundColor Red
    foreach ($c in $candidates) { Write-Host "    $c" -ForegroundColor DarkGray }
    Write-Host "  run it from the checkout, or pass the path to the checkout." -ForegroundColor Red
    $Host.SetShouldExit(1)
    return
}
Push-Location $root

if (-not $OutFile) { $OutFile = Join-Path $root "target\m1-verification.md" }

$results = New-Object System.Collections.Generic.List[object]
$facts = New-Object System.Collections.Generic.List[string]

function Add-Result {
    param([string]$Criterion, [string]$State, [string]$Detail)
    $results.Add([pscustomobject]@{ Criterion = $Criterion; State = $State; Detail = $Detail })
    $colour = switch ($State) {
        "pass" { "Green" }
        "fail" { "Red" }
        default { "Yellow" }
    }
    Write-Host ("  [{0}] {1} - {2}" -f $State.ToUpperInvariant(), $Criterion, $Detail) -ForegroundColor $colour
}

function Invoke-Sa6i {
    param([string[]]$Arguments)
    # A budget miss is exit code 3 on purpose, so the exit code is data here, not
    # an error: the caller reads $script:LastExit.
    $ErrorActionPreference = "Continue"
    $output = & $script:Exe @Arguments 2>&1
    $script:LastExit = $LASTEXITCODE
    return ($output | Out-String)
}

function Read-Percent {
    param([string]$Prompt)
    $answer = Read-Host $Prompt
    if ([string]::IsNullOrWhiteSpace($answer)) { return $null }
    $answer = $answer.Replace(',', '.').Trim().TrimEnd('%')
    $number = 0.0
    $styles = [System.Globalization.NumberStyles]::Float
    $invariant = [System.Globalization.CultureInfo]::InvariantCulture
    if ([double]::TryParse($answer, $styles, $invariant, [ref]$number)) {
        return $number
    }
    Write-Host "    (that is not a number; treated as skipped)" -ForegroundColor Yellow
    return $null
}

function Add-Fact {
    param([string]$Name, [scriptblock]$Body)
    try {
        $value = & $Body
        $facts.Add(("*{0}:* {1}" -f $Name, $value))
        return $value
    } catch {
        $facts.Add(("*{0}:* could not be read ({1})" -f $Name, $_.Exception.Message))
        return $null
    }
}

function Describe-ExitCode {
    param([int]$Code)
    if ($Code -eq 0) { return "0" }
    $hex = "0x{0:X8}" -f $Code
    switch ($hex) {
        "0xC0000135" { return "$hex STATUS_DLL_NOT_FOUND - a DLL the program needs is missing" }
        "0xC0000139" { return "$hex STATUS_ENTRYPOINT_NOT_FOUND - the program never started: a DLL it needs is missing or too old" }
        "0xC000007B" { return "$hex STATUS_INVALID_IMAGE_FORMAT - 32-bit and 64-bit were mixed" }
        "0xC0000142" { return "$hex STATUS_DLL_INIT_FAILED - the program could not initialise" }
        default { return $hex }
    }
}

function Get-MachineValue {
    # Get-CimInstance needs PowerShell 3. The first machine to run this did not have
    # it, and could read the same facts through Get-WmiObject (PowerShell 2) or .NET.
    param([scriptblock]$Cim, [scriptblock]$Wmi, [scriptblock]$DotNet)
    foreach ($attempt in @($Cim, $Wmi, $DotNet)) {
        if (-not $attempt) { continue }
        try {
            $value = & $attempt
            if ($null -ne $value -and "$value" -ne "") { return $value }
        } catch { }
    }
    return $null
}

function Describe-Toolchain {
    $lines = @()
    foreach ($tool in @("cargo", "rustc")) {
        $found = Get-Command $tool -ErrorAction SilentlyContinue
        if (-not $found) { $lines += "$tool is not on PATH"; continue }
        $ErrorActionPreference = "Continue"
        $text = (& $tool --version 2>&1 | Out-String).Trim()
        $code = $LASTEXITCODE
        $ErrorActionPreference = "Stop"
        if ($text) {
            $lines += $text
        } elseif ($found -and $code -ne 0) {
            # A toolchain that prints nothing and exits with a STATUS_* code never
            # ran: that is a dependency problem, not a version to report.
            $lines += "$tool at $($found.Source) printed nothing ($(Describe-ExitCode $code))"
        } else {
            $lines += "$tool at $($found.Source) printed nothing"
        }
    }
    return ($lines -join "; ")
}

try {
    Write-Host ""
    Write-Host "Sa6i - M1 verification" -ForegroundColor Cyan
    Write-Host "  Six exit criteria, one command, and a record at $OutFile"
    Write-Host ""

    # ---- what this machine is, so the numbers have a context ----
    Write-Host "==> This machine" -ForegroundColor Cyan
    Add-Fact "OS" {
        $caption = Get-MachineValue `
            { (Get-CimInstance Win32_OperatingSystem).Caption } `
            { (Get-WmiObject Win32_OperatingSystem).Caption } `
            { [System.Environment]::OSVersion.VersionString }
        $build = Get-MachineValue `
            { (Get-CimInstance Win32_OperatingSystem).BuildNumber } `
            { (Get-WmiObject Win32_OperatingSystem).BuildNumber } `
            { [System.Environment]::OSVersion.Version.Build }
        "$caption (build $build)"
    }
    Add-Fact "CPU" {
        Get-MachineValue `
            { (Get-CimInstance Win32_Processor | Select-Object -First 1).Name } `
            { (Get-WmiObject Win32_Processor | Select-Object -First 1).Name } `
            { $env:PROCESSOR_IDENTIFIER }
    }
    Add-Fact "Logical processors" {
        Get-MachineValue `
            { (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors } `
            { (Get-WmiObject Win32_ComputerSystem).NumberOfLogicalProcessors } `
            { [System.Environment]::ProcessorCount }
    }
    Add-Fact "Physical memory" {
        $bytes = Get-MachineValue `
            { (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory } `
            { (Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory } `
            { $null }
        if ($null -eq $bytes) { "not readable without WMI" } else { "{0:N1} GB" -f ($bytes / 1GB) }
    }
    Add-Fact "PowerShell" { $PSVersionTable.PSVersion.ToString() }
    Add-Fact "Rust" { Describe-Toolchain }
    foreach ($fact in $facts) { Write-Host "  $fact" }

    # rustc 1.78 and later need Windows 10; an older build number cannot compile
    # this at all, and the error it gives is a STATUS_* code, not a compiler error.
    $osVersion = [System.Environment]::OSVersion.Version
    if ($osVersion.Major -lt 10) {
        Write-Host ""
        Write-Host ("  This is Windows {0}.{1} (build {2}). rustc 1.78 and later require" -f $osVersion.Major, $osVersion.Minor, $osVersion.Build) -ForegroundColor Yellow
        Write-Host "  Windows 10: the toolchain cannot start here, only a built binary can run." -ForegroundColor Yellow
    }

    # ---- build ----
    Write-Host ""
    Write-Host "==> Build" -ForegroundColor Cyan
    $ErrorActionPreference = "Continue"
    cargo build --locked -p sa6i-link-cli
    $buildExit = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    $script:Exe = Join-Path $root "target\debug\sa6i-link.exe"
    if ($buildExit -ne 0) {
        $why = Describe-ExitCode $buildExit
        Write-Host "  the CLI did not build; nothing below can run" -ForegroundColor Red
        if ($buildExit -lt 0) {
            # Negative means the process never ran to completion: a STATUS_* code is
            # the loader's verdict, not the compiler's, and nothing above is wrong.
            Write-Host "  $why" -ForegroundColor Red
            Write-Host "  that is the toolchain failing to start, not a compile error." -ForegroundColor Yellow
        }
        Add-Result "Build" "fail" "cargo build --locked -p sa6i-link-cli exited $why"
        throw "build failed"
    }
    if (-not (Test-Path $script:Exe)) {
        # A non-Windows path would be the same name without .exe, but this script
        # is for the machine that has Task Manager on it.
        Add-Result "Build" "fail" "built, but $script:Exe is not there"
        throw "binary missing"
    }
    Add-Result "Build" "pass" "cargo build --locked -p sa6i-link-cli"

    # ---- 1. within three percent of Task Manager ----
    Write-Host ""
    Write-Host "==> 1. Within 3 % of Task Manager" -ForegroundColor Cyan
    Write-Host "  Taking $Samples samples at $IntervalMs ms. Watch Task Manager's Performance"
    Write-Host "  tab while this runs - at the end, its Utilisation and Memory figures are"
    Write-Host "  what the next two questions want."
    $report = Invoke-Sa6i @(
        "intel", "snapshot", "--samples", "$Samples", "--interval-ms", "$IntervalMs",
        "--average", "--json"
    )
    $exit = $script:LastExit
    $payload = $null
    try { $payload = $report | ConvertFrom-Json } catch { }
    $oursCpu = $null
    $oursMemory = $null
    if ($payload -and $payload.summary) {
        if ($payload.summary.cpu) { $oursCpu = $payload.summary.cpu.mean }
        if ($payload.summary.memory) { $oursMemory = $payload.summary.memory.mean }
    }
    if ($null -eq $oursCpu) {
        Add-Result "Within 3 % of Task Manager" "fail" "the run produced no summary to compare (exit $exit)"
    } else {
        $oursCpuText = if ($null -ne $oursCpu) { "{0:N1} %" -f $oursCpu } else { "no reading" }
        $oursMemoryText = if ($null -ne $oursMemory) { "{0:N1} %" -f $oursMemory } else { "no reading" }
        Write-Host ("  ours: cpu {0}  memory {1}  ({2} of {3} samples measured)" -f `
            $oursCpuText, $oursMemoryText, $payload.summary.cpu.measured, $payload.summary.cpu.of)
        $tmCpu = Read-Percent "  Task Manager CPU % (blank to skip)"
        $tmMemory = Read-Percent "  Task Manager Memory % (blank to skip)"
        if ($null -eq $tmCpu -and $null -eq $tmMemory) {
            Add-Result "Within 3 % of Task Manager" "eyes" ("ours cpu $oursCpuText, memory $oursMemoryText - Task Manager not entered")
        } else {
            $cpuOff = if ($null -ne $tmCpu) { [math]::Abs($oursCpu - $tmCpu) } else { $null }
            $memoryOff = if ($null -ne $tmMemory) { [math]::Abs($oursMemory - $tmMemory) } else { $null }
            $state = "pass"
            $parts = New-Object System.Collections.Generic.List[string]
            if ($null -ne $cpuOff) {
                $parts.Add(("cpu {0:N1} vs {1:N1} = {2:N1} off" -f $oursCpu, $tmCpu, $cpuOff))
                if ($cpuOff -gt 3.0) { $state = "fail" }
            }
            if ($null -ne $memoryOff) {
                $parts.Add(("memory {0:N1} vs {1:N1} = {2:N1} off" -f $oursMemory, $tmMemory, $memoryOff))
                if ($memoryOff -gt 3.0) { $state = "fail" }
            }
            Add-Result "Within 3 % of Task Manager" $state ($parts -join "; ")
        }
    }

    # ---- 3. the JSON contract, and the process rate ----
    Write-Host ""
    Write-Host "==> 3. The JSON contract" -ForegroundColor Cyan
    # Two samples, because a rate needs two: the second snapshot must carry a
    # CPU figure for processes that were in the first, and not 0 for the ones it
    # could not measure.
    $twoReport = Invoke-Sa6i @("intel", "snapshot", "--samples", "2", "--interval-ms", "$IntervalMs", "--json")
    $twoExit = $script:LastExit
    $two = $null
    try { $two = $twoReport | ConvertFrom-Json } catch { }
    if ($null -eq $two) {
        Add-Result "JSON contract" "fail" "the two-sample run did not print JSON (exit $twoExit)"
    } else {
        $required = @(
            "seq", "taken_at", "monotonic_ms", "cpu", "memory",
            "volumes", "disk_io", "gpu", "processes", "uptime"
        )
        $missing = @()
        foreach ($key in $required) {
            if ($null -eq $two.snapshot.PSObject.Properties[$key]) { $missing += $key }
        }
        if ($missing.Count -gt 0) {
            Add-Result "JSON contract" "fail" ("missing keys: " + ($missing -join ", "))
        } elseif ($null -eq $two.findings) {
            Add-Result "JSON contract" "fail" "no findings array"
        } else {
            $processes = @($two.snapshot.processes)
            $rated = @($processes | Where-Object { $_.cpu_percent.state -eq "value" })
            $unknown = @($processes | Where-Object { $_.cpu_percent.state -ne "value" })
            $detail = "{0} processes, {1} with a rate, {2} without" -f $processes.Count, $rated.Count, $unknown.Count
            if ($processes.Count -gt 0 -and $rated.Count -eq 0) {
                Add-Result "JSON contract" "fail" ($detail + " - the second sample should know the first one's processes")
            } elseif ($unknown.Count -gt 0 -and @($unknown | Where-Object { $null -ne $_.cpu_percent.value }).Count -gt 0) {
                Add-Result "JSON contract" "fail" ($detail + " - an unmeasured rate carried a value")
            } else {
                Add-Result "JSON contract" "pass" ($detail + "; keys and states as documented")
                if ($rated.Count -gt 0) {
                    $busiest = $rated | Sort-Object { $_.cpu_percent.value } -Descending | Select-Object -First 1
                    Write-Host ("  busiest: {0} (pid {1}) {2:N1} %" -f $busiest.name, $busiest.pid, $busiest.cpu_percent.value)
                }
            }
        }
    }

    # ---- 6. nothing leaves the machine ----
    Write-Host ""
    Write-Host "==> 6. Nothing leaves the machine" -ForegroundColor Cyan
    $ErrorActionPreference = "Continue"
    cargo test --locked -p sa6i-link-intel --test privacy
    $privacyExit = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($privacyExit -eq 0) {
        Add-Result "Nothing leaves the machine" "pass" "tests/privacy.rs: neither intel crate reaches a socket-capable crate"
    } else {
        Add-Result "Nothing leaves the machine" "fail" "tests/privacy.rs exited $privacyExit"
    }

    # ---- 2. one hertz for half an hour, under budget ----
    if ($Budget) {
        Write-Host ""
        Write-Host "==> 2. 1 Hz for half an hour, under budget" -ForegroundColor Cyan
        Write-Host ("  {0} samples at {1} ms - about {2:N0} minutes. Leave the machine alone," -f `
            $BudgetSamples, $IntervalMs, ($BudgetSamples * $IntervalMs / 60000))
        Write-Host "  or note what you did to it; either way the record says when it ran."
        $go = $Yes
        if (-not $go) {
            $answer = Read-Host "  Start it now? [y/N]"
            $go = $answer -match '^(y|yes)$'
        }
        if (-not $go) {
            Add-Result "1 Hz for 30 min under budget" "eyes" "skipped by the operator"
        } else {
            $started = Get-Date
            $budgetReport = Invoke-Sa6i @("intel", "snapshot", "--samples", "$BudgetSamples", "--interval-ms", "$IntervalMs", "--budget", "--no-findings")
            $budgetExit = $script:LastExit
            Write-Host $budgetReport
            $took = ((Get-Date) - $started).TotalMinutes
            # The budget lines are printed by the CLI in one shape; the exit code
            # is the verdict, so it is not re-derived from the text.
            if ($budgetExit -eq 0) {
                Add-Result "1 Hz for 30 min under budget" "pass" ("PASS, {0:N0} minutes wall clock" -f $took)
            } elseif ($budgetExit -eq 3) {
                Add-Result "1 Hz for 30 min under budget" "fail" ("the verdict was MISS, {0:N0} minutes wall clock - see the lines above" -f $took)
            } else {
                Add-Result "1 Hz for 30 min under budget" "fail" "exited $budgetExit"
            }
        }
    } else {
        Add-Result "1 Hz for 30 min under budget" "eyes" "not run - pass -Budget to take the half hour"
    }

    # ---- the two that are somebody's eyes, not this script's ----
    Add-Result "Win7 renders Unsupported, with reasons" "eyes" "needs the old machine: sa6i-link intel snapshot --json there, and look for state unsupported"
    Add-Result "No admin prompt anywhere" "eyes" "watch for a UAC shield during the runs above; there must not be one"
} catch {
    if ($_.Exception.Message -ne "build failed" -and $_.Exception.Message -ne "binary missing") {
        Write-Host ("  stopped: " + $_.Exception.Message) -ForegroundColor Red
        Add-Result "Run" "fail" $_.Exception.Message
    }
} finally {
    Pop-Location

    # ---- the record ----
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# M1 verification - $stamp")
    $lines.Add("")
    $lines.Add("Written by ``scripts/verify-m1.ps1``. Two of these six rows cannot be")
    $lines.Add("answered by a script: an old Windows, and a human watching for a UAC prompt.")
    $lines.Add("")
    foreach ($fact in $facts) { $lines.Add("- " + $fact) }
    $lines.Add("")
    $lines.Add("| Exit criterion | Result | Detail |")
    $lines.Add("| --- | --- | --- |")
    foreach ($result in $results) {
        $lines.Add(("| {0} | **{1}** | {2} |" -f $result.Criterion, $result.State, ($result.Detail -replace '\|', '\|')))
    }
    $lines.Add("")
    $lines.Add("Read this against docs/plan/M1-REPORT.md, which says what each criterion")
    $lines.Add("needs and which slice is responsible when one fails.")
    $directory = Split-Path -Parent $OutFile
    if ($directory -and -not (Test-Path $directory)) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
    try {
        Set-Content -Path $OutFile -Value $lines -Encoding UTF8
        Write-Host ""
        Write-Host "  record: $OutFile" -ForegroundColor Cyan
    } catch {
        Write-Host "  could not write $OutFile" -ForegroundColor Red
    }

    $failed = @($results | Where-Object { $_.State -eq "fail" })
    $eyes = @($results | Where-Object { $_.State -eq "eyes" })
    Write-Host ""
    Write-Host ("  {0} passed, {1} failed, {2} need eyes" -f @($results | Where-Object { $_.State -eq "pass" }).Count, $failed.Count, $eyes.Count)
    $code = if ($failed.Count -gt 0) { 1 } else { 0 }
    $global:LASTEXITCODE = $code
    # `exit` in a script called from a console closes that console, which reads as
    # a crash and takes the results with it. Set the code the host will return
    # instead: `powershell -File` still gets it, and the window survives long
    # enough to read what happened.
    $Host.SetShouldExit($code)
}
