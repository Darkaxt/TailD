# Reuse the existing TailDNS identity; never generate or rotate an APK key.
[CmdletBinding()]
param(
    [string]$SigningDirectory = "$env:LOCALAPPDATA\TailDNS\signing",
    [Parameter(Mandatory)][string]$Keytool
)
$ErrorActionPreference = 'Stop'
$repository = 'Darkaxt/TailD'
$environmentName = 'taild-android-release'
$expected = 'dcd0ede91eb7e0ed88a72b5289f84f8d4a61ccc22707f36378e15540b99d32e1'
$directory = [IO.Path]::GetFullPath($SigningDirectory)
if ((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'Signing identity directory must not be a reparse point.'
}
$keystore = Join-Path $directory 'taildns.jks'
$credentialPath = Join-Path $directory 'password.dpapi.xml'
foreach ($path in @($keystore, $credentialPath)) {
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Existing complete signing identity is required; no key will be created.' }
}
$credential = Import-Clixml -LiteralPath $credentialPath
try {
    $password = $credential.GetNetworkCredential().Password
    $env:TAILD_ANDROID_SIGNING_PASSWORD = $password
    $certificate = & $Keytool -list -v -keystore $keystore -alias taildns -storepass:env TAILD_ANDROID_SIGNING_PASSWORD 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Existing keystore could not be verified.' }
    $line = $certificate | Where-Object { $_ -match 'SHA256:' }
    $actual = (($line -replace '^.*SHA256:\s*', '') -replace ':', '').Trim().ToLowerInvariant()
    if ($actual -ne $expected) { throw 'Existing signer does not match the pinned upgrade identity.' }

    # The environment is scoped to main. No reviewer/approval checkpoint is added.
    @{ deployment_branch_policy = @{ protected_branches = $false; custom_branch_policies = $true } } |
        ConvertTo-Json -Compress | gh api --method PUT "repos/$repository/environments/$environmentName" --input - | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not establish isolated Android signing environment.' }
    $policies = gh api "repos/$repository/environments/$environmentName/deployment-branch-policies" | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect signing environment branch policy.' }
    if (!($policies.branch_policies | Where-Object { $_.name -eq 'main' -and $_.type -eq 'branch' })) {
        @{ name = 'main'; type = 'branch' } | ConvertTo-Json -Compress |
            gh api --method POST "repos/$repository/environments/$environmentName/deployment-branch-policies" --input - | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not scope Android signing to main.' }
    }
    [Convert]::ToBase64String([IO.File]::ReadAllBytes($keystore)) |
        gh secret set TAILD_ANDROID_KEYSTORE_BASE64 --repo $repository --env $environmentName
    if ($LASTEXITCODE -ne 0) { throw 'Could not provision the existing keystore into the isolated environment.' }
    $password | gh secret set TAILD_ANDROID_KEYSTORE_PASSWORD --repo $repository --env $environmentName
    if ($LASTEXITCODE -ne 0) { throw 'Could not provision the protected password.' }
    gh variable set TAILD_ANDROID_SIGNER_SHA256 --repo $repository --env $environmentName --body $expected
    if ($LASTEXITCODE -ne 0) { throw 'Could not pin the public Android signer.' }
    [PSCustomObject]@{ Repository = $repository; Environment = $environmentName; SignerSHA256 = $actual; GeneratedKey = $false } | ConvertTo-Json
} finally {
    Remove-Item Env:TAILD_ANDROID_SIGNING_PASSWORD -ErrorAction SilentlyContinue
    $password = $null
    $credential = $null
    $certificate = $null
}
