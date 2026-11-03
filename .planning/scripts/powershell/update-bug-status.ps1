#!/usr/bin/env pwsh
# Atualiza o painel de status "## Bugs" em .planning/backlog.md pra um bug do
# sdd-bugfix — espelha update-feature-status.ps1, mas pra bugs. Recalcula
# fase atual/veredito/próximo passo direto do que já existe em
# sdd/bugs/<slug>/ (mesma lógica de resolve-bug.ps1) e do conteúdo desses
# arquivos, então nunca fica dessincronizado do disco.
#
# Sem isso, um bug em andamento não deixa rastro em lugar nenhum fora da
# própria pasta — diferente de features, que aparecem em backlog.md →
# ## Features. Rodar depois de qualquer fase (Assess/Fix/Test) garante que
# dá pra ver de relance, sem abrir a pasta do bug, onde cada um parou.
#
# Usage:
#   ./update-bug-status.ps1 -Slug <slug> [-Json]

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Slug,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"

$repoRoot = Get-RepoRoot
$bugDir = Join-Path (Get-SddRoot -RepoRoot $repoRoot) "bugs/$Slug"
if (-not (Test-Path -LiteralPath $bugDir -PathType Container)) {
    [Console]::Error.WriteLine("ERROR: sdd/bugs/$Slug não existe")
    exit 1
}

$assessmentPath = Join-Path $bugDir 'assessment.md'
$fixPath = Join-Path $bugDir 'fix.md'
$testPath = Join-Path $bugDir 'test.md'

$hasAssessment = Test-Path -LiteralPath $assessmentPath -PathType Leaf
$hasFix = Test-Path -LiteralPath $fixPath -PathType Leaf
$hasTest = Test-Path -LiteralPath $testPath -PathType Leaf

$backlogPath = Join-Path $repoRoot '.planning/backlog.md'
$utf8 = [System.Text.Encoding]::UTF8
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

# Autocria um backlog.md mínimo se o repositório ainda não tiver um — mesmo
# esqueleto que update-feature-status.ps1 criaria, incluindo ## Bugs, pra
# ficar completo não importa qual dos dois scripts rodar primeiro.
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
    [System.IO.File]::WriteAllText($backlogPath, $skeleton, $utf8NoBom)
}

function Get-MetaField {
    param([string]$Content, [string]$Field)
    $m = [regex]::Match($Content, "(?m)^-\s*\*\*$Field\*\*:\s*(.+)$")
    if ($m.Success) { return $m.Groups[1].Value.Trim() }
    return $null
}

function Get-H1Title {
    param([string]$Content, [string]$Prefix)
    $m = [regex]::Match($Content, "(?m)^#\s*$Prefix\s*:\s*(.+)$")
    if ($m.Success) { return $m.Groups[1].Value.Trim() }
    return $null
}

# Recalcula fase/status/próximo-passo do zero a cada chamada — nunca confia
# em estado anterior da tabela, só no que está de fato em disco agora.
$titulo = $Slug
$faseAtual = 'Novo'
$statusValue = 'pendente'
$proximoPasso = 'Rodar fase Assess'

if ($hasAssessment) {
    $assessmentContent = [System.IO.File]::ReadAllText($assessmentPath, $utf8)
    $t = Get-H1Title -Content $assessmentContent -Prefix 'Bug Assessment'
    if ($t) { $titulo = $t }
    $veredito = Get-MetaField -Content $assessmentContent -Field 'Veredito'
    $severidade = Get-MetaField -Content $assessmentContent -Field 'Severidade'
    $faseAtual = 'Assess'
    $statusValue = if ($veredito -and $severidade) { "$veredito ($severidade)" } elseif ($veredito) { $veredito } else { 'sem veredito' }
    $proximoPasso = if ($veredito -eq 'invalid') { 'Nenhum — descartado (invalid)' } else { 'Rodar fase Fix' }
}

if ($hasFix) {
    $fixContent = [System.IO.File]::ReadAllText($fixPath, $utf8)
    $fixStatus = Get-MetaField -Content $fixContent -Field 'Status'
    $faseAtual = 'Fix'
    $statusValue = if ($fixStatus) { $fixStatus } else { 'sem status' }
    $proximoPasso = if ($fixStatus -eq 'not-applied') { 'Revisar — fix não foi aplicado' } else { 'Rodar fase Test' }
}

if ($hasTest) {
    $testContent = [System.IO.File]::ReadAllText($testPath, $utf8)
    $result = Get-MetaField -Content $testContent -Field 'Result'
    $faseAtual = 'Test'
    $statusValue = if ($result) { $result } else { 'sem resultado' }
    $proximoPasso = switch -Regex ($result) {
        '^verified' { 'Concluído' }
        '^partial' { 'Concluído (com ressalva) ou reabrir Assess' }
        '^failed' { 'Reabrir fase Assess com evidência nova' }
        default { 'Revisar test.md' }
    }
}

$hoje = Get-Date -Format 'yyyy-MM-dd'

# --- Atualiza a tabela ## Bugs em backlog.md ---
$lines = [System.Collections.Generic.List[string]]([System.IO.File]::ReadAllLines($backlogPath, $utf8))

$sectionIdx = -1
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i].TrimEnd() -eq '## Bugs') { $sectionIdx = $i; break }
}
if ($sectionIdx -lt 0) {
    [Console]::Error.WriteLine("ERROR: seção '## Bugs' não encontrada em backlog.md")
    exit 1
}

$headerIdx = -1
for ($i = $sectionIdx; $i -lt $lines.Count; $i++) {
    if ($lines[$i].TrimStart().StartsWith('| Slug')) { $headerIdx = $i; break }
}
if ($headerIdx -lt 0 -or $headerIdx + 1 -ge $lines.Count) {
    [Console]::Error.WriteLine("ERROR: cabeçalho da tabela de Bugs não encontrado/malformado em backlog.md")
    exit 1
}
$separatorIdx = $headerIdx + 1

$lastRowIdx = $separatorIdx
$foundRowIdx = -1
$i = $separatorIdx + 1
while ($i -lt $lines.Count -and $lines[$i].TrimStart().StartsWith('|')) {
    if ($lines[$i] -match [regex]::Escape("| $Slug ")) { $foundRowIdx = $i }
    $lastRowIdx = $i
    $i++
}

$newRow = "| $Slug | $titulo | $faseAtual | $statusValue | $proximoPasso | $hoje |"

if ($foundRowIdx -ge 0) {
    $lines[$foundRowIdx] = $newRow
} else {
    $lines.Insert($lastRowIdx + 1, $newRow)
}

[System.IO.File]::WriteAllText($backlogPath, ($lines -join "`n") + "`n", $utf8NoBom)

if ($Json) {
    [PSCustomObject]@{
        SLUG          = $Slug
        TITULO        = $titulo
        FASE          = $faseAtual
        STATUS        = $statusValue
        PROXIMO_PASSO = $proximoPasso
        DATA          = $hoje
    } | ConvertTo-Json -Compress
} else {
    Write-Output "OK: $Slug -> Fase=$faseAtual Status=$statusValue Próximo=$proximoPasso ($hoje)"
}
