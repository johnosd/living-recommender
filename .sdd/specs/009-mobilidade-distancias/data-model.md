# Modelo de dados — Mobilidade (spec 009)

## 1. Catálogo da fonte (`config/sources.yml` → `google_distances`)

| Campo | Valor / regra |
|---|---|
| `id` | `google_distances` |
| `publisher`, `responsible_party` | `Google Maps Platform`, `living-recommender` |
| `license_id` | `not_granted_by_source` (risco aceito, como o Pordata; a licença do dado não é concedida) |
| `usage_restriction`, `risk_accepted`, `substitution` | texto do risco (ADR-002 D8, 2026-11-03) e alternativa (OpenRouteService e GTFS da CP) |
| `attribution` | `Tempos de viagem: Google` (obrigatória; vai em toda linha `driving`/`transit`) |
| `collection_method`, `frequency`, `territorial_level` | `api_json`, `once`, `municipality` |
| `api_url` | `https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix` (HTTPS) |
| `key_env` | `GOOGLE_ROUTES_API_KEY` |
| `reference_period` | `AAAA-MM` do cálculo (ex.: `2026-12`) |
| `limits` | `min_interval_seconds` (>0), `max_attempts` (inteiro ≥ 1) |
| `max_elements_per_run` | teto inteiro positivo (valor inicial `2000`) |
| `pricing_verified_on` | data ISO ou `null`; `null` bloqueia `--execute` |
| `pricing` | por modo habilitado: `usd_per_1000`, `free_monthly` (números ≥ 0) |
| `modes.driving` | `travel_mode: DRIVE`, `routing_preference: TRAFFIC_UNAWARE` |
| `modes.transit` | **Ausente no catálogo real** (decisão do autor, 2026-11-21). Se habilitado: `travel_mode: TRANSIT`, `departure_time` RFC 3339 com fuso, dia útil, 08:00 Lisboa |

`mobility_source` exige **pelo menos um** modo e rejeita antes da rede: campo ausente, `api_url` não HTTPS, modo desconhecido, modo sem
`travel_mode`, `transit` sem `departure_time` ou com data no fim de semana, números não positivos.
`load_catalog` roteia `google_distances` para `mobility_source`, como faz com `wikipedia`.
Não pode haver `window` nem `datasets` na entrada (o roteador antigo os usaria).

## 2. Catálogo de polos (`config/poles.yml`)

```yaml
version: 1
poles:
  - {pole_id: lisboa, name: Lisboa, kind: cidade, routing_group: continente, scope: national, dico: "1106"}
  - {pole_id: aeroporto_lis, name: Aeroporto de Lisboa, kind: aeroporto, routing_group: continente,
     scope: national, latitude: 38.7813, longitude: -9.1359, source_ref: "<fonte pública>"}
  - {pole_id: sede_evora, name: Évora, kind: sede_distrito, routing_group: continente, scope: district, dico: "0705"}
  - {pole_id: funchal, name: Funchal, kind: capital_regional, routing_group: madeira, scope: island, dico: "3103"}
  - {pole_id: aeroporto_fnc, name: Aeroporto da Madeira, kind: aeroporto, routing_group: madeira, scope: island,
     district_or_island: "Ilha da Madeira", latitude: 32.6979, longitude: -16.7745, source_ref: "<fonte pública>"}
```

Regras (`resolve_poles`, FR-002/FR-004): `pole_id` único, `[a-z0-9_]+`; `kind` ∈ {cidade, aeroporto,
sede_distrito, capital_regional}; `scope` ∈ {national, district, island} e coerente com o tipo e o grupo
(`logic/pares-e-estados.md` §2); `dico` existente na dimensão, exceto aeroporto; coordenadas dentro da caixa
latitude 29–43 e longitude −32 a −6 (a mesma do clima); `source_ref` obrigatório em aeroporto; campo
desconhecido é erro. Qualquer violação rejeita o catálogo inteiro, com o `pole_id` na mensagem.
`poles_catalog_version` = SHA-256 do JSON canônico dos polos resolvidos, ordenados por `pole_id`.

Lista inicial (decisão do autor, 2026-11-21; 7 polos): cidades **Lisboa** e **Porto** (`scope: national`) e
aeroportos **LIS, OPO, FAO** (`national`), **FNC** (`island`, "Ilha da Madeira") e **PDL** (`island`,
"Ilha de São Miguel"). Sedes de distrito, Faro como cidade, capitais regionais e os aeroportos de Terceira,
Santa Maria e Porto Santo **não** entram agora; entram depois por mudança de catálogo (os escopos `district` e
`island` já existem), e só os pares novos são cobrados. Os exemplos acima com `sede_evora` e `funchal` só
ilustram o formato.

## 3. Bruto (imutável)

`raw/source=google_distances/dataset=<dico>--<pole_id>--<mode>/run_id=<run>/<dico>--<pole_id>--<mode>.json`
com os **bytes exatos** da resposta HTTP 200 válida (lista de um elemento). Respostas inválidas, erros e
falhas não são gravados. Manifest: `manifests/google_distances/<run_id>.json` (schema v2, spec 002).

`entry_extra` de cada par `changed`/`unchanged`:
`pair_signature`, `mode`, `pole_id`, `dico`, `requested_origin` `[lat, lon]`, `requested_destination`
`[lat, lon]`, `travel_mode`, `routing_preference`, `departure_time` (nulo no carro), `api_url`, `field_mask`,
`route_status` (`ROUTE_EXISTS` | `ROUTE_NOT_FOUND`), `returned_coordinates: "unavailable"`,
`poles_catalog_version`, `caop_version`. **Nunca** a chave, nem em `error`.

## 4. Staging `stg_municipality_pole_distance` (`lake/bronze/`)

Uma linha por par esperado e modo (inclui `straight_line`, `pendente`, `falha` e `sem_rota`).

| Coluna | Tipo | Regra |
|---|---|---|
| `dico` | varchar | FK `dim_municipality`; `not_null` |
| `pole_id` | varchar | FK da lista de polos vigente; `not_null` |
| `mode` | varchar | `straight_line`, `driving` ou `transit` |
| `km`, `minutes` | double | nulos fora de `ok`; `minutes` nulo também em `straight_line` |
| `status` | varchar | `ok`, `sem_rota`, `falha` ou `pendente` |
| `no_route_reason` | varchar | `ROUTE_NOT_FOUND` quando `sem_rota`; senão nulo |
| `error` | varchar | só em `falha`, já redigido |
| `method` | varchar | `haversine`, `identity` ou `google_routes_v2` |
| `departure_time` | varchar | só `transit` |
| `stale` | boolean | ver `logic/pares-e-estados.md` §5 |
| `calculated_at_utc`, `source_run_id` | varchar | do estado; nulos em `pendente`/`falha`/linha reta/identidade |
| `caop_version`, `poles_catalog_version` | varchar | proveniência |
| `license_id`, `attribution`, `usage_restriction`, `reference_period` | varchar | do catálogo; atribuição só em `driving`/`transit` |
| `processed_at_utc` | varchar | do build |

Chave: `(dico, pole_id, mode)`, única. `dim_mobility_pole` (`lake/bronze/dim_mobility_pole`) lista os polos
vigentes (`pole_id`, `name`, `kind`, `routing_group`, `scope`, `latitude`, `longitude`, `dico`) para o
`relationships` do staging.

## 5. Relatórios

- `rpt_mobility_coverage` (`lake/bronze/`): por `mode` e `pole_id`, contagens `ok`, `sem_rota`, `falha`,
  `pendente`, `stale` e `expected`, com `ok + sem_rota + falha + pendente = expected`.
- CSVs em `lake/bronze/` (`;`, UTF-8 com BOM, como o clima): `mobility_coverage.csv`, `mobility_no_route.csv`
  (`dico`, `name`, `pole_id`, `mode`, `reason`, `expected_absence`), `mobility_pending.csv`,
  `mobility_stale.csv`. `expected_absence = true` quando o município está numa ilha sem polo elegível.
