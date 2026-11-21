# Contrato — CLIs e funções públicas (spec 009)

Os testes de contrato (`tests/contracts/test_mobility_contract.py`) só tocam esta superfície.

## `pipelines.cli.collect_mobility`

```text
python -m pipelines.cli.collect_mobility [--local|--s3 ...] [--root .data] [--catalog config/sources.yml]
    [--poles config/poles.yml] [--silver .data/lake/silver]
    [--execute --confirm-elements N] [--max-elements M] [--no-wait]
```

`main(argv=None, *, client=None, fetcher=None, storage=None, env=None, municipalities=None, poles=None,
sleep=time.sleep) -> int`. `municipalities` e `poles` injetados (já resolvidos) dispensam ler a silver e o
YAML. `env` substitui `os.environ`. `client` é um `httpx.Client`; `fetcher`, se dado, vence `client`.

| Situação | Comportamento | Código |
|---|---|---|
| sem `--execute` | imprime a estimativa (pares, identidade, novos, desatualizados, elementos por modo, total, teto, custo estimado e pior caso); **não** lê a chave, **não** abre rede | 0 |
| `--execute` sem `--confirm-elements` | recusa | ≠ 0 |
| `--confirm-elements N` ≠ elementos estimados agora | recusa e mostra a estimativa atual | ≠ 0 |
| elementos > teto (`max_elements_per_run` ou `--max-elements`) | recusa antes de qualquer chamada | ≠ 0 |
| `pricing_verified_on` nulo | recusa | ≠ 0 |
| `modes.transit` habilitado e `departure_time` fora de [agora, agora + 90 dias] ou em fim de semana (não se aplica quando só `driving` está habilitado) | recusa | ≠ 0 |
| chave ausente (`GOOGLE_ROUTES_API_KEY` no `env` ou no `.env`) | recusa **antes** da rede; a mensagem cita o nome da variável e nunca um valor | ≠ 0 |
| `--execute` válido | consulta só os pares novos e desatualizados, grava bruto e manifest | 0 sem falha e sem pendente; 1 com `failed`; 2 com `pending` |
| nada a consultar | informa "nada a coletar" | 0 |

A ordem das recusas é: argumentos, catálogo, polos, confirmação, teto, preço, data, chave, rede. Erros de
configuração saem em stderr, sem traceback e sem a chave. Argumentos inválidos podem sair por `SystemExit(2)`
do `argparse`.

## `pipelines.cli.build_mobility`

`python -m pipelines.cli.build_mobility --local --root .data [--catalog ...] [--poles ...]`: monta o
staging, roda `dbt build --select tag:mobility`, escreve os CSVs de relatório e promove só os caminhos desta
fonte (`PROMOTED`), com rollback como no `build_climate`. Imprime cobertura por modo e polo. Nunca exige
chave nem rede. Falha (código 1) se algum `dico` do estado não existir na dimensão.

## Funções

| Função | Assinatura | Obs. |
|---|---|---|
| `mobility_source` | `(catalog, source_id="google_distances") -> dict` | `CatalogError` antes da rede |
| `load_mobility_municipalities` | `(silver_dir) -> list[dict]` | formato de `logic/pares-e-estados.md` §1 |
| `resolve_poles` | `(raw_poles, municipalities) -> list[dict]` | `ValueError` nomeando o `pole_id` |
| `load_poles` | `(path, municipalities) -> list[dict]` | |
| `poles_catalog_version` | `(poles) -> str` | SHA-256 hex |
| `pair_id` | `(dico, pole_id, mode) -> str` | `{dico}--{pole_id}--{mode}` |
| `route_pairs` | `(municipalities, poles) -> list[dict]` | `{id, dico, pole_id, mode, identity}` |
| `straight_line_rows` | `(municipalities, poles) -> list[dict]` | `{dico, pole_id, mode, km, minutes, status, ...}` |
| `estimate_run` | `(catalog, *, municipalities, poles, storage) -> dict` | chaves em `logic` §7 |
| `make_routes_fetcher` | `(source, *, api_key, client=None, sleep=time.sleep, on_quota=None)` | `fetch(item, destination)` |
| `validate_routes_response` | `(item, path) -> None` | `ValueError` com motivo |
| `collect_mobility` | `(catalog, *, municipalities, poles, storage, fetcher, run_id, collected_at_utc, work_dir, validator=None, max_elements=None)` | retorno de `collect_items` |
| `build_distance_rows` | `(catalog, *, municipalities, poles, storage, processed_at_utc) -> list[dict]` | uma linha por par e modo |
| `resolve_api_key` | `(env, source, *, root=None) -> str` | `ValueError` sem valor |

### Requisição ao Google (fixada pelos contratos)

`POST` JSON com `origins[0].waypoint.location.latLng`, `destinations[0].waypoint.location.latLng`
(`latitude`, `longitude`), `travelMode` (`DRIVE` ou `TRANSIT`); em `DRIVE` acrescenta
`routingPreference: TRAFFIC_UNAWARE` e **não** envia `departureTime`; em `TRANSIT` envia `departureTime`
igual ao do catálogo. Cabeçalhos: `X-Goog-Api-Key`, `X-Goog-FieldMask`
(`originIndex,destinationIndex,status,condition,distanceMeters,duration`), `Content-Type: application/json` e o
`User-Agent` de `pipelines.collectors._shared.http.USER_AGENT`.

### Item de coleta (`collect_items`)

`{id, dico, pole_id, mode, collection_method: "api_json", origin: api_url, origin_lat, origin_lon,
dest_lat, dest_lon, travel_mode, routing_preference, departure_time}`. O fetcher lê as coordenadas do item.
O item **não** pode carregar a chave.
