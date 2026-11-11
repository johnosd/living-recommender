# Implementation Plan: Ingestão Pordata e INE

**Slug**: `002-ingestao-pordata-ine` | **Date**: 2026-11-11 | **Spec**: `sdd/specs/002-ingestao-pordata-ine/spec.md`

## Summary

Estender o padrão de coleta da CAOP a duas fontes com **vários datasets independentes**: 16 CSV do Pordata por HTTP, 3 indicadores da API JSON do INE (rendas, criminalidade, poder de compra) e 1 planilha do Pordata carregada à mão. O novo coletor genérico (`collect_datasets`) guarda cada dataset como bruto imutável, com estado vigente próprio, manifest v2 por dataset, `unchanged` por impressão digital e **tolerância a falha por dataset**. Depois, um passo Python prepara um Parquet longo e resolve o município (nome + seed no Pordata; código no INE), e o dbt-duckdb testa a qualidade e materializa um único staging Bronze `stg_observation`, mais um relatório de cobertura (a resolução em Python e o Parquet sem particionamento físico estão no R-010). A CAOP, seu contrato travado e seu lake **não mudam**.

## Technical Context

**Language/Version**: Python 3.12 (`.python-version`), SQL/dbt Core. Mesma base da spec 001.

**Primary Dependencies**: já instaladas — `httpx`, `PyYAML`, `boto3`, `pyarrow`, `pandas`, `dbt-core`, `dbt-duckdb`; dev: `moto[s3]`, `pytest`, `ruff`. **Nova:** `openpyxl` (leitura da planilha manual, modo somente leitura). O adapter dbt-duckdb aceita `options` (`partition_by`) na materialização `external` e `external_location` em `source` ([documentação](https://github.com/duckdb/dbt-duckdb/blob/master/README.md); research R7).

**Storage**: `.data/` local e S3 com o mesmo layout: `raw/source=<id>/dataset=<dataset>/run_id=<run>/<arquivo>`, `manifests/<source_id>/<run_id>.json`, `lake/bronze/stg_observation/` e `lake/bronze/rpt_observation_coverage/` (Parquet). Reutiliza `LocalStorage` e `S3Storage` sem alterá-los.

**Testing**: pytest sem rede, com fakes injetados (fetcher, validator, storage) e fixtures sintéticas; moto para o S3; `dbt build` sobre uma Silver sintética. 5 contratos P1 travados. Padrão idêntico ao da 001.

**Target Platform**: Windows local nesta feature, portátil para ECS/Lambda (ADR-002). Sem deploy.

**Performance Goals**: nenhuma meta numérica. O download total do Pordata é ~82 MB (o dataset 1 tem 45 MB) e o do INE ~6 MB; arquivos vão para disco temporário, nunca inteiros na memória (o `HttpDownloader` já faz streaming).

**Constraints**: raw imutável; estado por dataset; ausência nunca vira zero; município não resolvido reprova; CAOP e seu lake intactos; nenhuma credencial em arquivo versionado; nenhum bruto real no Git; API do INE instável (timeouts de 60 s observados) e sem validadores HTTP.

**Scale/Scope**: 20 datasets (16 + 1 + 3), ~300 mil a 700 mil linhas municipais no maior CSV (dataset 1: 606 mil), 308 municípios. Volume total bem abaixo de 1 GB (ADR-001). Custo recorrente: US$ 0 (local e S3 simulado).

## Decisões Invariantes

- **D1. O dataset é a unidade.** Coleta, validação, impressão digital, estado vigente e falha são por dataset. O manifest é **v2** (`datasets[]`) e convive com o v1 da CAOP (`files[]`); o código e os manifests da CAOP não mudam.
- **D2. Falha por dataset não propaga.** `collect_datasets` devolve `changed`, `unchanged`, `partial` ou `failed` e só levanta exceção antes de começar (catálogo, `run_id`, destino). O CLI traduz `partial`/`failed` em código de saída 1. Uma entrada `failed` nunca é estado vigente.
- **D3. Bruto como veio; mudança por impressão digital.** CSV e planilha: `sha256` dos bytes. INE: `sha256` do JSON canônico **sem `DataExtracao`** (a API envia o horário da chamada e nenhum `ETag`). Sem GET condicional no v1; `ETag`/`Last-Modified` são só registrados.
- **D4. CSV do Pordata é validado e lido pelo rótulo.** O prefixo numérico das colunas varia (`Escala` é `07` ou `08`; o dataset 4 tem `Max. 08. Escala`; os datasets 1 e 559 têm `Nome País`). Linha municipal = `Âmbito Geográfico = "Município"`.
- **D5. Resolução territorial.** Pordata e planilha: nome → seed de sinônimos (5 linhas) ou nome normalizado **único**; ambiguidade ou ausência reprova, nunca palpite. INE: `dico = geocod[-4:]`, validado contra a dimensão. Pedir ao INE só `Dim2=lvl@5` (município); `Dim3=T,1,2,3,4,5,6` na criminalidade.
- **D6. Duas etapas, como na CAOP.** Python prepara um Parquet **longo e único** (parsing de CSV, JSON e XLSX); a resolução do município roda em Python (a função do contrato) e o dbt testa e materializa **um** modelo `stg_observation`, com `source_id`/`dataset_id` como colunas (sem particionamento físico; ver R-010), e o modelo de cobertura. O staging parte do **estado vigente de cada dataset**, conferido pelo `sha256` do bruto.
- **D7. Promoção por caminho, dbt por tag.** A promoção troca só `lake/bronze/stg_observation` e `lake/bronze/rpt_observation_coverage`; **nunca** `lake/bronze` ou `lake/silver` inteiros. Os modelos ganham as tags `caop` e `observations`; cada `build_*` roda `dbt build --select tag:<...>`.
- **D8. Ausente é ausente.** `value` nulo + `symbol` preservado; nunca 0, nunca estimado. Linhas de agregação do Pordata são excluídas e contadas.
- **D9. A carga manual usa o mesmo caminho.** `load_pordata_manual` chama `collect_datasets` com um fetcher que copia o arquivo do operador; o dataset tem estado e manifest como os outros. Leitor de Excel: `openpyxl`.
- **D10. Fora desta feature:** freguesia, Silver de indicadores, Gold, `published/`, deploy e agendamento, conditional GET, os datasets 845/294/445/447/582.

## Constitution Check

*GATE pré-design verificado após ler a constitution e os ADR-001/002; pós-design reavaliado depois de `research.md`, modelo, contratos e lógica.*

| Princípio | Pré-Design | Pós-Design | Notas |
| --- | --- | --- | --- |
| I. Nenhum segredo fora do cofre | Conforme | Conforme | Fontes públicas, sem chave. Modo local sem credenciais; S3 pela cadeia padrão da AWS. Os testes usam credenciais falsas do moto. `gitleaks` no CI. |
| II. Núcleo estático e sem chave | Conforme | Conforme | Nenhum servidor, API própria ou publicação. |
| III. Dados honestos e rastreáveis | Conforme | Conforme | Ausência explícita, junção por `dico` da CAOP, município sem correspondência reprova, fonte/período/licença em cada linha, cobertura medida. **Ressalva:** o Pordata não tem licença concedida (R-001); a publicação de indicadores derivados é de outra spec. |
| IV. Coleta responsável e licenciada | **Exceção justificada** | **Exceção justificada** | Catálogo antes do coletor, User-Agent, rate limit, retry e backoff: conformes. Os termos do Pordata não concedem reutilização; o autor decidiu coletar mesmo assim. Registrada como risco aceito (R-001), com mitigação e alternativa, como a constitution admite. |
| V. Bruto imutável e publicação atômica | Conforme | Conforme | Raw sem sobrescrita; `unchanged` sem raw novo; promoção atômica por caminhos (D7). Sem `current.json` nesta feature. |
| VI. Privacidade por padrão | Conforme | Conforme | Só estatísticas públicas por município; nenhum dado pessoal. |
| VII. Custo como requisito | Conforme | Conforme | Local e S3 simulado: US$ 0/mês. Nenhum recurso AWS criado. |

**Resultado:** nenhuma violação não justificável. A única exceção (princípio IV, Pordata) foi decidida pelo autor e está em Complexity Tracking e em R-001.

## Project Structure

### Documentation (this feature)

```text
sdd/specs/002-ingestao-pordata-ine/
├── spec.md
├── plan.md                  # este arquivo
├── tasks.md
├── research.md              # medições reais de 2026-11-11
├── data-model.md            # catálogo, manifest v2, staging, cobertura
├── contracts/ingestao-cli.md
├── logic/ingestao-datasets.md
├── quickstart.md
├── handoff.md
└── contract-tests.lock
```

### Source Code (repository root)

Estado real encontrado (spec 001) e o que esta feature acrescenta (`+`):

```text
config/sources.yml                                   # + pordata e ine
pipelines/
  cli/        collect_caop.py build_caop.py view_caop.py
              + collect_pordata.py collect_ine.py load_pordata_manual.py build_observations.py
  collectors/
    _shared/  catalog.py http.py manifest.py storage.py storage_s3.py
              + datasets.py (stub) dataset_manifest.py municipality.py (stub) observations.py
    caop/     handler.py schema.py transform.py names.py            # intocados
    + pordata/  validate.py handler.py transform.py xlsx.py
    + ine/      fingerprint.py (stub) validate.py fetch.py handler.py transform.py
analytics/dbt/
  models/staging/ stg_caop_*.sql                     # + tag caop
  models/marts/   dim_*.sql                          # + tag caop
  + models/bronze/ stg_observation.sql rpt_observation_coverage.sql sources.yml schema.yml
  + seeds/municipality_synonyms.csv
  tests/caop_quality.sql                             # + tag caop; + tests/observations_*.sql
tests/
  contracts/  test_caop_collection_contract.py (travado 001)
              + test_dataset_ingestion_contract.py (travado 002)
  unit/ integration/ fixtures/caop/                  # + fixtures/pordata/ fixtures/ine/
docs/runbooks/coletas.md  README.md  .docs/fontes_de_dados.md      # atualizar no Polish
.github/workflows/python.yml                         # dbt por tag
```

**Structure Decision:** seguir o desenho `pipelines/collectors/<fonte>/` da 001. O comum vai em `_shared/` (`datasets.py`, `dataset_manifest.py`, `municipality.py`, `observations.py`), sem tocar `manifest.py`, `handler.py` ou o contrato da CAOP. As CLIs seguem o padrão `collect_*`/`build_*`.

## Complexity Tracking

| Violação | Por que é necessária | Alternativa mais simples rejeitada porque |
| --- | --- | --- |
| Princípio IV: coletar o Pordata, cujos termos não concedem reutilização (R-001). | Decisão do autor em 2026-11-11 ("os dados são públicos"). nenhum dos 16 CSV tem equivalente já mapeado na API do INE (só o poder de compra foi verificado), e o Pordata é a base dos critérios de cultura, educação, saúde, emprego e população. | Abandonar o Pordata, ou pedir autorização antes de coletar, ou migrar tudo para o INE: mais seguros juridicamente, mas bloqueiam ou reescrevem a feature; o autor os recusou. Mitigação: atribuição, nenhum bruto redistribuído, e publicação de derivados só em outra spec, onde a licença será reavaliada. |

## Estratégia de Testes

Prioridade: unitário → contrato/integração → E2E local → verificação manual da fonte real. Os contratos usam fakes injetados e provam a fronteira pública, não os formatos reais; os validadores e transformações são cobertos por fixtures sintéticas nos três layouts de CSV, no JSON do INE e na planilha. O dbt é provado sobre uma Silver sintética. A coleta real (82 MB do Pordata, ~6 MB do INE, mais a planilha do autor) é verificação manual distinta (T035).

Comandos-base:

```powershell
uv sync --locked
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 002-ingestao-pordata-ine
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:caop
```

(O `dbt build` das observações e a fixture correspondente são criados em T022 a T024.)

### Testes de Contrato

Arquivo travado em `contract-tests.lock`: `tests/contracts/test_dataset_ingestion_contract.py`

Comando: `uv run --locked python -m pytest -q tests/contracts/test_dataset_ingestion_contract.py --basetemp .pytest_tmp`

Vermelho observado em 2026-11-11: **5 failed**, todos `NotImplementedError: not implemented` dos stubs, sem falha de import, sintaxe ou tipo. A suíte existente segue com 38 testes verdes e o `ruff` limpo.

| Teste | Origem | Fase | Vermelho esperado |
| --- | --- | --- | --- |
| `test_us1_ac1_fr004_fr005_every_dataset_is_stored_with_its_own_manifest_entry` | US1/AC1, FR-004/005 | US1 (Fase 3) | `NotImplementedError` em `collect_datasets` |
| `test_us1_ac2_ac3_fr006_unchanged_is_per_dataset_and_only_the_changed_one_writes_raw` | US1/AC2–3, FR-006 | US1 (Fase 3) | `NotImplementedError` em `collect_datasets` |
| `test_us1_ac4_ac5_fr007_fr008_failures_do_not_block_the_others_nor_become_state` | US1/AC4–5, FR-007/008 | US1 (Fase 3) | `NotImplementedError` em `collect_datasets` |
| `test_fr006_ine_response_is_unchanged_when_only_the_extraction_time_differs` | FR-006, research R3 | US2 (Fase 4) | `NotImplementedError` em `fingerprint_ine_response` |
| `test_us3_ac2_ac3_fr013_fr014_homonyms_use_explicit_rules_and_unresolved_names_fail` | US3/AC2–3, FR-013/014, Constitution III | US3 (Fase 5) | `NotImplementedError` em `resolve_municipality_names` |

Stubs criados pelo plan (não travados, ponto de partida do execute): `pipelines/collectors/_shared/datasets.py`, `pipelines/collectors/_shared/municipality.py`, `pipelines/collectors/ine/__init__.py`, `pipelines/collectors/ine/fingerprint.py`.

Limitação registrada: o verificador de trava não infere a contagem de testes Python (igual à spec 001); a contagem de 5 foi conferida pelo runner. Enquanto as Fases 3, 4 e 5 não terminarem, o `pytest` completo falha nesses contratos, e o job `quality` do CI fica vermelho nesta branch.

## Estado Atual

<!-- Sobrescrita a cada checkpoint pelo sdd-execute. Vazia na criação. -->

| Área | Estado |
| --- | --- |
| Fase | Todas as fases e o Checklist de Release concluídos (T001–T038), incluindo a Phase 9 de convergência. Resta rodar o `sdd-converge` outra vez. |
| Coleta | `collect_pordata`, `collect_ine` e `load_pordata_manual` verificados contra as fontes reais; o manifest v2 registra o método de coleta por dataset (`http_download`, `api_json`, `manual_upload`) e, na execução, o método comum ou `mixed`. |
| Staging | `build_observations` verificado contra a Silver real: 1.168.860 observações de 20 datasets, 308 municípios resolvidos, ausência nula com símbolo, cobertura por dataset; CAOP e seu lake intactos. |
| Contratos | 5 de 5 da 002 verdes (e 5 de 5 da CAOP); trava da 002 e da 001 íntegras. |
| Testes | 140 testes verdes; `dbt build` com 31 passos (tag `caop`) e 17 passos (tag `observations`); ruff limpo. |
| CI | Verde no GitHub em `d511ec5` (PR #2, mergeado). A Phase 9 ainda não foi enviada ao GitHub. |

## Riscos e Decisões

<!--
  IDs estáveis (R-001, R-002...), nunca deletados. Item resolvido ganha
  prefixo "Resolvido:" na célula de Mitigação em vez de sumir da tabela.
-->

| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |
| R-001 | **Risco aceito pelo autor (2026-11-11):** os Termos Legais do Pordata não concedem licença de reutilização e a cláusula 5.4 pede que se evite reproduzir e colocar o conteúdo à disposição do público. O `.docs` assumia "uso livre com citação" sem fonte. | Alto para a publicação; baixo para a coleta interna. A constitution III exige licença por indicador publicado. | Atribuição "Fonte: PORDATA" (e do INE onde a série for dele); bruto fora do Git e nunca redistribuído; `license_id: not_granted_by_source` no catálogo e em cada linha; a spec de publicação (Gold/`published/`) reavalia a licença antes de expor derivados. Alternativa documentada: séries equivalentes do INE (CC BY 4.0). Contato público dos termos: `pordata@ffms.pt`. |
| R-002 | A API do INE é instável: 2 de 6 pedidos de metadados deram timeout de 60 s; a de dados leva 3 a 6 s; não envia `ETag`. | Médio: falhas intermitentes de coleta. | Timeout de 90 s, até 3 tentativas com espera crescente, limite de taxa; falha por dataset (D2); impressão digital sem `DataExtracao` (D3). |
| R-003 | As URLs do blob do Pordata são internas e mudam sem aviso (o `Modelo_N` varia por tabela e a planilha antiga morreu). | Médio: dataset `failed` até corrigir o catálogo. | Falha explícita por dataset; catálogo versionado e revisado; validação por rótulos detecta mudança de estrutura; cada dataset é independente. |
| R-004 | As rendas do INE cobrem só 222 a 247 dos 308 municípios (mínimo de contratos por unidade). O `.docs` dizia "todos". | Médio: critério de custo sem dado em ~20% dos municípios. | Ausência explícita (`symbol`), relatório de cobertura (US4), correção do `.docs` no Polish; o fallback de aluguel (Idealista) é de outra spec. |
| R-005 | `openpyxl` é dependência nova, e o layout hierárquico da planilha do Pordata pode mudar. | Baixo: só a carga manual. | Resolvido: validação estrita (abas, cabeçalho de anos, 308 municípios) provada com fixtures inválidas e com a planilha real do autor (3.388 observações, `sha256` do arquivo intacto); falha explícita. |
| R-006 | `build_caop._promote` troca `lake/bronze` e `lake/silver` **inteiros**; reutilizá-lo apagaria a CAOP. | Alto se ocorrer. | Resolvido: D7 implementado em `pipelines/cli/_promote.py` e usado pelos dois builds; `test_the_caop_lake_is_left_byte_for_byte_untouched` e `test_rebuilding_the_caop_does_not_erase_the_observation_staging` provam a convivência. |
| R-007 | `dbt build` sem seleção, usado hoje por `build_caop` e pelo CI, passaria a executar os modelos novos sem entradas. | Alto: quebra o build da CAOP e o CI. | Resolvido: tags `caop`/`observations` e `--select tag:<...>` no `build_caop`, no `build_observations` e no workflow; os dois `dbt build` (31 e 11 passos) passam isolados. |
| R-008 | Se o INE passar a incluir outro campo volátil além de `DataExtracao`, a impressão digital mudaria sempre. | Médio: falsos `changed`. | Resolvido: a coleta real de 2026-11-11 expôs um segundo elemento variável, a **ordem das linhas** da criminalidade (2 de 12 períodos, sem diferença de conteúdo). A impressão digital passou a ordenar os registros, com teste de regressão e confirmação nas duas respostas reais; depois, duas coletas seguidas deram `unchanged` nos 3 indicadores. Estados gravados com o algoritmo anterior apareceriam como `changed` uma vez. |
| R-009 | Um município renomeado na fonte reprova o staging. | Baixo: é o comportamento desejado. | Falha lista os nomes; a seed (5 linhas) é mantida à mão, em PR. |
| R-010 | **Decisão de execução:** a resolução do município ficou **em Python** (a função do contrato, reutilizada), e o dbt testa o resultado (`not_null`, `relationships`); o plano previa a resolução em SQL pelo seed. O `stg_observation` ficou **sem particionamento físico**: um `data.parquet` único com `source_id`/`dataset_id`, como na CAOP. | Baixo: evita duas implementações da mesma regra e simplifica a promoção; a leitura por dataset continua por filtro. | Uma só regra testada pelo contrato 5; o particionamento por dataset pode ser reavaliado se o volume crescer (hoje ~1,2 milhão de linhas). |
| R-011 | **Decisão de execução:** o `build_caop` passou a promover **por tabela** (`promote_paths`), em vez de trocar `lake/bronze` e `lake/silver` inteiros. | Médio se não feito: reconstruir a CAOP apagaria o staging de observações. | Resolvido: testes do `build_caop` (5 testes de build) seguem verdes e `test_rebuilding_the_caop_does_not_erase_the_observation_staging` prova a convivência. |
| R-012 | **Decisão de convergência (F-001):** o manifest v2 registra o método de coleta **por dataset**, e o da execução é o comum ou `mixed`. Antes, a carga manual do Pordata gravava `http_download` (o método da fonte). | Baixo: trilha de auditoria imprecisa, sem efeito sobre o estado dos datasets nem sobre o staging. | Resolvido: corrigido em `datasets.py`/`dataset_manifest.py`, com testes nas três CLIs e verificação no manifest real; manifests antigos continuam legíveis. |

## Execution Notes

<!--
  Tabela append-only, mantida pelo sdd-execute. Quando passar de ~40 linhas,
  arquivar as mais antigas (exceto as ~10 mais recentes) em history.md,
  substituindo por uma linha de resumo consolidado aqui.
-->

| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |
| 2026-11-11 | Setup | T001 concluída: `openpyxl>=3.1,<4` adicionado e `uv.lock` regravado; ruff limpo. | Foundational: catálogo, http, manifest v2 e isolamento do dbt (T002–T006). |
| 2026-11-11 | Foundational | T002–T006 concluídas: catálogo de datasets e `sources.yml` (pordata/ine), `content_check` no `HttpDownloader`, manifest v2, dbt isolado por tag `caop`; 54 testes e `dbt build` 31/31 verdes. | US1: `collect_datasets` e a CLI do Pordata (T007–T013). |
| 2026-11-11 | US1 | T007–T013 concluídas: `collect_datasets`, validador de CSV por rótulo, `collect_pordata` e CLIs comuns; contratos US1 3/3 verdes; 87 testes verdes, incluindo falha parcial, concorrência e paridade local×S3. | US2: impressão digital e coleta do INE (T014–T019). |
| 2026-11-11 | US2 | T014–T019 concluídas: impressão digital do INE, validador, fetcher, `collect_ine` e CLI; contratos 4/5 verdes; 101 testes verdes, incluindo `unchanged` com outro `DataExtracao`, falha parcial e paridade local×S3. | US3: resolução de município, Parquet longo, dbt e `build_observations` (T020–T026). |
| 2026-11-11 | US3 | T020–T026 concluídas: resolução de município (contrato 5), Parquet longo, dbt `stg_observation`, `build_observations` com promoção por tabela (também no `build_caop`) e fixture; 5/5 contratos da 002 verdes, 118 testes e dbt 31 + 11 passos verdes. | US4: relatório de cobertura (T027–T028). |
| 2026-11-11 | US4 | T027–T028 concluídas: modelo de cobertura, teste de consistência, `coverage.csv` e tabela no terminal; 123 testes e dbt 31 + 17 passos verdes. | US5: planilha manual do Pordata (T029–T033). |
| 2026-11-11 | US5 | T029–T033 concluídas: leitor e validador da planilha com `openpyxl`, `load_pordata_manual`, fixture e testes; validado também com a planilha real do autor (3.388 observações); 135 testes e dbt 31 + 17 passos verdes. | Polish: documentação, coleta real e gate final (T034–T036). |
| 2026-11-11 | Phase 8 (Polish) | T034–T036 concluídas: documentação alinhada; coleta real das três fontes e build contra a Silver real (1.168.860 observações, 308 municípios, CAOP intacta); achado e correção da ordem variável das linhas do INE (R-008); gate local e `gitleaks` (dir e git) limpos; reprodução do CI em Linux verde (138 + 1 pulado). | CI no GitHub (exige enviar a branch); depois `sdd-converge`. |
| 2026-11-11 | CI | Branch enviada (commit `d511ec5`) e PR #2 mergeado: `Python quality` verde no GitHub em push e em pull_request, com os passos novos do dbt de observações e o job `secrets`. Último item do Checklist de Release marcado; status Implementada. | `sdd-converge`. |
| 2026-11-11 | Phase 9 (Convergence) | T037–T038 concluídas: método de coleta registrado por dataset no manifest v2 (a carga manual deixou de gravar `http_download`), com testes e verificação no dado real; `quickstart.md` corrigido; 140 testes e dbt 31 + 17 passos verdes. | `sdd-converge` outra vez; enviar a Phase 9 ao GitHub. |

**PRÓXIMO**: Rodar o `sdd-converge` outra vez para confirmar que não restam achados e sincronizar o status final; a Phase 9 ainda precisa ser enviada ao GitHub para o CI rodar sobre ela.

## Arquivos Principais

<!-- Sobrescrita a cada checkpoint — foco da etapa atual, não a árvore inteira. -->

- `pipelines/collectors/_shared/datasets.py` e `dataset_manifest.py` — `collection_method` por dataset e método da execução.
- `sdd/specs/002-ingestao-pordata-ine/data-model.md` e `quickstart.md` — regra do método e correções de documentação.
- `tests/unit/test_dataset_catalog_and_manifest.py` e os testes de integração das três CLIs — prova do método por dataset.

## Cuidados para Retomada

<!-- Armadilhas operacionais específicas desta feature, anexadas conforme descobertas. -->

- `HttpDownloader` agora recebe `content_check`; o padrão continua `zip_content_check`. Para CSV use `csv_content_check` e para a API do INE `json_content_check` com `timeout=90`. O `last_headers` é preenchido só depois de um download bem-sucedido.
- Datasets herdam `expected_labels`, `name_column` e `api_url` da fonte via `get_dataset_source`; leia a lista de datasets sempre por essa função (ela devolve os datasets já mesclados), nunca direto do YAML.
- `collect_datasets` lista `existing = storage.list_keys()` e lê os manifests uma vez; datasets `manual_upload` precisam ser excluídos por `dataset_ids` (feito em `pordata/handler.py`), senão o fetcher HTTP tentaria baixar uma planilha sem `origin`.
- As CLIs novas reutilizam `pipelines/cli/_common.py` (destino, `run_id`, resumo, código de saída). A `collect_caop` continua com o parser próprio; não a migre.
- No INE, `reference_period` e `source_release_date` do manifest vêm do JSON baixado (`UltimoPref`, `DataUltimoAtualizacao`), lidos pelo fetcher; se o JSON for inválido, quem reprova é o validador, nunca o fetcher.
- O teste de falha parcial do INE e os do Pordata dependem de `offline_downloader(..., failing=...)` em `tests/fixtures/pordata/layouts.py`, reutilizado pelo INE.
- O `build_caop` agora promove por tabela (`stg_caop_*`, `dim_*`), nunca `lake/bronze` ou `lake/silver` inteiros; o `build_observations` faz o mesmo com `stg_observation` e `rpt_observation_coverage`. Qualquer novo build do lake deve usar `pipelines/cli/_promote.py`.
- O `dbt build` das observações lê a Silver da CAOP por `source('caop_silver', 'dim_municipality')` com `OBS_SILVER_DIR`; sem a Silver o `build_observations` falha antes com a instrução de rodar `build_caop`.
- A resolução do município acontece em Python (`_resolve` em `build_observations.py`); o dbt só testa o resultado. Para o INE vale `geocod[-4:]`; para o Pordata, a seed `analytics/dbt/seeds/municipality_synonyms.csv` lida pelo Python (a seed não é tagueada e o dbt só a carregaria num `dbt seed`/`dbt build` sem seleção).
- Todo modelo externo novo precisa que o diretório de saída exista antes do `dbt build`: acrescente o caminho a `PROMOTED` em `build_observations.py` e à fixture `ci_seed.py`; o DuckDB não cria diretórios.
- Os testes que só leem o resultado de `build_observations` devem compartilhar um build por módulo (fixture `scope="module"` com `tmp_path_factory`): cada build roda o dbt (~5 a 8 s).
- A carga manual só lê o arquivo do operador (`shutil.copyfile` para o temporário); nunca o move, altera ou copia para dentro do repositório. A planilha real do autor fica fora do Git e só é usada na T035.
- `parse_pordata_xlsx` exige exatamente 308 linhas `Município`: se o Pordata mudar o layout (aba, cabeçalho ou contagem), a carga falha com o motivo em vez de aceitar uma planilha incompleta.
- Mudar o algoritmo da impressão digital do INE faz os estados já gravados (com o algoritmo anterior) aparecerem como `changed` uma vez por dataset: aceitável, mas é um raw extra por indicador. Foi o que ocorreu na coleta real de 2026-11-11, e por isso as coletas do INE feitas antes da correção foram descartadas e refeitas.
- Ao chamar `docker run -w /repo` use o PowerShell: o Git Bash converte `/repo` num caminho do Windows e o Docker recusa (`working directory ... is invalid`). Para o `gitleaks` no modo `dir`, varra uma cópia limpa dos arquivos (`git ls-files -co --exclude-standard`), nunca a raiz com `.data` e `.venv`.
- A cobertura que importa para o Gold está em `.data/lake/bronze/coverage.csv`: `ensino_nao_superior` tem o último ano (2024) vazio, então use `latest_period_with_data` (2023) e não `latest_period`.
- Leia o método de coleta sempre da **entrada do dataset**; o do nível da execução é um resumo (`mixed` quando há mais de um). Manifests anteriores a 2026-11-11 não têm o campo na entrada e valem o método da execução.
