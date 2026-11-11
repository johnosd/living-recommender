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
| Fase | Todas as fases concluídas, incluindo a Phase 7 (Convergence): T001–T039. Falta apenas rodar `sdd-converge` outra vez para confirmar a convergência. |
| Fonte real | Três ZIPs da CAOP2025 coletados em `.data/raw/`; recoleta real de 2026-11-11 deu `unchanged` (mesmos bytes). Bronze/Silver locais com 308 municípios, 3259 freguesias e 18 `dtmnfr` alfanuméricos. |
| Coleta e transformação | Coletor com destino local ou S3 (`--s3 --bucket [--prefix]`), checksums e manifests; normalização geoespacial e `dbt build` em área temporária com promoção após qualidade. O build lê só do disco local. |
| Visualização | `.data/explore/caop.html`, `municipios.csv` e `freguesias.csv` gerados da Silver real; guia em `docs/runbooks/coletas.md`. |
| Testes | 38/38 pytest (8 de S3 simulado com moto), Ruff, 31/31 passos dbt na fixture e trava P1 íntegra; build real local repetido após a simplificação (308 municípios, 3259 freguesias). Nenhum teste contra AWS real. |
| CI | Verde no GitHub em `f6fce21`, nos runs de push (43068328762) e de pull_request (43068428750): job `quality` (lint, pytest, fixture e `dbt build`) e job `secrets` (gitleaks sobre o histórico). PR #1 mergeado em `main`. Histórico: o workflow já havia passado em `8dd4ca3`.
| CI (histórico) | O workflow `Python quality` passou no GitHub em `8dd4ca3` (lint, pytest, fixture e `dbt build`). Os commits `8814d8a` e `a13a43c` (simplificação e S3) ainda não foram enviados, e o job `secrets` (só em PR) nunca rodou no GitHub. O mesmo `gitleaks` v8.30.1 rodou localmente via Docker sobre os 6 commits: `no leaks found`; o job `quality` foi reproduzido num container Linux a partir de `f6fce21` (37 passed, 1 skipped do Windows, dbt 31/31), sem substituir o run do GitHub. |

## Riscos e Decisões

<!-- IDs estáveis; o sdd-execute atualiza resoluções, não remove itens. -->

| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |
| R-001 | Esquema/camadas dos três GeoPackages reais ainda não inspecionados. | Alto: mapeamento e validação P1/P2. | Resolvido: T011 inspecionou três ZIPs/quatro GeoPackages reais, registrou camadas/campos/CRS em `research.md` R1 e criou fixture sintética. |
| R-002 | S3 não transaciona três objetos; crash pode deixar órfãos físicos. | Médio: limpeza operacional, sem visibilidade lógica. | Manifest `changed` só ao fim; leitores ignoram órfãos; remover em recuperação; falhas capturadas limpam run. |
| R-003 | DGT pode mudar URL, edição ou licença. | Médio: coleta/atribuição. | Resolvido: catálogo revisado por edição (reconferido em 2026-11-04 e na recoleta real de 2026-11-11); metadados registrados no manifest; erro explícito para HTML/ZIP inválido. |
| R-004 | CRS distintos e multipartes tornam área/ponto fáceis de errar. | Alto: dimensões incorretas. | Resolvido: GeoPandas por região/grupo, testes de contenção e fixture com exclave; 308 municípios como gate. |
| R-005 | A CAOP tem três URLs, enquanto `source_url` estava descrito no singular. | Médio: ambiguidade no schema do manifest. | Resolvido: `spec.md` explicita `source_url` como mapa por região; catálogo e `manifest.py` usam esse formato. |
| R-006 | A US2/AC1 exigia `dicofre` de seis dígitos, mas 18 códigos oficiais CAOP2025 têm letras após os quatro dígitos municipais. | Alto: o aceite excluiria freguesias válidas ou exigiria inventar códigos. | Resolvido: autor aprovou emenda de US2/AC1 e `data-model.md` para seis caracteres (`[0-9]{4}[0-9A-Z]{2}`), preservando `dtmnfr` oficial; US2 liberada. |
| R-007 | `Path.resolve()` no Windows retornou ocasionalmente `\\?\C:\...` para o mesmo caminho durante duas coletas concorrentes, e a comparação literal o tratou como fora da raiz. | Médio: teste de concorrência e coleta local podem falhar sem corrupção do bruto. | Resolvido: normalizar prefixo Windows antes da checagem de contenção; regressão reproduziu o erro antes da correção e 30 repetições da concorrência passaram depois. |
| R-008 | O "nunca sobrescrever" no S3 depende de escrita condicional (`IfNoneMatch="*"`), validada só no moto; o `upload_file` do boto3 não a aceita, então `put_file` usa `put_object` (limite de 5 GB). | Médio: se o S3 real das regiões candidatas se comportar diferente, a imutabilidade do raw deixa de ser garantida pelo backend (o `run_id` exclusivo continua protegendo o prefixo). | Verificar contra um bucket real antes do primeiro uso em produção (spec de infraestrutura); ZIPs atuais têm ~110 MB. |

## Execution Notes

<!-- Tabela append-only, mantida pelo sdd-execute. -->

| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |
| 2026-11-04 | Setup | T001–T004 concluídas: lock Python 3.12, CI, ignores e lint local. | Implementar helpers da Foundational; CI completo depende da US1/US2. |
| 2026-11-04 | Foundational | T005–T010 concluídas: catálogo DGT, HTTP, storage local e manifest; 7 testes unitários e Ruff verdes. | Inspecionar schema/CRS reais na US1; contratos P1 ainda vermelhos no stub. |
| 2026-11-04 | US1 | T011–T015 concluídas: fonte real inspecionada, coletor/CLI local e fixtures; 16/16 pytest, 5/5 contratos e Ruff verdes. | Resolver R-006 antes da US2; CI remoto e S3 ainda pendentes. |
| 2026-11-04 | Documentação operacional | Criado `docs/runbooks/coletas.md` a pedido do usuário, com execução local, saídas e status; README aponta para o guia. | Coleta real pela CLI permanece sem execução; R-006 bloqueia US2. |
| 2026-11-04 | US2 | T016–T024, T031–T032 concluídas: Bronze/Silver, 308/3259 linhas reais, visualizador HTML/CSV e correção da concorrência Windows; 27 pytest e 31 passos dbt verdes. | US3/S3 simulado e CI remoto pendentes; navegador automatizado indisponível para inspeção visual do HTML. |
| 2026-11-11 | Phase 4.1 (simplificação) | T033–T036 concluídas após revisão pedida pelo usuário: extração ZIP/GeoPackage unificada em `schema.py`, código morto e redundâncias removidos, filtro redundante do staging dbt retirado; 30 pytest, 31 passos dbt e build real verdes. Cinco itens da proposta original foram descartados após verificação (ver Cuidados). | Decisão do usuário sobre `--force-check`, `_canonical_path`, `strict_metadata`, adiar US3 e `HEAD`/ETag; US3/S3 e CI remoto pendentes. |
| 2026-11-11 | US3 | T025–T027 concluídas: `S3Storage` com escrita condicional, `--s3 --bucket [--prefix]`, preflight antes de qualquer listagem; 8 testes com S3 simulado cobrem paridade com o local (AC1), falha antes do download (AC2), modo local sem SDK (AC3) e limpeza/rerun após falha; 38 pytest e 31 passos dbt verdes. | Verificar `IfNoneMatch` num bucket real (R-008); CI remoto no GitHub; Phase 6 (README, quickstart, gate final). |
| 2026-11-11 | Phase 6 (Polish) | T028–T030 concluídas (e T037 junto com a T028): README e `.docs/fontes_de_dados.md` alinhados ao código; quickstart executado com coleta real contra a DGT (`unchanged`, 47 s, bytes idênticos aos de 04/11) e build/visualização sobre o dado real; gate local com ruff, 38 pytest, 31 passos dbt e trava íntegra. | `gitleaks` não rodou localmente (Docker parado); CI remoto dos commits atuais e job `secrets` (T038); `quickstart.md` ainda defasado (T039). |
| 2026-11-11 | Phase 7 (Convergence) | T037 e T039 concluídas: `.docs/fontes_de_dados.md` e `quickstart.md` alinhados ao código; `gitleaks` v8.30.1 do CI executado localmente via Docker (`no leaks found`, 6 commits). | T038: push dos commits `8814d8a` e `a13a43c`, conferência do workflow no Linux e exercício do job `secrets` em PR (exige autorização). |
| 2026-11-11 | Phase 7 (Convergence) | Job `quality` reproduzido em container Linux (Python 3.12.12) a partir de `f6fce21`: ruff limpo, 37 passed e 1 skipped (teste só do Windows), `dbt build` 31/31. Branch 3 commits à frente do `origin`; nada enviado. | T038: run real no GitHub e job `secrets` em PR, que exigem push/PR autorizados pelo usuário. |
| 2026-11-11 | Phase 7 (Convergence) | T038 concluída com evidência real: o usuário enviou os commits e abriu o PR #1 (mergeado em `main`); `Python quality` verde em push e em pull_request, com `quality` e `secrets` passando em `f6fce21`. Phase 7 completa (T037–T039). | Rodar `sdd-converge` para confirmar a convergência; R-008 (S3 real) segue aberto. |

**PRÓXIMO**: rodar `sdd-converge` para confirmar que as lacunas F-001 a F-004 foram cobertas e, se convergir limpo, sincronizar o status final.

## Arquivos Principais

<!-- Sobrescrita a cada checkpoint pelo sdd-execute. -->

- `README.md`, `.docs/fontes_de_dados.md` e `docs/runbooks/coletas.md` — documentação alinhada ao código (T028/T037).
- `sdd/specs/001-ingestao-caop/quickstart.md` — próximo a sincronizar (T039).
- `pipelines/collectors/_shared/storage_s3.py` e `pipelines/cli/collect_caop.py` — backend S3 e seleção de destino; `tests/integration/test_caop_s3.py` — prova com S3 simulado.
- `pipelines/collectors/caop/schema.py` — validação do bruto e extração/seleção de camadas (`extract_gpkgs`, `select_layers`), compartilhadas com a transformação.
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
- Armadilhas da simplificação (2026-11-11), para não repetir a proposta: `--local` é contrato da CLI e é passado pelos testes; `_validate_spatial` de `build_caop.py` valida a Silver entregue (WGS84 + dbt) e não duplica o `normalize_layer`; o `hasattr(storage, "preflight")` do coletor é exigido porque o `MemoryStorage` do contrato travado não tem `preflight`; `delete_prefix` será usado na recuperação de órfãos S3 (R-002); os `cast(...)` do staging protegem o tipo de colunas inteiramente nulas, como `parish_type`.

## Resultado Final

**Convergida em 2026-11-11** (`sdd-converge`, segunda passada: nenhum achado acionável). 50/50 tasks (T001–T039), 5/5 contratos P1 verdes e trava íntegra; PR #1 mergeado em `main` com `Python quality` (`quality` e `secrets`) verde no GitHub em push e em pull_request.

**O que foi construído.** Um coletor da CAOP2025 com destino local ou S3 (`collect_caop --local | --s3 --bucket [--prefix]`): baixa os três ZIPs da DGT, valida ZIP/GeoPackage/camadas/códigos/CRS antes de gravar, guarda o raw imutável com SHA-256 e registra um manifest `changed`, `unchanged` ou `failed`. A partir do último manifest `changed`, `build_caop` prepara Parquet (área por CRS métrico e `representative_point()` em WGS84), roda o dbt-duckdb (Bronze e Silver, com testes) em área temporária e só promove a saída após todos os gates. Resultado real: 308 municípios e 3259 freguesias (18 códigos com letras preservados). Há também `view_caop` (explorador HTML e CSVs). Sem Gold, `published/` nem deploy AWS, como previsto.

**Desvios em relação ao plano original** (detalhe nas Execution Notes):

- `dicofre` passou a texto de seis caracteres `[0-9]{4}[0-9A-Z]{2}` por causa dos 18 códigos oficiais alfanuméricos (R-006, emenda aprovada na US2/AC1).
- `source_url` do manifest virou mapa por região (R-005).
- Foram acrescentadas T031 (explorador HTML/CSV, a pedido do usuário) e T032 (comparação de caminhos do Windows, R-007).
- Phase 4.1 (T033–T036), pedida pelo usuário: extração ZIP/GeoPackage unificada em `schema.py`, código morto removido e filtro redundante do staging retirado. Cinco itens da proposta original foram descartados após verificação (`--local`, `_validate_spatial`, `preflight` obrigatório, `delete_prefix` e os `cast` do staging).
- US3: o `put_file` do S3 usa `put_object` com `IfNoneMatch="*"` porque o `upload_file` do boto3 não aceita escrita condicional. O `preflight` passou a rodar antes de qualquer listagem do destino, para que a falta de permissão vire uma mensagem clara.
- Phase 7 (Convergence, T037–T039): `.docs/fontes_de_dados.md` e `quickstart.md` alinhados ao código.

**Limitações conhecidas e aceitas** (não bloqueiam a convergência):

- **R-008:** o `IfNoneMatch` foi validado só no moto. Confirmar num bucket real antes do primeiro uso na AWS.
- **R-002 / D3:** não existe rotina automática que remova prefixos órfãos deixados por um crash no S3. Eles ficam invisíveis aos leitores, porque só o manifest `changed` vale, e a limpeza é manual com `delete_prefix`. A `logic/ingestao-e-territorio.md` menciona uma "rotina de recuperação"; ela ficou para a spec de infraestrutura.
- Pendentes de decisão do usuário no backlog: `--force-check` (no-op), `_canonical_path`, `strict_metadata`, detecção de `unchanged` por `HEAD`/ETag.
- Exemplo impreciso na US2/AC5: o homônimo "Calheta" não existe na CAOP2025 (o dos Açores é "Calheta de São Jorge"); o único é "Lagoa". A AC5 está comprovada com ela. A spec não foi editada.
