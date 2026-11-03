#!/usr/bin/env pwsh
# Cria a pasta sdd/specs/<NNN-slug>/ e semeia spec.md a partir do template.
# Usado só pelo sdd-specify. Não pré-copia plan.md/tasks.md (isso é
# responsabilidade do próprio sdd-plan, que lê os templates diretamente).
#
# Usage:
#   ./new-feature.ps1 "Descrição da feature" [-ShortName slug-curto] [-Json] [-DryRun]

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$FeatureDescription,
    [string]$ShortName,
    [switch]$Json,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"

$repoRoot = Get-RepoRoot
$specsDir = Join-Path (Get-SddRoot -RepoRoot $repoRoot) 'specs'

$slug = if ($ShortName) {
    New-SlugFromText -Text $ShortName
} else {
    New-SlugFromText -Text $FeatureDescription
}

$nextNumber = (Get-HighestFeatureNumber -SpecsDir $specsDir) + 1
$paddedNumber = '{0:D3}' -f $nextNumber
$dirName = "$paddedNumber-$slug"
$featureDir = Join-Path $specsDir $dirName

if (Test-Path -LiteralPath $featureDir) {
    [Console]::Error.WriteLine("ERROR: $featureDir já existe")
    exit 1
}

$specPath = Join-Path $featureDir 'spec.md'

if (-not $DryRun) {
    New-Item -ItemType Directory -Path $featureDir -Force | Out-Null
    $templateContent = Get-TemplateContent -RepoRoot $repoRoot -TemplateName 'spec'
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($specPath, $templateContent, $utf8NoBom)
}

if ($Json) {
    [PSCustomObject]@{
        FEATURE_DIR  = $featureDir
        FEATURE_NUM  = $paddedNumber
        SLUG         = $dirName
        SPEC_FILE    = $specPath
        DRY_RUN      = [bool]$DryRun
    } | ConvertTo-Json -Compress
} else {
    Write-Output "FEATURE_DIR: $featureDir"
    Write-Output "FEATURE_NUM: $paddedNumber"
    Write-Output "SLUG: $dirName"
    Write-Output "SPEC_FILE: $specPath"
}
