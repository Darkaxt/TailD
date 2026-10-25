param(
    [Parameter(Mandatory=$true)][string]$Output,
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][ValidateRange(1,65535)][int]$Subversion,
    [string]$PublicKey='Vq5UrOc4cj4reJmuVdRJ9YFiSRuax9qua/F/WpyW+bE='
)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$initialSource=git -C $repo rev-parse HEAD
$initialDirty=@(git -C $repo status --porcelain).Count -gt 0
$out=[IO.Path]::GetFullPath($Output)
if(Test-Path -LiteralPath $out){throw 'Connectivity output must be new'}
New-Item -ItemType Directory -Path $out | Out-Null
$scratch=Join-Path $out 'scratch'
New-Item -ItemType Directory -Path $scratch | Out-Null
$env:TEMP=$scratch; $env:TMP=$scratch
function Checked([string]$Program,[string[]]$Arguments){
    & $Program @Arguments
    if($LASTEXITCODE -ne 0){throw "Connectivity build failed: $Program ($LASTEXITCODE)"}
}
Push-Location $repo
try {
    $module=go mod download -json tailscale.com | ConvertFrom-Json
    if($LASTEXITCODE -ne 0 -or -not $module.Zip){throw 'Exact inherited core module unavailable'}
    # Go explicitly forbids overlays beneath GOMODCACHE. Export its verified
    # module ZIP into disposable build scratch, never edit/copy source into TailD.
    $sourceRoot=Join-Path $out 'source'
    [IO.Compression.ZipFile]::ExtractToDirectory($module.Zip,$sourceRoot)
    $core=Join-Path $sourceRoot ("github.com/Darkaxt/tailscale@"+$module.Version)
    $overlayRoot=Join-Path $out 'overlay'
    Checked $Python @('-B',(Join-Path $PSScriptRoot 'core_overlay.py'),'--core',$core,'--output',$overlayRoot)
    $overlay=Join-Path $overlayRoot 'overlay.json'
    $upstream=(Get-Content -LiteralPath (Join-Path $core 'VERSION.txt') -Raw).Trim()
    $commit='35f748d736afef777b95496742f0e9c1df9fbdb1'
    $flags="-X tailscale.com/version.longStamp=$upstream-taild.$Subversion -X tailscale.com/version.shortStamp=$upstream -X tailscale.com/version.gitCommitStamp=$commit"
    $payload=Join-Path $out 'payload'
    New-Item -ItemType Directory -Path $payload | Out-Null
    Push-Location $core
    try {
        Checked 'go' @('test','-mod=readonly','-overlay',$overlay,'./client/systray','./feature/clientupdate','./cmd/taildns-ipn','./cmd/taildns-installer','-count=1')
        # The Go linker reads COFF resources from the physical exported source,
        # unlike Go source overlays. This is generated task scratch, not cache.
        $syso=Join-Path $core 'cmd/taildns-installer/manifest_windows_amd64.syso'
        Checked 'go' @('run','-mod=readonly','./cmd/mkmanifest','amd64','cmd/taildns-installer/windows-manifest.xml',$syso)
        foreach($item in @(
            @('taildnsd.exe','./cmd/tailscaled',$flags),
            @('tailscale.exe','./cmd/tailscale',$flags),
            @('taildns.exe','./cmd/taildns',$flags),
            @('taildns-ipn.exe','./cmd/taildns-ipn',"$flags -H windowsgui"),
            @('taildns-installer.exe','./cmd/taildns-installer',"$flags -X main.updatePublicKeyBase64=$PublicKey")
        )){
            Checked 'go' @('build','-mod=readonly','-overlay',$overlay,'-buildvcs=false','-trimpath','-ldflags',$item[2],'-o',(Join-Path $payload $item[0]),$item[1])
        }
    } finally {Pop-Location}
    $version=& (Join-Path $payload 'tailscale.exe') version --json | ConvertFrom-Json
    if($LASTEXITCODE -ne 0 -or $version.short -ne $upstream -or $version.long -ne "$upstream-taild.$Subversion" -or $version.gitCommit -ne $commit){throw 'Connectivity identity mismatch'}
    Copy-Item -LiteralPath (Join-Path $core 'LICENSE') -Destination (Join-Path $payload 'inherited-core-LICENSE.txt')
    if((git -C $repo rev-parse HEAD) -ne $initialSource){throw 'Source changed during connectivity build'}
    [ordered]@{schema='taild-core-build-v1';core_commit=$commit;core_module=$module.Version;module_sum=$module.Sum;
        upstream_version=$upstream;subversion=$Subversion;source_commit=$initialSource;
        source_dirty=($initialDirty -or (@(git -C $repo status --porcelain).Count -gt 0));
        overlay=@(Get-ChildItem -LiteralPath $overlayRoot -Recurse -File | Where-Object Extension -eq '.go' | ForEach-Object {
            [ordered]@{path=[IO.Path]::GetRelativePath($overlayRoot,$_.FullName).Replace('\','/');sha256=(Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
        })} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $payload 'core-provenance.json') -Encoding utf8NoBOM
} finally {Pop-Location}
