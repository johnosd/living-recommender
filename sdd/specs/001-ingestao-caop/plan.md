# Implementation Plan: Fundação da ingestão e dimensão territorial CAOP

**Slug**: `001-ingestao-caop` | **Date**: 2026-11-04 | **Spec**: `sdd/specs/001-ingestao-caop/spec.md`

## Summary

Criar a primeira coleta rastreável do projeto: catálogo CAOP, download das três regiões, checksum/manifest, detecção de conteúdo inalterado, armazenamento local e S3 simulado com as mesmas chaves. A partir do último manifest `changed`, preparar GeoPackages em Parquet, materializar staging Bronze e dimensões territoriais Silver com dbt-duckdb, e bloquear saídas inválidas. Gold, publicação e infraestrutura AWS ficam para outras specs.

## Technical Context

**Language/Version**: Python 3.12 (`.python-version`, `pyproject.toml`); SQL/dbt Core. O repositório não tinha código de aplicação nem runner antes deste plano; o plano criou apenas o mínimo para os contratos vermelhos.

**Primary Dependencies**: `uv` para ambiente/lock; pytest/ruff; HTTPX, PyYAML, Boto3, Pyogrio/GeoPandas/Shapely/PyArrow, dbt Core + dbt-duckdb. Versões compatíveis estão no `uv.lock` e `uv sync --locked` passou no Python 3.12. GeoPandas lê camadas GeoPackage, reprojeta geometrias e calcula `representative_point()`; o adapter dbt-duckdb lê/escreve Parquet externo ([documentação](https://github.com/duckdb/dbt-duckdb/blob/master/README.md)).

**Storage**: `.data/` local e S3 com `raw/source=caop/version=<ano>/run_id=<id>/`, `manifests/caop/<id>.json`, `lake/bronze/` e `lake/silver/` em Parquet. `.data/` e `.pytest_tmp/` estão no `.gitignore`. Nenhum dado CAOP real no Git.

**Testing**: pytest sem rede com fakes/fixtures; 5 contratos P1 travados; testes adicionais de parser GeoPackage/CRS/geometria, CLI local, S3 simulado e `dbt build` sobre fixture. O script de trava não infere contagem de testes Python: a contagem de 5 é conferida pelo runner e no plano.

**Target Platform**: Windows local nesta feature, com código portátil para execução futura em ECS/Lambda conforme ADR-002. O normalizador GeoPackage pode exigir ambiente com GDAL; não há deploy AWS nesta spec.

**Performance Goals**: downloads grandes não ficam todos em memória; staging usa arquivos temporários, prazo e retry com backoff. Nenhuma meta de tempo numérica foi especificada.

**Constraints**: raw original e imutável; versões distintas da fonte/coleta/processamento; licença DGT e atribuição; três regiões/CRS; 308 municípios; ponto contido no polígono; dimensões só da edição vigente; `unchanged` sem novos arquivos raw; nenhuma credencial em arquivo versionado. P1 deve funcionar antes das dimensões e do S3.

**Scale/Scope**: três GeoPackages da edição vigente e duas dimensões; volume do projeto previsto abaixo de 1 GB (ADR-001), mas o tamanho real dos downloads será medido na primeira coleta. Custo recorrente da feature local/S3 simulado: US$ 0; AWS futura fora do escopo e sob gate da constitution.

## Decisões Invariantes

- **D1:** O catálogo fornece versão, período, licença e URLs de Continente, Açores e Madeira. O coletor apenas busca/valida/guarda bytes; geometria é transformada depois (ADR-002 D3/D4, `.docs/fontes_de_dados.md` §3.1).
- **D2:** `run_id` identifica tentativa, não edição da CAOP. A comparação usa checksums das três regiões contra o último manifest `changed`. `--force-check` repete verificação, sem forçar `changed`.
- **D3:** Somente manifest `changed` completo torna um prefixo raw consumível. Falha capturada limpa o prefixo do run e registra `failed`; um crash S3 pode deixar objetos órfãos invisíveis aos leitores e sujeitos a limpeza posterior (R-002).
- **D4:** Normalização geográfica usa CRS métrico por região para área, `representative_point()` para ponto interno, WGS84 para latitude/longitude, e código oficial como identidade. Não substituir ponto representativo por centroide geométrico.
- **D5:** Esta spec materializa staging em `lake/bronze` e dimensões em `lake/silver`, com Parquet e testes; não produz Gold, `published/vN`, SCD2, crosswalk ou seeds de sinônimos.
- **D6:** Local e S3 compartilham chaves/manifests; apenas o backend muda. Todo teste automatizado da coleta/transformação roda com fixture e sem rede/conta AWS real.

## Constitution Check

*GATE pré-design verificado após leitura da constitution; pós-design reavaliado após `research.md`, modelo, contrato e lógica.*

| Princípio | Pré-Design | Pós-Design | Notas |
| --- | --- | --- | --- |
| I. Nenhum segredo fora do cofre | Conforme | Conforme | Local sem credenciais; S3 simulado; `.env` ignorado; CI verifica segredos. |
| II. Núcleo do produto estático e sem chave | Conforme | Conforme | Nenhum servidor/API pública ou publicação nesta feature. |
| III. Dados honestos e rastreáveis | Conforme | Conforme | Fonte, licença, versão, período e run no manifest e dimensões; chaves oficiais; qualidade bloqueante. |
| IV. Coleta responsável e licenciada | Conforme | Conforme | Catálogo prévio, User-Agent, timeout, rate limit, retry, licença DGT. |
| V. Bruto imutável e publicação atômica | Conforme | Conforme | Raw sem sobrescrita; `unchanged` sem raw; manifest marca conclusão; publicação fora do escopo. |
| VI. Privacidade por padrão | Conforme | Conforme | Só limite administrativo público; sem dados pessoais ou preferências. |
| VII. Custo como requisito | Conforme | Conforme | Local e S3 simulado: sem recurso recorrente; AWS real/terraform fora do escopo. |

**Resultado:** nenhuma violação justificável ou não justificável. O detalhe da recuperação após crash S3 é risco técnico R-002, sem permitir que um prefixo incompleto seja usado.

## Project Structure

### Documentation (this feature)

```text
sdd/specs/001-ingestao-caop/
  spec.md                 # existente e editada antes deste plano
  plan.md                 # este plano
  tasks.md                # sequência de execução
  research.md             # DGT, geoespacial, dbt, S3
  data-model.md           # manifest/raw/bronze/silver
  contracts/caop-cli.md   # superfície do operador
  logic/ingestao-e-territorio.md
  quickstart.md
  handoff.md              # mapa da próxima sessão
  contract-tests.lock     # SHA256 do teste Python
```

### Source Code (repository root)

```text
.gitignore, .python-version, pyproject.toml, uv.lock
.github/workflows/python.yml                 # CI criado no Setup
config/sources.yml                            # catálogo CAOP criado na Foundational
pipelines/collectors/_shared/                 # catálogo, HTTP, storage e manifest
tests/unit/                                   # testes isolados da Foundational
pipelines/collectors/caop/schema.py            # inspeção/validação ZIP e GeoPackage
pipelines/cli/collect_caop.py                  # CLI local da US1
tests/integration/test_caop_cli_local.py       # execução local sem rede
README.md, .docs/, sdd/adr/, .planning/       # documentação existente
pipelines/collectors/caop/handler.py          # stub criado pelo sdd-plan
pipelines/collectors/__init__.py              # stub de pacote
pipelines/__init__.py                         # stub de pacote
tests/contracts/test_caop_collection_contract.py  # contrato travado
```

Ainda **não existem** `analytics/dbt/`, a CLI de build e o backend S3: são destinos concretos de criação nas próximas tasks, não arquivos encontrados.

**Structure Decision:** seguir o desenho `pipelines/` + `config/` + `analytics/dbt/` da spec e `.docs/fontes_de_dados.md`, criando apenas o necessário nesta feature. `pipelines.collectors.caop.handler.collect_caop` é a fronteira pública injetável dos contratos P1; a CLI monta downloader, validator e backend. Pyogrio/GeoPandas preparam GeoPackage; dbt-duckdb executa modelos Bronze/Silver. A árvore acima distingue o que existe do que ainda será criado.

## Complexity Tracking

Nenhuma violação da constitution exige exceção.

## Estratégia de Testes

Prioridade: unitário → contrato/integração → ponta a ponta local → verificação manual da fonte real. Os contratos P1 usam fakes de downloader/validator/storage e não provam o schema real; testes adicionais com GeoPackage sintético e a checagem manual da DGT cobrem essa fronteira. Os modelos Silver exigem testes dbt `not_null`, `unique`, `relationships`, códigos, áreas, 308 municípios e contenção espacial. O S3 simulado verifica chaves e falha antecipada de permissão. Sem testes de hardware.

Comandos-base atuais:

```powershell
uv sync --locked
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop
```

Após T018 criar `analytics/dbt/dbt_project.yml` e `profiles.yml`, comando de build local sobre fixture:

```powershell
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local
```

Esse último comando ainda não é executável: dbt e seus arquivos serão adicionados pelo `sdd-execute`.

### Testes de Contrato

Arquivo travado: `tests/contracts/test_caop_collection_contract.py`. Comando: `uv run --locked python -m pytest -q tests/contracts/test_caop_collection_contract.py --basetemp .pytest_tmp`. Vermelho observado: **5 failed**, todos por `NotImplementedError: not implemented` no stub `pipelines/collectors/caop/handler.py`, sem falha de importação/sintaxe. O primeiro uso do runner encontrou permissão negada no diretório temporário padrão do Windows; `--basetemp .pytest_tmp` resolveu o ambiente.

| Teste | Origem | Fase | Vermelho esperado |
| --- | --- | --- | --- |
| `test_us1_ac1_fr004_fr005_changed_has_three_immutable_raw_files_and_manifest` | US1/AC1, FR-004/005 | US1 | `NotImplementedError` |
| `test_us1_ac2_fr006_unchanged_writes_only_verification_manifest` | US1/AC2, FR-006 | US1 | `NotImplementedError` |
| `test_us1_ac3_fr007_download_failure_leaves_no_raw_and_records_failed` | US1/AC3, FR-007 | US1 | `NotImplementedError` |
| `test_us1_ac4_fr008_invalid_region_is_not_committed` | US1/AC4, FR-008 | US1 | `NotImplementedError` |
| `test_fr002_unknown_source_is_rejected_before_download` | FR-002 | US1 | `NotImplementedError` |

Stub não travado: `pipelines/collectors/caop/handler.py` (assinatura pública + exceção; corpo provisório). O script `.planning/scripts/powershell/check-contract-tests.ps1` trava SHA256, mas não tem adaptador de contagem/skip para Python: `contract-tests.lock` informa contagem desconhecida. A contagem de 5 foi confirmada pelo pytest; o executor não edita o teste travado.

## Estado Atual

<!-- Sobrescrita a cada checkpoint pelo sdd-execute. Vazia na criação. -->

| Área | Estado |
| --- | --- |
| Fase | Setup, Foundational, US1 e US2 concluídos (T001–T024, T031–T032); próxima fase US3/S3 simulado. |
| Fonte real | Três ZIPs da CAOP2025 coletados em `.data/raw/`; Bronze/Silver locais gerados com 308 municípios, 3259 freguesias e 18 `dtmnfr` alfanuméricos. |
| Coleta e transformação | Coletor local, checksums e manifests; normalização geoespacial e `dbt build` em área temporária com promoção após qualidade. |
| Visualização | `.data/explore/caop.html`, `municipios.csv` e `freguesias.csv` gerados da Silver real; guia em `docs/runbooks/coletas.md`. |
| Testes | 27/27 pytest, Ruff, 31/31 passos dbt na fixture e trava P1 íntegra; build real local passou. |
| CI | Workflow atualizado para gerar fixture e rodar dbt; execução remota no GitHub pendente. |

## Riscos e Decisões

<!-- IDs estáveis; o sdd-execute atualiza resoluções, não remove itens. -->

| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |
| R-001 | Esquema/camadas dos três GeoPackages reais ainda não inspecionados. | Alto: mapeamento e validação P1/P2. | Resolvido: T011 inspecionou três ZIPs/quatro GeoPackages reais, registrou camadas/campos/CRS em `research.md` R1 e criou fixture sintética. |
| R-002 | S3 não transaciona três objetos; crash pode deixar órfãos físicos. | Médio: limpeza operacional, sem visibilidade lógica. | Manifest `changed` só ao fim; leitores ignoram órfãos; remover em recuperação; falhas capturadas limpam run. |
| R-003 | DGT pode mudar URL, edição ou licença. | Médio: coleta/atribuição. | Catálogo revisado por edição; metadados registrados no manifest; erro explícito para HTML/ZIP inválido. |
| R-004 | CRS distintos e multipartes tornam área/ponto fáceis de errar. | Alto: dimensões incorretas. | GeoPandas por região/grupo, testes de contenção e fixture com exclave; 308 municípios como gate. |
| R-005 | A CAOP tem três URLs, enquanto `source_url` estava descrito no singular. | Médio: ambiguidade no schema do manifest. | Resolvido: `spec.md` explicita `source_url` como mapa por região; catálogo e `manifest.py` usam esse formato. |
| R-006 | A US2/AC1 exigia `dicofre` de seis dígitos, mas 18 códigos oficiais CAOP2025 têm letras após os quatro dígitos municipais. | Alto: o aceite excluiria freguesias válidas ou exigiria inventar códigos. | Resolvido: autor aprovou emenda de US2/AC1 e `data-model.md` para seis caracteres (`[0-9]{4}[0-9A-Z]{2}`), preservando `dtmnfr` oficial; US2 liberada. |
| R-007 | `Path.resolve()` no Windows retornou ocasionalmente `\\?\C:\...` para o mesmo caminho durante duas coletas concorrentes, e a comparação literal o tratou como fora da raiz. | Médio: teste de concorrência e coleta local podem falhar sem corrupção do bruto. | Resolvido: normalizar prefixo Windows antes da checagem de contenção; regressão reproduziu o erro antes da correção e 30 repetições da concorrência passaram depois. |

## Execution Notes

<!-- Tabela append-only, mantida pelo sdd-execute. -->

| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |
| 2026-11-04 | Setup | T001–T004 concluídas: lock Python 3.12, CI, ignores e lint local. | Implementar helpers da Foundational; CI completo depende da US1/US2. |
| 2026-11-04 | Foundational | T005–T010 concluídas: catálogo DGT, HTTP, storage local e manifest; 7 testes unitários e Ruff verdes. | Inspecionar schema/CRS reais na US1; contratos P1 ainda vermelhos no stub. |
| 2026-11-04 | US1 | T011–T015 concluídas: fonte real inspecionada, coletor/CLI local e fixtures; 16/16 pytest, 5/5 contratos e Ruff verdes. | Resolver R-006 antes da US2; CI remoto e S3 ainda pendentes. |
| 2026-11-04 | Documentação operacional | Criado `docs/runbooks/coletas.md` a pedido do usuário, com execução local, saídas e status; README aponta para o guia. | Coleta real pela CLI permanece sem execução; R-006 bloqueia US2. |
| 2026-11-04 | US2 | T016–T024, T031–T032 concluídas: Bronze/Silver, 308/3259 linhas reais, visualizador HTML/CSV e correção da concorrência Windows; 27 pytest e 31 passos dbt verdes. | US3/S3 simulado e CI remoto pendentes; navegador automatizado indisponível para inspeção visual do HTML. |

**PRÓXIMO**: executar a Fase 5 (US3), implementando backend S3 simulado com paridade de chaves/manifests e negativa de permissão antes do download.

## Arquivos Principais

<!-- Sobrescrita a cada checkpoint pelo sdd-execute. -->

- `pipelines/collectors/caop/transform.py` e `pipelines/collectors/caop/names.py` — preparo geográfico e nomes.
- `analytics/dbt/` — staging Bronze, dimensões Silver e testes de qualidade.
- `pipelines/cli/build_caop.py` e `pipelines/cli/view_caop.py` — build local e visualização.
- `tests/fixtures/caop/ci_seed.py` e `tests/integration/test_caop_build.py` — fixture nacional e prova sem rede.
- `docs/runbooks/coletas.md` — execução da coleta, build e abertura do explorador.

## Cuidados para Retomada

<!-- Anexados pelo sdd-execute. -->

- O build dbt no CI só é habilitado quando `analytics/dbt/dbt_project.yml` e `tests/fixtures/caop/ci_seed.py` existirem; T024 deve criar o gerador de fixture com esse caminho. O job pytest continuará vermelho até a implementação da US1.
- Resolvido em T011: as URLs e a licença foram conferidas nas páginas oficiais da DGT e o schema, as camadas e os CRS foram inspecionados nos arquivos reais em 2026-11-04.
- T011 fechou a inspeção real: o ZIP dos Açores tem dois GeoPackages com EPSG:5014/5015; os outros usam EPSG:3763 e EPSG:5016. Os 18 códigos alfanuméricos oficiais não podem ser filtrados para satisfazer o aceite numérico da US2.
- A Fase 4 preserva `dtmnfr` como `dicofre` texto de seis caracteres; a emenda de US2/AC1 foi aprovada pelo autor e registrada em R-006.
- O explorador HTML é gerado a partir da Silver com `uv run --locked python -m pipelines.cli.view_caop --root .data`; fica fora do Git em `.data/explore/`. A automação do navegador recusou a conexão nesta sessão; CSV, payload e sintaxe JavaScript foram verificados localmente.
