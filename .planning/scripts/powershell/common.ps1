#!/usr/bin/env pwsh
# Funções compartilhadas pelos scripts do sistema sdd-*.
#
# Deliberadamente mais simples que o common.ps1 do speckit: sem feature.json,
# sem variável de ambiente de "feature atual", sem stack de
# override/preset/extension para templates. Cada função exige seus parâmetros
# explicitamente.

# Acha a raiz do repositório subindo a árvore de diretórios até achar uma
# pasta .planning/ (o marcador deste sistema, análogo ao .specify/ do speckit).
function Get-RepoRoot {
    param([string]$StartDir = (Get-Location).Path)

    $resolved = Resolve-Path -LiteralPath $StartDir -ErrorAction SilentlyContinue
    $current = if ($resolved) { $resolved.Path } else { $null }
    if (-not $current) {
        [Console]::Error.WriteLine("ERROR: diretório inicial inválido: $StartDir")
        exit 1
    }

    while ($true) {
        if (Test-Path -LiteralPath (Join-Path $current ".planning") -PathType Container) {
            return $current
        }
        $parent = Split-Path $current -Parent
        if ([string]::IsNullOrEmpty($parent) -or $parent -eq $current) {
            [Console]::Error.WriteLine("ERROR: nenhuma pasta .planning/ encontrada subindo a partir de $StartDir")
            exit 1
        }
        $current = $parent
    }
}

# Raiz de todo o produto de trabalho do sistema sdd-* (sdd/specs, sdd/bugs, sdd/adr,
# assessments), agrupado sob uma única pasta visível no root do repo — em
# oposição a .planning/, que é só o maquinário compartilhado (scripts,
# templates, constitution, backlog).
function Get-SddRoot {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)
    return Join-Path $RepoRoot 'sdd'
}

# Resolve o diretório de uma feature a partir de -FeatureDir (caminho
# explícito, absoluto ou relativo à raiz) ou -Slug (nome completo ou parcial,
# resolvido por prefixo contra sdd/specs/NNN-*). Nunca lê estado global oculto.
function Resolve-FeatureDir {
    param(
        [string]$RepoRoot,
        [string]$FeatureDir,
        [string]$Slug
    )

    if ($FeatureDir) {
        $candidate = if ([System.IO.Path]::IsPathRooted($FeatureDir)) { $FeatureDir } else { Join-Path $RepoRoot $FeatureDir }
        $resolved = Resolve-Path -LiteralPath $candidate -ErrorAction SilentlyContinue
        if (-not $resolved) {
            [Console]::Error.WriteLine("ERROR: -FeatureDir não existe: $candidate")
            exit 1
        }
        return $resolved.Path
    }

    if ($Slug) {
        $specsDir = Join-Path (Get-SddRoot -RepoRoot $RepoRoot) 'specs'
        $exact = Join-Path $specsDir $Slug
        if (Test-Path -LiteralPath $exact -PathType Container) {
            return (Resolve-Path -LiteralPath $exact).Path
        }
        # tenta resolver por prefixo (ex: "exportar-legendas" -> "002-exportar-legendas")
        $matches = @(Get-ChildItem -Path $specsDir -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "*$Slug*" })
        if ($matches.Count -eq 1) {
            return $matches[0].FullName
        } elseif ($matches.Count -gt 1) {
            [Console]::Error.WriteLine("ERROR: -Slug '$Slug' é ambíguo, casa com: $($matches.Name -join ', ')")
            exit 1
        } else {
            [Console]::Error.WriteLine("ERROR: nenhuma feature encontrada pra -Slug '$Slug' em $specsDir")
            exit 1
        }
    }

    [Console]::Error.WriteLine("ERROR: informe -FeatureDir ou -Slug")
    exit 1
}

# Monta o objeto de paths de uma feature a partir do diretório já resolvido.
function Get-FeaturePaths {
    param([Parameter(Mandatory = $true)][string]$FeatureDir)

    [PSCustomObject]@{
        FEATURE_DIR   = $FeatureDir
        FEATURE_SPEC  = Join-Path $FeatureDir 'spec.md'
        IMPL_PLAN     = Join-Path $FeatureDir 'plan.md'
        TASKS         = Join-Path $FeatureDir 'tasks.md'
        RESEARCH      = Join-Path $FeatureDir 'research.md'
        DATA_MODEL    = Join-Path $FeatureDir 'data-model.md'
        QUICKSTART    = Join-Path $FeatureDir 'quickstart.md'
        CONTRACTS_DIR = Join-Path $FeatureDir 'contracts'
        HISTORY       = Join-Path $FeatureDir 'history.md'
    }
}

# Varre sdd/specs/NNN-* e retorna o maior número de sequência já usado (0 se nenhum).
function Get-HighestFeatureNumber {
    param([Parameter(Mandatory = $true)][string]$SpecsDir)

    if (-not (Test-Path -LiteralPath $SpecsDir -PathType Container)) { return 0 }

    $max = 0
    Get-ChildItem -Path $SpecsDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.Name -match '^(\d{3,})-') {
            $n = [int]$matches[1]
            if ($n -gt $max) { $max = $n }
        }
    }
    return $max
}

# Varre sdd/adr/ e retorna o maior número ADR-NNN já usado (0 se nenhum).
function Get-HighestAdrNumber {
    param([Parameter(Mandatory = $true)][string]$AdrDir)

    if (-not (Test-Path -LiteralPath $AdrDir -PathType Container)) { return 0 }

    $max = 0
    Get-ChildItem -Path $AdrDir -File -Filter '*.md' -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.Name -match '^ADR-(\d{3,})-') {
            $n = [int]$matches[1]
            if ($n -gt $max) { $max = $n }
        }
    }
    return $max
}

# Gera um slug kebab-case curto a partir de uma descrição livre.
function New-SlugFromText {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [int]$MaxWords = 4,
        [int]$MaxLength = 50
    )

    $stopWords = @('a', 'o', 'de', 'da', 'do', 'para', 'com', 'em', 'um', 'uma', 'e', 'the', 'a', 'to', 'for', 'of', 'and')
    $normalized = $Text.ToLowerInvariant() -replace '[^a-z0-9\s-]', ''
    $words = $normalized -split '\s+' | Where-Object { $_ -and ($stopWords -notcontains $_) }
    $selected = $words | Select-Object -First $MaxWords
    $slug = ($selected -join '-')
    if ($slug.Length -gt $MaxLength) { $slug = $slug.Substring(0, $MaxLength).TrimEnd('-') }
    if (-not $slug) { $slug = 'feature' }
    return $slug
}

# Lê o conteúdo literal de um template em .planning/templates/<nome>-template.md.
# Sem stack de override/preset/extension — leitura direta.
function Get-TemplateContent {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$TemplateName
    )

    $path = Join-Path $RepoRoot ".planning/templates/$TemplateName-template.md"
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        [Console]::Error.WriteLine("ERROR: template não encontrado: $path")
        exit 1
    }
    return [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
}

function Test-FileExists {
    param([string]$Path, [string]$Description)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        Write-Output "  [OK] $Description"
        return $true
    } else {
        Write-Output "  [FAIL] $Description"
        return $false
    }
}

function Test-DirHasFiles {
    param([string]$Path, [string]$Description)
    if ((Test-Path -LiteralPath $Path -PathType Container) -and (Get-ChildItem -Path $Path -ErrorAction SilentlyContinue | Select-Object -First 1)) {
        Write-Output "  [OK] $Description"
        return $true
    } else {
        Write-Output "  [FAIL] $Description"
        return $false
    }
}
