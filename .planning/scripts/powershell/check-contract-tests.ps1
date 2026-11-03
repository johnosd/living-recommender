#!/usr/bin/env pwsh
# Trava dos testes de contrato de uma feature (sdd-plan escreve, sdd-execute
# só pode fazer passar, nunca editar). Guarda caminho + SHA256 de cada arquivo
# de teste de contrato em sdd/specs/<slug>/contract-tests.lock e confere se
# nada mudou desde que foi travado.
#
# Hash é calculado com fim de linha normalizado (CRLF -> LF), pra um
# checkout com autocrlf não parecer adulteração.
#
# Também impõe o orçamento: no máximo $MaxTests casos nos arquivos JS/TS que o script analisa.
# Arquivos de outros runtimes mantêm o hash e registram contagem desconhecida.
#
# Usage:
#   ./check-contract-tests.ps1 -Slug <slug> [-Json]
#       confere a trava (default). Sai 1 se algum arquivo mudou/sumiu.
#   ./check-contract-tests.ps1 -Slug <slug> -Write -Paths <p1>,<p2> [-Json]
#       cria/regrava a trava com esses arquivos (caminhos relativos à raiz).
#   ./check-contract-tests.ps1 -Slug <slug> -Write [-Json]
#       regrava a trava com os mesmos arquivos já travados (emenda aprovada).

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Slug,
    [switch]$Write,
    [string[]]$Paths,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"

$MaxTests = 5

$repoRoot = Get-RepoRoot
$featureDir = Resolve-FeatureDir -RepoRoot $repoRoot -Slug $Slug
$lockPath = Join-Path $featureDir 'contract-tests.lock'

function Get-NormalizedHash {
    param([string]$FullPath)
    $text = [System.IO.File]::ReadAllText($FullPath)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($text.Replace("`r`n", "`n"))
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Get-TestStats {
    param([string]$FullPath)
    $extension = [System.IO.Path]::GetExtension($FullPath).ToLowerInvariant()
    if ($extension -notin @('.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx')) {
        return [PSCustomObject]@{ Count = $null; Forbidden = 0 }
    }
    $text = [System.IO.File]::ReadAllText($FullPath)
    $count = ([regex]::Matches($text, '(?m)^\s*(it|test)\s*\(')).Count
    $forbidden = ([regex]::Matches($text, '(?m)\b(it|test|describe)\.(skip|only|todo|each)\b')).Count
    [PSCustomObject]@{ Count = $count; Forbidden = $forbidden }
}

function Write-Result {
    param([bool]$Pass, [string]$Message, $Files)
    if ($Json) {
        [PSCustomObject]@{ PASS = $Pass; MESSAGE = $Message; LOCK = $lockPath; FILES = $Files } | ConvertTo-Json -Compress -Depth 4
    } else {
        Write-Output $(if ($Pass) { "PASS: $Message" } else { "FAIL: $Message" })
        foreach ($f in $Files) { Write-Output "  [$($f.status)] $($f.path) ($($f.tests) testes)" }
    }
    if (-not $Pass) { exit 1 }
}

if ($Write) {
    if (-not $Paths -or $Paths.Count -eq 0) {
        if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) {
            [Console]::Error.WriteLine("ERROR: sem -Paths e sem trava existente em $lockPath")
            exit 1
        }
        $Paths = @((Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json).files | ForEach-Object { $_.path })
    }

    $entries = @()
    $total = 0
    $hasUnknownCount = $false
    foreach ($p in $Paths) {
        $rel = $p.Replace('\', '/') -replace '^\./', ''
        $full = Join-Path $repoRoot $rel
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
            [Console]::Error.WriteLine("ERROR: arquivo de contrato não existe: $rel")
            exit 1
        }
        $stats = Get-TestStats -FullPath $full
        if ($stats.Forbidden -gt 0) {
            [Console]::Error.WriteLine(('ERROR: {0} usa uma regra de teste desabilitado — proibido em teste de contrato' -f $rel))
            exit 1
        }
        if ($null -eq $stats.Count) { $hasUnknownCount = $true } else { $total += $stats.Count }
        $entries += [PSCustomObject]@{ path = $rel; sha256 = (Get-NormalizedHash -FullPath $full); tests = if ($null -eq $stats.Count) { 'unknown' } else { $stats.Count } }
    }

    if (-not $hasUnknownCount -and $total -gt $MaxTests) {
        [Console]::Error.WriteLine("ERROR: $total testes de contrato, orçamento máximo é $MaxTests")
        exit 1
    }

    $lock = [PSCustomObject]@{
        feature  = (Split-Path $featureDir -Leaf)
        lockedAt = (Get-Date).ToString('yyyy-MM-dd HH:mm')
        total    = if ($hasUnknownCount) { $null } else { $total }
        files    = $entries
    }
    [System.IO.File]::WriteAllText($lockPath, ($lock | ConvertTo-Json -Depth 4), (New-Object System.Text.UTF8Encoding $false))
    $files = @($entries | ForEach-Object { [PSCustomObject]@{ path = $_.path; status = 'LOCKED'; tests = $_.tests } })
    if ($hasUnknownCount) { $writeMessage = 'trava gravada (contagem não inferida para arquivos sem adaptador)' } else { $writeMessage = ('trava gravada ({0}/{1} testes)' -f $total, $MaxTests) }
    Write-Result -Pass $true -Message $writeMessage -Files $files
    exit 0
}

if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) {
    Write-Result -Pass $true -Message 'feature sem testes de contrato (nenhum contract-tests.lock)' -Files @()
    exit 0
}

$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
$files = @()
$ok = $true
foreach ($e in $lock.files) {
    $full = Join-Path $repoRoot $e.path
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
        $files += [PSCustomObject]@{ path = $e.path; status = 'MISSING'; tests = $e.tests }
        $ok = $false
        continue
    }
    $status = if ((Get-NormalizedHash -FullPath $full) -eq $e.sha256) { 'OK' } else { 'CHANGED' }
    if ($status -ne 'OK') { $ok = $false }
    $files += [PSCustomObject]@{ path = $e.path; status = $status; tests = $e.tests }
}

if ($ok) {
    $lockTotal = if ($null -eq $lock.total) { 'contagem não inferida' } else { "$($lock.total) testes de contrato" }
    Write-Result -Pass $true -Message "trava íntegra ($lockTotal)" -Files $files
} else {
    Write-Result -Pass $false -Message 'teste de contrato alterado ou removido desde a trava; só o sdd-plan ou uma emenda aprovada pode mudar isso' -Files $files
}
