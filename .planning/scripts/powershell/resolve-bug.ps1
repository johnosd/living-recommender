#!/usr/bin/env pwsh
# Resolve/cria sdd/bugs/<slug>/ e reporta qual fase (assess/fix/test)
# roda a seguir, baseado em quais relatórios já existem. Usado só pelo
# sdd-bugfix. Diferente de sdd/specs/ e sdd/adr/, bugs não usam numeração sequencial
# — o slug é o único identificador, igual ao design do extension "bug" do
# spec-kit que inspirou este skill.
#
# Usage:
#   ./resolve-bug.ps1 [-Slug <slug>] [-Title "<descrição livre>"] [-Json]

[CmdletBinding()]
param(
    [string]$Slug,
    [string]$Title,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"

$repoRoot = Get-RepoRoot
$bugsDir = Join-Path (Get-SddRoot -RepoRoot $repoRoot) 'bugs'

if (-not $Slug -and -not $Title) {
    [Console]::Error.WriteLine("ERROR: informe -Slug ou -Title")
    exit 1
}

$resolvedSlug = if ($Slug) {
    ($Slug.ToLowerInvariant() -replace '[^a-z0-9-]', '-') -replace '-+', '-' -replace '^-|-$', ''
} else {
    New-SlugFromText -Text $Title -MaxWords 6 -MaxLength 60
}

$bugDir = Join-Path $bugsDir $resolvedSlug
$isNew = -not (Test-Path -LiteralPath $bugDir -PathType Container)

if ($isNew) {
    New-Item -ItemType Directory -Path $bugDir -Force | Out-Null
}

$assessmentPath = Join-Path $bugDir 'assessment.md'
$fixPath = Join-Path $bugDir 'fix.md'
$testPath = Join-Path $bugDir 'test.md'

$hasAssessment = Test-Path -LiteralPath $assessmentPath -PathType Leaf
$hasFix = Test-Path -LiteralPath $fixPath -PathType Leaf
$hasTest = Test-Path -LiteralPath $testPath -PathType Leaf

$nextPhase = if (-not $hasAssessment) { 'assess' }
    elseif (-not $hasFix) { 'fix' }
    elseif (-not $hasTest) { 'test' }
    else { 'complete' }

if ($Json) {
    [PSCustomObject]@{
        SLUG           = $resolvedSlug
        BUG_DIR        = $bugDir
        IS_NEW         = $isNew
        HAS_ASSESSMENT = $hasAssessment
        HAS_FIX        = $hasFix
        HAS_TEST       = $hasTest
        NEXT_PHASE     = $nextPhase
        ASSESSMENT     = $assessmentPath
        FIX            = $fixPath
        TEST           = $testPath
    } | ConvertTo-Json -Compress
} else {
    Write-Output "SLUG: $resolvedSlug"
    Write-Output "BUG_DIR: $bugDir"
    Write-Output "NEXT_PHASE: $nextPhase"
    Write-Output "HAS_ASSESSMENT: $hasAssessment / HAS_FIX: $hasFix / HAS_TEST: $hasTest"
}
