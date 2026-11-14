# Quickstart: Censos 2021 por freguesia

CLI, preparação, relatórios e modelos estão implementados. Este documento define o procedimento de aceite reproduzível; consultar os checkpoints em plan.md/tasks.md para as evidências efetivamente concluídas.

## Prerequisites

- Repositório e Python 3.12 com `uv sync --locked`; preservar alterações locais preexistentes e não atualizar dependências incidentalmente.
- Dimensões locais `lake/silver/dim_parish/data.parquet` e `dim_municipality/data.parquet`; correspondência `xwalk_parish_2013_2025/data.parquet`, com versões compatíveis. Não reconstruir/apagar dados existentes só para o smoke.
- T001: evidência da licença/termos da fonte e semântica territorial registrada; API sem chave. Falha/indisponibilidade de robots precisa de diagnóstico registrado, nunca contorno.
- Disco gravável para raw e candidato; somente um build censitário por raiz. Não testar sobre `.data` real se a intenção é usar fixtures.

## Automated checks

```powershell
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 006-censos-2021-freguesia -Json
```

Conferir também as travas 001–005 usando seus slugs; o executor não modifica arquivos travados. Os cinco contratos da feature devem passar sem qualquer alteração dos arquivos travados.

## Offline end-to-end acceptance

```powershell
uv run --locked python -m tests.fixtures.censos2021.ci_seed --root .data/ci-censos
uv run --locked python -m pipelines.cli.build_censos --local --root .data/ci-censos
```

Conferir census_reports/coverage.csv: universo completo, own/inherited/missing, motivo para ausências; total e grupos de suportes diferentes não aparentam soma reconciliada. Repetir fixture/coleta controlada sem sobrescrever run; simular falha de input/dbt/promoção pelos testes de integração e verificar hashes da saída anterior e tabelas de outras fontes.

Para dbt direto depois do seed:

```powershell
$env:CENSOS_BUILD_DIR = '.data/ci-censos'
$env:CENSOS_PREPARED_DIR = '.data/ci-censos/prepared'
$env:OBS_SILVER_DIR = '.data/ci-censos/lake/silver'
$env:CAOP_DUCKDB_PATH = '.data/ci-censos/censos.duckdb'
$env:DBT_TARGET_PATH = '.data/ci-censos/dbt-target'
$env:DBT_LOG_PATH = '.data/ci-censos/dbt-logs'
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:censos
```

Rodar em terminal dedicado ou restaurar as variáveis antes de outros builders.

## Official-data acceptance

Depois dos gates offline e T001, registrar a fonte no catálogo e executar:

```powershell
uv run --locked python -m pipelines.cli.collect_censos --local --root .data
uv run --locked python -m pipelines.cli.build_censos --local --root .data
```

Guardar run/manifest, checksums, duração/bytes/retries, revisão, geografia e evidências de cobertura dos 19 recortes canônicos em todos os municípios/regiões. O total deve concordar com as categorias na mesma origem ou ter explicação estatística oficial verificável. Validar os recortes exatos 25–39/65+ pela disponibilidade dos limites; não criar os indicadores finais.

Repetir coleta e comprovar unchanged sem novos originais. Não declarar concluída enquanto houver falha técnica/idade obrigatória não verificada. Para escolher explicitamente um run completo anterior após falha recente, usar `build_censos --local --root .data --run-id <run-completo>` e registrar a escolha; não ocultar a falha mais recente.

Leitura manual do relatório é complemento à checagem automatizada. Hardware, navegador e E2E visual não se aplicam; fonte real e CI remoto têm evidências separadas da fixture e do teste local.

## Emenda de coleta D2

O catálogo atual declara201 itens:2 metadados,102 lotes2025 e97 lotes2013. Cada lote contém até32 códigos oficiais e todas as categorias da respectiva família. O coletor preserva uma resposta raw por lote e reprova linhas perdidas/repetidas/extras; o preparo verifica a união nacional contra os metadados e a CAOP. O build mantém suporte aos snapshots antigos de41 consultas por idade. Os comandos acima continuam os mesmos. A prova real por lotes e sua repetição ficam no checkpoint atual de plan.md.

### Prova real concluída após emenda D2 — 2026-11-13

Coleta inicial `20261113T231450079026Z-ddf26aad`:201 chamadas/201 respostas,200 changed e1 metadado unchanged,32.804.869 bytes referenciados,449,406s. Repetição `20261113T232234325869Z-00a1b4a4`:201/201 unchanged,201 chamadas,449.906s,nenhum novo raw. Ambos os manifests estão em `.data/manifests/censos/`;originais,hashes,consultas e revisões da primeira rodada foram conferidos após a segunda. Recibos e auditorias em `.data/receipts/censos-proof/`.

Build real aprovado:3.259 freguesias,308 municípios,19 categorias canônicas e61.921 observações próprias;0 herdadas,0 ausentes. Bronze123.761 linhas;população total2021 de10.343.066. Cobertura regional completa e18 códigos alfanuméricos preservados. Todas as observações têm fonte,licença,território,run e referências raw verificadas. Vinte e dois arquivos vizinhos permaneceram idênticos. dbt:4 modelos e21 testes aprovados. Relatórios: `.data/lake/silver/census_reports/`. Fonte INE,Censos2021,CC-BY-4.0. O método de reexpressão não foi divulgado pelo publicador nas evidências consultadas;essa limitação permanece registrada,sem estimativa do projeto.

Validação local: `uv run --locked python -m pytest -q --basetemp .data/tmp/censos-batches-full` →411 passed em571,46s;2 regressões adicionais (histórico completo41 itens e repetição por lotes) →2 passed em3,37s,fora da coleta inicial dessa suíte. Área censos →61 passed em32,12s antes dessas2 adições. `uv run --locked ruff check pipelines tests` aprovado. Seed/build de CLI em `.data/ci-censos-batches` aprovado;travas001–006 íntegras;revisão independente sem bug material. O CI remoto e seu scan de segredos seguem pendentes de commit/push/PR autorizado;nenhuma execução em nuvem ou publicação foi demonstrada. Não marcar Implementada/Convergida antes do gate restante.
