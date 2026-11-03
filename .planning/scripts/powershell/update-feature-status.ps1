#!/usr/bin/env pwsh
# Atualiza o painel de status em .planning/backlog.md pra uma feature, e,
# quando -Status é passado, também a linha **Status**: em spec.md (regex,
# só essa linha, sem tocar no resto do arquivo).
#
# Sem -Status: só recalcula Progresso a partir dos checkboxes de tasks.md
# (uso normal em cada checkpoint do sdd-execute).
#
# Usage:
#   ./update-feature-status.ps1 -Slug <NNN-slug> [-Status <valor>] [-Json]

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Slug,
    [string]$Status,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"

$repoRoot = Get-RepoRoot
$featureDir = Resolve-FeatureDir -RepoRoot $repoRoot -Slug $Slug
$dirName = Split-Path -Leaf $featureDir
$paths = Get-FeaturePaths -FeatureDir $featureDir
$backlogPath = Join-Path $repoRoot '.planning/backlog.md'

# Autocria um backlog.md mínimo se o repositório ainda não tiver um — puramente
# mecânico (esqueleto de seções), sem entrevista. Diferente da constitution
# (que exige julgamento e por isso é responsabilidade do sdd-plan), aqui não
# há decisão de projeto envolvida.
if (-not (Test-Path -LiteralPath $backlogPath -PathType Leaf)) {
    $skeleton = @"
# Backlog

Painel único de ideias futuras e status de features/bugs geridas pelo
sistema sdd-*. Mantido automaticamente por update-feature-status.ps1 e
update-bug-status.ps1.

## Ideias Futuras

## Features

| Slug | Título | Status | Progresso | Última Atualização |
| --- | --- | --- | --- | --- |

## Bugs

| Slug | Título | Fase Atual | Veredito/Status | Próximo Passo | Última Atualização |
| --- | --- | --- | --- | --- | --- |
"@
    $planningDir = Join-Path $repoRoot '.planning'
    if (-not (Test-Path -LiteralPath $planningDir -PathType Container)) {
        New-Item -ItemType Directory -Path $planningDir -Force | Out-Null
    }
    $utf8NoBomInit = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($backlogPath, $skeleton, $utf8NoBomInit)
}

# Progresso: conta checkboxes em tasks.md, se existir.
$progresso = 'N/A'
if (Test-Path -LiteralPath $paths.TASKS -PathType Leaf) {
    $tasksContent = [System.IO.File]::ReadAllText($paths.TASKS, [System.Text.Encoding]::UTF8)
    $total = ([regex]::Matches($tasksContent, '- \[[ xX]\]')).Count
    $checked = ([regex]::Matches($tasksContent, '- \[[xX]\]')).Count
    $progresso = "$checked/$total tasks"
}

# Título: tenta extrair de spec.md; senão usa o slug.
$titulo = $dirName
if (Test-Path -LiteralPath $paths.FEATURE_SPEC -PathType Leaf) {
    $specContent = [System.IO.File]::ReadAllText($paths.FEATURE_SPEC, [System.Text.Encoding]::UTF8)
    $titleMatch = [regex]::Match($specContent, '^# Feature Specification:\s*(.+)$', 'Multiline')
    if ($titleMatch.Success) { $titulo = $titleMatch.Groups[1].Value.Trim() }
}

$hoje = Get-Date -Format 'yyyy-MM-dd'

# --- Atualiza a tabela ## Features em backlog.md ---
$lines = [System.Collections.Generic.List[string]]([System.IO.File]::ReadAllLines($backlogPath, [System.Text.Encoding]::UTF8))

$sectionIdx = -1
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i].TrimEnd() -eq '## Features') { $sectionIdx = $i; break }
}
if ($sectionIdx -lt 0) {
    [Console]::Error.WriteLine("ERROR: seção '## Features' não encontrada em backlog.md")
    exit 1
}

# Acha a linha do cabeçalho da tabela (começa com "| Slug") e a linha separadora logo depois.
$headerIdx = -1
for ($i = $sectionIdx; $i -lt $lines.Count; $i++) {
    if ($lines[$i].TrimStart().StartsWith('| Slug')) { $headerIdx = $i; break }
}
if ($headerIdx -lt 0 -or $headerIdx + 1 -ge $lines.Count) {
    [Console]::Error.WriteLine("ERROR: cabeçalho da tabela de Features não encontrado/malformado em backlog.md")
    exit 1
}
$separatorIdx = $headerIdx + 1

# Acha linhas de dados existentes (começam com "|") logo após o separador.
$lastRowIdx = $separatorIdx
$foundRowIdx = -1
$i = $separatorIdx + 1
while ($i -lt $lines.Count -and $lines[$i].TrimStart().StartsWith('|')) {
    if ($lines[$i] -match [regex]::Escape("| $dirName ")) { $foundRowIdx = $i }
    $lastRowIdx = $i
    $i++
}

$statusFinal = if ($Status) { $Status } else {
    if ($foundRowIdx -ge 0) {
        $cols = $lines[$foundRowIdx].Trim('|').Split('|') | ForEach-Object { $_.Trim() }
        $cols[2]
    } else {
        'Especificada'
    }
}

$newRow = "| $dirName | $titulo | $statusFinal | $progresso | $hoje |"

if ($foundRowIdx -ge 0) {
    $lines[$foundRowIdx] = $newRow
} else {
    $lines.Insert($lastRowIdx + 1, $newRow)
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($backlogPath, ($lines -join "`n") + "`n", $utf8NoBom)

# --- Atualiza spec.md **Status**: quando -Status foi passado ---
if ($Status -and (Test-Path -LiteralPath $paths.FEATURE_SPEC -PathType Leaf)) {
    $specContent = [System.IO.File]::ReadAllText($paths.FEATURE_SPEC, [System.Text.Encoding]::UTF8)
    if ($specContent -match '(?m)^\*\*Status\*\*:.*$') {
        $specContent = [regex]::Replace($specContent, '(?m)^\*\*Status\*\*:.*$', "**Status**: $Status")
        [System.IO.File]::WriteAllText($paths.FEATURE_SPEC, $specContent, $utf8NoBom)
    }
}

if ($Json) {
    [PSCustomObject]@{
        SLUG      = $dirName
        STATUS    = $statusFinal
        PROGRESSO = $progresso
        DATA      = $hoje
    } | ConvertTo-Json -Compress
} else {
    Write-Output "OK: $dirName -> Status=$statusFinal Progresso=$progresso ($hoje)"
}
