# Implementation Plan: Correspondência de freguesias 2013→2025

**Slug**: `004-correspondencia-freguesias` | **Date**: 2026-11-12 | **Spec**: `sdd/specs/004-correspondencia-freguesias/spec.md`

## Summary

Coletar as duas tabelas oficiais do INE (código pré-2013 → 2013, e pré-2013 → 2025 para as 302 freguesias repostas) como uma fonte catalogada de dois datasets, reaproveitando `collect_datasets` sem alterá-lo. Uma função pandas determinística encadeia as tabelas pelo código pré-2013 e produz uma linha por par (2013, 2025), com a natureza da relação e os sinais de herança, origem parcial, mudança de nome e de município. Um gate em Python reprova a promoção se a tabela não cobrir toda a `dim_parish`; o dbt testa e materializa a tabela e um relatório de cobertura, promovidos por caminho em `lake/silver`. A pesquisa mostrou que a derivação fecha **100%** contra a `dim_parish` real, então não há interseção espacial nem pesos. CAOP, Pordata, INE e clima **não mudam**.

## Technical Context

**Language/Version**: Python 3.12 (`.python-version`), SQL/dbt Core. Mesma base das specs 001 a 003.

**Primary Dependencies**: já instaladas: `httpx`, `PyYAML`, `boto3`, `pandas`, `pyarrow`, `openpyxl`, `dbt-core`, `dbt-duckdb`; dev: `moto[s3]`, `pytest`, `ruff`. **Nenhuma dependência nova.**

**Storage**: `.data/` local e S3 com o mesmo layout: `raw/source=ine_parish_crosswalk/dataset=<id>/run_id=<run>/<id>.xlsx`, `manifests/ine_parish_crosswalk/<run_id>.json`, `lake/silver/xwalk_parish_2013_2025/` e `lake/silver/rpt_parish_crosswalk_coverage/` (Parquet), mais dois CSV legíveis: `lake/silver/parish_crosswalk_report.csv` (o relatório, com versão da CAOP, data e atribuição em todas as linhas) e `lake/silver/parish_crosswalk_review.csv` (os pares para revisão). Reutiliza `LocalStorage` e `S3Storage` sem alterá-los.

**Testing**: pytest sem rede, com downloader e storage injetados e planilhas sintéticas no layout real; moto para o S3; `dbt build` sobre uma Silver sintética. 5 contratos travados (ver Estratégia de Testes).

**Target Platform**: Windows local nesta feature, portátil para ECS/Lambda (ADR-002). Sem deploy.

**Performance Goals**: nenhuma meta numérica. Duas planilhas (205 KB e 27 KB) e ~4,6 mil linhas; a derivação e o dbt levam segundos.

**Constraints**: bruto imutável; estado por tabela; `dim_*` e demais fontes intactas (SC-006); nenhum segredo; nenhuma planilha real no Git; os links `smi.ine.pt/Versao/Download/N` não têm estabilidade garantida (falha explícita).

**Scale/Scope**: 2 tabelas, 3.260 pares, 3.259 freguesias. Custo recorrente: US$ 0 (local e S3 simulado).

## Decisões Invariantes

- **D1. Uma fonte, dois datasets.** `ine_parish_crosswalk` com `reorganizacao_2013` (tabela A) e `reposicao_2025` (tabela B), coletados por `collect_datasets` com estado e falha por tabela. `datasets.py`, `manifest.py` e os manifests v1/v2 não mudam. A única alteração em `_shared/` é `xlsx_content_check` em `http.py`.
- **D2. Colunas por rótulo normalizado; aba declarada no catálogo.** NFC + colapso de espaços + `casefold`; cabeçalho na linha 1; nunca por posição (research R3).
- **D3. Código válido = `[0-9A-Z]{6}`.** Célula numérica inteira de exatamente 6 dígitos é aceita e normalizada (contada); numérica com menos dígitos, decimal, negativa ou texto fora do padrão reprova com o valor na mensagem (R1, R2).
- **D4. Linha de legenda ≠ linha inválida.** Texto não-código na primeira coluna com **todas** as outras colunas mapeadas vazias é legenda (ignorada e contada); com dado nas outras colunas reprova. Linha totalmente vazia é pulada sem contar.
- **D5. Derivação em Python, determinística.** `derive_parish_crosswalk` encadeia A e B pelo `pre_code` **na granularidade da linha da A**; pré-2013 ausente da B mantém código e designação de 2013; o par é único; saída ordenada (R6).
- **D6. Relação por par.** `destinos(c13)` e `origens(c25)` decidem as quatro naturezas; `inherited = destinos(c13) > 1` (R4). Nenhum peso, área ou população: a herança é só um sinal.
- **D7. Cobertura é um gate em Python e uma segunda camada no dbt.** `verify_coverage` roda antes do dbt e reprova a promoção (FR-012); o dbt repete as checagens estruturais. Nada é promovido em caso de falha.
- **D8. Estado vigente das duas tabelas.** O build exige as duas com estado `changed`/`unchanged` válido, bruto no disco e `sha256`/`bytes` conferindo; senão informa qual falta (FR-015).
- **D9. Promoção por caminho.** `lake/silver/xwalk_parish_2013_2025` e `lake/silver/rpt_parish_crosswalk_coverage`; nunca `lake/silver` inteiro. Tag dbt `parish_crosswalk`; `dbt build --select tag:parish_crosswalk`.
- **D10. Fora desta feature:** TopoJSON, pesos/repartição, coletor `censos`, versões da CAOP posteriores à 2025, `parish_synonyms`, deploy e agendamento.

## Constitution Check

*GATE pré-design verificado após ler a constitution e os ADR-001/002/003; pós-design reavaliado depois de `research.md`, modelo, contratos e lógica.*

| Princípio | Pré-Design | Pós-Design | Notas |
| --- | --- | --- | --- |
| I. Nenhum segredo fora do cofre | Conforme | Conforme | Fonte pública sem chave. Local sem credenciais; S3 pela cadeia padrão. Testes com credenciais falsas do moto. `gitleaks` no CI. |
| II. Núcleo estático e sem chave | Conforme | Conforme | Nenhum servidor nem publicação. A tabela é insumo do pipeline. |
| III. Dados honestos e rastreáveis | **Conforme, mais estrito** | **Conforme, mais estrito** | Junção por `dicofre` oficial; ausente nunca é preenchido; a herança é sinalizada (`inherited`) e a origem parcial também; fonte, licença e checksum em cada linha. **Tensão:** o princípio pede que "uma freguesia sem correspondência gere aviso e entre no relatório"; esta feature **reprova a promoção** da própria correspondência (decisão do autor na entrevista). Isso cumpre o aviso (a mensagem lista os códigos) e é mais forte, mas é uma regra diferente da dos indicadores. Ver Complexity Tracking. |
| IV. Coleta responsável e licenciada | **Conforme com pendência** | **Conforme com pendência** | Catálogo antes do coletor; `User-Agent`, 1 req/s, retry com backoff. **Pendência:** a licença específica das planilhas e os termos de download automatizado do INE não foram verificados (R-002); assumida CC-BY-4.0 como a fonte `ine`, a confirmar em T028. Só registrar como risco aceito se os termos forem restritivos. |
| V. Bruto imutável e publicação atômica | Conforme | Conforme | Raw sem sobrescrita; `unchanged` sem bruto novo; promoção atômica por caminho com backup; falha antes da promoção preserva a tabela anterior. |
| VI. Privacidade por padrão | Conforme | Conforme | Códigos e designações administrativas; nenhum dado pessoal. |
| VII. Custo como requisito | Conforme | Conforme | US$ 0/mês: local e S3 simulado. Nenhum recurso AWS criado. |

**Restrições do projeto:** "Território: CAOP vigente; … correspondência 2013→2025" (ADR-002 D5) é exatamente o que a feature entrega. "Fora do Escopo do MVP": nenhum item tocado (a freguesia continua só drill-down).

**Resultado:** nenhuma violação não justificável. A tensão do princípio III está registrada abaixo.

## Project Structure

### Documentation (this feature)

```text
sdd/specs/004-correspondencia-freguesias/
├── spec.md
├── plan.md                         # este arquivo
├── tasks.md
├── research.md                     # medições reais de 2026-11-12 e decisões R1-R7
├── data-model.md                   # catálogo, tabelas normalizadas, correspondência, relatório
├── contracts/correspondencia-cli.md
├── logic/derivacao-correspondencia.md
├── quickstart.md
├── handoff.md
└── contract-tests.lock
```

### Source Code (repository root)

Estado real encontrado (specs 001 a 003) e o que esta feature acrescenta (`+`):

```text
config/sources.yml                                       # + ine_parish_crosswalk
pipelines/
  cli/        collect_*.py build_*.py _common.py _promote.py
              + collect_parish_crosswalk.py build_parish_crosswalk.py
  collectors/
    _shared/  catalog.py datasets.py http.py ...         # http.py: + xlsx_content_check (única mudança)
    + parish_crosswalk/  layout.py validate.py transform.py derive.py coverage.py handler.py   # stubs já criados
analytics/dbt/
  dbt_project.yml                                        # + tag parish_crosswalk
  models/bronze/schema.yml                               # + tabela dim_parish no source caop_silver
  + models/crosswalk/ xwalk_parish_2013_2025.sql rpt_parish_crosswalk_coverage.sql schema.yml
  + tests/parish_crosswalk_*.sql
tests/
  contracts/  test_parish_crosswalk_contract.py          # travado (5 casos)
  fixtures/   + parish_crosswalk/ tables.py (travado) ci_seed.py
  unit/ integration/                                     # + testes da feature
docs/runbooks/coletas.md  README.md  .docs/fontes_de_dados.md      # atualizar no Polish
.github/workflows/python.yml                             # + passo dbt da feature
```

**Structure Decision:** seguir o desenho `pipelines/collectors/<fonte>/` e o par `collect_*`/`build_*` das specs anteriores. `layout.py` concentra a leitura da planilha para que `validate.py` e `transform.py` nunca divirjam. O dbt materializa e testa, mas a regra de negócio mora em `derive.py`/`coverage.py`, onde os contratos a alcançam sem rede.

## Complexity Tracking

| Violação | Por que é necessária | Alternativa mais simples rejeitada porque |
| --- | --- | --- |
| Princípio III (tensão): reprovar a promoção quando falta cobertura, em vez de só avisar. | Decisão explícita do autor (entrevista de 2026-11-12). A correspondência é uma tabela estrutural: se ela estiver incompleta, qualquer indicador por freguesia ligado a ela perde dado sem que ninguém perceba. A mensagem de reprovação e o relatório continuam atendendo ao "aviso + relatório" do princípio. | Só avisar e promover (rejeitada na entrevista): deixaria o `censos` juntar dados a freguesias sem correspondência em silêncio. Se a constitution for emendada para distinguir tabelas estruturais de indicadores, esta linha some. |

## Estratégia de Testes

Prioridade: unitário → contrato/integração → E2E local → verificação manual da fonte real. Os contratos usam downloader, storage e planilhas sintéticas no layout real e exercem só a fronteira pública. O dbt é provado sobre uma Silver sintética. A coleta real (duas planilhas, 233 KB) é uma verificação manual distinta (T026).

Comandos-base:

```powershell
uv sync --locked
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
```

> Use sempre `python -m pytest` (o executável `pytest` não coloca a raiz no `sys.path`) e `--basetemp .pytest_tmp` (o diretório temporário padrão do Windows pode negar permissão), como no CI.

### Testes de Contrato

Arquivos travados em `contract-tests.lock`: `tests/contracts/test_parish_crosswalk_contract.py` e a fixture `tests/fixtures/parish_crosswalk/tables.py`.

Comando: `uv run --locked python -m pytest -q --basetemp .pytest_tmp tests/contracts/test_parish_crosswalk_contract.py`

Integridade: `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 004-correspondencia-freguesias`. O script não infere a contagem de testes de arquivos Python (`tests: unknown`); o orçamento de 5 foi respeitado à mão.

| Teste | Origem | Fase | Vermelho esperado (antes do execute) |
| --- | --- | --- | --- |
| `test_us1_ac1_ac2_ac3_fr002_fr003_fr004_both_tables_are_stored_untouched_and_state_is_per_table` | US1/AC1-AC3, FR-002, FR-003, FR-004 | Fase 3 | `NotImplementedError: not implemented: collect_parish_crosswalk (T008)` |
| `test_us1_ac4_ac5_fr005_invalid_tables_fail_per_table_without_partial_raw_and_recover_next_run` | US1/AC4-AC5, FR-005 | Fase 3 | `NotImplementedError: … collect_parish_crosswalk (T008)` |
| `test_fr005_fr006_reader_keeps_codes_as_text_normalizes_whole_numeric_cells_and_ignores_legends` | FR-005, FR-006 | Fase 3 | `NotImplementedError: … read_crosswalk_table (T007)` |
| `test_us2_ac1_to_ac6_fr007_to_fr011_fr014_pairs_relations_flags_and_determinism` | US2/AC1-AC6, FR-007 a FR-011, FR-014 | Fase 4 | `NotImplementedError: … derive_parish_crosswalk (T013)` |
| `test_us3_ac2_ac3_ac4_fr012_coverage_gate_lists_every_gap_by_kind` | US3/AC2-AC4, FR-012 | Fase 5 | `NotImplementedError: … verify_coverage (T019)` |

Stubs criados pelo plan (ponto de partida do execute, **não** travados): `pipelines/collectors/parish_crosswalk/{validate,transform,derive,coverage,handler}.py`. `layout.py` não existe ainda (T004).

Verificado no plan: lint limpo; os 5 contratos falham só por `NotImplementedError`; 165 testes existentes (contratos e unitários) seguem verdes.

## Estado Atual

<!-- Sobrescrita a cada checkpoint pelo sdd-execute. Vazia na criação. -->

| Área | Estado |
| --- | --- |
| Branch | `feature/004-correspondencia-freguesias`, criada de `origin/main` em 2026-11-12; nada commitado |
| Fase 1 (Setup) | Concluída: T001–T003 |
| Fase 2 (Foundational) | Concluída: T004 `layout.py`, T005 (31 testes) |
| Fase 3 (US1) | Concluída: T006–T012; contratos 1–3 verdes; coleta local e S3 (moto) cobertas |
| Fase 4 (US2) | Concluída: T013–T018; contrato 4 verde; `build_parish_crosswalk` promove `lake/silver/xwalk_parish_2013_2025` e o CSV de revisão |
| Fase 5 (US3) | Concluída: T019–T023; contrato 5 verde (**5/5 contratos verdes**); gate de cobertura antes do dbt, relatório `rpt_parish_crosswalk_coverage` promovido |
| Fase 6 (Polish) | Concluída localmente: T024–T029. **Pendente de ação do autor:** CI remoto (exige push/PR), `gitleaks` do CI e os commits (Quality Gate 7) |
| Fase 7 (Convergence) | Concluída: T030–T034. Relatório legível `parish_crosswalk_report.csv` (CF-001) e atribuição em todas as linhas do relatório (CF-002) |
| Catálogo | `ine_parish_crosswalk` em `config/sources.yml` (licença assumida, R-002 aberto) |
| Verificação real (T026) | Coleta HTTP e build contra o INE e a `dim_parish` reais: 3.260 pares, 3.259/3.259 freguesias cobertas, valores idênticos à referência, 2ª coleta `unchanged`, SHA-256 das outras tabelas inalterados (detalhe no `research.md`) |
| Licença (R-002) | `CC-BY-4.0` mantida com ressalva: aviso geral do INE visto por busca, sem aviso específico para as planilhas |
| Gates | `ruff` limpo; suíte completa **319 verdes**; dbt por tag: CAOP 31/31, observações 17/17, clima 23/23, correspondência 25/25; as 4 travas de contrato íntegras; build real conferido (SHA-256 das outras tabelas inalterados) |

## Riscos e Decisões

<!--
  IDs estáveis (R-001, R-002...), nunca deletados. Item resolvido ganha
  prefixo "Resolvido:" na célula de Mitigação em vez de sumir da tabela.
-->

| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |
| R-001 | Os links `smi.ine.pt/Versao/Download/9160` e `/10698` não têm estabilidade garantida; só foram observados em 2026-11-12. | Médio: a coleta passaria a devolver HTML ou outro arquivo. | Resolvido: `xlsx_content_check` no download, `validate_crosswalk_table` e falha explícita por tabela; nunca dado silencioso (US1/AC4). Confirmado pelos testes T012 e pelo contrato 2. O risco externo de o INE mudar o link permanece, e vira falha explícita. |
| R-002 | A licença específica das planilhas e os termos de download automatizado do INE não foram verificados. | Médio: contradiz o princípio IV se os termos proibirem. | Parcialmente resolvido em 2026-11-12 (T028): o INE declara CC BY 4.0, com a fonte identificada, para a informação estatística (aviso do catálogo de publicações 2026, visto só por busca: `www.ine.pt` devolve 403 a download scriptado e não foi contornado); o `robots.txt` do `smi.ine.pt` só veta Baiduspider e SemrushBot. **Não há aviso específico para estas duas planilhas** (metadados do SMI). Mantida `CC-BY-4.0` com a ressalva no catálogo. Para fechar de vez, o autor pode abrir a página de termos do INE no navegador, ou perguntar ao INE; se restritiva, registrar risco aceito como no Pordata. |
| R-003 | A spec diz que "código lido como número é erro", mas as planilhas reais têm 51 células inteiras de 6 dígitos. | Alto se aplicado literalmente: a coleta real reprovaria. | Resolvido: decisão D3 / research R1 (aceitar inteiro de exatamente 6 dígitos; reprovar menos dígitos). Confirmada pela coleta real (51 células normalizadas, nenhum erro) e pelos testes do `layout.py`. Nota para a spec: a regra está coerente com o texto ("zeros perdidos"). |
| R-004 | Códigos alfanuméricos (`0308FC`) existem em 31 linhas e na `dim_parish`. | Alto se a validação fosse `\d{6}`. | Resolvido: D3 / research R2, `[0-9A-Z]{6}`. Confirmado pela coleta real (31 códigos alfanuméricos aceitos; a `dim_parish` tem 18). |
| R-005 | O FR-009 ("mesmo conjunto de pares") admite duas leituras (par ou componente). | Baixo: muda a classificação, não a cobertura. | D6 / research R4: por par. Registrado como achado do Analyze. |
| R-006 | O marcador `(parte)` é textual; se o INE mudar o texto, `partial_origin` some em silêncio. | Médio para a herança correta. | Resolvido: o relatório mostra a contagem (`source_partial_rows` 11, `partial_origin_pairs` 8) e o T026 a conferiu na coleta real sem divergência. |
| R-007 | A `dim_parish` precisa existir e ser a CAOP 2025; uma CAOP nova sem tabela do INE reprova a cobertura. | Baixo: é o comportamento desejado. | Resolvido: mensagem de erro clara com os códigos, e a tabela anterior preservada byte a byte (T023); estender a correspondência é outra entrega (spec, Fora de Escopo). |
| R-008 | O source `caop_silver` do dbt é definido em `models/bronze/schema.yml`; um segundo bloco com o mesmo nome pode ser rejeitado pelo dbt. | Baixo: build quebra. | Resolvido: T003 acrescentou `dim_parish` ao source existente; `dbt parse` e os quatro builds por tag (31/17/23/25) passam. |
| R-010 | Descoberto na T001: `tests/unit/test_climate_catalog.py::test_real_catalog_and_existing_sources` (spec 003) fixa o conjunto **exato** de fontes do catálogo. Acrescentar uma fonte o quebra. | Baixo: era previsível; o arquivo não está sob trava. | Resolvido: asserção atualizada para incluir `ine_parish_crosswalk`. Toda fonte futura repetirá o ajuste. |
| R-011 | Descoberto no T026: o resumo do build imprimia `→`, ausente em cp1252 (console do Windows); o build terminava e o `print` levantava `UnicodeEncodeError`. Os testes não o pegavam porque `capsys` usa UTF-8. | Médio: o comando saía com erro depois de promover. | Resolvido: texto sem a seta e `test_cli_output_can_be_printed_on_a_windows_console` (confere `.encode("cp1252")` da saída de sucesso e de falha). Toda saída de CLI nova deve passar por essa checagem. |
| R-012 | Descoberto na reverificação da Fase 7: `test_changed_then_unchanged_then_only_the_altered_table_is_written` (T010) falhou uma vez na suíte completa (máquina lenta, 14m20s). O helper regerava as duas planilhas com o openpyxl, que grava a hora de criação (resolução de segundos) nos metadados; os bytes da tabela A mudavam quando as duas gerações caíam em segundos diferentes e ela virava `changed`. Era instável por construção (~5% mesmo com a máquina rápida). | Baixo: só o teste; o coletor grava os bytes recebidos, sem regerar nada. | Resolvido: o teste regera só a tabela que deve mudar e reaproveita os bytes da outra; provado forçando 1,2 s entre as gerações e com a suíte inteira verde depois. Regra para testes novos: nunca compare bytes de planilhas geradas em momentos diferentes. |
| R-009 | `name_changed` é verdadeiro em 297 dos 3.260 pares (quase todos de uniões desfeitas), então o sinal tem pouco poder de discriminar. | Baixo: apenas informativo. | Resolvido: mantido por exigência da spec (FR-008); o consumidor deve usar `relation` e `inherited` para decidir, e o runbook o documenta. |

## Execution Notes

<!--
  Tabela append-only, mantida pelo sdd-execute. Quando passar de ~40 linhas,
  arquivar as mais antigas (exceto as ~10 mais recentes) em history.md,
  substituindo por uma linha de resumo consolidado aqui.
-->

| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |
| 2026-11-12 | Fase 1 (Setup) | Catálogo `ine_parish_crosswalk`, `xlsx_content_check` (+ teste), tag dbt `parish_crosswalk` e `dim_parish` no source `caop_silver`. Branch criada de `origin/main`. `ruff` limpo, `tests/unit` 154 verdes, `dbt parse` ok. | Fase 2: `layout.py` |
| 2026-11-12 | Fase 2 (Foundational) | `layout.py` (`normalize_code`, `normalize_label`, `load_rows`) e 31 testes. `CrosswalkSchemaError` passou a ser definida em `layout.py` e é reexportada por `validate.py` (evita import circular; o nome público para os contratos não muda). | Fase 3: US1 (validate, transform, handler, CLI) |
| 2026-11-12 | Fase 3 (US1) | `validate`, `transform`, `handler` e CLI de coleta; contratos 1–3 verdes de primeira. Testes novos (18): 5 integração local, 2 S3 (moto), 11 unitários do validador. Achado: XML corrompido num ZIP válido escapava do tratamento; corrigido em `layout.py`. | Fase 4: derivação e dbt |
| 2026-11-12 | Fase 4 (US2) | `derive.py`, `build_parish_crosswalk.py` (`prepare_crosswalk`, build, CSV de revisão), modelo e testes dbt, `ci_seed.py`; contrato 4 verde de primeira. Leitura + derivação nas planilhas reais reproduziram a referência. dbt 18/18 na fixture; builds das specs 001–003 intactos. | Fase 5: gate de cobertura e relatório |
| 2026-11-12 | Fase 5 (US3) | `verify_coverage` (contrato 5 verde de primeira, **5/5 contratos**), gate no build antes do dbt, relatório dbt + 2 testes, `table_stats.parquet`. Gate Python e testes dbt reprovam lacunas e preservam a tabela anterior byte a byte (provado também forçando só o dbt). dbt 24/24 na fixture. | Fase 6: CI, docs, verificação real |
| 2026-11-12 | Fase 6 (Polish) | Passo de CI (reproduzido local: 24/24); docs (`fontes_de_dados`, runbook, README); **verificação real contra o INE sem divergência**; suíte completa 318 verdes; dbt por tag das 4 features; travas 001–004 íntegras; licença verificada em parte. Achado: `→` quebrava o `print` em cp1252 (R-011), corrigido com teste. | CI remoto, `gitleaks` e commits dependem do autor |

| 2026-11-12 | Fase 7 (Convergence) | CF-001 e CF-002 fechados: `attribution` no relatório dbt (25/25) e `parish_crosswalk_report.csv` legível, com versão da CAOP, data e atribuição em todas as linhas; testes e docs sincronizados. Reverificação: build real sem divergência, SHA-256 das outras tabelas inalterados, 4 dbt por tag e 4 travas íntegras, suíte 319 verdes. Achado: T010 instável por bytes de planilha regerada (R-012), corrigido. | Rodar `/sdd-converge` de novo; CI remoto e commits dependem do autor |

**PRÓXIMO**: nenhuma task aberta. Rodar `/sdd-converge 004-correspondencia-freguesias` outra vez para confirmar que não sobra achado acionável. Aguarda o autor: criar os commits (curtos, em inglês), fazer push/PR e conferir o CI remoto e o `gitleaks`; depois `/sdd-converge 004-correspondencia-freguesias`. O status só vira `Implementada` quando os 2 itens do Checklist de Release forem marcados.

## Arquivos Principais

<!-- Sobrescrita a cada checkpoint — foco da etapa atual, não a árvore inteira. -->

- Código: `pipelines/collectors/parish_crosswalk/*`, `pipelines/cli/{collect,build}_parish_crosswalk.py`, `analytics/dbt/models/crosswalk/`, `analytics/dbt/tests/parish_crosswalk_*.sql`
- Catálogo e CI: `config/sources.yml` (`ine_parish_crosswalk`), `.github/workflows/python.yml`
- Docs: `.docs/fontes_de_dados.md`, `docs/runbooks/coletas.md`, `README.md`, `research.md` (verificação real)
- Pendente de ação do autor: commits, push/PR e CI remoto
- `tests/contracts/test_parish_crosswalk_contract.py` e `tests/fixtures/parish_crosswalk/tables.py` (**travados**)

## Cuidados para Retomada

<!-- Armadilhas operacionais específicas desta feature, anexadas conforme descobertas. -->

- Rode os testes com `uv run --locked python -m pytest -q --basetemp .pytest_tmp ...` (o `pytest` direto não acha `pipelines` e o temp padrão do Windows nega permissão).
- O DuckDB não cria o diretório de saída dos modelos `external`: o build (`build_parish_crosswalk`) e o `ci_seed.py` fazem `mkdir` dos caminhos de `PROMOTED` antes do `dbt build`. Se acrescentar um modelo promovido, acrescente o caminho a `PROMOTED`.
- Planilhas geradas pelo openpyxl não são determinísticas: a hora de criação entra nos metadados (segundos). Em testes, gere cada planilha **uma vez** e reaproveite os bytes; só regere a que deve mudar (R-012).
- A suíte completa varia de 6 a 14 minutos conforme a carga da máquina (com o dbt de cinco builds). Se o monitor expirar, confira `Get-Process`/o log antes de concluir que travou.
- O console do Windows usa cp1252: não imprima `→`, `≥` e afins nas CLIs (R-011). Para reproduzir o console real, rode com `PYTHONIOENCODING=cp1252`.
- O `www.ine.pt` devolve 403 a download scriptado (e o `robots.txt` dele também); o `smi.ine.pt`, onde estão as planilhas, responde 200. Não troque o User-Agent para contornar.
- O dbt do projeto lê as variáveis `XWALK_BUILD_DIR`, `XWALK_PREPARED_DIR`, `OBS_SILVER_DIR` e `CAOP_DUCKDB_PATH`; para rodar `dbt build --select tag:parish_crosswalk` à mão, aponte todas para a mesma raiz da fixture (ver `quickstart.md` §2).
- `analytics/dbt/target/` é ignorado pelo Git, mas um `grep -r` em `analytics/dbt` varre o `manifest.json` (centenas de KB); restrinja a busca a `models/` e `tests/`.

## Resultado Final

**Convergida em 2026-11-12**, na segunda rodada do `sdd-converge` (a primeira achou CF-001 e CF-002, fechados na Fase 7). "Convergida" significa que o código, os testes e a documentação batem com a spec, o plano e a constitution. Não significa "publicada": o CI remoto e os commits ainda dependem do autor (ver *Em aberto*).

### O que foi construído
- **Fonte `ine_parish_crosswalk`** em `config/sources.yml`, com as duas planilhas oficiais do INE (antes de 2013 → 2013, e antes de 2013 → as 302 freguesias repostas em 2025) coletadas por `collect_parish_crosswalk` como bruto imutável, com manifest e `unchanged` por `sha256`; falha isolada por tabela.
- **Derivação** em Python puro (`derive_parish_crosswalk`): uma linha por par (2013, 2025), com a natureza da relação (um-para-um, um-para-muitos, muitos-para-um, muitos-para-muitos) e os sinais de herança, origem parcial, nome e município alterados. Sem pesos: a herança é só um sinal.
- **Gate de cobertura** (`verify_coverage`) antes do dbt, mais uma segunda camada de testes dbt; uma lacuna reprova a promoção e preserva a tabela anterior byte a byte.
- **Saídas** em `lake/silver`: `xwalk_parish_2013_2025`, `rpt_parish_crosswalk_coverage` (Parquet) e dois CSV legíveis (`parish_crosswalk_report.csv` e `parish_crosswalk_review.csv`), promovidos por caminho.
- **Verificação real** contra o INE e a `dim_parish` real: 3.260 pares, 3.259 de 3.259 freguesias, valores idênticos à referência da pesquisa, 2ª coleta `unchanged`, SHA-256 das outras tabelas inalterados.
- **Gates finais:** suíte completa 319 verdes; dbt por tag CAOP 31/31, observações 17/17, clima 23/23, correspondência 25/25; as quatro travas de contrato íntegras; 5/5 contratos da 004 verdes, sem atalhos.

### Desvios em relação ao plano original
1. **Regra de código numérico** refinada (R-003, D3): a spec diz "número é erro", o código aceita inteiro de exatamente 6 dígitos, porque as planilhas reais têm 51 células assim.
2. **Código `[0-9A-Z]{6}`**, e não 6 dígitos (R-004).
3. **`CrosswalkSchemaError`** passou a ser definida em `layout.py` e reexportada por `validate.py` (evita import circular); o nome público dos contratos não mudou.
4. **`layout.py` endurecido** contra XML corrompido dentro de um ZIP válido (achado do teste T012).
5. **Extras documentados:** `table_stats.parquet` e as colunas `source_*` do relatório, `CrosswalkDerivationError`, `names` e truncamento em 50 códigos no gate.
6. **`ci_seed.py` criado na Fase 4**, e não na Fase 6, porque o T018 precisava dele.
7. **Fase 7 (converge):** CSV legível do relatório e coluna `attribution` (FR-013, US3/AC5, FR-019).
8. **Achados da execução:** `test_climate_catalog.py` da spec 003 fixava o conjunto de fontes (R-010); o resumo imprimia `→`, que quebra em cp1252 (R-011); o teste T010 era instável por regerar planilhas com hora de criação nos metadados (R-012). Os três foram corrigidos com teste.

### Em aberto (nenhum bloqueia a convergência)
- **Decisões do autor, sem task:** CF-003 (redação da spec sobre código numérico), CF-004 (qual estado usar quando a última execução de uma tabela falhou), CF-007 (constitution III: aviso × reprovar), Analyze A-003 (R-005, redação do FR-009) e CF-006/R-002 (licença das planilhas: `CC-BY-4.0` do aviso geral do INE, sem aviso específico confirmado na página oficial).
- **Externo:** push/PR, CI remoto e `gitleaks` (SC-007, constitution I) e os commits em inglês (Quality Gate 7). São os 2 itens não marcados do Checklist de Release em `tasks.md`.
