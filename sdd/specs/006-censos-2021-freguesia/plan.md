# Implementation Plan: Censos 2021 por freguesia

**Slug**: `006-censos-2021-freguesia` | **Date**: 2026-11-13 | **Spec**: `sdd/specs/006-censos-2021-freguesia/spec.md`

## Summary

Coletar contagens oficiais de população total e idade, preservá-las com metadados e preparar observações por freguesia vigente com cobertura explícita. Reutilizar coleta por datasets e manifest v2; adicionar validação censitária separada do INE municipal, resolução territorial e materializações dbt-duckdb isoladas. O principal é o indicador 0014632 na geografia 2025; 0011719 fornece fallback detalhado anterior, sempre subordinado à compatibilidade e à evidência de ausência legítima. Nenhum percentual, densidade, site ou publicação.

## Technical Context

**Language/Version**: Python >=3.12,<3.13 (`pyproject.toml`), SQL/Jinja nos modelos dbt, PowerShell para SDD.

**Primary Dependencies**: httpx >=0.28,<1; dbt-core e dbt-duckdb >=1.9,<2; pandas disponível pela stack geoespacial existente; pyarrow >=20,<25; PyYAML >=6,<7. Resolver versões por `uv.lock`, sem upgrade incidental. Nenhuma dependência nova planejada.

**Storage**: LocalStorage com chaves do layout S3; raw imutável, manifest v2, Bronze/Silver Parquet. Build local em candidato com DuckDB exclusivo e promoção por caminhos; S3 de produção e implantação fora do escopo.

**Testing**: pytest >=8,<10, ruff >=0.11; doubles offline e dbt real com fixtures. Exatos cinco casos novos de contrato travados; regressões existentes preservadas.

**Target Platform**: Windows/PowerShell local e Linux/GitHub Actions. Handler de coleta sem dependência de CLI, compatível com adaptação futura a Lambda; nenhuma função AWS criada agora.

**Performance Goals**: uma requisição por vez, intervalo mínimo 2 s, timeout 90 s, até 3 tentativas com backoff 2 s crescente como INE existente; cada dataset consulta só uma idade e 2021. Registrar duração/bytes/linhas da execução real, sem prometer SLA ainda não medido.

**Constraints**: edição 2021 separada da geografia; limites etários por metadado do indicador; ausência nunca vira zero; não inferir território pelo nome; não estimar valores territoriais; preservar estado e trabalho de outras features.

**Scale/Scope**: dimensão local atual de 3.259 freguesias/308 municípios em CAOP 2025; cardinalidade vem da dimensão em execução. 19 datasets de dados principais + 20 legados + 2 metadados = 41 requisições antes de retries, aproximadamente 124 mil observações pelas contagens sondadas. Essa estimativa não é prova de cobertura etária real.

**Cost**: API pública sem chave/pagamento; nenhum recurso recorrente criado, incremento AWS US$ 0/mês nesta entrega local. Estimativa preliminar de armazenamento local de dezenas de MB por revisão, a medir; custo de eventual implantação é trabalho futuro, sujeito ao orçamento da constitution.

**Exploration synthesis**: `collect_datasets` já resolve validação, SHA256, estados independentes e manifest; `entry_extra` permite snapshot sem mudar seu contrato. `make_ine_fetcher` e a canonicalização são reutilizáveis. `validate_ine_response` municipal não serve para geocod de freguesia. `latest_dataset_states` mistura sucessos por dataset, portanto só serve à deduplicação, não à seleção de um lote preparado. `build_parish_crosswalk`, `_promote.py`, modelos external e tags oferecem o padrão a seguir, com reforço de presença de todas as saídas e relatórios no candidato. ADR-001 e ADR-002 lidas integralmente; ADR-003 trata BYOK e não se aplica a API pública sem chave.

## Decisões Invariantes

- **D1 — Fontes e recortes**: principal 0014632, fallback 0011719, com metadados próprios e 2021 explícito. Sexo T/HM e nacionalidade T no principal; códigos etários não são intercambiáveis entre indicadores. Fonte nacional cadastrada antes de coleta operacional.
- **D2 — Coleta responsável**: Emenda aprovada pelo usuário em2026-11-13: lotes explícitos de até32 freguesias e todas as categorias da família por resposta. Catálogo congela o universo oficial de metadados e IDs estáveis por família/lote (201 itens:2 metadados +102 lotes2025 +97 lotes2013); cada snapshot inclui códigos/idades/seletores. O build exige união exata com metadados e CAOP vigente, sem sobreposição. Snapshots históricos por idade continuam legíveis; sem rede em testes/build, sem scraper, proxy ou contorno. API HTTP 200 com erro interno reprova. Verificação de regras da fonte é gate T001, inclusive diagnóstico do robots indisponível.
- **D3 — Identidade de entrada**: congelar snapshot resolvido da configuração e assinatura em cada entrada; fingerprint incorpora consulta. Só DataExtracao é volátil. Build lê um manifest completo, resolve unchanged nele e verifica hashes; falha recente não é escondida por escolha automática de run antigo.
- **D4 — Território por observação**: prioridade oficial compatível; fallback por correspondência válida, herança explícita e nenhuma soma territorial automática. Supressão oficial não permite fallback para revelar dado oculto. `partial_origin` prevalece sobre o nome da relação. Mudança de CAOP não suportada exige nova evidência/decisão, não uma associação por igualdade de código.
- **D5 — Idades e coerência**: preservar todas as categorias nativas em Bronze; harmonizar por limites para 19 categorias canônicas (total + 18), somando apenas 85–89 e 90+ do mesmo território/edição no fallback quando ambos publicados. Sem percentuais/densidade. Coerência de total/faixas é avaliada na origem de mesmo suporte territorial, não entre total próprio e faixa herdada.
- **D6 — Cobertura honesta**: matriz dimensão vigente × categorias obrigatórias, com own/inherited/missing e motivo/evidência. Omissão técnica bloqueia; não é ausência oficial. Resumos contam cobertura, sem somar populações herdadas como exclusivas.
- **D7 — Isolamento e promoção**: build offline, lock exclusivo censitário, dependências territoriais congeladas, candidato próprio; dbt verde e readiness true antes de promover só quatro tabelas e census_reports. Erro preserva vigente. Diagnóstico de falha separado dos relatórios vigentes. Não tocar published/current.json.
- **D8 — Provas**: fixture verde e execução real nacional são gates distintos; sem execução real SC-007 não foi cumprido. CI remoto também precisa de evidência própria, não inferida de teste local.

## Constitution Check

| Princípio | Pré-Design | Pós-Design | Notas |
| --- | --- | --- | --- |
| I. Nenhum segredo fora do cofre | PASS | PASS | API pública; sem credenciais novas; CI de segredos existente preservado. |
| II. Núcleo do produto estático e sem chave | PASS | PASS | Só pipeline offline; nenhuma API dinâmica/site/publicação nova. |
| III. Dados honestos e rastreáveis | PASS | PASS | D3–D6, limites e símbolos oficiais, herança por observação, órfãos auditados. |
| IV. Coleta responsável e licenciada | PASS | PASS | Catálogo/CC BY 4.0/atribuição e verificação de termos em T001 antes de coleta; sem exceção aprovada ou necessária no design. Robots 403 é pendência operacional explícita, não permissão presumida. |
| V. Bruto imutável e publicação atômica | PASS | PASS | Snapshot, idempotência semântica, candidato e rollback por caminhos; nenhuma publicação externa. Limites de queda de processo documentados em L4. |
| VI. Privacidade por padrão | PASS | PASS | Apenas contagens agregadas; sem microdados, visitantes ou rastreamento. Supressão preservada. |
| VII. Custo como requisito | PASS | PASS | Incremento recorrente zero nesta execução local; métricas reais de armazenamento em T023. |

Quality gates: lint, pytest offline, dbt com testes de unicidade/relationships/faixas, docs/catalog/runbook e verificação de segredos no CI. Ranker, E2E visual, infraestrutura e Terraform não são tocados; não introduzir requisitos desses domínios nesta feature.

## Project Structure

### Documentation (this feature)

```text
sdd/specs/006-censos-2021-freguesia/
  spec.md
  plan.md
  tasks.md
  research.md
  data-model.md
  contracts/censos-cli.md
  logic/territory-and-readiness.md
  quickstart.md
  contract-tests.lock
  handoff.md
```

### Source Code (repository root)

```text
pyproject.toml / uv.lock                       existentes
config/sources.yml                            existente; incluir censos
pipelines/collectors/_shared/                  existente; reutilizar datasets/storage/http/manifests
pipelines/collectors/ine/                      existente; reutilizar fetch/fingerprint sem alterar validador municipal
pipelines/collectors/parish_crosswalk/          existente; dependência territorial
pipelines/collectors/censos2021/                NOVO; quatro stubs já criados
  handler.py / transform.py / territory.py / coverage.py
  validate.py / prepare.py                     a criar
pipelines/cli/_common.py / _promote.py          existentes; reutilizar
pipelines/cli/collect_censos.py                 a criar
pipelines/cli/build_censos.py                   a criar
analytics/dbt/dbt_project.yml                  existente; incluir tag censos
analytics/dbt/models/censos/                   a criar: quatro modelos + schema.yml
analytics/dbt/tests/censos_integrity.sql        a criar
analytics/dbt/tests/censos_coverage.sql         a criar
tests/contracts/test_censos2021_contract.py     NOVO, travado
tests/fixtures/censos2021/responses.py           NOVO, travado
tests/fixtures/censos2021/ci_seed.py             a criar
tests/unit/test_censos_*.py                     a criar
tests/integration/test_collect_censos.py        a criar
tests/integration/test_censos_build.py          a criar
.github/workflows/python.yml                   existente; incluir fixture + dbt censos
docs/runbooks/coletas.md / .docs/fontes_de_dados.md / README.md  existentes; atualizar
```

**Structure Decision**: estender as pastas existentes; novos módulos e modelos explícitos para censos. Nenhuma nova aplicação, biblioteca ou infraestrutura. Arquivos marcados a criar não são alegados como existentes na exploração.

## Complexity Tracking

Nenhuma violação da constitution no design. Gates de verificação da fonte não são exceções aceitas.

| Violação | Por que é necessária | Alternativa mais simples rejeitada porque |
| --- | --- | --- |

## Estratégia de Testes

Prioridade: unitário → contrato/integração → execução ponta a ponta local offline → confirmação com fonte real. Manual só para interpretação/inspeção dos relatórios, não para substituir validações automáticas. Testes de promoção, coerência das origens e run incompleto são adicionais aos cinco contratos, detalhados em tasks.md.

Comandos-base (build/fixture ainda serão implementados):

```powershell
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest tests/contracts/test_censos2021_contract.py -q --tb=short --basetemp .pytest_tmp_censos_plan
uv run --locked python -m pytest -q --basetemp .pytest_tmp
uv run --locked python -m tests.fixtures.censos2021.ci_seed --root .data/ci-censos
uv run --locked python -m pipelines.cli.build_censos --local --root .data/ci-censos
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 006-censos-2021-freguesia -Json
```

O build chama `uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:censos`, isolando via `CENSOS_BUILD_DIR`, `CENSOS_PREPARED_DIR`, `OBS_SILVER_DIR`, `CAOP_DUCKDB_PATH`, `DBT_TARGET_PATH` e `DBT_LOG_PATH`. No Python usar executável dbt do ambiente, como os builders existentes, sem spawn de shell construído por string. Quickstart traz o comando direto com env vars.

### Testes de Contrato

Arquivos travados: `tests/contracts/test_censos2021_contract.py`, `tests/fixtures/censos2021/responses.py`. Reutilizado sem edição o helper MemoryStorage da spec 003 e a fábrica ine_response da spec 002. Stubs não travados: os quatro módulos públicos novos (handler/transform/territory/coverage).

Comando executado: `uv run --locked python -m pytest tests/contracts/test_censos2021_contract.py -q --tb=short --basetemp .pytest_tmp_censos_plan`.

| Teste (nome completo no arquivo) | Origem | Fase | Vermelho confirmado |
| --- | --- | --- | --- |
| test_us1_fr004_fr005_raw_metadata_unchanged_and_revision | US1/AC1,2,4; FR-004/005; V | 2 | NotImplementedError: 006: collect_censos |
| test_us1_ac3_fr006_invalid_response_has_no_raw_and_recovers | US1/AC3; FR-006; V | 2 | NotImplementedError: 006: collect_censos |
| test_fr002_fr012_fr013_reader_preserves_age_bounds_zero_suppression_and_rejects_corruption | FR-002/012/013; III | 3 | NotImplementedError: 006: read_censos_response |
| test_fr008_fr009_fr010_fr011_official_precedence_inheritance_and_partial_absence | FR-008/009/010/011; SC-004; III | 3 | NotImplementedError: 006: align_censos |
| test_fr014_fr015_sc001_sc006_coverage_distinguishes_documented_absence_from_lost_record | FR-014/015; SC-001/006 | 4 | NotImplementedError: 006: assess_censos_coverage |

Resultado em 2026-11-13: **5 failed em 1,11 s**, todos nos stubs esperados, sem erro de import/sintaxe. `pytest --collect-only -q` confirmou **5 casos**. Limitação: check-contract-tests.ps1 só conta JS/TS, logo o lock registra `unknown`; pytest é a contagem verificável de 5/5 nesta feature. Não há skip/only/todo/parametrização escondendo casos.

Regressão dirigida executada: testes unitários de validação/fingerprint INE, catálogo/manifests, catálogo/derivação/cobertura da correspondência, storage/HTTP e contratos de ingestão/correspondência: **74 passed em 1,91 s**. Integrações existentes `test_collect_ine_local.py`, `test_collect_parish_crosswalk_local.py` e `test_collect_parish_crosswalk_s3.py`: **10 passed em 4,56 s**. Lint global `ruff check pipelines tests` passou; travas 001–006 íntegras. São 84 regressões verdes, separadas dos cinco contratos deliberadamente vermelhos. Não foi rodada a suíte completa nesta etapa de planejamento.

## Estado Atual

| Área | Estado |
| --- | --- |
| Fases1–4 e emenda D2 | Implementadas;201 itens por lotes32;contratos históricos preservados |
| Validação local | Suíte global411/411 em571,46s +2 regressões adicionais;61 testes da área em32,12s;lint e travas001–006 aprovados |
| Quickstart offline | `.data/ci-censos-batches`:6 freguesias,76 próprias/19 herdadas/19 ausentes;dbt real |
| Coleta nacional | Run20261113T231450079026Z-ddf26aad:201 respostas,200 changed/1 unchanged,32.804.869 bytes em449,406s;nenhuma falha |
| Build real | Pronto:3.259 freguesias/308 municípios/19 categorias =61.921 próprias,0 herdadas/ausentes;4 modelos e21 testes dbt aprovados;22 arquivos vizinhos intactos |
| Repetição | Run20261113T232234325869Z-00a1b4a4:201/201 unchanged em449.906s,0 novos raw;hashes/consultas/revisões idênticos |
| CI remoto | Pendente;sem commit/push autorizado;gate distinto das provas locais |

## Riscos e Decisões

<!--
  IDs estáveis (R-001, R-002...), nunca deletados. Item resolvido ganha
  prefixo "Resolvido:" na célula de Mitigação em vez de sumir da tabela.
-->

| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |
| R-001 | Semântica territorial/termos ainda exigem evidência operacional; robots 403 | Associação indevida ou coleta incompatível | T001 antes de coleta; não estimar método/limites; parar se proibição aplicável. |
| R-002 | Limite de linhas/timeouts da API | Run incompleto | D2 emendada, lotes de até32, retries limitados; manifest falhado bloqueia build default. |
| R-003 | Códigos etários diferentes; 85+ não coincide nas fontes | Perfil etário falso | D5, limites por metadado e harmonização com proveniência; testes complementares. |
| R-004 | Estados por dataset de runs parciais ou mudança de catálogo | Mistura de revisões/configurações | D3 e seleção de manifest completo com snapshots/hashes, sem nova leitura do catálogo para reconstrução. |
| R-005 | Total próprio e faixas herdadas não têm mesmo território | Denominador falso | D4–D6; validar coerência na origem e registrar proveniência por observação. |
| R-006 | Workspace com alterações de 005 e arquivos compartilhados | Perda de trabalho/regressão | Não trocar branch/resetar; ler diffs antes de alterar catálogo/dbt/CI/docs; travas 001–005 íntegras. |
| R-007 | Rename múltiplo não é ACID contra queda de processo | Saída intermediária em interrupção abrupta | Lock e diagnóstico/recovery L4; testes de rollback em falha de promoção; sem promessa de publicação/concorrência. |
| R-008 | Revisão independente encontrou ausência oficial perdida, soma parcial excessiva, recuperação de run e limpeza pós-promoção | Reprovação indevida ou aceitação inválida | Resolvido: T025, testes de regressão dirigidos verdes e revalidação independente (6 casos); proteção local à006 e helper compartilhado preservado. |
| R-009 | Consultas nacionais por faixa excederam timeout; piloto de 32 freguesias respondeu | T023 sem prova nacional | Resolvido: D2/T026 aprovadas e implementadas;T023 nacional pronta com3.259 freguesias e repetição201/201 unchanged;contratos preservados. |

## Execution Notes

<!--
  Tabela append-only, mantida pelo sdd-execute. Quando passar de ~40 linhas,
  arquivar as mais antigas (exceto as ~10 mais recentes) em history.md,
  substituindo por uma linha de resumo consolidado aqui.
-->

| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |
| 2026-11-13 | Fase 1 | Catálogo com 41 itens e evidência oficial registrados; uv run --locked python -m pytest tests/unit/test_censos_catalog.py tests/unit/test_climate_catalog.py tests/unit/test_dataset_catalog_and_manifest.py -q --basetemp .data/tmp/censos-phase1: 32 passed; sem contrato nesta fase | Implementar US1 (Fase 2) |
| 2026-11-13 | Fase 2 | Coleta e CLI offline local/S3 implementadas com snapshot e idempotência; uv run --locked python -m pytest tests/contracts/test_censos2021_contract.py tests/unit/test_censos_validate.py tests/integration/test_collect_censos.py -q -k "us1 or bad_responses or query_identity or cli_local or manifest_failure or s3_moto" --basetemp .data/tmp/censos-phase2: 13 passed; contratos US1 2/2 verdes | Implementar US2 (Fase 3) |
| 2026-11-13 | Fase 3 | Leitor e correspondência territorial implementados; dbt external com 20 passos verdes após criar diretórios candidatos; uv run --locked python -m pytest tests/contracts/test_censos2021_contract.py -q -k "reader or precedence" --basetemp .data/tmp/censos-us2-final: 2/2 verdes; testes complementares 7 verdes; dbt build --select tag:censos: 20/20 | Implementar US3 (Fase 4) |
| 2026-11-13 | Fase 4 | Cobertura e build com lock/rollback; relatório nacional sem somar heranças; uv run --locked python -m pytest tests/integration/test_censos_build.py tests/unit/test_censos_territory.py tests/unit/test_censos_coverage.py tests/contracts/test_censos2021_contract.py -q --basetemp .data/tmp/censos-phase4: 23 passed, contratos completos 5/5 verdes | Polish: CI, docs, suíte completa e prova nacional real |

| 2026-11-13 | Polish/T023 | Suíte final 399 verdes, quickstart e revisão aprovados; tentativa real parcial preservada após 9 chamadas; piloto de lotes 32×19 validado | Aguardar decisão sobre D2; CI remoto pendente |

| 2026-11-13 | Emenda D2/T026 | Catálogo201 itens, lotes cartesianos e união nacional implementados;61 testes da área verdes e regressão histórica completa adicional verde; revisão independente sem bug material | Coleta real iniciada; suíte global em andamento |

| 2026-11-13 | Fechamento local D2/T023/T026 | Nacional3.259 freguesias/61.921 próprias,dbt25/25,22 arquivos vizinhos intactos;repetição201/201 unchanged;suíte411 +2 regressões/lint/travas verdes;T024 auditada | T022/CI remoto e scan aguardam commit/push/PR autorizado |

**PRÓXIMO**: obter autorização de commit/push/PR (workspace inclui005 prévia e006) ou aguardar envio pelo usuário,então validar CI remoto/scan antes de marcar Implementada.

## Arquivos Principais

- `config/sources.yml`:201 consultas oficiais explícitas.
- `pipelines/collectors/censos2021/` e `pipelines/cli/{collect_censos,build_censos}.py`.
- `analytics/dbt/models/censos/` e `analytics/dbt/tests/censos_*.sql`.
- `tests/unit/test_censos_*.py`, `tests/integration/test_*censos*.py` e fixture CI não travada.
- `docs/runbooks/coletas.md` e relatórios locais `.data/lake/silver/census_reports/`.

## Cuidados para Retomada

<!-- Armadilhas operacionais específicas desta feature, anexadas conforme descobertas. -->

- Usar --basetemp dentro do projeto: o Temp global apresentou ACL negada nesta sessão.


### Histórico do bloqueio operacional — antes da emenda D2

Suíte final: 399/399 verdes em421,27s; área censos:49/49 em31,24s; lint aprovado; travas001–006 íntegras. Coleta nacional por faixa resultou em timeouts reiterados. O processo foi interrompido após 9 tentativas HTTP registradas; bruto preservado e manifest parcial recuperado em `manifests/censos/20261113T224403345700Z-3d498ac9.json`. Não houve promoção censitária.

Pilotos no indicador0014632: quatro freguesias/total responderam em1,4s; lista128/256/512 códigos gerou erroPLSQL de buffer; lote16 freguesias com19 categorias retornou304 observações em1,5s, e lote32 retornou608 em0,9s. Uma fonte alternativa0014630 foi descartada por ter grupos amplos que não permitem25–39. A alternativa viável exige reabrir D2: lotes explícitos de32 freguesias com todas as categorias, preservando cada resposta original, com201 itens estimados (102 lotes2025 +97 lotes2013 +2 metadados) e novos testes de completude por lote. Decisão pendente do usuário; nenhuma mudança dessa estratégia foi aplicada.

### Emenda D2 aprovada — 2026-11-13

Usuário escolheu reabrir D2 e coletar em lotes de32. A lista explícita é versionada no catálogo a partir dos dois metadados oficiais já preservados, sem pré-coleta dinâmica nem alteração do bruto. Cada resposta é um raw separado. A completude é validada por par freguesia/faixa e na união de toda a família. Os contratos travados permanecem inalterados. T026 registra a implementação. Red dirigido inicial:5 falhas esperadas por leitor/validador ainda singulares;5 proteções existentes verdes.

### Primeira prova nacional por lotes — 2026-11-13

Coleta real `20261113T231450079026Z-ddf26aad`, manifest `manifests/censos/20261113T231450079026Z-ddf26aad.json`:201 chamadas/201 respostas,200 novos raw e1 metadado unchanged reaproveitado do run parcial preservado;32.804.869 bytes referenciados,449,406s,sem falhas. Intervalo mínimo2s,timeout90s,até3 tentativas;foram201 chamadas para201 itens,sem retries nesta rodada. Fonte INE,CC-BY-4.0,edição2021,geografias2025/2013. Recibos em `.data/receipts/censos-proof/<run>.jsonl` e `<run>.summary.json` (ignorados pelo Git).

Comando de build: `uv run --locked python -m pipelines.cli.build_censos --local --root .data --run-id 20261113T231450079026Z-ddf26aad`. Resultado pronto,sem bloqueadores:3.259 freguesias,308 municípios,19 categorias canônicas e61.921 observações próprias;0 herdadas,0 ausentes. Bronze123.761 linhas nativas (61.921 atuais,61.840 legadas). Total populacional de2021:10.343.066. Os18 códigos alfanuméricos estão presentes. Todas as observações aceitas têm origem,indicador,licença,raw/checksum e run;nenhuma dessas colunas tem nulos. Os recortes futuros25–39 e65+ são exatos pelos limites disponíveis;nenhum indicador percentual foi criado.

dbt real:4 modelos success +21 testes pass. Relatórios em `.data/lake/silver/census_reports/`;readiness.json,coverage.csv,summary.csv,orphans.csv e resultados dbt preservados. A comparação de SHA256 confirmou22 arquivos de lakes vizinhos intactos. Auditoria em `.data/receipts/censos-proof/national-build-audit.json`. Resumo por região,em observações:continente57.931,Madeira1.026,Açores2.964,todas próprias. Ausência de herança nesta rodada não elimina a política de fallback e seus testes. Isso demonstra operação local;CI remoto e nuvem não foram demonstrados.

### Prova real concluída após emenda D2 — 2026-11-13

Coleta inicial `20261113T231450079026Z-ddf26aad`:201 chamadas/201 respostas,200 changed e1 metadado unchanged,32.804.869 bytes referenciados,449,406s. Repetição `20261113T232234325869Z-00a1b4a4`:201/201 unchanged,201 chamadas,449.906s,nenhum novo raw. Ambos os manifests estão em `.data/manifests/censos/`;originais,hashes,consultas e revisões da primeira rodada foram conferidos após a segunda. Recibos e auditorias em `.data/receipts/censos-proof/`.

Build real aprovado:3.259 freguesias,308 municípios,19 categorias canônicas e61.921 observações próprias;0 herdadas,0 ausentes. Bronze123.761 linhas;população total2021 de10.343.066. Cobertura regional completa e18 códigos alfanuméricos preservados. Todas as observações têm fonte,licença,território,run e referências raw verificadas. Vinte e dois arquivos vizinhos permaneceram idênticos. dbt:4 modelos e21 testes aprovados. Relatórios: `.data/lake/silver/census_reports/`. Fonte INE,Censos2021,CC-BY-4.0. O método de reexpressão não foi divulgado pelo publicador nas evidências consultadas;essa limitação permanece registrada,sem estimativa do projeto.

Validação local: `uv run --locked python -m pytest -q --basetemp .data/tmp/censos-batches-full` →411 passed em571,46s;2 regressões adicionais (histórico completo41 itens e repetição por lotes) →2 passed em3,37s,fora da coleta inicial dessa suíte. Área censos →61 passed em32,12s antes dessas2 adições. `uv run --locked ruff check pipelines tests` aprovado. Seed/build de CLI em `.data/ci-censos-batches` aprovado;travas001–006 íntegras;revisão independente sem bug material. O CI remoto e seu scan de segredos seguem pendentes de commit/push/PR autorizado;nenhuma execução em nuvem ou publicação foi demonstrada. Não marcar Implementada/Convergida antes do gate restante.
