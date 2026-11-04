# Handoff — 001-ingestao-caop

## Contexto

Repositório `living-recommender`, branch `feature/fundacao-ingestao`. Python 3.12 + `uv` para coletor, GeoPandas/Pyogrio para preparar geometrias, dbt Core + dbt-duckdb para Bronze/Silver. Próximo comando: `/sdd-execute 001-ingestao-caop`. Backlog: `Planejada`, 0/38 tasks. A `spec.md` já estava modificada pela conversa anterior para explicitar Raw/Bronze/Silver/Gold; releia-a. Antes deste plano não havia projeto Python/dbt; `pyproject.toml`, `uv.lock`, `.python-version`, stub e teste de contrato foram criados pelo plano.

## O que a feature entrega

- **US1/P1:** coleta local CAOP de três regiões, raw original, manifest/checksum, `unchanged` sem novo raw e falha sem parcial após erro tratado.
- **US2/P2:** dimensões vigentes de 308 municípios e freguesias, staging Bronze, Silver com área regional e ponto dentro do polígono; sem SCD2/Gold.
- **US3/P3:** mesmo layout/chaves no S3 simulado; sem deploy ou conta AWS real.

## Leitura obrigatória, em ordem

1. `spec.md`: escopo, US/FR/SC e limite Bronze/Silver.
2. `plan.md`: decisões D1–D6, constitution, riscos e comandos.
3. `tasks.md`: ordem T001–T030 e rastreabilidade.
4. `research.md`: fontes DGT, geoespacial, dbt e S3; R1 exige inspeção de GeoPackages reais antes do mapeamento.
5. `data-model.md`: catálogo, manifest, Raw/Bronze/Silver e proveniência.
6. `contracts/caop-cli.md`: argumentos, saídas e códigos da CLI.
7. `logic/ingestao-e-territorio.md`: algoritmo de coleta/seleção e cálculo territorial.
8. `quickstart.md`: verificação automatizada e coleta local manual.
9. `.planning/memory/constitution.md`: princípios I–VII e gates de qualidade.

## Testes de contrato

`tests/contracts/test_caop_collection_contract.py`: **5 testes P1**, todos na Fase 3. Rodar `uv run --locked python -m pytest -q tests/contracts/test_caop_collection_contract.py --basetemp .pytest_tmp`. Resultado atual esperado: 5 falhas por `NotImplementedError` do stub. Verificar integridade com `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop`. A trava Python guarda SHA256, mas o script não infere contagem/skip; o pytest confirmou cinco casos. Não há travas de outras features.

## Stubs criados

`pipelines/collectors/caop/handler.py`: `CollectionError` e assinatura pública `collect_caop(catalog, storage, downloader, validator, run_id, collected_at_utc, work_dir)`; corpo `NotImplementedError`, não travado. Os pacotes `pipelines/`, `pipelines/collectors/` e `pipelines/collectors/caop/` têm `__init__.py` vazios. `pyproject.toml` só tem pytest/ruff; T001 acrescenta dependências reais.

## Armadilhas já mapeadas

- DGT publica três ZIP/GeoPackage para CAOP2025; edição 2025 não é data de coleta/publicação. URLs/licença entram no catálogo, nunca hardcoded. Inspecionar camadas/CRS reais: modelo conceitual da DGT não garante layout do arquivo distribuído.
- O runner pytest precisa de `--basetemp .pytest_tmp` neste Windows: a pasta temporária padrão deu acesso negado. `.pytest_tmp/` é ignorada pelo Git.
- `representative_point()` dentro do polígono, não centroide geométrico; área no CRS métrico de cada região/grupo; código oficial é a chave, nunca nome.
- Selecionar o último manifest `changed`; ignorar `failed`, `unchanged` e prefixos S3 sem manifest. `--force-check` não muda checksum/status.
- `lake/gold/`, `published/vN`, AWS real e histórico `valid_from/valid_to` estão fora desta spec.

## Pendências do Analyze

- **A-001 MEDIUM:** FR-005 fala em `source_url` singular, mas a CAOP tem três URLs; `data-model.md` propõe mapa por região. Formalizar o formato na spec antes de congelar o schema do manifest.
- **A-002 MEDIUM:** FR-007/SC-005 dizem que falha não deixa parcial em `raw/`; S3 não tem transação entre três objetos. O plano garante limpeza após falha capturada e invisibilidade lógica sem manifest; alinhar a redação da spec para crash/orfandade antes do aceite US3.

## Gate de pronto

Contratos 5/5 verdes e trava íntegra; `uv run --locked ruff check pipelines tests`, `uv run --locked python -m pytest -q --basetemp .pytest_tmp` e `uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local` verdes após T018; integração S3 simulada; `quickstart.md`; catálogo/atribuição e README atualizados; CI com verificação de segredos; backlog sincronizado. Coleta real DGT é verificação manual adicional, distinta dos testes sem rede. Não há gate de hardware nem deploy AWS nesta feature.
