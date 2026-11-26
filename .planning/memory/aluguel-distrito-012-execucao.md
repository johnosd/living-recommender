# Aluguel por distrito e região (012) — achados da execução (2026-11-26)

Feature: `.sdd/specs/012-aluguel-distrito-regiao/`. Complementa `aluguel-distrito-012-planejamento.md`.

## Resultado no lake real (snapshot 2026-11, catálogo `6917af159e07`)

- 10 tabelas Gold; 150 linhas distritais (25 áreas) e 42 regionais (7).
- Mediana `ALL`: municípios 42 próprios, 254 do distrito, 12 da região; freguesias 135, 284 do município, 2 777 do
  distrito, 63 da região.
- Comparado com a Gold anterior (catálogo `160da2ce8218`): nenhum valor existente mudou ou sumiu; só ausências de
  aluguel ganharam valor (1 915 linhas municipais e 20 583 de freguesia). A normalização de todos os critérios e as
  colunas antigas da tabela municipal de aluguel ficaram idênticas.

## Achado para o ranker (Fase 4)

As amostras próprias de município estão só nos distritos do Porto (15), Faro (14) e Lisboa (13), os únicos
extraídos por município. Como a normalização usa só próprios (FR-011), o P5–P95 representa os mercados caros: dos
valores herdados de `custo_aluguel_mediana`, ficam abaixo do P5 109 de 266 (`ALL`), 201 de 282 (`T1`) e 201 de 277
(`T3`). Se o ranker só limitar o score a 0–1, muitos municípios do interior empatam no melhor custo.

## Armadilhas confirmadas

- Normalizar por `origin` no município quebra testes que montam um perfil "municipal" a partir do de freguesia.
- Heredoc do Bash com muitas aspas simples falha na ferramenta de shell; grave o script em arquivo.
