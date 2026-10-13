param(
    [Parameter(Mandatory=$true)][string]$Output,
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][ValidateRange(1,65535)][int]$Subversion,
    [switch]$SkipFrontendBuild,
    [string]$FixturePublicKey,
    [switch]$IncludeConnectivity
)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$initialSource=git -C $repo rev-parse HEAD
$initialDirty=@(git -C $repo status --porcelain).Count -gt 0
$out=[IO.Path]::GetFullPath($Output)
if(Test-Path -LiteralPath $out){throw 'Package output must be new; no automatic overwrite or cleanup'}
New-Item -ItemType Directory -Path $out | Out-Null
$scratch=Join-Path $out 'scratch'
New-Item -ItemType Directory -Path $scratch | Out-Null
$env:TEMP=$scratch
$env:TMP=$scratch
$env:PYINSTALLER_CONFIG_DIR=Join-Path $out 'pyinstaller-cache'
function Invoke-Checked([string]$Program,[string[]]$Arguments){
    & $Program @Arguments
    if($LASTEXITCODE -ne 0){throw "Build operation failed: $Program ($LASTEXITCODE)"}
}
Push-Location (Join-Path $repo 'desktop')
try {
    Push-Location $repo
    try {
        Invoke-Checked 'go' @('mod','download','tailscale.com')
        $coreDirectory=(& go list -m -f '{{.Dir}}' tailscale.com).Trim()
        if($LASTEXITCODE -ne 0 -or -not $coreDirectory){throw 'Pinned core module unavailable'}
        $upstream=(Get-Content -LiteralPath (Join-Path $coreDirectory 'VERSION.txt') -Raw).Trim()
    } finally {Pop-Location}
    $version="$upstream+$Subversion"
    $env:TAILD_VERSION_RESOURCE=Join-Path $out 'version-resource.txt'
    Invoke-Checked $Python @('-B',(Join-Path $PSScriptRoot 'package_version.py'),'--output',$env:TAILD_VERSION_RESOURCE,
        '--upstream',$upstream,'--subversion',"$Subversion")
    if($FixturePublicKey){
        $env:TAILD_RUNTIME_SOURCE=Join-Path $out 'fixture-runtime-source'
        Invoke-Checked $Python @('-B',(Join-Path $PSScriptRoot 'fixture_build.py'),'--source',$PSScriptRoot,
            '--output',$env:TAILD_RUNTIME_SOURCE,'--public-key',$FixturePublicKey)
    } else {$env:TAILD_RUNTIME_SOURCE=$PSScriptRoot}
    if(-not $SkipFrontendBuild){Invoke-Checked 'npm.cmd' @('ci','--ignore-scripts');Invoke-Checked 'npm.cmd' @('run','build')}
    $payload=Join-Path $out 'payload'
    Invoke-Checked $Python @('-B','-m','PyInstaller','--distpath',$payload,
        '--workpath',(Join-Path $out 'freeze-work'),(Join-Path $repo 'desktop/TailD.spec'))
    $package=Join-Path $payload 'TailD'
    if($IncludeConnectivity){
        $connectivityBuild=Join-Path $out 'connectivity-build'
        & (Join-Path $PSScriptRoot 'build_connectivity.ps1') -Output $connectivityBuild -Python $Python -Subversion $Subversion -PublicKey $(if($FixturePublicKey){$FixturePublicKey}else{'Vq5UrOc4cj4reJmuVdRJ9YFiSRuax9qua/F/WpyW+bE='})
        if(-not $?){throw 'Connectivity build failed'}
        Copy-Item -LiteralPath (Join-Path $connectivityBuild 'payload') -Destination (Join-Path $package 'connectivity') -Recurse
        Invoke-Checked $Python @('-B',(Join-Path $PSScriptRoot 'core_manifest.py'),'--package',(Join-Path $package 'connectivity'),
            '--provenance',(Join-Path $package 'connectivity/core-provenance.json'),'--subversion',"$Subversion")
    }
    Invoke-Checked 'dotnet' @('publish','native/TailD.Desktop.csproj','--configuration','Release',
        '--runtime','win-x64','--self-contained','true','-p:RestoreLockedMode=true',
        "-p:Version=$version","-p:FileVersion=$upstream.$Subversion",'-p:IncludeSourceRevisionInInformationalVersion=false',
        "-p:BaseIntermediateOutputPath=$out/dotnet-obj/","-p:BaseOutputPath=$out/dotnet-bin/",'--output',(Join-Path $package 'desktop'),'--nologo')
    $licenseRoot=Join-Path $package 'licenses'
    New-Item -ItemType Directory -Path $licenseRoot | Out-Null
    Copy-Item -LiteralPath (Join-Path $repo 'LICENSE') -Destination (Join-Path $licenseRoot 'inherited-core-BSD.txt')
    Copy-Item -LiteralPath (Join-Path $repo 'desktop/NOTICE.md') -Destination (Join-Path $licenseRoot 'NOTICE.md')
    Invoke-Checked $Python @('-B',(Join-Path $PSScriptRoot 'package_notices.py'),'--output',$licenseRoot,
        '--nuget',$(if($env:NUGET_PACKAGES){$env:NUGET_PACKAGES}else{Join-Path $env:USERPROFILE '.nuget/packages'}))
    # Build provenance is nonsecret source/runtime identity, not an update
    # manifest or a signature claim. Signing/installer gates consume it later.
    $source=git -C $repo rev-parse HEAD
    if($source -ne $initialSource){throw 'Source revision changed during packaging; refuse provenance'}
    $dirty=$initialDirty -or (@(git -C $repo status --porcelain).Count -gt 0)
    $core=(Select-String -Path (Join-Path $repo 'go.mod') -Pattern '^replace tailscale.com => ').Line
    if(-not $core){throw 'Missing exact inherited core replace pin'}
    $files=@(Get-ChildItem -LiteralPath $package -Recurse -File | Sort-Object FullName | ForEach-Object {
        [ordered]@{path=[IO.Path]::GetRelativePath($package,$_.FullName).Replace('\','/');size=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
    })
    [ordered]@{schema='taild-local-package-v1';source_commit=$source;source_dirty=$dirty;core_replace=$core;upstream_version=$upstream;subversion=$Subversion;
        architecture='windows-amd64';authenticode='not-signed';delivery='local-verification-only';fixture_trust=[bool]$FixturePublicKey;connectivity=[bool]$IncludeConnectivity;files=$files} |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $out 'provenance.json') -Encoding utf8NoBOM
    Write-Output "Local candidate: $package"
} finally {Pop-Location}
