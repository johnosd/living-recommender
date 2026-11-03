#!/usr/bin/env pwsh
# Cria sdd/adr/ADR-NNN-slug.md semeado a partir do template. Usado só
# pelo sdd-adr. Não sobrescreve ADRs existentes — emenda é sempre uma nota
# inline na ADR antiga, nunca um novo arquivo substituindo o anterior.
#
# Usage:
#   ./new-adr.ps1 "Título da decisão" [-Json] [-DryRun]

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Title,
    [switch]$Json,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"

$repoRoot = Get-RepoRoot
$adrDir = Join-Path (Get-SddRoot -RepoRoot $repoRoot) 'adr'

$slug = New-SlugFromText -Text $Title -MaxWords 5
$nextNumber = (Get-HighestAdrNumber -AdrDir $adrDir) + 1
$paddedNumber = '{0:D3}' -f $nextNumber
$fileName = "ADR-$paddedNumber-$slug.md"
$adrPath = Join-Path $adrDir $fileName

if (Test-Path -LiteralPath $adrPath) {
    [Console]::Error.WriteLine("ERROR: $adrPath já existe")
    exit 1
}

if (-not $DryRun) {
    if (-not (Test-Path -LiteralPath $adrDir -PathType Container)) {
        New-Item -ItemType Directory -Path $adrDir -Force | Out-Null
    }
    $templateContent = Get-TemplateContent -RepoRoot $repoRoot -TemplateName 'adr'
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($adrPath, $templateContent, $utf8NoBom)
}

if ($Json) {
    [PSCustomObject]@{
        ADR_NUM  = $paddedNumber
        ADR_FILE = $adrPath
        DRY_RUN  = [bool]$DryRun
    } | ConvertTo-Json -Compress
} else {
    Write-Output "ADR_NUM: $paddedNumber"
    Write-Output "ADR_FILE: $adrPath"
}
