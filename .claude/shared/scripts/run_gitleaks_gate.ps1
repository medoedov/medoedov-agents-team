[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GitleaksPath,

    [Parameter(Mandatory = $true)]
    [string]$WorktreePath,

    [Parameter(Mandatory = $true)]
    [string]$SourceCommit,

    [Parameter(Mandatory = $true)]
    [string]$TempParent,

    [Parameter(Mandatory = $true)]
    [string]$ResultPath
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$script:InternalFailureExitCode = 70

function Assert-AbsolutePathText {
    param([string]$PathText)

    if ([string]::IsNullOrWhiteSpace($PathText)) {
        throw "Input path is empty."
    }
    if (-not [System.IO.Path]::IsPathRooted($PathText)) {
        throw "Input path is not absolute."
    }
    if ([regex]::IsMatch($PathText, '(^|[\\/])\.\.([\\/]|$)')) {
        throw "Input path contains traversal."
    }
}

function Assert-NoReparseComponents {
    param([string]$ExistingPath)

    $item = Get-Item -LiteralPath $ExistingPath -Force
    while ($null -ne $item) {
        $isReparse = (
            $item.Attributes -band [System.IO.FileAttributes]::ReparsePoint
        ) -ne 0
        if ($isReparse) {
            throw "A path component is a reparse point."
        }
        if ($item -is [System.IO.FileInfo]) {
            $item = $item.Directory
        }
        else {
            $item = $item.Parent
        }
    }
}

function Resolve-ExistingFilePath {
    param([string]$PathText)

    Assert-AbsolutePathText -PathText $PathText
    $fullPath = [System.IO.Path]::GetFullPath($PathText)
    if (-not [System.IO.File]::Exists($fullPath)) {
        throw "Required file is absent."
    }
    Assert-NoReparseComponents -ExistingPath $fullPath
    return $fullPath
}

function Resolve-ExistingDirectoryPath {
    param([string]$PathText)

    Assert-AbsolutePathText -PathText $PathText
    $fullPath = [System.IO.Path]::GetFullPath($PathText)
    if (-not [System.IO.Directory]::Exists($fullPath)) {
        throw "Required directory is absent."
    }
    Assert-NoReparseComponents -ExistingPath $fullPath
    return $fullPath.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

function Resolve-SafeResultPath {
    param(
        [string]$PathText,
        [string]$ResolvedTempParent
    )

    Assert-AbsolutePathText -PathText $PathText
    $fullPath = [System.IO.Path]::GetFullPath($PathText)
    $parent = [System.IO.Path]::GetDirectoryName($fullPath)
    if (-not [string]::Equals(
        $parent,
        $ResolvedTempParent,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Result parent is outside the permitted directory."
    }
    $name = [System.IO.Path]::GetFileName($fullPath)
    if ($name -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.json$') {
        throw "Result filename is not permitted."
    }
    if (
        [System.IO.File]::Exists($fullPath) -or
        [System.IO.Directory]::Exists($fullPath)
    ) {
        throw "Result path already exists."
    }
    return $fullPath
}

function Get-BytesSha256 {
    param([byte[]]$Bytes)

    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        return (
            [System.BitConverter]::ToString($hasher.ComputeHash($Bytes))
        ).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $hasher.Dispose()
    }
}

function Get-FileSha256 {
    param([string]$Path)

    $stream = [System.IO.File]::OpenRead($Path)
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        return (
            [System.BitConverter]::ToString($hasher.ComputeHash($stream))
        ).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $hasher.Dispose()
        $stream.Dispose()
    }
}

function Get-StringSha256 {
    param([string]$Value)

    return Get-BytesSha256 -Bytes (
        [System.Text.Encoding]::UTF8.GetBytes($Value)
    )
}

function Get-NormalizedSid {
    param([System.Security.Principal.IdentityReference]$Identity)

    if ($Identity -is [System.Security.Principal.SecurityIdentifier]) {
        return $Identity.Value.ToUpperInvariant()
    }
    $sid = $Identity.Translate(
        [System.Security.Principal.SecurityIdentifier]
    )
    return $sid.Value.ToUpperInvariant()
}

function New-OwnerOnlyDirectorySecurity {
    $owner = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $inheritance = (
        [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
        [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    )
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetOwner($owner)
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $owner,
        [System.Security.AccessControl.FileSystemRights]::FullControl,
        $inheritance,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    [void]$acl.AddAccessRule($rule)
    return $acl
}

function Assert-OwnerOnlyDirectoryAcl {
    param([string]$DirectoryPath)

    if (
        -not [System.IO.Directory]::Exists($DirectoryPath) -or
        (
            (Get-Item -LiteralPath $DirectoryPath -Force).Attributes -band
            [System.IO.FileAttributes]::ReparsePoint
        ) -ne 0
    ) {
        throw "Nonce directory identity is invalid."
    }
    $verified = [System.IO.Directory]::GetAccessControl($DirectoryPath)
    $verifiedOwner = $verified.GetOwner(
        [System.Security.Principal.SecurityIdentifier]
    )
    $ownerSid = Get-NormalizedSid -Identity $verifiedOwner
    $rules = $verified.GetAccessRules(
        $true,
        $true,
        [System.Security.Principal.SecurityIdentifier]
    )
    if ($rules.Count -eq 0) {
        throw "Owner access rule is absent."
    }
    foreach ($entry in $rules) {
        $entrySid = Get-NormalizedSid -Identity $entry.IdentityReference
        if (
            $entrySid -ne $ownerSid -or
            $entry.IsInherited -or
            $entry.AccessControlType -ne
                [System.Security.AccessControl.AccessControlType]::Allow
        ) {
            throw "Nonce access rules are not owner-only."
        }
    }
    return Get-StringSha256 -Value $ownerSid
}

function New-OwnerOnlyFileSecurity {
    $owner = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl = New-Object System.Security.AccessControl.FileSecurity
    $acl.SetOwner($owner)
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $owner,
        [System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    [void]$acl.AddAccessRule($rule)
    return $acl
}

function Assert-OwnerOnlyFileAcl {
    param([string]$FilePath)

    if (
        -not [System.IO.File]::Exists($FilePath) -or
        (
            (Get-Item -LiteralPath $FilePath -Force).Attributes -band
            [System.IO.FileAttributes]::ReparsePoint
        ) -ne 0
    ) {
        throw "Reserved file identity is invalid."
    }
    $verified = [System.IO.File]::GetAccessControl($FilePath)
    $verifiedOwner = $verified.GetOwner(
        [System.Security.Principal.SecurityIdentifier]
    )
    $ownerSid = Get-NormalizedSid -Identity $verifiedOwner
    $rules = $verified.GetAccessRules(
        $true,
        $true,
        [System.Security.Principal.SecurityIdentifier]
    )
    if ($rules.Count -eq 0) {
        throw "Reserved file owner access rule is absent."
    }
    foreach ($entry in $rules) {
        $entrySid = Get-NormalizedSid -Identity $entry.IdentityReference
        if (
            $entrySid -ne $ownerSid -or
            $entry.IsInherited -or
            $entry.AccessControlType -ne
                [System.Security.AccessControl.AccessControlType]::Allow
        ) {
            throw "Reserved file access rules are not owner-only."
        }
    }
}

function Reserve-OwnerOnlyFile {
    param([string]$FilePath)

    $security = New-OwnerOnlyFileSecurity
    $stream = New-Object -TypeName System.IO.FileStream -ArgumentList @(
        $FilePath,
        [System.IO.FileMode]::CreateNew,
        [System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.IO.FileShare]::None,
        4096,
        [System.IO.FileOptions]::None,
        $security
    )
    try {
        $stream.Flush()
    }
    finally {
        $stream.Dispose()
    }
    Assert-OwnerOnlyFileAcl -FilePath $FilePath
    $item = Get-Item -LiteralPath $FilePath -Force
    return [ordered]@{
        path = $FilePath
        creation_ticks = $item.CreationTimeUtc.Ticks
    }
}

function Assert-ReservedFile {
    param([object]$Reservation)

    Assert-OwnerOnlyFileAcl -FilePath $Reservation.path
    $item = Get-Item -LiteralPath $Reservation.path -Force
    if ($item.CreationTimeUtc.Ticks -ne $Reservation.creation_ticks) {
        throw "Reserved file identity changed."
    }
}

function New-NonceDirectory {
    param([string]$ResolvedTempParent)

    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        $name = "gitleaks-gate-" + [guid]::NewGuid().ToString("N")
        $candidate = [System.IO.Path]::Combine($ResolvedTempParent, $name)
        $security = New-OwnerOnlyDirectorySecurity
        try {
            [void][System.IO.Directory]::CreateDirectory($candidate, $security)
            $ownerDigest = Assert-OwnerOnlyDirectoryAcl `
                -DirectoryPath $candidate
            return [ordered]@{
                path = $candidate
                owner_digest = $ownerDigest
            }
        }
        catch [System.IO.IOException] {
            continue
        }
    }
    throw "Could not reserve a unique nonce directory."
}

function Read-ReportCount {
    param([string]$ReportPath)

    $json = [System.IO.File]::ReadAllText($ReportPath)
    $trimmed = $json.Trim()
    if (
        $trimmed.Length -lt 2 -or
        $trimmed[0] -ne '[' -or
        $trimmed[$trimmed.Length - 1] -ne ']'
    ) {
        throw "Gitleaks report must be a JSON array."
    }
    try {
        $parsed = ConvertFrom-Json -InputObject $json
    }
    catch {
        throw "Gitleaks report is not valid JSON."
    }
    if ($null -eq $parsed) {
        return 0
    }
    return @($parsed).Count
}

function Invoke-GitleaksScan {
    param(
        [string]$Executable,
        [string[]]$ArgumentList,
        [string]$ScanId,
        [string]$ReportPath,
        [string]$StdoutPath, [string]$StderrPath,
        [object[]]$Reservations
    )
    foreach ($reservation in $Reservations) {
        Assert-ReservedFile -Reservation $reservation
    }
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $Executable @ArgumentList 1> $StdoutPath 2> $StderrPath
        $toolExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($null -eq $toolExitCode) {
        $toolExitCode = $script:InternalFailureExitCode
    }
    foreach ($reservation in $Reservations) {
        Assert-ReservedFile -Reservation $reservation
    }
    $findingCount = $null
    $reportDigest = $null
    if ([System.IO.File]::Exists($ReportPath)) {
        try {
            $findingCount = Read-ReportCount -ReportPath $ReportPath
            $reportDigest = Get-FileSha256 -Path $ReportPath
        }
        catch {
            $toolExitCode = $script:InternalFailureExitCode
        }
    }
    else {
        $toolExitCode = $script:InternalFailureExitCode
    }
    return [ordered]@{
        scan_id = $ScanId
        exit_code = [int]$toolExitCode
        findings_count = $findingCount
        report_sha256 = $reportDigest
        stdout_sha256 = Get-FileSha256 -Path $StdoutPath
        stderr_sha256 = Get-FileSha256 -Path $StderrPath
    }
}

function Remove-NonceDirectory {
    param(
        [string]$NoncePath,
        [string]$ResolvedTempParent
    )

    if ([string]::IsNullOrWhiteSpace($NoncePath)) {
        return "not_created"
    }
    $prefix = $ResolvedTempParent +
        [System.IO.Path]::DirectorySeparatorChar
    if (-not $NoncePath.StartsWith(
        $prefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Nonce containment check failed."
    }
    if (
        [System.IO.Path]::GetFileName($NoncePath) -notmatch
            '^gitleaks-gate-[0-9a-f]{32}$'
    ) {
        throw "Nonce identity check failed."
    }
    Assert-NoReparseComponents -ExistingPath $NoncePath
    [System.IO.Directory]::Delete($NoncePath, $true)
    if ([System.IO.Directory]::Exists($NoncePath)) {
        throw "Nonce cleanup did not complete."
    }
    return "complete"
}

function Write-JsonNoClobber {
    param(
        [string]$Path,
        [object]$Value
    )

    $json = ConvertTo-Json -InputObject $Value -Depth 6
    $encoding = New-Object System.Text.UTF8Encoding($false)
    $bytes = $encoding.GetBytes($json)
    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush()
    }
    finally {
        $stream.Dispose()
    }
}

$exitCode = $script:InternalFailureExitCode
$noncePath = $null
$safeResultPath = $null
$cleanupStatus = "not_created"
$scans = @()
$gitleaksDigest = $null
$worktreeDigest = $null
$aclOwnerSidDigest = $null

try {
    if ($SourceCommit -notmatch '^[0-9a-fA-F]{40}$') {
        throw "Source commit is not a 40-hex identity."
    }
    $resolvedGitleaks = Resolve-ExistingFilePath -PathText $GitleaksPath
    if ([System.IO.Path]::GetExtension($resolvedGitleaks) -ne ".exe") {
        throw "Scanner must be a native executable."
    }
    $resolvedWorktree = Resolve-ExistingDirectoryPath -PathText $WorktreePath
    $resolvedTempParent = Resolve-ExistingDirectoryPath -PathText $TempParent
    $safeResultPath = Resolve-SafeResultPath `
        -PathText $ResultPath `
        -ResolvedTempParent $resolvedTempParent

    $chatPath = [System.IO.Path]::Combine($resolvedWorktree, "chats.csv")
    if (
        [System.IO.File]::Exists($chatPath) -or
        [System.IO.Directory]::Exists($chatPath)
    ) {
        throw "Content-prohibited path is materialized."
    }

    $nonce = New-NonceDirectory -ResolvedTempParent $resolvedTempParent
    $noncePath = $nonce.path
    $aclOwnerSidDigest = $nonce.owner_digest
    $gitleaksDigest = Get-FileSha256 -Path $resolvedGitleaks
    $worktreeDigest = Get-StringSha256 -Value $resolvedWorktree

    $currentReport = [System.IO.Path]::Combine($noncePath, "current.json")
    $historyReport = [System.IO.Path]::Combine($noncePath, "history.json")
    $currentOut = [System.IO.Path]::Combine($noncePath, "current.stdout")
    $currentErr = [System.IO.Path]::Combine($noncePath, "current.stderr")
    $historyOut = [System.IO.Path]::Combine($noncePath, "history.stdout")
    $historyErr = [System.IO.Path]::Combine($noncePath, "history.stderr")

    $currentReservations = @(
        (Reserve-OwnerOnlyFile -FilePath $currentReport),
        (Reserve-OwnerOnlyFile -FilePath $currentOut),
        (Reserve-OwnerOnlyFile -FilePath $currentErr)
    )
    $historyReservations = @(
        (Reserve-OwnerOnlyFile -FilePath $historyReport),
        (Reserve-OwnerOnlyFile -FilePath $historyOut),
        (Reserve-OwnerOnlyFile -FilePath $historyErr)
    )

    $currentArguments = @(
        "dir",
        $resolvedWorktree,
        "--redact",
        "--no-banner",
        "--exit-code",
        "0",
        "--report-format",
        "json",
        "--report-path",
        $currentReport
    )
    $historyArguments = @(
        "git",
        $resolvedWorktree,
        "--log-opts",
        (
            $SourceCommit.ToLowerInvariant() +
            " -- . :(top,exclude,literal)chats.csv"
        ),
        "--redact",
        "--no-banner",
        "--exit-code",
        "0",
        "--report-format",
        "json",
        "--report-path",
        $historyReport
    )

    $scans += Invoke-GitleaksScan `
        -Executable $resolvedGitleaks `
        -ArgumentList $currentArguments `
        -ScanId "current_dir" `
        -ReportPath $currentReport `
        -StdoutPath $currentOut `
        -StderrPath $currentErr `
        -Reservations $currentReservations
    $scans += Invoke-GitleaksScan `
        -Executable $resolvedGitleaks `
        -ArgumentList $historyArguments `
        -ScanId "git_history" `
        -ReportPath $historyReport `
        -StdoutPath $historyOut `
        -StderrPath $historyErr `
        -Reservations $historyReservations

    $exitCode = 0
    foreach ($scan in $scans) {
        if ($scan.exit_code -ne 0 -and $exitCode -eq 0) {
            $exitCode = [int]$scan.exit_code
        }
    }
}
catch {
    if ($exitCode -eq 0) {
        $exitCode = $script:InternalFailureExitCode
    }
}
finally {
    try {
        if ($null -ne $noncePath) {
            $cleanupStatus = Remove-NonceDirectory `
                -NoncePath $noncePath `
                -ResolvedTempParent $resolvedTempParent
        }
    }
    catch {
        $cleanupStatus = "failed"
        $exitCode = $script:InternalFailureExitCode
    }
}

if ($null -ne $safeResultPath) {
    $totalFindings = 0
    foreach ($scan in $scans) {
        if ($null -ne $scan.findings_count) {
            $totalFindings += [int]$scan.findings_count
        }
    }
    $classificationRequired = $false
    if ($exitCode -ne 0) {
        $status = "scan_failed"
    }
    elseif ($totalFindings -gt 0) {
        $status = "scan_completed_with_findings"
        $classificationRequired = $true
    }
    else {
        $status = "scan_completed_clean"
    }
    $summary = [ordered]@{
        schema_version = 1
        status = $status
        exit_code = [int]$exitCode
        classification_required = $classificationRequired
        terminal_gate_passed = $false
        source_commit = $SourceCommit.ToLowerInvariant()
        gitleaks_sha256 = $gitleaksDigest
        worktree_identity_sha256 = $worktreeDigest
        acl_owner_sid_sha256 = $aclOwnerSidDigest
        scans = $scans
        cleanup_status = $cleanupStatus
    }
    try {
        Write-JsonNoClobber -Path $safeResultPath -Value $summary
    }
    catch {
        $exitCode = $script:InternalFailureExitCode
    }
}

if ($exitCode -ne 0) {
    [Console]::Error.WriteLine("Gitleaks gate failed closed.")
    exit $exitCode
}

[Console]::Out.WriteLine("Gitleaks gate completed.")
exit 0
