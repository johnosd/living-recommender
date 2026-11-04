# Tasks: Fundação da ingestão e dimensão territorial CAOP

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/caop-cli.md`, `logic/ingestao-e-territorio.md`.

**Prerequisites**: `spec.md` e `plan.md`; teste P1 travado em `contract-tests.lock`.

**Organization**: setup/fundação → US1 P1 → US2 P2 → US3 P3 → Polish. IDs `T001`–`T030` são estáveis; `T031` foi acrescentada na US2 a pedido do usuário para visualizar as dimensões. `[P]` indica arquivos independentes; contratos travados não são editados pelo executor.

## Path Conventions

- Existentes após este plano: `pyproject.toml`, `uv.lock`, `.python-version`, `pipelines/collectors/caop/handler.py` (stub), `tests/contracts/test_caop_collection_contract.py` (travado), `.planning/`, `.docs/`, `sdd/adr/`.
- Criar na execução: `config/sources.yml`, `pipelines/collectors/_shared/`, `pipelines/cli/`, `pipelines/collectors/caop/{schema.py,transform.py,names.py}`, `analytics/dbt/`, `tests/{unit,integration,fixtures}/` e `.github/workflows/`.
- Dados locais em `.data/`, temporários do pytest em `.pytest_tmp/`, ambos ignorados pelo Git. Caminhos S3 usam o mesmo prefixo relativo do modo local.

## Phase 1: Setup (Shared Infrastructure)

**Objetivo**: fechar ambiente Python repetível e CI mínimo para executar a coleta sem depender de instalação global.

### Implementation

- [X] T001 [P] Completar `pyproject.toml`/`uv.lock` com dependências Python 3.12 compatíveis (HTTP, YAML, Boto3, GeoPandas/Pyogrio/PyArrow, dbt Core/dbt-duckdb, pytest/ruff), mantendo `.python-version` e `uv sync --locked` funcionais (FR-003, FR-009, FR-017, SC-004).
- [X] T002 [P] Criar `.github/workflows/python.yml` com instalação via lock, `ruff`, `pytest`, build dbt em fixtures e verificação de segredos no PR; não fazer coleta de rede no CI (constitution I/Quality Gates; FR-017, SC-004).
- [X] T003 [P] Confirmar `.gitignore` para `.data/`, `.pytest_tmp/`, `.venv/`, `.env` e artefatos dbt em `analytics/dbt/target/`, sem ignorar fixtures sintéticas (constitution I/V).

### Testes da Fase

- [X] T004 Verificar `uv sync --locked` e `uv run --locked ruff check pipelines tests` localmente, sem requerer AWS.

**Critério de Conclusão**: ambiente Python 3.12 instala pelo lock; CI está definido sem credenciais; nenhum bruto real ou segredo entra no Git.

**Registro da Fase**:

- Status: concluída em 2026-11-04 (T001–T004).
- Feito: dependências Python 3.12 fixadas em `uv.lock`; CI com lint, pytest, build dbt condicionado à fixture e varredura de segredos no PR; artefatos locais ignorados e fixtures preservadas.
- Contrato: sem contrato nesta fase; `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop` → PASS, trava íntegra. Os cinco contratos P1 seguem vermelhos no stub até a US1.
- Testes executados: `uv lock` → 89 pacotes resolvidos; `uv sync --locked` → 81 instalados; `uv run --locked ruff check pipelines tests` → All checks passed; parse YAML do workflow → válido; `git check-ignore -v --no-index` → artefatos ignorados e fixture não ignorada.
- Pendências: o job pytest do CI passará após a US1; o build dbt depende de `analytics/dbt/dbt_project.yml` e `tests/fixtures/caop/ci_seed.py` da US2/T024; workflow ainda não executado no GitHub.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Objetivo**: oferecer catálogo, download, storage e manifest reutilizáveis ao coletor CAOP e às futuras fontes.

### Implementation

- [X] T005 [P] Criar `config/sources.yml` com CAOP e `pipelines/collectors/_shared/catalog.py`: três URLs/versão/licença/publicador/frequência/método/nível, validação de fonte cadastrada e revisão da edição DGT em `research.md` R1 (FR-001/002, constitution III/IV).
- [X] T006 [P] Criar `pipelines/collectors/_shared/http.py`: User-Agent identificado, timeout, limite de taxa, retry com backoff e download em arquivo temporário; nunca gravar HTML como GeoPackage (FR-003, edge cases).
- [X] T007 [P] Criar `pipelines/collectors/_shared/storage.py`: interface de chaves, backend local sem sobrescrita, escrita temporária + promoção e limpeza por run; `.data/` é a raiz padrão configurável (FR-004/007/009/010).
- [X] T008 Criar `pipelines/collectors/_shared/manifest.py`: schema/versionamento JSON, SHA-256 e tamanho por arquivo, `changed`/`unchanged`/`failed`, seleção do último `changed` bem-sucedido e separação de edição/período/data de coleta (FR-005/006/014, constitution III/V).

### Testes da Fase

- [X] T009 [P] Criar `tests/unit/test_catalog_and_manifest.py` para catálogo ausente, metadados completos, seleção após `failed`/`unchanged` e checksums (FR-001/002/005/006).
- [X] T010 [P] Criar `tests/unit/test_local_storage_and_http.py` para rejeição de sobrescrita, arquivo temporário, timeout/backoff/limite de taxa com HTTP simulado (FR-003/004/007/010).

**Critério de Conclusão**: helpers isolados passam em pytest sem rede; fonte não catalogada é recusada; storage local preserva bytes e chaves.

**Registro da Fase**:

- Status: concluída em 2026-11-04 (T005–T010).
- Feito: catálogo CAOP2025 com três URLs oficiais e metadados; download HTTP com User-Agent, limite de taxa, timeout, retry/backoff e arquivo temporário; storage local imutável; manifest versionado com SHA-256, estados e seleção do último `changed`. `source_url` como mapa por região foi explicitado na spec.
- Contrato: sem contrato nesta fase; `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop` → PASS, trava íntegra. Os cinco contratos P1 continuam vermelhos no stub até a US1.
- Testes executados: `uv run --locked python -m pytest -q tests/unit --basetemp .pytest_tmp` → 7 passed; `uv run --locked ruff check pipelines tests` → All checks passed; `git diff --check` → sem erro.
- Pendências: T011 deve inspecionar os três GeoPackages reais para validar camadas, colunas e CRS; nenhum download real foi feito nesta fase.

---

## Phase 3: User Story 1 — Coletar CAOP com rastreabilidade (Priority: P1) 🎯 MVP

**Objetivo**: um comando local coleta três regiões como bytes originais, registra manifest e evita duplicação quando nada mudou.

**Independent Test**: executar a CLI com fixtures/destino vazio e repetir; segundo run é `unchanged`, sem novos arquivos raw.

### Contrato da Fase

- `test_us1_ac1_fr004_fr005_changed_has_three_immutable_raw_files_and_manifest`
- `test_us1_ac2_fr006_unchanged_writes_only_verification_manifest`
- `test_us1_ac3_fr007_download_failure_leaves_no_raw_and_records_failed`
- `test_us1_ac4_fr008_invalid_region_is_not_committed`
- `test_fr002_unknown_source_is_rejected_before_download`
- Comando: `uv run --locked python -m pytest -q tests/contracts/test_caop_collection_contract.py --basetemp .pytest_tmp`

### Implementation

- [X] T011 [P] Inspecionar três GeoPackages da DGT e implementar `pipelines/collectors/caop/schema.py` para validar ZIP/GeoPackage, camadas, colunas e códigos; registrar mapeamento observado em `research.md` R1 e fixture sintética em `tests/fixtures/caop/` (US1/AC4, FR-008/017 → contrato: `test_us1_ac4_fr008_invalid_region_is_not_committed`).
- [X] T012 Implementar o stub público `pipelines/collectors/caop/handler.py` segundo `logic/ingestao-e-territorio.md`: download/validação completos antes do commit, checksum por região, `run_id` exclusivo, manifest final, `unchanged`, `failed` e limpeza em falha capturada (US1/AC1–4, FR-004–008 → contratos: os cinco da fase).
- [X] T013 Criar `pipelines/cli/collect_caop.py` com `--local`, `--root`, `--force-check`, resumo e códigos de saída conforme `contracts/caop-cli.md`; `--force-check` não altera a regra de checksum (FR-011, SC-001).

### Testes da Fase

- [X] T014 [P] Criar `tests/integration/test_caop_cli_local.py` com fixture GeoPackage mínima, execução CLI sem rede, primeira coleta/segunda `unchanged`, erro de arquivo inválido e nenhum bruto parcial (FR-008/011/017, SC-001/005).
- [X] T015 [P] Criar `tests/unit/test_caop_concurrency.py` para runs simultâneos com prefixos distintos, último manifest `changed` e retry esgotado, sem corromper bruto anterior (edge cases, constitution V).

**Critério de Conclusão**: `uv run --locked python -m pytest -q tests/contracts/test_caop_collection_contract.py --basetemp .pytest_tmp` → 5/5 verdes e `check-contract-tests.ps1 -Slug 001-ingestao-caop` íntegro; testes adicionais verdes; CLI local funciona sem credenciais (SC-001/005).

**Registro da Fase**:

- Status: concluída em 2026-11-04 (T011–T015); gate de decisão antes da US2.
- Feito: três ZIPs reais inspecionados em `.data/` (quatro GeoPackages); validador de camadas, campos, códigos e CRS; coletor local com raw imutável, `changed`/`unchanged`/`failed`, limpeza e CLI; fixtures sintéticas, integração e concorrência sem rede.
- Contrato: `uv run --locked python -m pytest -q tests/contracts/test_caop_collection_contract.py --basetemp .pytest_tmp` → 5/5 verdes; `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop` → PASS, trava íntegra.
- Testes executados: `uv run --locked python -m pytest -q --basetemp .pytest_tmp` → 16 passed; `uv run --locked ruff check pipelines tests` → All checks passed; validação real dos três ZIPs → 308 municípios e 3259 freguesias, quatro CRS/grupos esperados; `git diff --check` → sem erro.
- Pendências: US2/AC1 e `data-model.md` exigem `dicofre` numérico de seis dígitos, mas 18 códigos oficiais CAOP2025 contêm letras. Decidir emenda do critério antes de implementar US2. CI remoto e S3 ainda não executados.

---

## Phase 4: User Story 2 — Dimensões oficiais (Priority: P2)

**Objetivo**: transformar a última CAOP válida em staging Bronze e dimensões Silver vigentes, com área/ponto e qualidade bloqueante.

**Independent Test**: com três arquivos raw de fixture, rodar transformação e testes, conferir 308 municípios na fixture nacional de aceite, chaves/hierarquia e ponto dentro de cada polígono.

### Implementation

- [X] T016 [P] Criar `pipelines/collectors/caop/names.py` com regra única de normalização (minúsculas, sem acentos, espaços colapsados), preservando o nome oficial; distinguir homônimos por código/região (US2/AC4–5, FR-016).
- [X] T017 Criar `pipelines/collectors/caop/transform.py` segundo `logic/ingestao-e-territorio.md`: abrir GeoPackages por região, mapear entidades/códigos oficiais, dissolver multipartes, calcular área por CRS métrico e `representative_point()` em WGS84, manter geometria de verificação e proveniência (US2/AC1–5, FR-012–014).
- [X] T018 Criar `analytics/dbt/dbt_project.yml` e `analytics/dbt/profiles.yml` com target DuckDB local e diretórios Bronze/Silver, sem credenciais versionadas; usar Parquet preparado e materialização externa validada conforme `research.md` R3 (FR-014, constitution I/V).
- [X] T019 [P] Criar `analytics/dbt/models/staging/stg_caop_municipalities.sql`, `stg_caop_parishes.sql` e `analytics/dbt/models/staging/schema.yml` para staging Bronze tipado e proveniência, consumindo só o `source_run_id` selecionado (FR-014).
- [X] T020 Criar `analytics/dbt/models/marts/dim_municipality.sql`, `dim_parish.sql` e `analytics/dbt/models/marts/schema.yml` para Silver com colunas de `data-model.md`, nomes/códigos/áreas/pontos e apenas edição vigente (FR-012–014, US2/AC1–5).
- [X] T021 Criar `analytics/dbt/tests/caop_quality.sql` (ou testes SQL separados) para 308 municípios, `dicofre[:4]=dico`, área positiva, relações e chaves; `not_null`/`unique`/`relationships` em `schema.yml`; falha aborta promoção (FR-015, SC-002).
- [X] T022 Criar `pipelines/cli/build_caop.py` para selecionar último manifest `changed`, verificar checksums, preparar Parquet, executar `dbt build` em área temporária, validar contenção espacial e promover Bronze/Silver só após sucesso (FR-014/015/017, SC-002/004).

### Testes da Fase

- [X] T023 [P] Criar `tests/unit/test_caop_geometry.py` com polígonos sintéticos multipartes/exclave, CRS por região, área positiva, ponto contido e nomes/homônimos (US2/AC2–5, FR-012/013/015/016).
- [X] T024 Criar `tests/integration/test_caop_build.py` e gerador de fixture nacional sintética em `tests/fixtures/caop/` com 308 códigos municipais, freguesias válidas e três regiões; verificar Parquet Bronze/Silver, seleção do manifest correto e falha de dbt/geometria sem promoção; rodar `dbt build` local (FR-014/015/017, SC-002/004).
- [X] T031 [descoberta na US2] Criar visualizador HTML local e CSVs de municípios/freguesias a partir da Silver, com instruções de uso, para tornar a base inspecionável pelo operador.
- [X] T032 [descoberta durante T024] Corrigir a comparação de caminhos locais no Windows quando `Path.resolve()` devolve o prefixo estendido `\\?\` durante coletas concorrentes; adicionar regressão sem afrouxar a trava P1.

**Critério de Conclusão**: `dbt build` sobre fixture e verificações espaciais verdes; dimensões vigentes com 308 municípios na edição real/fixture nacional; todas as freguesias válidas e pontos internos; falha preserva saída Silver anterior (SC-002/004).

**Registro da Fase**:

- Status: concluída em 2026-11-04 (T016–T024, T031–T032).
- Feito: código oficial `dtmnfr` preservado inclusive sufixos alfanuméricos; normalização de nomes e geometrias em quatro CRS; Bronze/Silver Parquet com dbt e gates espacial/de qualidade; promoção só após sucesso. Execução real local produziu 308 municípios e 3259 freguesias. Explorador HTML e dois CSVs gerados em `.data/explore/` para inspeção. Corrigida a comparação de caminhos Windows durante concorrência.
- Contrato: fase sem contrato novo; `uv run --locked python -m pytest -q tests/contracts/test_caop_collection_contract.py --basetemp .pytest_tmp` → 5/5 verdes na suíte completa; `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop` → PASS, trava íntegra.
- Testes executados: `uv run --locked python -m pytest -q --basetemp .pytest_tmp` → 27 passed; `uv run --locked ruff check pipelines tests` → All checks passed; `uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local` → 31/31 passos verdes na fixture; `uv run --locked python -m pipelines.cli.build_caop --local --root .data` → 308 municípios/3259 freguesias reais; regressão Windows falhou antes da correção e passou depois, com 30 repetições da concorrência verdes; sintaxe JavaScript do HTML validada com `node --check`.
- Pendências: execução do CI no GitHub e backend S3 simulado pertencem às fases seguintes. A conexão do navegador automatizado recusou a sessão; o HTML foi gerado e validado estruturalmente, mas a interação visual no navegador ainda depende de abertura pelo operador.

---

## Phase 5: User Story 3 — Mesmo coletor em S3 (Priority: P3)

**Objetivo**: trocar o destino por S3 mantendo chaves/manifests e falhando antes do download quando não há escrita.

**Independent Test**: rodar a mesma fixture com backend local e S3 simulado e comparar chaves, bytes e campos estáveis do manifest.

### Implementation

- [ ] T025 [P] Criar `pipelines/collectors/_shared/storage_s3.py` usando Boto3, com prefixo por run, escrita sem sobrescrita, pré-teste de escrita/remoção antes da rede, limpeza de falha e listagem de manifests; nenhuma conta AWS real (FR-009/010, US3/AC1–3).
- [ ] T026 Integrar `--s3 --bucket [--prefix]` em `pipelines/cli/collect_caop.py` e backend em `pipelines/collectors/caop/handler.py`, mantendo a API pública/contratos P1 (FR-009/011, SC-003).

### Testes da Fase

- [ ] T027 Criar `tests/integration/test_caop_s3.py` com simulador S3 ou Stubber: paridade de chaves/manifest, ausência de credenciais no modo local, negativa de escrita antes do download, falha de upload com limpeza lógica e rerun idempotente (US3/AC1–3, FR-007/009/010/017, SC-003/005).

**Critério de Conclusão**: testes S3 simulados e contratos P1 verdes, paridade local/S3 demonstrada, falha de permissão antes da rede e nenhuma dependência de AWS real.

**Registro da Fase**:

- Status:
- Feito:
- Contrato:
- Testes executados:
- Pendências:

---

## Phase 6: Polish & Cross-Cutting Concerns

**Objetivo**: consolidar evidência, documentação e gates para entregar a fundação com qualidade verificável.

### Implementation

- [ ] T028 [P] Atualizar `README.md` e `.docs/fontes_de_dados.md` com comando local, CAOP/atribuição, arquitetura Raw/Bronze/Silver, ausência de Gold nesta feature e como reprocessar/limpar órfãos (FR-001/011/014, constitution III/IV/V).
- [ ] T029 Executar `quickstart.md` com fixture e, se a DGT estiver acessível, uma coleta real local das três regiões; registrar URL/licença/versão e não inserir brutos em Git (FR-008/017, SC-001/002).
- [ ] T030 Executar CI/local: `ruff`, pytest completo, `dbt build`, `check-contract-tests.ps1`; conferir os cinco SCs e o gate de segredos; atualizar `sdd/specs/001-ingestao-caop/plan.md`, `tasks.md` e `.planning/backlog.md` somente como o `sdd-execute` prescreve (SC-001–005, constitution Quality Gates).

### Testes da Fase

- [ ] Conferir a suíte completa `uv run --locked python -m pytest -q --basetemp .pytest_tmp`, o S3 simulado e a execução local do `dbt build`; nenhum teste automatizado exige rede.

**Critério de Conclusão**: todos os requisitos/SC rastreados; contratos 5/5 verdes e trava íntegra; lint/dbt/pytest/CI verdes; quickstart executado; documentação e backlog sincronizados.

**Registro da Fase**:

- Status:
- Feito:
- Contrato:
- Testes executados:
- Pendências:

### Checklist de Release

- [X] Fase 1 (setup) concluída.
- [X] Fase 2 (fundação) concluída.
- [X] Fase 3 (US1) concluída.
- [X] Fase 4 (US2) concluída.
- [ ] Fase 5 (US3) concluída.
- [ ] Cinco contratos verdes no pytest completo; `check-contract-tests.ps1` íntegro.
- [ ] `ruff`, `pytest` e `dbt build` verdes com fixtures sem rede; CI e verificação de segredos verdes.
- [ ] Licença/atribuição e catálogo DGT corretos; nenhum bruto real ou credencial no Git.
- [ ] `quickstart.md` executado; coleta real local, se disponível, distinguida da prova automatizada.
- [ ] Nenhum Gold/publicação/deploy AWS introduzido nesta feature.

---

## Dependencies & Execution Order

- Setup → Foundational → US1 → US2/US3 → Polish. US2 depende do bruto da US1; US3 reutiliza o coletor US1 e pode ser implementada após ele independentemente da US2.
- MVP verificável: terminar até US1 e parar para conferir os cinco contratos e a CLI local.
- `[P]` indica arquivos sem dependência direta; não pressupõe delegação nem dispensa a ordem dos gates.

## Rastreabilidade

| Requisito | Tasks principais |
| --- | --- |
| FR-001, FR-002 | T005, T009, T011, T012 |
| FR-003 | T006, T010 |
| FR-004, FR-005, FR-006 | T007, T008, T012, T014 |
| FR-007, FR-008 | T007, T011, T012, T014, T027 |
| FR-009, FR-010, FR-011 | T007, T013, T025, T026, T027 |
| FR-012, FR-013 | T017, T020, T023 |
| FR-014, FR-015 | T008, T017–T024 |
| FR-016 | T016, T023 |
| FR-017 | T002, T011, T014, T023, T024, T027 |
| SC-001 | T012–T014, T029 |
| SC-002 | T017, T020–T024, T029 |
| SC-003 | T025–T027 |
| SC-004 | T001, T002, T024, T030 |
| SC-005 | T012, T014, T027, T030 |
