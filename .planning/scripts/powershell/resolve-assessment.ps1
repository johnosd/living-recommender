#!/usr/bin/env pwsh
# Resolve/cria sdd/assessments/<slug>/ e reporta qual fase (define/decide/complete)
# roda a seguir. Usado só pelo sdd-assess. Explora é opcional e não entra na
# resolução de NEXT_PHASE — Define é o estágio mínimo viável, roda direto
# sobre a entrada do usuário se Explora não tiver sido feita.
#
# Usage:
#   ./resolve-assessment.ps1 [-Slug <slug>] [-Title "<descrição livre>"] [-Json]

[CmdletBinding()]
param(
    [string]$Slug,
    [string]$Title,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"

$repoRoot = Get-RepoRoot
$assessDir = Join-Path (Get-SddRoot -RepoRoot $repoRoot) 'assessments'

if (-not $Slug -and -not $Title) {
    [Console]::Error.WriteLine("ERROR: informe -Slug ou -Title")
    exit 1
}

$resolvedSlug = if ($Slug) {
    ($Slug.ToLowerInvariant() -replace '[^a-z0-9-]', '-') -replace '-+', '-' -replace '^-|-$', ''
} else {
    New-SlugFromText -Text $Title -MaxWords 6 -MaxLength 60
}

$itemDir = Join-Path $assessDir $resolvedSlug
$isNew = -not (Test-Path -LiteralPath $itemDir -PathType Container)

if ($isNew) {
    New-Item -ItemType Directory -Path $itemDir -Force | Out-Null
}

$exploraPath = Join-Path $itemDir 'explora.md'
$problemPath = Join-Path $itemDir 'problem.md'
$decisionPath = Join-Path $itemDir 'decision.md'

$hasExplora = Test-Path -LiteralPath $exploraPath -PathType Leaf
$hasProblem = Test-Path -LiteralPath $problemPath -PathType Leaf
$hasDecision = Test-Path -LiteralPath $decisionPath -PathType Leaf

$nextPhase = if (-not $hasProblem) { 'define' }
    elseif (-not $hasDecision) { 'decide' }
    else { 'complete' }

if ($Json) {
    [PSCustomObject]@{
        SLUG         = $resolvedSlug
        ASSESS_DIR   = $itemDir
        IS_NEW       = $isNew
        HAS_EXPLORA  = $hasExplora
        HAS_PROBLEM  = $hasProblem
        HAS_DECISION = $hasDecision
        NEXT_PHASE   = $nextPhase
        EXPLORA      = $exploraPath
        PROBLEM      = $problemPath
        DECISION     = $decisionPath
    } | ConvertTo-Json -Compress
} else {
    Write-Output "SLUG: $resolvedSlug"
    Write-Output "ASSESS_DIR: $itemDir"
    Write-Output "NEXT_PHASE: $nextPhase"
    Write-Output "HAS_EXPLORA: $hasExplora / HAS_PROBLEM: $hasProblem / HAS_DECISION: $hasDecision"
}
