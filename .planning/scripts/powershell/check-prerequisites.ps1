#!/usr/bin/env pwsh
# Gate de pré-requisitos por estágio do fluxo sdd-*. Chamado pelos 4 skills
# como primeira ação substantiva.
#
# Usage:
#   ./check-prerequisites.ps1 -Stage specify|plan|execute|converge [-FeatureDir <path>] [-Slug <slug>] [-Json] [-PathsOnly]
#
# Contrato de handoff (ver plano):
#   specify  -> nada obrigatório; avisa (não bloqueia) se a constitution não existir
#   plan     -> exige spec.md e .planning/memory/constitution.md
#   execute  -> exige spec.md, plan.md e tasks.md
#   converge -> exige spec.md, plan.md e tasks.md; avisa (não bloqueia) se tasks.md tiver 0 itens marcados

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('specify', 'plan', 'execute', 'converge')][string]$Stage,
    [string]$FeatureDir,
    [string]$Slug,
    [switch]$Json,
    [switch]$PathsOnly
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"

$repoRoot = Get-RepoRoot
$constitutionPath = Join-Path $repoRoot '.planning/memory/constitution.md'

# O estágio "specify" ainda não tem uma feature — só checa a constitution.
if ($Stage -eq 'specify') {
    $constitutionExists = Test-Path -LiteralPath $constitutionPath -PathType Leaf
    if ($Json) {
        [PSCustomObject]@{
            STAGE                = $Stage
            PASS                 = $true
            CONSTITUTION_EXISTS  = $constitutionExists
        } | ConvertTo-Json -Compress
    } else {
        if (-not $constitutionExists) {
            Write-Output "AVISO: .planning/memory/constitution.md não existe ainda. sdd-plan vai bloquear até ela existir."
        } else {
            Write-Output "OK: constitution encontrada."
        }
    }
    exit 0
}

$resolvedDir = Resolve-FeatureDir -RepoRoot $repoRoot -FeatureDir $FeatureDir -Slug $Slug
$paths = Get-FeaturePaths -FeatureDir $resolvedDir

if ($PathsOnly) {
    if ($Json) {
        $paths | ConvertTo-Json -Compress
    } else {
        $paths.PSObject.Properties | ForEach-Object { Write-Output "$($_.Name): $($_.Value)" }
    }
    exit 0
}

function Fail-Missing {
    param([string]$FileDescription, [string]$NextSkill)
    [Console]::Error.WriteLine("ERROR: $FileDescription não encontrado em $resolvedDir")
    [Console]::Error.WriteLine("Rode $NextSkill primeiro.")
    exit 1
}

switch ($Stage) {
    'plan' {
        if (-not (Test-Path -LiteralPath $paths.FEATURE_SPEC -PathType Leaf)) {
            Fail-Missing -FileDescription 'spec.md' -NextSkill 'sdd-specify'
        }
        if (-not (Test-Path -LiteralPath $constitutionPath -PathType Leaf)) {
            [Console]::Error.WriteLine("ERROR: .planning/memory/constitution.md não existe. Crie a constitution antes de planejar.")
            exit 1
        }
    }
    'execute' {
        if (-not (Test-Path -LiteralPath $paths.FEATURE_SPEC -PathType Leaf)) {
            Fail-Missing -FileDescription 'spec.md' -NextSkill 'sdd-specify'
        }
        if (-not (Test-Path -LiteralPath $paths.IMPL_PLAN -PathType Leaf)) {
            Fail-Missing -FileDescription 'plan.md' -NextSkill 'sdd-plan'
        }
        if (-not (Test-Path -LiteralPath $paths.TASKS -PathType Leaf)) {
            Fail-Missing -FileDescription 'tasks.md' -NextSkill 'sdd-plan'
        }
    }
    'converge' {
        if (-not (Test-Path -LiteralPath $paths.FEATURE_SPEC -PathType Leaf)) {
            Fail-Missing -FileDescription 'spec.md' -NextSkill 'sdd-specify'
        }
        if (-not (Test-Path -LiteralPath $paths.IMPL_PLAN -PathType Leaf)) {
            Fail-Missing -FileDescription 'plan.md' -NextSkill 'sdd-plan'
        }
        if (-not (Test-Path -LiteralPath $paths.TASKS -PathType Leaf)) {
            Fail-Missing -FileDescription 'tasks.md' -NextSkill 'sdd-plan'
        }
        $tasksContent = [System.IO.File]::ReadAllText($paths.TASKS, [System.Text.Encoding]::UTF8)
        $checkedCount = ([regex]::Matches($tasksContent, '- \[[xX]\]')).Count
        if ($checkedCount -eq 0) {
            Write-Output "AVISO: tasks.md não tem nenhum item marcado ainda. sdd-converge pode não achar nada implementado."
        }
    }
}

$docs = @()
if (Test-Path -LiteralPath $paths.RESEARCH -PathType Leaf) { $docs += 'research.md' }
if (Test-Path -LiteralPath $paths.DATA_MODEL -PathType Leaf) { $docs += 'data-model.md' }
if ((Test-Path -LiteralPath $paths.CONTRACTS_DIR -PathType Container) -and (Get-ChildItem -Path $paths.CONTRACTS_DIR -ErrorAction SilentlyContinue | Select-Object -First 1)) { $docs += 'contracts/' }
if (Test-Path -LiteralPath $paths.QUICKSTART -PathType Leaf) { $docs += 'quickstart.md' }
if (Test-Path -LiteralPath $paths.HISTORY -PathType Leaf) { $docs += 'history.md' }
if (Test-Path -LiteralPath (Join-Path $paths.FEATURE_DIR 'contract-tests.lock') -PathType Leaf) { $docs += 'contract-tests.lock' }

if ($Json) {
    [PSCustomObject]@{
        STAGE          = $Stage
        PASS           = $true
        FEATURE_DIR    = $paths.FEATURE_DIR
        AVAILABLE_DOCS = $docs
    } | ConvertTo-Json -Compress
} else {
    Write-Output "PASS: pré-requisitos do estágio '$Stage' atendidos."
    Write-Output "FEATURE_DIR: $($paths.FEATURE_DIR)"
    Write-Output "AVAILABLE_DOCS:"
    foreach ($d in $docs) { Write-Output "  [OK] $d" }
}
