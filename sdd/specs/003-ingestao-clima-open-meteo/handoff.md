# Handoff para o sdd-execute: 003-ingestao-clima-open-meteo

## Contexto

- **Repositório/branch:** `living-recommender`, branch `feature/002-ingestao-pordata-ine` (não houve branch nova para a 003; confirme com o autor antes de commitar). Há alterações **não commitadas** de sessões anteriores (`.planning/backlog.md` e arquivos da spec 002) e as desta sessão; releia o `git status` antes de agir.
- **Stack:** Python 3.12 + `uv`, `httpx`, `pandas`/`pyarrow`, dbt-core + dbt-duckdb, pytest, `moto`, `ruff`. Sem dependência nova.
- **Próximo comando:** `/sdd-execute 003-ingestao-clima-open-meteo`
- **Status no backlog:** `Planejada`. São 38 tasks (T001–T038); o backlog mostra `0/54` porque o script conta toda caixa `- [ ]`, inclusive as 16 do Checklist de Release.
- **Arquivos que o plan criou ou alterou em disco:** `pipelines/collectors/_shared/datasets.py` (só duas classes novas, `StopCollection` e `QuotaExhausted`), `pipelines/collectors/open_meteo/*` (stubs), `tests/contracts/test_climate_collection_contract.py`, `tests/fixtures/open_meteo/*`.

## O que a feature entrega

- **US1 (P1):** `collect_open_meteo` baixa o clima **diário** dos 308 municípios (modelo `era5`, 13 variáveis, janela fixa 2024-11-01 a 2026-10-31 = 730 dias, **uma requisição por município**), guarda o bruto imutável e registra um manifest v2 por município (`dataset_id` = `dico`), com `unchanged` por impressão digital e falha isolada.
- **US2 (P2):** coleta **retomável** por cota. O plano gratuito comporta ~100–140 municípios/dia (~3 dias no total). Cota diária esgotada ou Ctrl+C → o município corrente e os seguintes ficam `pending`, o manifest é gravado e a CLI sai com **código 2**.
- **US3 (P2):** `build_climate` gera `stg_climate_daily` (2.922.920 linhas, formato longo, dia local, `null` preservado), testado pelo dbt e promovido por caminho.
- **US4 (P3):** relatórios `rpt_climate_coverage` e `rpt_climate_points` (+ dois CSV), com pontos devolvidos pela grade a mais de 25 km sinalizados.
- **Decisões do autor que contrariam a expectativa óbvia:** janela de **só 2 anos** (clima atual), não 10 ou 30; **sem WWO**; **sem freguesia**; licença não comercial do plano gratuito é **risco aceito**.

## Leitura obrigatória, em ordem

1. `spec.md`: o quê, user stories, FR-001…FR-023, SC-001…SC-008.
2. `plan.md`: Decisões Invariantes D1–D13, Constitution Check, Riscos R-001…R-010, comandos de teste.
3. `tasks.md`: 38 tasks por fase, contratos amarrados às fases, rastreabilidade FR/SC.
4. `logic/coleta-clima.md`: **o mais importante**: assinatura de `collect_items`, regras de estado atual, impressão digital, as 9 validações, fluxo do 429, handler, staging e cobertura.
5. `data-model.md`: entrada do catálogo (YAML pronto), entrada do manifest, colunas do Parquet, modelos Bronze.
6. `contracts/clima-cli.md`: opções, saída e códigos de saída das duas CLIs.
7. `research.md`: por que `era5`, `timezone=auto`, peso da cota, 429 não verificado.
8. `quickstart.md`: verificação manual e a coleta real (T037).
9. `.planning/memory/constitution.md`: sobretudo III (ausente é ausente) e IV (risco aceito).

## Testes de contrato

- **Arquivos travados** (`contract-tests.lock`):
  - `tests/contracts/test_climate_collection_contract.py`: **5 testes** (Fase 3: 2; Fase 4: 2; Fase 5: 1).
  - `tests/fixtures/open_meteo/responses.py`: helper (respostas sintéticas, catálogo, `MemoryStorage`, textos dos limites).
- **Comando:** `uv run --locked python -m pytest -q tests/contracts/test_climate_collection_contract.py --basetemp .pytest_tmp` (use `-k us1`, `-k us2`, `-k us3` por fase).
- **Integridade:** `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 003-ingestao-clima-open-meteo`
- **Travas de outras features que esta pode quebrar:** `-Slug 002-ingestao-pordata-ine` (`tests/contracts/test_dataset_ingestion_contract.py`) e `-Slug 001-ingestao-caop`. A T003 refatora `datasets.py`, que a 002 usa: rode as duas travas e a suíte (140 testes) em **cada** fase.
- **Estado inicial:** 5 vermelhos por `NotImplementedError`; suíte existente 140 verde; `ruff` limpo.
- O verificador não conta testes Python; o limite de 5 foi respeitado à mão.

## Stubs criados

| Arquivo | O que existe | Provisório até |
| --- | --- | --- |
| `pipelines/collectors/open_meteo/handler.py` | `collect_open_meteo` com a assinatura final e `NotImplementedError` | T010 |
| `pipelines/collectors/open_meteo/fetch.py` | `make_open_meteo_fetcher(source, *, client, sleep, wait_on_limits)` | T011 (básico), T017 (cota) |
| `pipelines/collectors/open_meteo/validate.py` | `validate_open_meteo_response(item, path)` | T008 |
| `pipelines/collectors/open_meteo/fingerprint.py` | `fingerprint_open_meteo_response(path)` | T009 |
| `pipelines/collectors/open_meteo/transform.py` | `read_climate_response(path)` + `COLUMNS` | T024 |
| `pipelines/collectors/_shared/datasets.py` | `StopCollection`, `QuotaExhausted` já **reais** (não stub) | (permanentes) |

## Armadilhas já mapeadas

- **Não use `era5_land` nem `best_match`:** o primeiro devolve 9 das 13 variáveis nulas; o segundo mistura modelos (research R1).
- **Não use o `HttpDownloader` no cliente do Open-Meteo:** ele descarta o corpo das respostas de erro, e o `reason` do 429 decide minuto/hora/dia. Reutilize só `RateLimiter`, `USER_AGENT` e `json_content_check`.
- **`generationtime_ms` varia a cada chamada:** fica fora da impressão digital (o `sha256` do manifest continua sendo o dos bytes).
- **O dia é o texto de `daily.time`:** nada de `pd.to_datetime(utc=True)` nem `tz_localize` (Açores e Madeira deslocariam dias). `value` nulo → `NaN`; **nunca** `fillna`; `0` legítimo fica `0`.
- **`collect_datasets` precisa seguir devolvendo exatamente 4 chaves** e o contrato da 002 não pode mudar. Faça `collect_items` por extração, sem reescrever a lógica.
- **`pending` nunca é estado** (`latest_dataset_states` só aceita `changed`), e uma entrada `pending` não tem `key`.
- **Estado "atual" = `reference_period` e `model` iguais ao catálogo.** `unchanged` e `changed` de `--recollect` guardam os campos extras também.
- **O source dbt `caop_silver` está em `models/bronze/schema.yml`:** não o redeclare em `models/climate/` (o dbt recusa nomes repetidos). Ele lê `OBS_SILVER_DIR`, que `build_climate` e o CI precisam definir (R-009).
- **Cada `dbt build` roda `--select tag:<feature>`:** nunca `dbt build` sem seleção (R-007 da spec 002).
- **A promoção é por caminho** (`_promote.promote_paths`); nunca troque `lake/bronze` inteiro. O DuckDB não cria o diretório de saída dos modelos externos: crie `lake/bronze/<modelo>/` antes do dbt, como `build_observations` faz.
- **Sem rede em nenhum teste:** `httpx.MockTransport` e fetchers fake. S3 só com `moto`.
- **O texto real do 429 não foi verificado (R-002).** A fixture usa a forma documentada; 429 desconhecido = hora.
- **Ctrl+C:** `KeyboardInterrupt` não é `Exception`; trate-o em `_collect_one` e em `collect_items` (T003), senão o bruto do item interrompido fica órfão.
- **Windows/PowerShell:** os comandos do quickstart são PowerShell. O console pode exibir acentos errados (cp1252); não é um defeito do arquivo.
- **O pandas não está declarado no `pyproject.toml`** (vem de dependências transitivas, como na 002); não "corrija" isso nesta feature.

## Pendências do Analyze

| ID | Severidade | Resumo | Recomendação |
| --- | --- | --- | --- |
| A-001 | resolvido | Spec dizia que a 2ª execução termina "todos `unchanged`"; o plano (D6) pula os atuais. | **Resolvido em 2026-11-11:** `spec.md` (US1/AC2–3, teste independente da US1, SC-001) alinhada ao FR-013; Clarifications registradas. Nada a fazer no código. |
| A-002 | resolvido | Spec dizia que minuto/hora geram espera, "não interrupção"; o plano limita as esperas e oferece `--no-wait`. | **Resolvido em 2026-11-11:** `spec.md` (FR-012, US2/AC3) alinhada ao plano (espera limitada, depois `pending`); Clarifications registradas. Nada a fazer no código. |
| A-003 | LOW | A estimativa de cota da spec (~70 chamadas/município, ~20 mil) é o limite inferior da do plano (68–100; 21 mil a 31 mil). | Ajustar a Assumption da spec depois da medição real (T037). |
| A-004 | LOW | Execução concorrente (edge case da spec) não tem teste dedicado; o comportamento é herdado do `run_id` único e do estado por manifest. | Aceitar ou acrescentar um teste de duas execuções simultâneas em T015. |

## Gate de pronto

- 5/5 contratos verdes e as três travas íntegras (`check-contract-tests.ps1` para 001, 002 e 003).
- `uv run --locked ruff check pipelines tests` limpo.
- `uv run --locked python -m pytest -q --basetemp .pytest_tmp` verde (sem rede; ~2 min).
- `dbt build --select tag:caop`, `tag:observations` e `tag:climate` verdes isoladamente (o do clima sobre `tests.fixtures.climate.ci_seed`, com `OBS_SILVER_DIR=.data/ci-climate/lake/silver`).
- CI verde (passo novo do dbt do clima).
- Docs a atualizar no Polish: `config/sources.yml`, `.docs/fontes_de_dados.md` (§3.3, §3.4, §4), `docs/runbooks/coletas.md`, `README.md`.
- **Passada real é recomendação forte, não gate de merge:** T037 (coleta de ~3 dias, SC-008) mede o peso real da cota e confere o texto do 429. Registre o resultado em `research.md` (R3, R4) e em Execution Notes.

## Checkpoint após execução — 2026-11-11 (prevalece sobre o retrato de planejamento acima)

Fases 1–6 implementadas e commitadas por fase na branch `feature/003-ingestao-clima-open-meteo`. Gate final local: 210/210 testes, 5/5 contratos, três travas íntegras e ruff limpo; dbt CAOP 31/31, observações 17/17 e clima 23/23. Use **target `climate`** para o clima, com 384 MB e uma thread; `local` continua para as outras fontes. Volume: 2.922.920 linhas e pico amostrado de 555,90 MiB da árvore de processos.

D6/FR-013 foram emendados por decisão explícita do autor: mudanças nas variáveis/unidades também provocam recoleta, com assinatura persistida. JSON idêntico de outro modelo deve gerar novo estado. A promoção agora inclui rollback dos CSV e das três tabelas. Variáveis extras são filtradas antes da transformação.

Fonte real: 71/308 municípios atuais, 237 pendentes por limite horário, 3 recoletas unchanged e 673.790 linhas reais no Bronze; 7 arquivos dos outros lakes preservados byte a byte. O texto horário real coincide com a fixture; minuto/dia não foram observados. **Não alterar fixtures travadas.** T037 e CI remoto continuam pendentes; o status permanece Em Execução. Retomar pelo PRÓXIMO e Estado Atual de plan.md; tasks.md é a fonte de verdade. Não incluir alterações anteriores da spec 002 nos commits da 003.
