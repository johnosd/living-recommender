# Implementation Plan: Ingestão de clima Open-Meteo

**Slug**: `003-ingestao-clima-open-meteo` | **Date**: 2026-11-11 | **Spec**: `sdd/specs/003-ingestao-clima-open-meteo/spec.md`

## Summary

Coletar o clima **diário dos 308 municípios** do Open-Meteo (arquivo histórico, reanálise `era5`) numa janela fixa de 24 meses completos (2024-11-01 a 2026-10-31), uma requisição por município no ponto representativo da CAOP, e levá-lo a um staging Bronze em formato longo com relatório de cobertura. Reutiliza o padrão da spec 002 (manifest v2, estado vigente por unidade, impressão digital, tolerância a falha) com a **unidade passando de dataset para município**, o que exige extrair o miolo de `collect_datasets` para `collect_items` e acrescentar três capacidades: o status `pending`, a parada limpa por cota (`QuotaExhausted`, Ctrl+C) e a noção de "estado atual" (janela e modelo iguais ao catálogo).

Como o plano gratuito comporta ~100 a 140 municípios por dia, a coleta é **retomável**: ao esgotar a cota ela grava o manifest com os restantes como `pending` e sai com código 2; a execução seguinte consulta só os pendentes. Depois, `build_climate` confere os brutos, escreve um Parquet longo (2,9 milhões de linhas, em fluxo), roda o dbt-duckdb (testes de chave, de dias por município, de faixa física e de relação com a dimensão) e promove por caminho três tabelas Bronze. A sondagem de 2026-11-11 mostrou que o `era5_land` devolve 9 das 13 variáveis nulas e que o `best_match` não é reprodutível, então o modelo é `era5` (grade de ~25 km, limitação registrada em R-004).

## Technical Context

**Language/Version**: Python 3.12 (`requires-python = ">=3.12,<3.13"`), SQL/dbt Core. Mesma base das specs 001 e 002.

**Primary Dependencies**: já instaladas, **nenhuma nova**: `httpx` (cliente e `MockTransport` nos testes), `PyYAML`, `boto3`, `pyarrow`, `pandas`, `dbt-core`, `dbt-duckdb`; dev: `moto[s3]`, `pytest`, `ruff`. O cliente oficial `openmeteo-requests` foi descartado (research R7).

**Storage**: `.data/` local e S3 com o mesmo layout da spec 002: `raw/source=open_meteo/dataset=<dico>/run_id=<run>/<dico>.json` e `manifests/open_meteo/<run>.json`; Bronze em `lake/bronze/{stg_climate_daily,rpt_climate_coverage,rpt_climate_points}/` (Parquet) e dois CSV de apoio. Reutiliza `LocalStorage` e `S3Storage` sem alterá-los.

**Testing**: pytest sem rede, com fetcher/storage injetados, `httpx.MockTransport` para o cliente, `moto` para o S3 e um `dbt build` sobre uma Silver sintética. 5 contratos travados (P1/P2). Padrão idêntico ao das specs 001 e 002.

**Target Platform**: Windows local nesta feature, portátil para Lambda/ECS (ADR-002 D4). Sem deploy. O limite de 15 min do Lambda **não** comporta a coleta (horas, por causa da cota); a implantação futura exigirá ECS ou execuções por lote com `--max-municipalities` (registrado em R-007).

**Performance Goals**: nenhuma meta de latência. A coleta é limitada pela cota do plano gratuito (~3 dias para os 308 municípios). `build_climate` deve processar as 2,9 milhões de linhas em fluxo, sem manter o conjunto em memória (verificado em T036).

**Constraints**: raw imutável; estado por município; ausência nunca vira zero; município fora de 308 reprova a execução; nenhuma chave de API (a fonte é gratuita sem chave); CAOP, Pordata/INE e seus lakes e contratos **não mudam de comportamento**; plano gratuito só para uso não comercial (R-001); resolução de ~25 km (R-004).

**Scale/Scope**: 308 municípios × 13 variáveis × 730 dias = 2.922.920 observações; ~22 MB de JSON bruto por coleta completa; custo recorrente US$ 0.

## Decisões Invariantes

- **D1. O município é a unidade.** Coleta, validação, impressão digital, estado vigente, falha e pendência são por município; `dataset_id` no manifest é o `dico`. O manifest continua sendo o v2 (`datasets[]`); o da CAOP (v1) não muda.
- **D2. Um só ponto de extensão compartilhado.** O miolo de `collect_datasets` vira `collect_items` em `_shared/datasets.py`; `collect_datasets` fica como invólucro e **devolve exatamente as quatro chaves de hoje**. É a única mudança em código das specs anteriores; o contrato travado da 002, o da 001 e os 140 testes existentes a protegem.
- **D3. `pending` é uma entrada, nunca estado.** Entrada `pending` exige `error`, não tem `key`/`sha256` e é ignorada por `latest_dataset_states`. Status da execução: `failed` se todas falharam; `partial` se houver `failed` ou `pending`; senão `changed`/`unchanged`.
- **D4. Modelo e requisição fixos.** `models=era5`, `timezone=auto`, 13 variáveis do catálogo, **uma requisição por município com a janela inteira**. Mudar modelo, janela ou variáveis é mudança de catálogo e torna todos os municípios pendentes de novo; os brutos antigos permanecem.
- **D5. Cota por classificação do 429.** `reason` com `minutely` → espera 61 s (até 5×); `hourly` → espera 3.605 s (1×); `daily` → `QuotaExhausted` sem esperar; 429 sem palavra reconhecida é tratado como `hourly`. `--no-wait` e esperas esgotadas viram `QuotaExhausted`. `QuotaExhausted` e Ctrl+C marcam o item corrente e os seguintes como `pending` e a execução sai com **código 2**; `failed` sai com **1** e vence.
- **D6. Estado atual.** Um município está atual se o `reference_period` (a janela), o `model` e a assinatura ordenada de variáveis/unidades da sua entrada `changed` mais recente forem iguais aos do catálogo. Entradas sem assinatura exigem recoleta; reordenar a lista não altera a assinatura. Sem `--recollect`, a execução pula os atuais sem chamar a fonte; com ele, consulta e compara a impressão digital. Sem nada a fazer: `up_to_date`, sem manifest e sem consumir `run_id`.
- **D7. Mudança por impressão digital sem `generationtime_ms`.** O `sha256` do manifest é o dos bytes; o `fingerprint` é o JSON canônico sem `generationtime_ms`, o único campo volátil observado (research R5). O bruto guarda os bytes originais.
- **D8. O dia é o dia local.** A data de cada observação é o texto de `daily.time` (a fonte agrega no fuso do município com `timezone=auto`), convertido para `date` sem deslocamento de fuso.
- **D9. Ausente é ausente.** `null` da fonte → valor nulo; `0` legítimo continua `0`; nenhum `fillna`, interpolação, herança entre municípios que dividem a mesma célula da grade, nem conversão de unidade. Nulos esparsos **não** reprovam o bruto; variável inteiramente nula, dias faltantes ou unidade diferente **reprovam**.
- **D10. Staging próprio, por tag e promoção por caminho.** `stg_climate_daily` não entra em `stg_observation` (período inteiro vs data, 2,9 milhões de linhas, proveniência própria). Modelos com a tag `climate`; `dbt build --select tag:climate`; promoção só de `lake/bronze/stg_climate_daily`, `rpt_climate_coverage` e `rpt_climate_points`. Staging **parcial é válido**: municípios sem estado atual saem como `not_collected`, nunca como erro.
- **D11. Dimensão e ponto.** As coordenadas vêm de `dim_municipality` (`representative_lat/lon`), lida de um diretório local (`--silver`, padrão `<root>/lake/silver`). A execução é recusada, antes de qualquer rede, se a dimensão faltar, não tiver `expected_municipalities` (308) municípios, repetir `dico` ou tiver coordenada ausente/fora de Portugal.
- **D12. Sem dependências novas e sem chave.** Haversine em Python puro; cliente `httpx`; nada em `.env`.
- **D13. Fora desta feature:** WWO, score/extremos/TCI/normais, freguesia, índice UV, séries longas (10/30 anos), dados horários, Silver/Gold, `published/`, deploy e agendamento.

## Constitution Check

*GATE pré-design verificado após ler a constitution e os ADR-001/002/003; pós-design reavaliado depois de `research.md`, modelo de dados, contratos, lógica e testes de contrato.*

| Princípio | Pré-Design | Pós-Design | Notas |
| --- | --- | --- | --- |
| I. Nenhum segredo fora do cofre | Conforme | Conforme | A API do arquivo é gratuita e **sem chave**; nada em `.env` ou no Git. Testes com `MockTransport`; S3 só com as credenciais falsas do `moto`. `gitleaks` no CI. |
| II. Núcleo estático e sem chave | Conforme | Conforme | Só coleta e staging em lote; nenhum servidor, API própria ou chave no navegador. |
| III. Dados honestos e rastreáveis | Conforme | Conforme | Ausência explícita (D9), junção pelo `dico` da CAOP (sem nomes), fonte/janela/modelo/licença em cada linha e no manifest, cobertura medida, pontos divergentes visíveis. **Ressalva:** a série de 24 meses não é uma normal climática; a camada Silver deve rotular o indicador como "últimos 24 meses" (R-004). |
| IV. Coleta responsável e licenciada | **Exceção justificada** | **Exceção justificada** | Catálogo antes do coletor, User-Agent, taxa mínima, retry com backoff e respeito aos limites de cota: conformes. O plano gratuito do Open-Meteo é **só para uso não comercial**; o autor decidiu coletar mesmo assim, como risco aceito (R-001), com mitigação e alternativa, como a constitution admite. |
| V. Bruto imutável e publicação atômica | Conforme | Conforme | Raw sem sobrescrita; `unchanged` sem raw novo; promoção atômica por caminhos (D10); uma falha no dbt mantém o staging anterior. Sem `current.json` nesta feature. |
| VI. Privacidade por padrão | Conforme | Conforme | Só clima em coordenadas de municípios; nenhum dado pessoal, nenhum rastreamento. |
| VII. Custo como requisito | Conforme | Conforme | Local e S3 simulado: US$ 0/mês. Nenhum recurso AWS criado. |

**Resultado:** nenhuma violação não justificável. A única exceção (princípio IV, licença de uso do plano gratuito) foi decidida pelo autor na spec (Clarifications) e está em Complexity Tracking e em R-001.

## Project Structure

### Documentation (this feature)

```text
sdd/specs/003-ingestao-clima-open-meteo/
├── spec.md
├── plan.md                  # este arquivo
├── tasks.md
├── research.md              # sondagens de 2026-11-11 (modelo, fuso, cota, 429)
├── data-model.md            # catálogo, manifest, staging, relatórios, lake
├── contracts/clima-cli.md
├── logic/coleta-clima.md
├── quickstart.md
├── handoff.md
└── contract-tests.lock
```

### Source Code (repository root)

Estado real encontrado (specs 001 e 002) e o que esta feature acrescenta (`+`) ou altera (`~`):

```text
config/sources.yml                                    # ~ + open_meteo
pipelines/
  cli/        collect_caop.py build_caop.py view_caop.py collect_pordata.py collect_ine.py
              load_pordata_manual.py build_observations.py _common.py _promote.py
              + collect_open_meteo.py build_climate.py
  collectors/
    _shared/  catalog.py http.py manifest.py storage.py storage_s3.py dataset_manifest.py
              municipality.py observations.py datasets.py
              ~ catalog.py (validate_climate_source / get_climate_source / ramo em load_catalog)
              ~ datasets.py (collect_items, StopCollection/QuotaExhausted já criadas pelo plan)
              ~ dataset_manifest.py (status pending)
    caop/ pordata/ ine/                                # intocados
    + open_meteo/  municipalities.py validate.py fingerprint.py fetch.py handler.py
                   transform.py points.py             # handler/fetch/validate/fingerprint/transform: stubs do plan
analytics/dbt/
  dbt_project.yml                                     # ~ + tag climate
  models/bronze/ stg_observation.sql rpt_observation_coverage.sql schema.yml   # intocados
  + models/climate/ stg_climate_daily.sql rpt_climate_coverage.sql rpt_climate_points.sql schema.yml
  + tests/climate_*.sql
tests/
  contracts/  test_caop_collection_contract.py (001) test_dataset_ingestion_contract.py (002)
              + test_climate_collection_contract.py (travado 003)
  fixtures/   caop/ pordata/ ine/ observations/
              + open_meteo/ (responses.py travado) + climate/ci_seed.py
  unit/ integration/                                  # + testes novos (ver tasks.md)
.github/workflows/python.yml                          # ~ + passo dbt do clima
docs/runbooks/coletas.md  README.md  .docs/fontes_de_dados.md   # ~ atualizar no Polish
```

**Structure Decision:** seguir `pipelines/collectors/<fonte>/` e as CLIs `collect_*`/`build_*` das specs 001 e 002. A lógica comum fica em `_shared/` (só `datasets.py`, `dataset_manifest.py` e `catalog.py` mudam, de forma retrocompatível). A promoção usa `_promote.py` e o `dbt` roda por tag, como na spec 002.

## Complexity Tracking

| Violação | Por que é necessária | Alternativa mais simples rejeitada porque |
| --- | --- | --- |
| Princípio IV: coletar o Open-Meteo no plano gratuito, que é só para uso não comercial (R-001). | Decisão do autor (spec, Clarifications 2026-11-11): é a fonte principal de clima por decisão de 2026-11-03, a única identificada com séries recentes por coordenada e licença CC BY 4.0 com atribuição. O produto está na Fase A (sem receita). | Pagar o plano comercial agora ou trocar de fonte (WWO, com 1 ano e chave de teste): mais seguros juridicamente, mas custam dinheiro ou perdem cobertura; o autor os recusou. Mitigação: atribuição em todo registro, nenhum bruto redistribuído, nada publicado nesta spec; migrar para plano comercial é gate de entrada na Fase B comercial. |

## Estratégia de Testes

Prioridade: unitário → contrato/integração → E2E local → verificação manual da fonte real. Os contratos usam fakes injetados e `httpx.MockTransport` e provam a fronteira pública, não o formato real; a validação, o cliente, a transformação e os pontos têm testes unitários próprios com fixtures sintéticas (inclusive as inválidas). O dbt é provado sobre uma Silver sintética com 308 municípios e uma janela curta (31 dias); o volume completo (730 dias) é verificado uma vez em T036. A coleta real (~21 mil a 31 mil chamadas, 3 dias) é a verificação manual distinta (T037, SC-008). **O texto real do 429 não foi verificado** (research R4); a fixture usa a forma documentada.

Comandos-base:

```powershell
uv sync --locked
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 002-ingestao-pordata-ine
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 003-ingestao-clima-open-meteo
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:caop
```

(O `dbt build` do clima e a fixture são criados em T021 a T026 e T032; ver `quickstart.md` §3.)

### Testes de Contrato

Arquivos travados em `contract-tests.lock`: `tests/contracts/test_climate_collection_contract.py` e o helper de fixtures `tests/fixtures/open_meteo/responses.py`

Comando: `uv run --locked python -m pytest -q tests/contracts/test_climate_collection_contract.py --basetemp .pytest_tmp`

Vermelho observado em 2026-11-11: **5 failed**, todos `NotImplementedError: not implemented` dos stubs (3 em `collect_open_meteo`, 1 em `make_open_meteo_fetcher`, 1 em `read_climate_response`), sem falha de import, sintaxe ou tipo. A suíte existente segue com **140 testes verdes** e o `ruff` limpo; as travas das specs 001 e 002 seguem íntegras.

| Teste | Origem | Fase | Vermelho esperado |
| --- | --- | --- | --- |
| `test_us1_ac1_ac2_fr005_fr006_fr007_each_municipality_is_stored_and_recollecting_is_unchanged` | US1/AC1–2, FR-005/006/007 | US1 (Fase 3) | `NotImplementedError` em `collect_open_meteo` |
| `test_us1_ac4_ac5_fr007_fr008_invalid_responses_fail_per_municipality_without_partial_raw_nor_state` | US1/AC4–5, FR-007/008, FR-013 | US1 (Fase 3) | `NotImplementedError` em `collect_open_meteo` |
| `test_us2_ac1_ac2_ac4_fr012_fr013_fr015_quota_stop_marks_pending_and_resume_fetches_only_pending` | US2/AC1–2/4, FR-012/013/015 | US2 (Fase 4) | `NotImplementedError` em `collect_open_meteo` |
| `test_us2_ac3_fr003_fr012_minute_limit_waits_and_daily_limit_stops_without_waiting` | US2/AC3, FR-003, FR-012, Constitution IV | US2 (Fase 4) | `NotImplementedError` em `make_open_meteo_fetcher` |
| `test_us3_ac2_ac4_ac5_fr016_fr017_staging_keeps_nulls_local_dates_and_source_units` | US3/AC2/4/5, FR-016/017, Constitution III | US3 (Fase 5) | `NotImplementedError` em `read_climate_response` |

Stubs criados pelo plan (ponto de partida do execute, não travados): `pipelines/collectors/open_meteo/{__init__,handler,fetch,validate,fingerprint,transform}.py`. Classes reais (não stub) já adicionadas a `pipelines/collectors/_shared/datasets.py`: `StopCollection` e `QuotaExhausted`.

Limitação registrada: o verificador de trava não infere a contagem de testes Python (igual às specs 001 e 002); as 5 funções foram contadas pelo runner. Enquanto as Fases 3, 4 e 5 não terminarem, o `pytest` completo falha nesses contratos e o job `quality` do CI fica vermelho nesta branch. O verificador não impõe o orçamento a arquivos Python; o limite de 5 foi respeitado à mão.

Não coberto pelos contratos (fica nos testes de fase e no `quickstart.md`): validação linha a linha do bruto, impressão digital, esperas por hora, promoção atômica, dbt, cobertura e ponto divergente, S3, CLIs e a coleta real.

## Estado Atual

| Área | Estado |
| --- | --- |
| Implementação | Fases 1–6 concluídas; Polish local concluído, gate externo pendente |
| Qualidade local | 210/210 pytest; 5/5 contratos; ruff limpo; três travas íntegras |
| dbt isolado | CAOP 31/31; observations 17/17; climate 23/23 |
| Volume sintético | 2.922.920 linhas; 555,90 MiB de pico amostrado da árvore; 117,99 MiB do Python; build 20,38 s |
| Fonte real | 71/308 atuais; 237 pending por cota horária; 673.790 linhas; 3 recoletas unchanged; zero falhas |
| Preservação real | 7 arquivos dos outros lakes com SHA-256 inalterado |
| CI remoto | [PR #3](https://github.com/johnosd/living-recommender/pull/3), commit afa0903: quality e secrets/gitleaks aprovados; 209 testes verdes e 1 específico de Windows dispensado no Linux; dbt 31/31, 17/17, 23/23 |
| Pendente | somente T037 até 308/308 e medição restante. Status segue Em Execução |

## Riscos e Decisões

<!--
  IDs estáveis (R-001, R-002...), nunca deletados. Item resolvido ganha
  prefixo "Resolvido:" na célula de Mitigação em vez de sumir da tabela.
-->

| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |
| R-001 | O plano gratuito do Open-Meteo é **só para uso não comercial** (CC BY 4.0 vale para os dados, mas a API gratuita não). | Médio: bloqueia uso comercial futuro; nada é publicado nesta spec. | Risco aceito pelo autor (spec, Clarifications). Atribuição no catálogo, no manifest e em cada linha; `usage_restriction` no catálogo; migrar para um plano comercial é gate da Fase B comercial. Complexity Tracking. |
| R-002 | O texto real do 429 (minuto/hora/dia) **não foi verificado**; a classificação se apoia em palavras-chave de uma forma documentada (research R4). | Médio: um dia classificado como hora faria esperar 1 h antes de parar. | Padrão seguro: 429 desconhecido = hora, que espera e depois pausa com `pending`, nunca falha o município. Parcialmente verificado em T037: limite horário real igual a `HOUR_LIMIT`; minuto e dia ainda não observados. Nenhuma fixture travada alterada. |
| R-003 | O peso real das requisições não é exposto pela API; a estimativa é 68 a 100 chamadas por município (21 mil a 31 mil no total). | Médio: pode exigir mais de 3 dias. | `--max-municipalities` para controlar o gasto; medir o peso real em T037 e registrar em `research.md`. A coleta é retomável por construção. |
| R-004 | Grade de ~25 km do `era5`: municípios vizinhos partilham a célula e recebem séries iguais; relevo (Serra da Estrela, Madeira) suavizado; células de mar (Corvo: 12 km, elevação 0). **Além disso, 24 meses não são uma normal climática.** | Médio para a qualidade do critério "clima". | `rpt_climate_points` mostra distância e elevação; nada é corrigido nem herdado entre vizinhos (D9). A camada Silver deve rotular o indicador "últimos 24 meses" e comparar municípios com cautela. Alternativa futura: ampliar a janela (mudança de catálogo) ou trocar de modelo. |
| R-005 | A extração de `collect_items` altera código compartilhado com a spec 002. | Alto se regredir. | Resolvido: `collect_datasets` fica como invólucro com as mesmas quatro chaves; 210/210 testes e o contrato travado da 002, o da 001 e os 140 testes são o gate (T003/T005); `check-contract-tests.ps1` das duas features em cada fase. |
| R-006 | Os meses finais da janela podem vir de reanálise preliminar e ser revistos pela fonte. | Baixo: uma recoleta pode virar `changed`. | Comportamento correto pela constitution V (bruto novo, o antigo permanece). Documentar no runbook; `--recollect` explícito. |
| R-007 | O manifest só é gravado no fim da execução. Um encerramento forçado perde o progresso (brutos órfãos), e a espera de 1 h por limite horário alonga a janela de risco. Lambda (15 min) não comporta a coleta. | Médio. | Ctrl+C é tratado (marca `pending` e grava o manifest); `--max-municipalities` permite lotes curtos; órfãos são ignorados (o estado vem só de manifests) e refeitos. Implantação futura: ECS ou lotes pequenos. |
| R-008 | A dimensão `dim_municipality` é lida de um diretório local mesmo com `--s3`. | Baixo nesta fase local. | `--silver` explícito e documentado; ler da Silver no S3 fica para a orquestração. |
| R-009 | O source dbt `caop_silver` lê `OBS_SILVER_DIR`; o build do clima precisa defini-lo. | Baixo: build falha com mensagem clara se faltar. | `build_climate` e o passo do CI definem `OBS_SILVER_DIR`; documentado em `quickstart.md` e no `_run_dbt`. Não duplicar o source (o dbt recusa nomes repetidos). |
| R-010 | Volume de 2,9 milhões de linhas e a memória do `pandas`/`pyarrow`. | Baixo. | Resolvido: escrita em fluxo, um município por vez (`ParquetWriter`); T036 confirmou 2.922.920 linhas, Python 117,99 MiB de pico e árvore de processos 555,90 MiB amostrados, com limite do DuckDB em R-015. |

| R-011 | Fixtures usam janela curta, diferente do catálogo real de 730 dias. | Baixo: build não deve confundir períodos. | `build_climate` recebe catálogo injetado ou `--catalog` explícito; o seed grava `catalog.yml`. Quickstart usa esse argumento, sem alterar o catálogo de produção. |

| R-012 | D4 e D6 divergiam sobre mudança de variáveis. | Alto: pularia coleta de variável nova. | Resolvido: autor escolheu recoleta automática em 2026-11-11; assinatura das variáveis/unidades persistida e comparada junto com janela/modelo. Deduplicação só entre configurações compatíveis, inclusive na troca de modelo com JSON igual. |
| R-013 | CSV aberto no Excel pode falhar depois da promoção dos Parquet. | Alto: relatórios e tabelas ficariam divergentes. | Promoção dos dois CSV e três tabelas numa transação com rollback; testes de PermissionError em cada destino; helper compartilhado das specs anteriores preservado. |
| R-014 | Variável extra malformada é tolerada na coleta mas podia bloquear a transformação. | Baixo: bruto aceito não chegaria ao staging. | Filtrar as variáveis declaradas antes de percorrer as séries; parâmetro opcional mantém a interface dos contratos. |

| R-015 | Volume completo teve pico amostrado de 1.501,91 MB na árvore de processos, embora Python ficasse em 119,18 MB. | Médio: acima do alvo de ~1 GB; DuckDB usava limite padrão da máquina. | Resolvido: target exclusivo `climate`, uma thread e `memory_limit: 384MB`; target `local` de CAOP/observations preservado. Volume repetido: 2.922.920 linhas, 556 MiB de pico amostrado da árvore e 118 MiB do Python; build 20,38 s. Suíte final 210/210 verde, três travas íntegras e lint limpo. |

## Execution Notes

<!--
  Tabela append-only, mantida pelo sdd-execute. Quando passar de ~40 linhas,
  arquivar as mais antigas (exceto as ~10 mais recentes) em history.md,
  substituindo por uma linha de resumo consolidado aqui.
-->

| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |
| 2026-11-11 | Fase 1 | Catálogo climático validado; fontes anteriores preservadas | Implementar núcleo compartilhado; contratos 003 ainda são stubs |
| 2026-11-11 | Fase 2 | collect_items extraído com pending, limite e parada limpa; invólucro 002 preservado | Implementar US1; baseline antes da refatoração: 146 verdes e 5 stubs |
| 2026-11-11 | Fase 3 | Coleta 308 municípios local e S3 simulado; validação e impressão digital implementadas | US2 retomada já verde pelo núcleo; faltam HTTP429 e transformação. S3 teve 2 iterações por filtro do snapshot |
| 2026-11-11 | Fase 4 | Coleta retomável com limites minuto/hora/dia, Ctrl+C, lotes e códigos 0/1/2 | Transformação e build US3 |
| 2026-11-11 | Fase 5 | Staging diário em fluxo, checksum e dbt isolado; promoção preserva outros lakes | Relatórios US4; catálogo explícito das fixtures documentado em R-011 |
| 2026-11-11 | Fase 6 | Relatórios e CSV com rollback conjunto; estado por janela/modelo/variáveis; revisão corrigida | Polish, volume, smoke real e CI remoto; regressões da revisão: 32 testes focados verdes |
| 2026-11-11 | Fase 7 | Implementação e verificação local concluídas; volume 2922920; fonte real 71/308 com 237 pending | T037: completar 308/308 após cota horária; CI remoto/gitleaks sem evidência. Não marcar Implementada ainda |
| 2026-11-11 | Fase 7 — retomada | PR #3 em rascunho autorizado e criado; CI 43107887816 com quality e secrets verdes no commit afa0903. Validação local da retomada: 11/11 e três travas íntegras. Duas tentativas reais preservaram os 71 atuais, zero bruto novo, 237 pending e retorno 2 | T037: a fonte ainda recusa por cota horária; falta 308/308 |


**PRÓXIMO**: retomar `uv run --locked python -m pipelines.cli.collect_open_meteo --local --no-wait` após a cota ficar disponível; executar `build_climate --local`; concluir T037 antes de Implementada. CI do PR #3 já confirmado; manter o PR em rascunho enquanto a coleta estiver incompleta.

## Arquivos Principais

- `sdd/specs/003-ingestao-clima-open-meteo/{tasks,quickstart,research}.md`
- `pipelines/cli/{collect_open_meteo,build_climate}.py`
- `analytics/dbt/profiles.yml` e `models/climate/`
- `docs/runbooks/coletas.md`, `.docs/fontes_de_dados.md`, `README.md`

## Cuidados para Retomada

<!-- Armadilhas operacionais específicas desta feature, anexadas conforme descobertas. -->

- A branch de execução é `feature/003-ingestao-clima-open-meteo`; commits por fase autorizados pelo autor. Alterações anteriores da spec 002 e sua linha no backlog ficaram fora dos commits desta feature.
- Estado atual inclui assinatura de variáveis/unidades por decisão do autor. Modelos/janelas/assinaturas incompatíveis não deduplicam entre si, mesmo com JSON igual.
- O target dbt do clima agora é `climate` (384 MB, uma thread); `local` continua para CAOP e observations. Use `--catalog` explícito nos builds das fixtures curtas.
- Não editar os contratos travados. A fonte confirmou só o 429 horário, idêntico à fixture; demais limites continuam sintéticos.
- Não regerar fixtures sobre roots existentes nem apagar os brutos reais. `.data/ci-climate-final` e `.data/ci-full-bounded` contêm as fixtures finais; `.data/lake/bronze/stg_climate_daily` contém a prova real parcial.
- A primeira tentativa de baseline coincidiu com a alteração de catálogo e foi invalidada; repetição estável antes da extração: 146 verdes e 5 stubs vermelhos, sem regressão anterior.
- A CLI com --no-wait salva pending e encerra ao encontrar cota. A sessão coletou até a cota horária; não completar T037 nem declarar 308/308 com 71 atuais.

### Medição reproduzível de T036

```powershell
uv run --locked python -m tests.fixtures.climate.ci_seed --root .data/volume-novo --days 730
uv run --locked python -m pipelines.cli.build_climate --local --root .data/volume-novo --catalog .data/volume-novo/catalog.yml
```

Medição em 2026-11-11 no root sintético `.data/ci-full-bounded`: seed 16,28 s; build 20,38 s; Python PeakWorkingSetSize 117,99 MiB; pico amostrado (intervalo 500 ms) da árvore uv/Python/dbt 555,90 MiB. Resultado: 2.922.920 linhas e 308 municípios. Antes do target limitado, o pico amostrado foi 1.501,91 MiB; não se confundem pico do Python e de todos os processos. A primeira tentativa do monitor lançou Python fora do PATH do uv e foi invalidada por dbt não encontrado; a repetição usou `uv run --locked`.

## Comandos do gate final executado

```powershell
uv sync --locked
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 002-ingestao-pordata-ine
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 003-ingestao-clima-open-meteo
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:caop
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:observations
# Climate: fixture em .data/ci-climate-final e CLIMATE_BUILD_DIR/CLIMATE_PREPARED_DIR/OBS_SILVER_DIR/CAOP_DUCKDB_PATH apontados para esse root.
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target climate --select tag:climate
uv run --locked python -m pipelines.cli.build_climate --local --root .data/ci-climate-final --catalog .data/ci-climate-final/catalog.yml
uv run --locked python -m pipelines.cli.build_climate --local
```

A suíte final foi executada após o target de memória; os três builds dbt foram isolados, sem serviços externos. O build real foi chamado pela função pública `build_climate(.data)` com verificação de SHA-256 dos outros 7 arquivos antes/depois; a CLI `build_climate --local` também passou, com as mesmas 673.790 linhas. Na etapa local anterior à retomada, não houve execução de UI/browser (não aplicável a pipeline sem interface), S3 real, AWS, publicação ou CI remoto; a confirmação remota posterior está registrada na seção seguinte.

## CI remoto e retomada confirmados — 2026-11-11, 22:03 UTC

- PR em rascunho: [#3](https://github.com/johnosd/living-recommender/pull/3), criado após autorização explícita do autor; head `afa0903f24d5c289071ce449fc04a6e22cd843ea`.
- [Workflow pull_request](https://github.com/johnosd/living-recommender/actions/runs/43107887816): `quality` e `secrets` concluídos com sucesso. Pytest: 209 passed, 1 skipped (teste de prefixo estendido exclusivo de Windows); lint limpo; dbt CAOP 31/31, observations 17/17, climate 23/23. Gitleaks v8.30.1 examinou 17 commits e reportou `no leaks found`.
- Código/configuração/testes locais conferidos idênticos ao commit validado no CI (`git diff --quiet afa0903 -- pipelines tests analytics config .github`). Este checkpoint altera só documentação; não há push adicional nem merge.
- Validação local desta retomada: `uv run --locked python -m pytest -q tests/contracts/test_climate_collection_contract.py tests/unit/test_local_storage_and_http.py --basetemp .data/resume-contract-tests` → 11/11; ruff limpo e três travas íntegras.
- Retomadas às 21:53 e 22:00 UTC: ambas retornaram 2 por cota horária; municípios atuais foram pulados; 237 pending, sem falhas nem bruto novo. Não presumir que a disponibilidade da fonte volte na virada da hora UTC.
- Ao capturar logs de subprocessos no Windows, definir `PYTHONIOENCODING=utf-8` no ambiente do processo; a primeira leitura UTF-8 de um log CP1252 falhou somente na apresentação, depois de a coleta já ter retornado corretamente 2. O coletor e os manifests não foram afetados.

Consultas somente leitura: `gh run list --branch feature/003-ingestao-clima-open-meteo --limit 8 --json databaseId,headSha,status,conclusion,workflowName,url,createdAt`; `gh run view 43107887816 --json headSha,status,conclusion,jobs,url`; `gh run view 43107887816 --log`.
