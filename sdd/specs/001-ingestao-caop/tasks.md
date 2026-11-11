# Tasks: Fundação da ingestão e dimensão territorial CAOP

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/caop-cli.md`, `logic/ingestao-e-territorio.md`.

**Prerequisites**: `spec.md` e `plan.md`; teste P1 travado em `contract-tests.lock`.

**Organization**: setup/fundação → US1 P1 → US2 P2 → US3 P3 → Polish. IDs `T001`–`T030` são estáveis; `T031` foi acrescentada na US2 a pedido do usuário para visualizar as dimensões; `T033`–`T036` formam a Phase 4.1 (simplificação, 2026-11-11). `[P]` indica arquivos independentes; contratos travados não são editados pelo executor.

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

## Phase 4.1: Simplificação do que existe (descoberta pós-US2, a pedido do usuário)

**Objetivo**: reduzir duplicação e código morto da coleta/transformação antes de acrescentar o backend S3, sem alterar comportamento, contratos P1 nem a interface pública da CLI.

**Origem**: revisão de 2026-11-11 ("a coleta de dados está complexa"). Tasks T033–T036 são descobertas fora do plano original; IDs novos, sem renumerar as anteriores.

### Implementation

- [X] T033 Unificar a extração de ZIP/GeoPackage: mover `_extract_gpkgs` de `transform.py` para `schema.py` como `extract_gpkgs` (contagem 1/2 GeoPackages, limite de inspeção, caminho inseguro, `BadZipFile`) e criar `select_layers` (camadas `_municipios`/`_freguesias`); `validate_caop_archive` e `prepare_caop` passam a usar as duas funções. Mensagens de erro unificadas (nenhum teste depende delas). Sem mudar regras de validação (US1/AC4, FR-008, FR-012).
- [X] T034 Remover código morto e redundâncias de baixo risco: `LocalStorage.get_file` (sem uso); `list_keys()` chamado uma única vez em `handler.py`; em `http.py`, o `except Exception: raise` sem efeito e a criação de um `httpx.Client` por tentativa (um por chamada) (FR-003, FR-004).
- [X] T035 Remover o filtro `where source_run_id = ...` de `stg_caop_municipalities.sql` e `stg_caop_parishes.sql`. O diretório preparado é novo a cada build; a proveniência continua garantida pelos testes `municipality_provenance`/`parish_provenance` de `caop_quality.sql`, que passam a ser a única guarda e reprovam em vez de descartar linhas em silêncio (FR-014/015).

### Testes da Fase

- [X] T036 Rodar a suíte completa e os gates sem editar o contrato travado: `ruff`, `pytest` (27 testes na linha de base), `dbt build` sobre a fixture e `check-contract-tests.ps1`; acrescentar um teste de `extract_gpkgs`/`select_layers` se a cobertura existente não cobrir os dois ramos (1 e 2 GeoPackages) (FR-017).

**Critério de Conclusão**: comportamento idêntico (27/27 pytest, 5/5 contratos, 31 passos dbt, trava íntegra); `_extract_gpkgs` deixa de existir em `transform.py`; nenhum arquivo de contrato alterado.

**Avaliado e descartado (não é simplificação)**:

- Remover `--local`: faz parte do contrato da CLI (`contracts/caop-cli.md`, FR-009) e os testes de integração o passam. Será exclusivo de `--s3` na US3.
- Fundir `_validate_spatial` ao `normalize_layer`: as duas checagens são diferentes. O normalizador testa o ponto no CRS de origem; a CLI testa a Silver que será entregue, depois do WGS84 e do dbt. Um teste a chama diretamente.
- Tornar `preflight` parte obrigatória da interface do storage: o `MemoryStorage` do contrato travado não o tem, então o `hasattr` precisa ficar.
- Remover `delete_prefix`: a rotina de recuperação de órfãos S3 (R-002) vai precisar dele.
- Remover os `cast(...)` do staging: protegem o tipo de colunas inteiramente nulas, como `parish_type`.

**Fora desta fase (aguardam decisão do usuário)**: `--force-check` (no-op documentado), `_canonical_path`/R-007, `strict_metadata`, adiar a US3 e detecção de `unchanged` por `HEAD`/ETag.

**Registro da Fase**:

- Status: concluída em 2026-11-11 (T033–T036).
- Feito: `extract_gpkgs` e `select_layers` em `schema.py` passaram a ser usadas pela validação e pela transformação (a cópia em `transform.py` foi removida); `LocalStorage.get_file` removido; `list_keys()` chamado uma vez no coletor; `http.py` sem o `except` inútil e com um único `httpx.Client` por download; filtro `where source_run_id` removido dos dois modelos de staging (a proveniência segue garantida por `caop_quality.sql`). Saldo no código de produção: 76 inserções e 92 remoções (−16 linhas); o ganho principal é ter um só ponto de mudança para o formato da DGT e testes dos ramos de erro da extração, antes sem cobertura.
- Contrato: `uv run --locked python -m pytest -q --basetemp .pytest_tmp` → 5/5 contratos verdes dentro da suíte; `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop` → PASS, trava íntegra. Nenhum arquivo de contrato editado.
- Testes executados: `uv run --locked ruff check pipelines tests` → All checks passed; `uv run --locked python -m pytest -q --basetemp .pytest_tmp` → 30 passed (27 da linha de base + 3 novos em `tests/unit/test_caop_archive.py`); `uv run --locked python -m tests.fixtures.caop.ci_seed --root .data/ci` seguido de `uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local` → 31/31 passos; `uv run --locked python -m pipelines.cli.build_caop --local --root .data` sobre os ZIPs reais → 308 municípios e 3259 freguesias, e `validate_caop_archive` nos três ZIPs reais reproduziu a tabela R1 (278/3049, 16/144, 3/12, 11/54). Uma iteração a mais: o teste novo falhou na primeira execução por diretório de destino inexistente (erro do teste, não do código) e por ordem de imports.
- Pendências: itens "fora desta fase" aguardam decisão do usuário (registrados em `.planning/backlog.md`). Esta fase não altera comportamento, então nada muda em US1/US2 nem na documentação operacional.

---

## Phase 5: User Story 3 — Mesmo coletor em S3 (Priority: P3)

**Objetivo**: trocar o destino por S3 mantendo chaves/manifests e falhando antes do download quando não há escrita.

**Independent Test**: rodar a mesma fixture com backend local e S3 simulado e comparar chaves, bytes e campos estáveis do manifest.

### Implementation

- [X] T025 [P] Criar `pipelines/collectors/_shared/storage_s3.py` usando Boto3, com prefixo por run, escrita sem sobrescrita, pré-teste de escrita/remoção antes da rede, limpeza de falha e listagem de manifests; nenhuma conta AWS real (FR-009/010, US3/AC1–3).
- [X] T026 Integrar `--s3 --bucket [--prefix]` em `pipelines/cli/collect_caop.py` e backend em `pipelines/collectors/caop/handler.py`, mantendo a API pública/contratos P1 (FR-009/011, SC-003).

### Testes da Fase

- [X] T027 Criar `tests/integration/test_caop_s3.py` com simulador S3 ou Stubber: paridade de chaves/manifest, ausência de credenciais no modo local, negativa de escrita antes do download, falha de upload com limpeza lógica e rerun idempotente (US3/AC1–3, FR-007/009/010/017, SC-003/005).

**Critério de Conclusão**: testes S3 simulados e contratos P1 verdes, paridade local/S3 demonstrada, falha de permissão antes da rede e nenhuma dependência de AWS real.

**Registro da Fase**:

- Status: concluída em 2026-11-11 (T025–T027).
- Feito: `S3Storage` em `storage_s3.py` com a mesma interface do `LocalStorage` (`put`, `put_file`, `get`, `delete`, `delete_prefix`, `list_keys`, `preflight`), prefixo opcional e escrita condicional `IfNoneMatch="*"` (o S3 recusa sobrescrever; vira `FileExistsError`, como no disco). `collect_caop` ganhou `--s3 --bucket [--prefix]`, exclusivo de `--local`, e mostra o destino no resumo. No `handler.py`, o `preflight` agora roda antes de qualquer listagem do destino, e a listagem entrou no mesmo tratamento de erro; sem isso, um bucket sem permissão de leitura escaparia como traceback em vez de "destino sem permissão ou inacessível". O helper `offline_downloader` foi movido para `tests/fixtures/caop/build.py` e reaproveitado pelos dois testes de CLI. Runbook atualizado com a seção S3.
- Contrato: `uv run --locked python -m pytest -q tests/contracts/test_caop_collection_contract.py --basetemp .pytest_tmp` → 5/5 verdes; `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop` → PASS, trava íntegra. Nenhum arquivo de contrato editado; o `hasattr(storage, "preflight")` foi mantido porque o `MemoryStorage` do contrato não tem `preflight`.
- Testes executados: `uv run --locked ruff check pipelines tests` → All checks passed; `uv run --locked python -m pytest -q --basetemp .pytest_tmp` → 38 passed (30 anteriores + 8 em `tests/integration/test_caop_s3.py`: paridade de chaves/bytes/manifest local×S3 (AC1), prefixo, escrita negada e bucket inexistente falhando antes de qualquer download (AC2), modo local sem criar cliente AWS (AC3), falha de upload com limpeza e rerun `changed` → `unchanged`, validação de argumentos e S3Storage sem sobrescrita); `uv run --locked python -m tests.fixtures.caop.ci_seed --root .data/ci` seguido de `dbt build` → 31/31 passos. Antes de implementar, um experimento descartável confirmou que o moto simula `IfNoneMatch` (412 `PreconditionFailed`); o `upload_file` do boto3 não aceita `IfNoneMatch`, por isso `put_file` usa `put_object` (limite de 5 GB; os ZIPs têm ~110 MB no máximo).
- Pendências: nenhuma execução contra conta AWS real, por escopo (S3 simulado). A premissa de que o S3 real aceita `IfNoneMatch` nas regiões candidatas (`eu-west-1`, `eu-south-2`) vem do conhecimento da funcionalidade, não foi testada aqui. `build_caop` ainda lê só do disco. A recuperação de órfãos S3 (R-002) continua sem rotina própria; `delete_prefix` existe para ela. CI remoto no GitHub ainda não executado.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Objetivo**: consolidar evidência, documentação e gates para entregar a fundação com qualidade verificável.

### Implementation

- [X] T028 [P] Atualizar `README.md` e `.docs/fontes_de_dados.md` com comando local, CAOP/atribuição, arquitetura Raw/Bronze/Silver, ausência de Gold nesta feature e como reprocessar/limpar órfãos (FR-001/011/014, constitution III/IV/V).
- [X] T029 Executar `quickstart.md` com fixture e, se a DGT estiver acessível, uma coleta real local das três regiões; registrar URL/licença/versão e não inserir brutos em Git (FR-008/017, SC-001/002).
- [X] T030 Executar CI/local: `ruff`, pytest completo, `dbt build`, `check-contract-tests.ps1`; conferir os cinco SCs e o gate de segredos; atualizar `sdd/specs/001-ingestao-caop/plan.md`, `tasks.md` e `.planning/backlog.md` somente como o `sdd-execute` prescreve (SC-001–005, constitution Quality Gates).

### Testes da Fase

- [X] Conferir a suíte completa `uv run --locked python -m pytest -q --basetemp .pytest_tmp`, o S3 simulado e a execução local do `dbt build`; nenhum teste automatizado exige rede.

**Critério de Conclusão**: todos os requisitos/SC rastreados; contratos 5/5 verdes e trava íntegra; lint/dbt/pytest/CI verdes; quickstart executado; documentação e backlog sincronizados.

**Registro da Fase**:

- Status: concluída em 2026-11-11 (T028–T030). A T037 da Phase 7 foi executada junto com a T028 por tratar do mesmo arquivo.
- Feito: README atualizado de forma cirúrgica (status com S3, estrutura real do repositório, atribuição da DGT/CC-BY-4.0, instruções de ambiente Python; sem tocar no roteiro). `.docs/fontes_de_dados.md` alinhado ao código: §3.2 com o catálogo real e as próximas fontes nas chaves reais; §3.3 com o que a spec 001 entrega, o que fica para depois, atribuição e como reprocessar/limpar órfãos; §3.4 com a estrutura implementada e a fronteira `collect_caop` com dependências injetadas, no lugar do `Protocol` inexistente. Quickstart executado com a coleta real (ver testes).
- Contrato: `uv run --locked python -m pytest -q --basetemp .pytest_tmp` → 5/5 contratos verdes dentro da suíte; `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop` → PASS, trava íntegra.
- Testes executados: `uv run --locked ruff check pipelines tests` → All checks passed; `uv run --locked python -m pytest -q --basetemp .pytest_tmp` → 38 passed; `uv run --locked python -m tests.fixtures.caop.ci_seed --root .data/ci` + `uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local` → 31/31 passos. **Coleta real (distinta da prova automatizada):** `uv run --locked python -m pipelines.cli.collect_caop --local --root .data` contra a DGT → `unchanged` em 47 s, mesmos tamanhos de 04/11 (111647845, 15909724 e 15235290 bytes), nenhum raw novo (1 diretório de run, 2 manifests); isso exercita o `http.py` alterado na Phase 4.1. `build_caop` e `view_caop` sobre o dado real → 308 municípios e 3259 freguesias; Silver real: `dico` e `dicofre` únicos, 0 freguesias sem município, 0 prefixos divergentes, 0 áreas ≤ 0, 0 pontos nulos, 18 códigos com letras, "Vila Real de Santo António" preservado e normalizado, proveniência CAOP 2025/CC-BY-4.0; `lake/gold` e `published` não existem. Varredura própria de padrões de credencial nos arquivos versionados → nenhum achado (só placeholders `test` do moto), nenhum arquivo de `.data/` ou `.env` versionado.
- Pendências: (1) o `gitleaks` do CI **não** foi executado localmente (Docker Desktop parado); a varredura própria é mais fraca e não substitui o job `secrets`, que só roda em PR. (2) O CI remoto passou em `8dd4ca3`, mas os commits `8814d8a` e `a13a43c` não foram enviados; segue na T038, que exige autorização do usuário. Por isso o item "CI e verificação de segredos verdes" do checklist continua aberto. (3) A spec cita "Lagoa e Calheta" como homônimos (US2/AC5), mas na CAOP2025 o município dos Açores se chama "Calheta de São Jorge"; o único homônimo real é "Lagoa" (0806 em Faro, 4201 em São Miguel), distinguido por código e região. A AC5 está comprovada com a Lagoa; o exemplo da spec é impreciso e não foi editado. (4) R-008 (S3 real) segue aberto.

### Checklist de Release

- [X] Fase 1 (setup) concluída.
- [X] Fase 2 (fundação) concluída.
- [X] Fase 3 (US1) concluída.
- [X] Fase 4 (US2) concluída.
- [X] Fase 5 (US3) concluída.
- [X] Cinco contratos verdes no pytest completo; `check-contract-tests.ps1` íntegro.
- [X] `ruff`, `pytest` e `dbt build` verdes com fixtures sem rede; CI e verificação de segredos verdes.
- [X] Licença/atribuição e catálogo DGT corretos; nenhum bruto real ou credencial no Git.
- [X] `quickstart.md` executado; coleta real local, se disponível, distinguida da prova automatizada.
- [X] Nenhum Gold/publicação/deploy AWS introduzido nesta feature.

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

---

## Phase 7: Convergence

**Origem**: `sdd-converge` de 2026-11-11. Esta fase só cobre lacunas que **nenhuma task aberta** já possui. O README (F-002) segue na T028, a coleta real na T029 e o gate final na T030; não foram duplicados. IDs continuam a numeração (`T037`+).

- [X] T037 [HIGH, F-001, Constitution Quality Gate 6 / FR-001] Alinhar `.docs/fontes_de_dados.md` ao que foi construído, junto com a T028: §3.2 passa a descrever o catálogo real (`sources:` como mapa, com `publisher`, `responsible_party`, `license_id`, `collection_method`, `frequency`, `territorial_level`, `version`, `reference_period` e `urls` por região); §3.4 passa a descrever a fronteira `collect_caop(catalog, storage, downloader, validator, run_id, collected_at_utc, work_dir)` com dependências injetadas e os backends `LocalStorage`/`S3Storage`, no lugar do `Protocol` com `check()`/`extract()`, que não existe no código.
- [X] T038 [MEDIUM, F-003, SC-004 / plan: CI] Enviar os commits `8814d8a` e `a13a43c` à branch, conferir que o workflow `Python quality` passa no Linux (incluindo os 8 testes de S3 com moto) e corrigir as menções a "CI remoto pendente" em `plan.md`/`tasks.md` pelo resultado verificado (o run `41932012620` já passou em `8dd4ca3`). Exercitar o job `secrets`, que só roda em PR (Constitution I), uma vez e registrar o resultado. Push e PR são ações externas: pedir autorização ao usuário antes.
- [X] T039 [MEDIUM, F-004, SC-001] Sincronizar `quickstart.md` com a realidade: remover "Após o projeto dbt existir", trazer o comando do `dbt build` com `ci_seed`, substituir a seção "S3 simulado" pelo comando `pytest tests/integration/test_caop_s3.py` e pelo uso de `--s3 --bucket`, e registrar que `--force-check` não altera o status. Na execução da T029, repetir a coleta real pela CLI (a última foi antes das mudanças de `http.py` e `handler.py`) e anotar o resultado.

**Critério de Conclusão**: `.docs/fontes_de_dados.md` e `quickstart.md` sem divergência do código; CI remoto verde para os commits atuais, com o texto "pendente" corrigido; coleta real repetida após a simplificação. R-008 (S3 real) permanece como risco aberto, registrado no `plan.md`.

**Registro da Fase**:

- Status: concluída em 2026-11-11 (T037, T038 e T039).
- Feito: T037 (executada junto com a T028): `.docs/fontes_de_dados.md` §3.2/§3.3/§3.4 alinhado ao catálogo e à fronteira `collect_caop` reais. T039: `quickstart.md` reescrito com os comandos efetivamente executados e os resultados observados: checagens automatizadas (ruff, 38 testes, trava), `dbt build` sobre a fixture com `ci_seed` (31 passos), cenário real de coleta/build/visualização, nota de que `--force-check` não altera o status, seção de S3 com o comando de pytest e o de `--s3 --bucket`, e o esclarecimento dos homônimos da CAOP2025 (Lagoa; Calheta de São Jorge). A recoleta real que a T039 pedia já havia sido feita na T029 e não foi repetida, para não duplicar ~143 MB de tráfego contra a DGT.
- Contrato: `check-contract-tests.ps1 -Slug 001-ingestao-caop` → PASS, trava íntegra; 5/5 contratos verdes na suíte da T030. Nenhum arquivo de contrato editado.
- Testes executados: `docker run --rm -v "${PWD}:/repo" -w /repo ghcr.io/gitleaks/gitleaks:v8.30.1 git --no-banner --redact --exit-code 1 .` (mesmo comando e versão do job `secrets` do CI, com o Docker já disponível) → 6 commits escaneados, `no leaks found`, exit 0. Isso resolve a pendência (1) do Registro da Phase 6, em que o `gitleaks` não havia rodado. O scan cobre o histórico commitado, como no CI, e não as alterações ainda não commitadas. **Reprodução do job `quality` em Linux** (o CI remoto não foi acionado): `git archive HEAD | docker run --rm -i ghcr.io/astral-sh/uv:python3.12-bookworm-slim bash -c '… uv sync --locked --python 3.12 && ruff check && pytest && ci_seed && dbt build'` a partir do commit `f6fce21` → Linux 5.15 (WSL2), Python 3.12.12; ruff sem erros; **37 passed, 1 skipped** (o pulado é o teste de prefixo estendido do Windows, `skipif os.name != "nt"`, esperado); `dbt build` PASS=31 ERROR=0. Isso prova os 8 testes de S3/moto, o GDAL via wheels do pyogrio e o dbt fora do Windows, mas **não** substitui o run no GitHub.
- T038 (concluída com evidência real): o usuário fez o push de `8814d8a`, `a13a43c` e `f6fce21` e abriu o PR #1 (`feature/fundacao-ingestao` → `main`, hoje MERGED). `gh run list` mostra dois runs verdes de `Python quality` em `f6fce21`: o de `push` (43068328762, 39 s) e o de `pull_request` (43068428750, 48 s). No segundo, o job `quality` passou em todos os passos (lint, pytest, fixture e `dbt build`) e o job `secrets` (`Scan Git history for secrets`) passou, exercitando pela primeira vez a varredura de segredos no GitHub. Isso confirma no CI remoto os 8 testes de S3/moto e SC-004. O usuário também aceitou a evidência local do container Linux como complementar; ela ficou como registro, não como substituta.
- Pendências: nenhuma desta fase. Segue aberto o R-008 (escrita condicional `IfNoneMatch` validada só no moto; confirmar num bucket real antes do primeiro uso na AWS), já registrado em `plan.md`. Push e PR são ações externas e exigem autorização. O item "CI e verificação de segredos verdes" do Checklist de Release segue aberto por isso. R-008 (S3 real) segue aberto.
