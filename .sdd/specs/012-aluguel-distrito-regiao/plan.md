# Implementation Plan: Aluguel por distrito e por região na Gold, com herança marcada

**Slug**: `012-aluguel-distrito-regiao` | **Date**: 2026-11-26 | **Spec**: `.sdd/specs/012-aluguel-distrito-regiao/spec.md`

**Nota**: Este template é preenchido pelo skill `sdd-plan`; a definição do skill
descreve o fluxo de execução completo.

## Summary

Acrescentar à camada Gold da spec 011:

- duas tabelas novas de aluguel do Idealista, por distrito (ou ilha) e por região da fonte (P1);
- herança marcada no perfil municipal: sem amostra própria, o aluguel vem do distrito e, se faltar, da região (P1);
- a mesma cadeia na freguesia e a contagem de próprios e herdados por nível no mart de qualidade (P2).

Abordagem: um módulo novo `pipelines/gold/areas.py` (hierarquia, estatísticas por área e herança) como
pós-processamento do perfil municipal já calculado, mais ajustes pequenos em `parish.py`, `quality.py`,
`criteria.py` e `prepare.py`. O dbt continua só tipando e testando.

## Technical Context

**Language/Version**: Python 3.12; SQL DuckDB 2.0 nos modelos dbt.

**Primary Dependencies**: pandas, numpy, pyarrow, PyYAML, dbt-core, dbt-duckdb, duckdb. Nenhuma dependência nova
no pipeline. O grupo opcional `notebook` do `pyproject.toml` (jupyterlab, ipykernel, matplotlib) já está no disco,
ainda sem commit, e é só para o notebook.

**Storage**: parquet no lake local. Lê as mesmas 8 entradas da 011 (mais as colunas `district_or_island` de
`dim_municipality` e `source_subregion` de `idealista_listings`) e escreve 10 tabelas em `.data/lake/gold/`.

**Testing**: pytest (`tests/contracts`, `tests/unit`, `tests/integration`) e testes dbt (`schema.yml` e
`analytics/dbt/tests/gold_*.sql`). O CI já roda `ci_seed` e `build_gold`.

**Target Platform**: CLI local Windows/Linux (`pipelines.cli.build_gold --local`).

**Performance Goals**: N/A. São cerca de 18 mil anúncios e 192 linhas novas.

**Constraints**: constitution III (nada imputado em silêncio, n ≥ 10, herdado sinalizado), IV e VI (só
agregados); contratos travados da 011; seleção dbt por tag; promoção por caminho.

**Scale/Scope**: 25 distritos ou ilhas, 7 regiões, 308 municípios, 3 259 freguesias.

## Decisões Invariantes

- **D1. Mesma regra em todo nível:** snapshot vigente, IQR de Tukey 1,5 em cada território × tipologia com n ≥ 10,
  mediana e percentis só com n ≥ 10 elegíveis, €/m² com área de 10 a 1 000 m². A marca de outlier é **recalculada
  por área**; a da freguesia continua vindo do município (D6 da 011).
- **D2. O `dico` vence o nome:** anúncio com município entra no distrito dele; sem município, no distrito da fonte.
  Nenhum anúncio entra na mediana de um município ao qual não pertence.
- **D3. Região da fonte, derivada do snapshot** (reserva: região autónoma). Uma única região por distrito, senão o
  build falha. Não há mapa fixo distrito → região, e não é NUTS II.
- **D4. Nomes de ilha só pela seed** `analytics/dbt/seeds/idealista_island_aliases.csv`. Nome sem par falha.
- **D5. Cadeia por variante e por medida:** freguesia (própria) › município (próprio) › distrito › região.
- **D6. Herdado = cópia exata** do valor e da proveniência do nível de origem, com `origin = herdado`,
  `origin_level` e `value_status = observado`.
- **D7. Coluna nova `origin_level`** nos perfis municipal e de freguesia. `territorial_inheritance` continua só dos
  Censos, e `rent_coverage` continua só da amostra própria.
- **D8. Só próprio normaliza e conta como cobertura**, nos dois níveis territoriais.
- **D9. Herança é pós-processamento:** `rent_stats`, `rent_indicators` e as demais famílias não mudam de
  assinatura; `apply_rent_inheritance` roda uma vez no `prepare`, antes da freguesia, do catálogo e da qualidade.
- **D10. Só tabelas agregadas**, com fonte, licença, atribuição e mês do snapshot.

## Constitution Check

*GATE: deve passar antes da Fase 0. Reavaliado após o design da Fase 1.*

| Princípio | Pré-Design | Pós-Design | Notas |
| --- | --- | --- | --- |
| I. Nenhum segredo fora do cofre | ✅ | ✅ | Só parquet local; nenhuma chave. |
| II. Núcleo estático e sem chave | ✅ | ✅ | Só alimenta o futuro `published/vN`. |
| III. Dados honestos e rastreáveis | ✅ | ✅ | Herdado marcado com o nível; proveniência por linha; n ≥ 10 em todo nível. A junção de distrito usa o nome do CAOP (não há código de distrito na dimensão), com seed explícita para as ilhas e falha sem correspondência (D4). |
| IV. Coleta responsável e licenciada | ✅ | ✅ | Sem coleta; só agregados do Idealista. |
| V. Bruto imutável e publicação atômica | ✅ | ✅ | As 10 tabelas são promovidas pelo mesmo build isolado (D11 da 011). |
| VI. Privacidade por padrão | ✅ | ✅ | Nenhuma linha por anúncio; notebook versionado sem saídas. |
| VII. Custo como requisito | ✅ | ✅ | Nenhum recurso com custo. |
| Restrição: ranking por município, freguesia só drill-down | ✅ | ✅ | Não cria score nem ranking. |
| Quality gates 3 e 6 | ✅ | ✅ | Testes dbt nas tabelas novas; metodologia no `criteria_catalog`; dicionário regenerado. |

Sem violações: o Complexity Tracking fica vazio.

## Project Structure

### Documentation (this feature)

```text
.sdd/specs/012-aluguel-distrito-regiao/
├── spec.md
├── plan.md                 # este arquivo
├── research.md             # medições no lake real e decisões técnicas
├── data-model.md           # tabelas novas e colunas alteradas
├── logic/heranca.md        # áreas, estatísticas, cadeia de herança, qualidade
├── quickstart.md
├── contract-tests.lock
├── handoff.md
└── tasks.md
```

### Source Code (repository root)

```text
analytics/
├── dbt/
│   ├── seeds/idealista_island_aliases.csv      # NOVO
│   ├── models/gold/
│   │   ├── gold_rent_by_district_typology.sql  # NOVO
│   │   ├── gold_rent_by_region_typology.sql    # NOVO
│   │   ├── gold_{municipality,parish}_indicator.sql, gold_rent_by_municipality_typology.sql,
│   │   │   gold_data_quality.sql               # + colunas
│   │   └── schema.yml
│   └── tests/
│       ├── gold_rent_area_matches_caop.sql     # NOVO
│       ├── gold_rent_inherited_equals_source.sql  # NOVO
│       └── gold_{key_unique,rent_min_sample,value_ranges,absence_has_reason,quality_consistency,
│                 parish_inherited_equals_municipality}.sql  # ampliados
└── notebooks/explorar_gold.ipynb               # lê distrito e região da Gold (ainda sem commit)
config/criteria.yml                             # methodology_pt dos 2 critérios de aluguel
pipelines/
├── cli/build_gold.py                           # + 2 tabelas em GOLD_TABLES
└── gold/
    ├── areas.py                                # NOVO (stub criado pelo plan)
    ├── common.py, rent.py, criteria.py, parish.py, quality.py, prepare.py  # ajustes
tests/
├── contracts/test_gold_area_rent_contract.py   # NOVO, TRAVADO
├── unit/test_gold_areas.py                     # NOVO
├── unit/test_gold_parish.py                    # ajuste (perfil falso sem `origin`)
├── integration/test_gold_build.py              # ampliado
└── fixtures/gold/ci_seed.py                    # + distrito, sub-região e anúncios só distritais
.docs/{modelo_de_dados.md, runbooks/coletas.md, plano_plataforma_recomendacao_portugal.md}
README.md
```

**Structure Decision**: a lógica nova fica em `pipelines/gold/areas.py`, ao lado de `rent.py`, de quem reusa as
regras de amostra. Modelos e testes ficam nas pastas `gold` já existentes, sob a mesma tag.

## Complexity Tracking

> **Preencher SOMENTE se o Constitution Check tiver violações que precisam ser justificadas**

| Violação | Por que é necessária | Alternativa mais simples rejeitada porque |
| --- | --- | --- |

## Estratégia de Testes

Prioridade: unitário → contrato/integração → E2E → manual (último recurso).

Comandos-base:

```powershell
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
uv run --locked python -m pytest tests/contracts/test_gold_area_rent_contract.py -q --basetemp .pytest_tmp
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 012-aluguel-distrito-regiao
uv run --locked python -m tests.fixtures.gold.ci_seed --root .data/ci-gold
uv run --locked python -m pipelines.cli.build_gold --local --root .data/ci-gold --criteria .data/ci-gold/criteria.yml
uv run --locked python -m pipelines.cli.model_docs --check
```

- **Unitário** (`tests/unit/test_gold_areas.py`): paridade com a regra municipal (SC-005), região vazia, anúncio
  sem distrito, `dico` desconhecido, snapshot vazio, `reference_levels`, ilha `regional_only` que herda, critério
  sem valor próprio.
- **Integração** (`tests/integration/test_gold_build.py`): build completo com dbt, tabelas novas, herança de ponta
  a ponta e qualidade.
- **Manual**: build real e `quickstart.md`.

### Testes de Contrato

Arquivos travados em `contract-tests.lock`: `tests/contracts/test_gold_area_rent_contract.py`

Comando: `uv run --locked python -m pytest tests/contracts/test_gold_area_rent_contract.py -q --basetemp .pytest_tmp`

O script de trava não tem adaptador para pytest (contagem "unknown"). A contagem manual dá **5 funções de teste**,
sem `skip`, `xfail` nem `parametrize`. Confirmado em 2026-11-26: 5 falhas. Uma implementação descartável, em cópia
fora do repositório, deixou os 5 e os 5 da 011 verdes.

| Teste | Origem | Fase | Vermelho esperado (antes do execute) |
| --- | --- | --- | --- |
| `test_us1_ac1_ac4_fr001_fr004_fr006_district_and_region_use_every_listing_of_the_area_with_their_own_iqr` | US1-AC1–AC4, FR-001–FR-004, FR-006 | Fase 3 | `NotImplementedError: district_rent_stats` |
| `test_fr003_fr005_hierarchy_has_one_region_per_municipality_and_rejects_unknown_or_ambiguous_areas` | FR-003, FR-005, Constitution III | Fase 3 | `NotImplementedError: territory_hierarchy` |
| `test_us2_ac1_ac4_fr007_fr010_municipality_inherits_per_variant_from_the_finest_area_and_marks_it` | US2-AC1–AC4, FR-007–FR-010, SC-003 | Fase 4 | `NotImplementedError: territory_hierarchy` |
| `test_us2_ac5_fr011_sc004_normalization_uses_only_own_municipal_values` | US2-AC5, FR-011, SC-004 | Fase 4 | asserção: `n` é 31, e não 21 |
| `test_us3_ac1_ac2_fr012_fr014_parish_chain_keeps_the_source_level_and_quality_counts_it` | US3-AC1/AC2, FR-012–FR-014 | Fase 5 | asserção: falta a coluna `origin_level` |

Stubs criados pelo plan (ponto de partida do execute, não travados): `pipelines/gold/areas.py`.

## Estado Atual

<!-- Sobrescrita a cada checkpoint pelo sdd-execute. Vazia na criação. -->

| Área | Estado |
| --- | --- |
| US1, US2 e US3 | Implementadas; build real verde (catálogo `6917af159e07`) |
| Contratos | 012 5/5 e 011 5/5 verdes; travas íntegras |
| Suíte completa | 853 passaram; `ruff` limpo |
| Documentação, notebook, memória e backlog | Atualizados |
| Git | Na branch `feature/012-aluguel-distrito-regiao`; sem push |

## Riscos e Decisões

<!--
  IDs estáveis (R-001, R-002...), nunca deletados. Item resolvido ganha
  prefixo "Resolvido:" na célula de Mitigação em vez de sumir da tabela.
-->

| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |
| R-001 | Distrito do continente sem nenhum anúncio num snapshot fica sem região | Seus municípios não herdam nem da região | Aceito: hoje os 18 têm anúncios; a ausência aparece com motivo. Se ocorrer, avaliar seed distrito → região. |
| R-002 | Grafia nova de ilha na fonte (por exemplo, São Jorge) falha o build | Build parado até acrescentar a linha na seed | Resolvido: intencional (constitution III); a mensagem cita o nome e a seed (contrato e auditoria de 2026-11-26). |
| R-003 | A região é a do Idealista, não a NUTS II (Santarém no Alentejo, Setúbal na AML) | Leitura errada da referência regional | Resolvido: documentado no catálogo (`methodology_pt`), no dicionário de dados e no runbook. |
| R-004 | Critério de aluguel sem nenhum valor próprio num nível falha o build, mesmo com herdados | Um snapshot só distrital pararia o build | Resolvido: aceito (sem valor próprio não há normalização); o `CriteriaError` cita o critério e diz "nenhum valor próprio" (teste unitário). |
| R-005 | `T0` tem só 14 municípios próprios; herdados podem cair fora do P5–P95 | Normalização frágil no ranker | Encaminhar à Fase 4: limitar o score a 0–1 e revisar variantes com pouca amostra. |
| R-006 | 254 municípios usam o valor do distrito no `ALL`: o aluguel não os diferencia entre si | Ranking empata dentro do distrito | Encaminhar à Fase 4: decidir se o herdado pesa menos ou aparece com selo. |
| R-007 | Pendência A1 da 011: a freguesia mantém a mediana `ALL` própria com n ≥ 10 (o plano §8.4 sugeria só €/m²) | A cadeia da freguesia parte dessa regra | Mantida a regra convergida; confirmar com o autor. |
| R-008 | A mudança de `with_value` e da metodologia gera nova `catalog_version` | Consumidores comparam versões | Resolvido: esperado (D8 da 011); o build real gerou a versão `6917af159e07`. |
| R-009 | A entrada da spec citava `territorial_inheritance = distrito\|regiao`; o plano usa `origin_level` | Nome de coluna diferente do texto de entrada | Resolvido: decisão D7 apresentada ao autor, que mandou executar; `origin_level` implementada e a FR-008 atendida. |
| R-010 | Medido no build real: as amostras próprias estão só nos distritos do Porto (15), Faro (14) e Lisboa (13), e o P5–P95 vem delas (FR-011) | Em `custo_aluguel_mediana`, ficam abaixo do P5 de 33% (`T0`) a 73% (`T3`) dos herdados; um score limitado a 0–1 empataria muitos municípios no melhor custo | Encaminhar à Fase 4 (backlog); mudar a normalização exigiria rever a FR-011 |

## Execution Notes

<!--
  Tabela append-only, mantida pelo sdd-execute. Quando passar de ~40 linhas,
  arquivar as mais antigas (exceto as ~10 mais recentes) em history.md,
  substituindo por uma linha de resumo consolidado aqui.
-->

| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |
| 2026-11-26 | Fase 1 (Setup) | T001: fixture com distrito, sub-região e anúncios só distritais; contrato e integração da 011 verdes (11/11) | — |
| 2026-11-26 | Fase 2 (Foundational) | T002–T004; 58 testes Gold verdes | — |
| 2026-11-26 | Fase 3 (US1) | T005–T012: tabelas de distrito e região; 2/2 contratos verdes | — |
| 2026-11-26 | Fase 4 (US2) | T013–T022: herança municipal marcada; 4/4 contratos e 73 testes Gold verdes | — |
| 2026-11-26 | Fase 5 (US3) | T023–T027: freguesia e qualidade por nível; 5/5 contratos e 75 testes Gold verdes | — |
| 2026-11-26 | Fase 6 (Polish) | T028–T033: notebook, documentos, build real e suíte completa (853); SC-001–SC-006 conferidos | R-010 para o ranker |

**PRÓXIMO**: `/sdd-converge 012-aluguel-distrito-regiao`.

## Arquivos Principais

<!-- Sobrescrita a cada checkpoint — foco da etapa atual, não a árvore inteira. -->

- `pipelines/gold/areas.py`: áreas, estatísticas e herança.
- `analytics/dbt/tests/gold_rent_inherited_equals_source.sql`: garantia da cópia exata.
- `.sdd/specs/012-aluguel-distrito-regiao/quickstart.md`: verificação no lake real.

## Cuidados para Retomada

<!-- Armadilhas operacionais específicas desta feature, anexadas conforme descobertas. -->
- O build real substitui as tabelas de `lake/gold/`: para comparar com a versão anterior, copie-as antes.
- A suíte completa leva ~13 min: rode em segundo plano.

## Resultado Final

Convergida em 2026-11-26, sem achado acionável.

**Construído**

- `pipelines/gold/areas.py`: colocação dos anúncios por distrito e região, estatísticas por área, hierarquia
  territorial, `reference_levels` e `apply_rent_inheritance`.
- Tabelas novas `gold_rent_by_district_typology` e `gold_rent_by_region_typology`; a Gold passou a ter 10 tabelas.
- `origin` e `origin_level` no perfil municipal, `origin_level` na freguesia, `reference_level*` na tabela municipal
  de aluguel e herdados por nível no mart de qualidade.
- Normalização e cobertura só com valores próprios; metodologia da cadeia no catálogo; seed dos nomes de ilha.
- Notebook, dicionário de dados, runbook, README e plano do projeto atualizados.

**Desvios em relação ao plano**

- `rent._frame` ganhou o parâmetro `columns` para montar as tabelas de área.
- A mensagem do `CriteriaError` passou a dizer "nenhum valor próprio".
- O ajuste previsto em `test_gold_parish.py` (T016) foi necessário.

**Evidências**

- Contratos 012 (5/5) e 011 (5/5) verdes, travas íntegras; suíte completa com 853 testes na T033; na convergência,
  75 testes Gold, `ruff` e `model_docs --check` verdes.
- Lake real (snapshot 2026-11): 42 municípios próprios, 254 do distrito e 12 da região na mediana `ALL`; nenhum valor
  anterior mudou; SC-005 com 324 linhas sem divergência; nenhuma tabela com coluna por anúncio.
- Os 9 testes dbt tocados pela feature retornaram 0 linhas nos dados reais e reprovaram cópias adulteradas em memória.

**Em aberto**

- Desvios aceitos: um distrito do continente sem anúncios não herda da região (R-001, FR-007); o nome de distrito da
  fonte só é validado em anúncios sem município (D2, FR-005).
- Para o autor e a Fase 4: R-005, R-006, R-007 e R-010 (também no backlog).
- Ainda não verificado: o CI, porque a branch não foi enviada; o notebook foi executado só por `nbconvert`.
