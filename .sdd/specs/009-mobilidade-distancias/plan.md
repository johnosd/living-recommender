# Implementation Plan: Mobilidade — distâncias e tempos de viagem dos municípios até polos fixos

**Slug**: `009-mobilidade-distancias` | **Date**: 2026-11-21 | **Spec**: `.sdd/specs/009-mobilidade-distancias/spec.md`

## Summary

Entregar o critério "Distância a capitais" em dois modos (linha reta e carro) para os 308
municípios, até polos fixos declarados em `config/poles.yml`.

- **Linha reta** (US1): haversine entre o ponto representativo da CAOP e cada polo, calculado no build, sem API.
- **Carro** (US2; o transporte público ficou de fora por decisão do autor, D14): CLI local de **cálculo único** sobre a Routes API
  (`computeRouteMatrix`, um par por requisição). Reaproveita o motor `collect_items` da spec 003: estado por
  par, retomada, parada limpa em cota e manifest v2. A estimativa vem **antes** do gasto; gastar exige
  `--execute` + confirmação do número de elementos + teto.
- **Auditoria** (US3): staging longo com os quatro estados (`ok`, `sem_rota`, `falha`, `pendente`), bandeira
  `stale` e relatório de cobertura (modelos dbt + CSV).

A decisão técnica de maior efeito é **um par por requisição**: o estado vigente, a retomada e a cobrança só
dos pares novos ou alterados ficam exatos (research R5). Nada da camada Silver/Gold, do ranker ou da UI entra.

## Technical Context

**Language/Version**: Python 3.12 (`uv`, lockfile `uv.lock`); SQL do dbt Core com DuckDB.

**Primary Dependencies**: `httpx`, `pandas`, `pyarrow`, `pyyaml` e `dbt-duckdb`, todos já no projeto. **Nenhuma
dependência nova.** Reuso: `_shared/datasets.collect_items`, `_shared/dataset_manifest`, `_shared/http`
(`USER_AGENT`, `RateLimiter`, `json_content_check`), `_shared/storage(_s3)`, `open_meteo/points.haversine_km`,
`cli/_common`, `cli/_promote`.

**Storage**: bruto e manifests no layout local/S3 já usado (`raw/source=google_distances/...`,
`manifests/google_distances/<run>.json`); staging Parquet em `lake/bronze/`.

**Testing**: `pytest` (suíte offline, `httpx.MockTransport`, `MemoryStorage`), `dbt build --select tag:mobility`
sobre fixture, `ruff`. Nenhum teste toca a rede nem usa chave real.

**Target Platform**: CLI local (Windows/Linux). Sem Lambda, ECS ou Terraform nesta feature.

**Performance Goals**: ~1.400 requisições a ~0,2 s cada (≈ 5 min), muito abaixo do limite de 3.000
elementos por minuto. Build do staging em segundos (≈ 3,6 mil linhas).

**Constraints**: chave só em `.env` ou ambiente; toda saída redigida; HTTP 200 com erro é falha; nenhum valor
imputado; bruto imutável; cálculo único (sem agendamento).

**Scale/Scope**: 308 municípios; 7 polos iniciais (Lisboa, Porto e 5 aeroportos); ~1.404 pares consultados por
modo habilitado (**1.404 elementos**, só carro); ~3,6 mil linhas no staging (`308 × 7` = 2.156 de linha reta
mais ~1.400 de carro, com identidade). A estimativa exata sai do `estimate`.

**Custo (constitution VII)**: **único**, não recorrente. Estimado **US$ 0** (1.404 elementos, dentro
do teto gratuito de 10.000); limite superior conservador **~US$ 7** sem nenhum teto gratuito (research R2, **a confirmar** na página de preços). Impacto
mensal após a coleta: **zero**. A CLI recusa gastar sem `pricing_verified_on`, sem confirmação do número de
elementos e acima do teto (`max_elements_per_run`, inicial 2.000).

## Decisões Invariantes

- **D1. Routes API v2, `computeRouteMatrix`, uma requisição 1×1 por par e modo.** Chave em
  `X-Goog-Api-Key`, nunca em query string. Máscara fixa `originIndex,destinationIndex,status,condition,distanceMeters,duration`.
- **D2. Item de coleta = `{dico}--{pole_id}--{mode}`**, ordenado por `id`. Um bruto por par. Estado vigente por
  `collect_items`/`latest_dataset_states`. Mudança da assinatura do par (coordenadas, modo, partida, API,
  máscara) torna o par `stale`, e a recoleta grava **nova revisão**, sem apagar a anterior.
- **D3. Elegibilidade** (`logic/pares-e-estados.md` §2): mesmo grupo de roteamento, e escopo `national`
  (continente), `district` (mesma sede de distrito) ou `island` (mesma ilha). Pares entre ilhas diferentes não
  são consultados: seriam `ZERO_RESULTS` pagos. A linha reta cobre **todos** os pares.
- **D4. Identidade**: município igual ao do polo não é consultado; linha `ok` com `0.0`/`0.0` e `method=identity`.
- **D5. Carro sem tráfego e sem partida** (`TRAFFIC_UNAWARE`): tempo reprodutível, na faixa mais barata.
  Desvio do FR-007/ADR-002 D8 (que pediam partida em dia útil às 08:00), justificado em research R4 e aberto a
  decisão do autor (A-001). Se um dia o transporte público for habilitado (D14), ele usa `departureTime` fixo
  no catálogo (dia útil, 08:00 de Lisboa) e a CLI valida a data (futura, ≤ 90 dias, dia útil) **antes** da rede.
- **D6. Linha reta é derivada no build**, de `dim_municipality` + polos, com o raio e a função de
  `open_meteo/points.haversine_km` (R = 6371,0088 km). Não gera bruto nem manifest; a "idempotência" é o
  resultado determinístico (A-003).
- **D7. Só respostas HTTP 200 válidas viram bruto**, incluindo `ROUTE_NOT_FOUND` (que vira `sem_rota`). Erro
  dentro de HTTP 200, corpo inválido, índices errados, campo ausente → **falha**, nada gravado. HTTP 401/403 →
  `AuthorizationStop` (`StopCollection`): para a execução, restantes `pending`. HTTP 429/`RESOURCE_EXHAUSTED` →
  `QuotaExhausted`. 408/5xx/rede → retry com backoff exponencial (2–60 s + jitter), `max_attempts` do catálogo.
- **D8. Gasto controlado**: sem `--execute` só estima. `--execute` exige `--confirm-elements N` igual à
  estimativa atual, `N ≤ teto` (`--max-elements` pode elevá-lo, explicitamente), `pricing_verified_on` não
  nulo, data de partida válida e chave presente. Aviso (não recusa) se `pricing_verified_on` tem mais de 30 dias.
- **D9. Segredo**: `resolve_api_key` lê `GOOGLE_ROUTES_API_KEY` de `env` ou do `.env` na raiz do repositório;
  toda string que sai do coletor passa por `redact(text, key)`. SSM fica só documentado (R6).
- **D10. Staging com uma linha por par esperado e modo**, inclusive `pendente`, `falha` e `sem_rota`
  (`data-model.md` §4). `minutes` é nulo em `straight_line` (não se aplica).
- **D11. Build isolado e promoção por caminho**, como o clima: `prepare` (Parquet) → `dbt build
  --select tag:mobility` → CSVs → `promote_paths`. Falha preserva a versão anterior.
- **D12. Polos**: a lista inicial é **enxuta, por decisão do autor (2026-11-21)**: as cidades Lisboa e Porto e
  os aeroportos LIS, OPO, FAO, FNC e PDL, **7 polos**. Sedes de distrito, Faro como cidade e capitais regionais
  ficam fora por ora. O código mantém os escopos `district` e `island` (os contratos os exercitam); ampliar a
  lista é mudança de `config/poles.yml`, e só os pares novos são cobrados. O autor ainda confere as
  coordenadas dos aeroportos antes da coleta real (FR-003).
- **D13. A coleta real é manual do autor**; o agente que executar esta feature NÃO a roda nem pede chave.
- **D14. Só o carro é calculado agora (decisão do autor, 2026-11-21).** Os modos vêm de `modes` no catálogo, e o catálogo real habilita só `driving`. O suporte a `transit` fica no código e nos contratos (o fixture habilita os dois modos), mas **desabilitado**: sem entrada `modes.transit` no `config/sources.yml`, a CLI não valida data de partida e a estimativa, o staging e o relatório só têm `driving`. Habilitá-lo depois é mudança de catálogo; só os pares novos são cobrados. Contraria o ADR-002 D8 ("três modos na v1"); a emenda está registrada no [ADR-004](../../adr/ADR-004-mobilidade-linha-reta-e-carro.md).

## Constitution Check

*GATE: passa antes da Fase 0 e foi reavaliado após o design.* Constitution v1.0.0.

| Princípio | Pré-Design | Pós-Design | Notas |
| --- | --- | --- | --- |
| I. Nenhum segredo fora do cofre | PASS | PASS | Chave só em ambiente/`.env` (no `.gitignore`); header, não URL; redação de toda saída; contrato 5 prova o vazamento por eco do servidor e por mensagem do `httpx`; o scan do CI continua. |
| II. Núcleo estático e sem chave | PASS | PASS | A chave é do pipeline em lote; nada vai ao navegador; o site continuará lendo arquivos estáticos publicados. |
| III. Dados honestos e rastreáveis | PASS | PASS | Quatro estados explícitos; `sem_rota`/`falha`/`pendente` com `km` nulo, nunca imputados; fonte, período, licença e atribuição em toda linha; `dico` sem correspondência falha o build; herança de freguesia fica fora e sinalizada. |
| IV. Coleta responsável e licenciada | PASS (com risco aceito) | PASS | Entrada em `config/sources.yml` **antes** do coletor (T001); User-Agent identificado; taxa limitada, retry com backoff; parada no primeiro erro de cota/autorização. Termos do Google: **risco aceito registrado** (ADR-002 D8, 2026-11-03), com mitigação (cálculo único, atribuição) e alternativa documentada. |
| V. Bruto imutável e publicação atômica | PASS | PASS | Revisões novas em `run_id` novo; nunca sobrescreve; `unchanged` por impressão digital; promoção atômica por caminho com rollback. |
| VI. Privacidade por padrão | PASS | PASS | Sem dados de usuário; sem chamadas do navegador; coordenadas são as de centroides públicos da CAOP. |
| VII. Custo como requisito | PASS | PASS | Custo único estimado e com teto e confirmação; recorrente zero; recurso AWS nenhum. Preços **a confirmar** (R-001), por isso `--execute` depende de `pricing_verified_on`. |

Quality gates: lint e testes no CI; coletores sem rede com fixtures; modelos dbt com testes; documentação
(`config/sources.yml`, `.docs/fontes_de_dados.md`, runbook) na mesma mudança; commits curtos em inglês.

## Project Structure

### Documentation (this feature)

```text
.sdd/specs/009-mobilidade-distancias/
├── spec.md
├── plan.md                  # este arquivo
├── research.md              # Routes API, custo, formato, partida, chave, polos
├── data-model.md            # catálogo, polos, bruto, staging, relatórios
├── contracts/mobility-cli.md
├── logic/pares-e-estados.md # elegibilidade, identidade, estados, estimativa
├── quickstart.md
├── tasks.md
├── handoff.md
└── contract-tests.lock
```

### Source Code (repository root)

```text
config/
├── sources.yml                          # + entrada google_distances (T001)
└── poles.yml                            # novo (T002)
pipelines/
├── collectors/
│   ├── _shared/catalog.py               # load_catalog roteia google_distances (T006)
│   └── mobility/                        # novo
│       ├── catalog.py  municipalities.py  poles.py  pairs.py  state.py
│       ├── straight_line.py  rows.py  estimate.py
│       ├── secrets.py  fetch.py  validate.py  handler.py
└── cli/
    ├── collect_mobility.py              # estimativa e cálculo único (T021)
    └── build_mobility.py                # staging + dbt + relatórios (T013)
analytics/dbt/
├── dbt_project.yml                      # + mobility: tags ['mobility']
└── models/mobility/
    ├── stg_municipality_pole_distance.sql  dim_mobility_pole.sql
    ├── rpt_mobility_coverage.sql           schema.yml
└── tests/mobility_*.sql
tests/
├── contracts/test_mobility_contract.py  # TRAVADO
├── fixtures/mobility/responses.py       # TRAVADO
├── fixtures/mobility/ci_seed.py         # novo (T014)
├── unit/test_mobility_*.py              # novos
└── integration/test_mobility_*.py       # novos
.github/workflows/python.yml             # + passos do fixture e do dbt de mobilidade (T028)
.docs/fontes_de_dados.md  .docs/runbooks/coletas.md   # atualizados no Polish
```

**Structure Decision**: o coletor segue a forma da spec 003 (`open_meteo/`): um pacote por fonte em
`pipelines/collectors/mobility/`, CLIs `collect_*`/`build_*` em `pipelines/cli/`, dbt por tag em
`analytics/dbt/models/mobility/`. A diferença é a unidade de coleta (par, não município), tratada só em
`pairs.py`, `state.py` e `handler.py`; o motor `collect_items` não muda.

## Complexity Tracking

Sem violações da constitution a justificar. Duas escolhas que merecem registro, sem violar nada:

| Escolha | Por que é necessária | Alternativa mais simples rejeitada porque |
| --- | --- | --- |
| ~3.800 requisições 1×1 em vez de matrizes origem×vários destinos | Estado, retomada e cobrança exatos por par (FR-015, FR-024) | Matriz por município recobraria pares já pagos ao acrescentar um polo e acoplaria falhas |
| Linha reta sem bruto/manifest | Não há coleta: é função de duas entradas versionadas | Gravar um "bruto" derivado criaria uma segunda fonte da verdade sem ganho de rastreabilidade |

## Estratégia de Testes

Prioridade: unitário → contrato/integração → E2E → manual (último recurso).

Comandos-base:

```powershell
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
uv run --locked python -m tests.fixtures.mobility.ci_seed --root .data/ci-mobility
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:mobility
```

Unitário (escritos pelo executor): validação do catálogo e dos polos (um caso por regra de rejeição),
elegibilidade e contagem do catálogo real, haversine contra valores conhecidos, assinatura e obsolescência,
classificação das respostas (`validate`), retry/backoff e redação da chave, estimativa e recusas da CLI,
leitura de `.env`. Integração: coleta com `LocalStorage`, build completo com dbt sobre fixture, S3 simulado
(`moto`), CLI de ponta a ponta com `MockTransport`.

### Testes de Contrato

Arquivos travados em `contract-tests.lock`: `tests/contracts/test_mobility_contract.py` e
`tests/fixtures/mobility/responses.py`.

Comando: `uv run --locked python -m pytest tests/contracts/test_mobility_contract.py -q --basetemp .data/tmp/mobility-contracts`

Integridade: `powershell -NoProfile -Command "& .\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 009-mobilidade-distancias"`

| Teste | Origem | Fase | Vermelho esperado (antes do execute) |
| --- | --- | --- | --- |
| `test_us1_fr001_fr004_fr005_fr006_fr013_fr014_eligible_pairs_and_straight_line_cover_every_municipality` | US1-AC1/AC2/AC5, FR-001/004/005/006/013/014 | 3 (US1) | `NotImplementedError: spec 009: T008` (`resolve_poles`) |
| `test_us2_ac1_ac2_ac3_fr008_fr009_fr010_estimate_needs_no_key_or_network_and_spending_needs_confirmation` | US2-AC1/AC2/AC3, FR-008/009/010 | 4 (US2) | `NotImplementedError: spec 009: T008` |
| `test_us2_ac4_ac6_ac7_fr011_fr012_fr016_fr017_fr018_responses_become_ok_sem_rota_falha_or_pendente` | US2-AC4/AC6/AC7, FR-011/012/016/017/018, FR-027 | 4 (US2) | `NotImplementedError: spec 009: T008` |
| `test_us2_ac5_us3_ac1_ac3_fr015_fr024_fr025_resume_skips_stored_pairs_and_a_changed_pole_stales_only_its_pairs` | US2-AC5, US3-AC1/AC3, FR-015/024/025 | 4 (US2) | `NotImplementedError: spec 009: T008` |
| `test_constitution_i_fr010_fr028_the_api_key_never_reaches_storage_output_or_error_messages` | Constitution I, FR-010/028 | 4 (US2) | `NotImplementedError: spec 009: T008` |

Todos falham primeiro em `resolve_poles` porque todos montam os polos; cada um passa a falhar no stub seguinte
conforme o executor avança (`T009`, `T011`, `T012`, `T017`…`T021`). O vermelho é por `NotImplementedError`, não
por importação, sintaxe ou tipo (verificado). A suíte existente permaneceu verde com os stubs (todas as demais passam).

Stubs criados pelo plan (ponto de partida do execute, **não travados**): `pipelines/collectors/mobility/{catalog,poles,pairs,straight_line,estimate,fetch,validate,handler,rows,secrets}.py` e `pipelines/cli/collect_mobility.py`. Faltam criar (não há stub): `municipalities.py`, `state.py`, `cli/build_mobility.py`.

## Estado Atual

<!-- Sobrescrita a cada checkpoint pelo sdd-execute. -->

| Área | Estado |
| --- | --- |
| Fases 1 a 5 e Polish | Concluídas e no PR #11 (CI verde) |
| Phase 6 (Convergence) | T031–T034 concluídas (source_id, atribuição nos relatórios, mobility_retired.csv, data-model alinhado). T035 (decisão do autor) e T036 (CI remoto) abertas |
| Contratos | 5/5 verdes; trava íntegra |
| Suíte | 710 testes verdes localmente (712 s), lint limpo; build real offline com source_id e atribuição |
| Aberto | T035: autor aprova as emendas de FR-011/US2-AC4, FR-021 e US1-AC4. T036: CI remoto após push. Gates do autor: coordenadas dos aeroportos, preço e coleta real |

## Riscos e Decisões

| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |
| R-001 | Preço e faixa de cobrança do carro (`DRIVE`, `TRAFFIC_UNAWARE`) e da máscara de campos **não confirmados** (resumo de busca; research R2) | Custo real pode passar da estimativa | Preços no catálogo; `pricing_verified_on` obrigatório; teto de elementos; confirmação do número exato; custo único |
| R-002 | (Só se `transit` for habilitado) `departureTime` vale só até ~100 dias à frente | Coleta falha se a data do catálogo envelhecer | Validação antes da rede; trocar a data invalida (marca `stale`) todos os pares de transporte, então fixá-la só na execução real |
| R-003 | Termos de uso do Google contra guardar/exibir a matriz | Contestação futura | **Risco aceito** (ADR-002 D8, 2026-11-03); atribuição em toda linha; substituição documentada |
| R-004 | A API não devolve coordenadas ajustadas à via | FR-011 e o edge case "ponto fora de via" não são atendidos como escritos | Gravar só as coordenadas pedidas e `returned_coordinates: unavailable`; sem sinalização de divergência (A-002) |
| R-005 | (Só se `transit` for habilitado) transporte público em municípios rurais devolve `ROUTE_NOT_FOUND` com frequência | Cobertura de `transit` baixa | Esperado e mostrado como `sem_rota`; nunca preenchido pelo carro (constitution III) |
| R-006 | Lista de polos e coordenadas dos aeroportos não aprovadas/conferidas | Polo errado vira dado errado em 308 municípios | Aprovação do autor antes de `--execute` (FR-003); `source_ref` obrigatório; executor confere cada coordenada |
| R-007 | ~3.800 brutos e entradas de manifest; `latest_dataset_states` lê todos os manifests | Lentidão de leitura | Volume pequeno (≈ 4k entradas); medir no build; sem otimização antecipada |
| R-008 | Carro sem `departureTime` desvia do FR-007/ADR-002 D8 | O tempo de carro não é "08:00 de dia útil" | `TRAFFIC_UNAWARE` é reprodutível e mais barato; autor confirma (A-001); ADR emendado só se ele discordar |
| R-009 | Cota gratuita mensal pode já estar consumida por outro uso da conta | Custo acima do estimado | Aviso na CLI; o pior caso (sem teto gratuito) está sempre impresso |
| R-010 | O eAIP (ais.nav.pt) devolveu HTTP 503 com Retry-After 3600 em 2026-11-21; só o LPPT foi conferido (pelo AIP via busca) | Coordenadas de OPO, FAO, FNC e PDL aproximadas (~1 km) | Marcadas como APROXIMADO no `source_ref` de `config/poles.yml`; o autor confere antes da coleta real (A-007) |
| R-011 | `test_climate_catalog.py` fixava a lista exata de fontes do catálogo | Acrescentar uma fonte quebrava o teste | Resolvido: lista atualizada com `google_distances` (mesma prática das specs anteriores) |
| R-012 | As linhas de linha reta não tinham licença (FR-022); o dbt acusou | Linha sem fonte/licença viola a constitution III | Resolvido: `license_id` lido da dimensão CAOP (`load_mobility_municipalities`); atribuição só nas linhas do Google |
| R-013 | A ordem das recusas do contrato (confirmação, teto, preço, data, chave) não pôde ser sequencial: o contrato 2 exige que a falta da chave apareça mesmo quando o teto também recusa | Mensagem de recusa incompleta se uma só fosse reportada | Resolvido: a CLI junta todas as recusas e as imprime juntas (melhor para o operador); `contracts/mobility-cli.md` ajustado |
| R-014 | Um `.env` real na raiz tornaria o teste de chave ausente não hermético | Teste dependente da máquina do autor | Resolvido: `.env` só é lido quando `env` não é injetado (`resolve_api_key(root=None)` nos testes) |

## Execution Notes

| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |
| 2026-11-21 | Fases 1 e 2 | Fonte e polos no catálogo; catálogo, polos, pares e estado implementados com 72 testes novos. eAIP devolveu 503 (Retry-After 3600): coordenadas dos aeroportos ficaram aproximadas e marcadas para conferência | Conferir as coordenadas dos 4 aeroportos no eAIP quando o site voltar |
| 2026-11-21 | Fase 3 (US1) | Linha reta, linhas por estado, build com dbt e relatórios CSV; contrato da US1 verde. O dbt apontou linhas sem licença, corrigido lendo license_id da dimensão CAOP | Fase 4: coleta do Google (fetch, validate, handler, estimate, CLI) |
| 2026-11-21 | Fase 4 (US2) | Coleta do Google: fetch com retry/parada em 401/403/429, redação da chave em toda mensagem, validação de HTTP 200 com erro, handler sobre collect_items, estimativa e CLI com confirmação. Os 5 contratos passaram de primeira; 705 testes verdes | Fase 5: teste do relatório de cobertura; depois Polish |
| 2026-11-21 | Fase 5 (US3) | Relatório de cobertura com os quatro estados, ausência esperada nas ilhas sem polo e `stale`; o teste confirma que um polo alterado marca só os seus pares sem alterar resultados | Polish: documentação, CI e validação final |
| 2026-11-21 | Polish | Documentação, passo de CI, quickstart offline e nota de memória; suíte final 707 passed. Recusas conferidas com dados reais (confirmação, preço e chave listados juntos, nenhum bruto do Google criado) | Falta o gitleaks do CI (push/PR) e os gates do autor |
| 2026-11-21 | Release | PR #11 aberto; quality pass (4m17s e 7m40s) e secrets/gitleaks pass (14 s) no CI remoto. Checklist de release completo | Gates do autor para a coleta real; sdd-converge |
| 2026-11-21 | Phase 6 (Convergence) | T031 `source_id` (caop|google_distances) no staging e no dbt; T032 atribuição e risco aceito em todos os CSVs e no console; T033 `mobility_retired.csv`; T034 data-model alinhado. 710 testes verdes | T035 (decisão do autor) e push para o CI remoto (T036) |

**PRÓXIMO**: T035 (autor decide as 3 emendas da spec), push da Phase 6 e CI do PR #11 (T036); depois sdd-converge.

## Arquivos Principais

- `config/sources.yml` (google_distances) e `config/poles.yml` (7 polos)
- `pipelines/collectors/mobility/*` e `pipelines/cli/{collect_mobility,build_mobility}.py`
- `analytics/dbt/models/mobility/` e `analytics/dbt/tests/mobility_*.sql`
- `.docs/fontes_de_dados.md`, `.docs/runbooks/coletas.md`, `.github/workflows/python.yml`, `.planning/memory/mobilidade-009-execucao.md`

## Cuidados para Retomada
- `load_catalog` trata `google_distances` antes dos ramos `window`/`datasets`; não acrescente essas chaves à entrada.
- `route_pairs` aceita `modes`; o padrão (ambos os modos) é só para os contratos. O código real passa `tuple(source['modes'])`.
- O eAIP pode voltar a responder; reconferir as coordenadas dos aeroportos antes da coleta real.
- A CLI de coleta lê `.env` da raiz do repositório só quando usa o ambiente real; com `env` injetado, nunca.
- `--no-wait` foi retirado: um 429 para a coleta de imediato (FR-012); rode o mesmo comando depois.
