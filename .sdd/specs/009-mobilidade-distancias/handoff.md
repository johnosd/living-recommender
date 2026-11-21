# Handoff — Mobilidade 009

## Contexto

Repositório `J:/living-recommender`, branch `feature/009-mobilidade-distancias` (criada a partir do `main`
em `921fb69`). Stack: Python 3.12, `uv`, `httpx`, Parquet e dbt/DuckDB. Backlog: **Planejada**, 0/40 (30 tasks e 10 checkboxes de release)
Próximo comando: **`/sdd-execute 009-mobilidade-distancias`**.
Sem commit/push/PR autorizado; nada desta feature foi commitado ainda (spec, plano, testes e stubs estão só no
disco). Reler `.planning/backlog.md` e `config/sources.yml` antes de editar: o autor pode ter mexido neles.

## O que a feature entrega

- **US1/P1**: distância em **linha reta** dos 308 municípios até todos os polos, sem API, com proveniência.
  Entrega valor sozinha.
- **US2/P2**: **cálculo único** de **carro** (transporte público fora por decisão do autor, plan D14) pela Routes API do Google, **um par por
  requisição**. A CLI estima primeiro, só gasta com `--execute --confirm-elements N`, respeita um teto,
  retoma só os pendentes e **nunca vaza a chave**.
- **US3/P2**: staging longo com `ok`/`sem_rota`/`falha`/`pendente`, bandeira `stale` e relatório de cobertura.

**Lista de polos (decisão do autor, 2026-11-21): só 7**: cidades Lisboa e Porto e aeroportos LIS, OPO, FAO, FNC e PDL. Sem sedes de distrito, Faro como cidade nem capitais regionais. O código mantém os escopos `district` e `island` porque o contrato os exercita.

Decisões do plano que contrariam a expectativa óbvia: o carro **não** usa horário de partida
(`TRAFFIC_UNAWARE`); o catálogo real **não** habilita `transit` (o código o suporta e os contratos o exercitam, mas está desligado); pares entre ilhas diferentes **não** são consultados;
município igual ao do polo vira `0.0` sem chamada; a linha reta **não** gera bruto.
**Esta feature não faz a coleta real e não pede a chave**: isso é do autor (`quickstart.md` §4).

## Leitura obrigatória, em ordem

Em `.sdd/specs/009-mobilidade-distancias/`:

1. `spec.md`: escopo, 3 stories, 29 requisitos, 10 critérios.
2. `plan.md`: decisões D1–D13, constitution pré/pós, custo, riscos R-001–R-009.
3. `tasks.md`: T001–T030, fases e gates; registros ainda vazios.
4. `research.md`: Routes API, preço (**a confirmar**), formato de resposta, partida, chave, polos.
5. `logic/pares-e-estados.md`: **elegibilidade, identidade, estados, `stale`, estimativa**. Leia inteiro.
6. `data-model.md`: catálogo da fonte, `poles.yml`, bruto, staging, relatórios.
7. `contracts/mobility-cli.md`: CLI, ordem das recusas, assinaturas e a requisição ao Google.
8. `quickstart.md`: verificação offline e roteiro da coleta real (gate do autor).
9. `.planning/memory/constitution.md` (princípios I, III, IV, V, VII são os que esta feature toca).

Padrão a copiar: spec 003 (`pipelines/collectors/open_meteo/*`, `pipelines/cli/{collect_open_meteo,build_climate}.py`,
`analytics/dbt/models/climate/`, `tests/fixtures/open_meteo/responses.py`).

## Testes de contrato

`tests/contracts/test_mobility_contract.py`: **5 casos** (1 de US1/fase 3; 4 de US2/fase 4). Helper travado:
`tests/fixtures/mobility/responses.py`. Ambos são imutáveis no execute. A data de partida do fixture é
calculada a partir de hoje (terça-feira a ~14 dias), para nunca expirar.

```powershell
uv run --locked python -m pytest tests/contracts/test_mobility_contract.py -q --basetemp .data/tmp/mobility-contracts
powershell -NoProfile -Command "& .\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 009-mobilidade-distancias"
```

Vermelho confirmado: 5 `NotImplementedError` (`spec 009: T008`, o primeiro stub que cada teste alcança), sem
erro de importação, sintaxe ou tipo. A suíte existente segue verde com os stubs. Travas de **outras** features
(001–008) não são tocadas por esta; só `_shared/catalog.py` muda (T006), e os testes de catálogo existentes
devem continuar verdes.

## Stubs criados

Em `pipelines/collectors/mobility/` (todos com `raise NotImplementedError("spec 009: T0NN")`, **não travados**):
`catalog.py` (T006), `poles.py` (T008), `pairs.py` (T009), `straight_line.py` (T011), `rows.py` (T012),
`secrets.py` (T016), `fetch.py` (T017), `validate.py` (T018), `handler.py` (T019), `estimate.py` (T020) e
`pipelines/cli/collect_mobility.py` (T021). **Sem stub, a criar**: `municipalities.py` (T004), `state.py`
(T010), `pipelines/cli/build_mobility.py` (T013), `config/poles.yml` (T002), modelos dbt (T014/T023),
`tests/fixtures/mobility/ci_seed.py` (T014). `resolve_api_key` e `redact` ficam em `secrets.py`;
`AuthorizationStop` fica em `fetch.py`.

## Armadilhas já mapeadas

- **A chave é o risco nº 1.** O contrato 5 faz o servidor ecoar a chave no corpo do erro e uma exceção do
  `httpx` carregar a chave na mensagem. Passe **toda** string de erro por `redact`, inclusive a que vai para o
  manifest (`error`), stdout e stderr. A chave vai em header, nunca em URL.
- **Ordem dos itens é contrato**: `collect_items` recebe os itens ordenados por `id`
  (`{dico}--{pole_id}--{mode}`); o teste 3 depende de qual item está em qual posição.
- `collect_items` trata `StopCollection` como "este e os seguintes ficam `pending`". Use isso para 401/403
  (`AuthorizationStop`) e `QuotaExhausted` para 429. HTTP 200 com erro no elemento é **falha** (não grava, não
  para a execução). `ROUTE_NOT_FOUND` é resposta **válida**: grava o bruto e vira `sem_rota`.
- `latest_dataset_states` só vê entradas `changed`. `falha` e `pendente` vêm de `latest_attempts` (T010),
  que você escreve lendo os manifests; uma falha **mais nova** que o estado não o apaga.
- O estado é por assinatura (`pair_signature`). Mudar coordenada de polo, partida (se `transit` for habilitado), `api_url` ou a
  máscara marca o par como `stale` e a recoleta cobra de novo. **Não** altere `departure_time` do catálogo depois
  da coleta real.
- `load_catalog` hoje decide por `window`/`datasets`/`manual_extension`. A entrada nova **não** pode ter `window`
  nem `datasets`; o ramo `google_distances` precisa vir **antes** desses testes (T006).
- Windows: `uv run` pode imprimir caracteres acentuados corrompidos no console; não é erro dos arquivos
  (UTF-8). O script de trava recebe `-Paths` como array: use `powershell -Command "& ...ps1 ... -Paths 'a','b'"`.
- O fixture do catálogo traz `limits.min_interval_seconds = 0.01`; passe sempre `sleep=` injetado nos testes
  para não esperar de verdade.
- Dados reais ficam em `.data/` (ignorado pelo Git). Nunca versione resposta do Google nem `.env`.

## Pendências do Analyze

| ID | Sev. | Resumo | Recomendação |
| --- | --- | --- | --- |
| A-001 | MEDIUM | FR-007 e ADR-002 D8 pedem partida em dia útil, 08:00; o plano usa carro sem partida e sem tráfego (D5) | O autor confirma; se discordar, o carro passa a `TRAFFIC_AWARE` com data fixa (faixa mais cara, 100 elementos por requisição) |
| A-009 | RESOLVIDO | O ADR-002 D8 previa três modos na v1; o autor decidiu só linha reta e carro (plan D14) | Emendado em 2026-11-21: [ADR-004](../../adr/ADR-004-mobilidade-linha-reta-e-carro.md) e nota inline no ADR-002 D8 |
| A-002 | MEDIUM | FR-011 ("coordenadas devolvidas") e o edge case "ponto fora de via" não são atendíveis: a API não devolve coordenadas ajustadas | Aceitar e anotar na spec; o manifest grava `returned_coordinates: unavailable` |
| A-003 | LOW | US1-AC4 pede `unchanged` na linha reta; o plano não grava bruto (D6), o resultado é determinístico | Aceitar; o teste de integração compara o hash do Parquet |
| A-004 | MEDIUM | FR-021 diz `minutes` nulo só quando `status ≠ ok`; em `straight_line` o tempo não se aplica | Ajustar o texto do FR-021 para excluir `straight_line` |
| A-005 | LOW | A spec cita ~8 polos por município e ~5 mil elementos; com os 7 polos iniciais o cálculo dá ~5 por município e 1.404 elementos (só carro) | Corrigir os números em `.docs/fontes_de_dados.md` (T026) |
| A-006 | MEDIUM | FR-013 pareia ilhas com "polos do mesmo grupo"; o plano exige a **mesma ilha** (D3), então 9 ilhas (8 dos Açores e Porto Santo) ficam só com linha reta | O autor confirma; Terceira e Santa Maria podem entrar depois por catálogo |
| A-007 | MEDIUM | Aberto: coordenadas dos 5 aeroportos (FR-003; a lista de 7 polos já foi decidida pelo autor) e preço/faixa do carro (research R2, a confirmar) | Gates do autor antes de `--execute`; não bloqueiam o `sdd-execute` |
| A-008 | LOW | SC-008/SC-009/SC-010 só se provam com a coleta real, fora desta feature | Convergência deve registrar "pendente de coleta real", não "feito" |

Nenhum achado CRITICAL ou HIGH; nenhum viola a constitution.

## Gate de pronto

- Contratos 5/5 verdes e `check-contract-tests.ps1` íntegro; trava das specs anteriores intacta.
- `uv run --locked ruff check pipelines tests` limpo; `uv run --locked python -m pytest -q --basetemp .pytest_tmp` verde.
- `dbt build --select tag:mobility` verde sobre o fixture (`ci_seed`), e o passo novo do CI no
  `.github/workflows/python.yml`.
- `quickstart.md` §2–§3 executados. **§4 (coleta real) não é gate**: é pendência do autor e vai registrada como tal.
- Docs atualizadas no Polish: `config/sources.yml`, `config/poles.yml`, `.docs/fontes_de_dados.md`,
  `.docs/runbooks/coletas.md`; nota em `.planning/memory/`.
- Passada em hardware real: não se aplica. Sem commit/push/PR sem autorização.
