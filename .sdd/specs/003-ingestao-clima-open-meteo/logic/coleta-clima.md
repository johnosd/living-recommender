# Lógica: coleta de clima por município, cota e staging

Regras onde um executor erraria sem saber. O "porquê" está no `plan.md` (Decisões Invariantes) e no `research.md`; aqui estão as assinaturas e a ordem das operações.

## 1. `collect_items`: o miolo compartilhado (T003, T004)

`pipelines/collectors/_shared/datasets.py` passa a ter `collect_items`; `collect_datasets` vira um invólucro que resolve o catálogo e chama `collect_items`, **devolvendo exatamente as quatro chaves de hoje** (`status`, `run_id`, `manifest_key`, `datasets`). O contrato travado da spec 002 e os 140 testes existentes não podem mudar.

```python
def collect_items(
    source: dict, items: Sequence[dict], *, source_id: str, storage, fetcher, validator,
    run_id: str, collected_at_utc: str, work_dir: Path,
    fingerprint=None,
    state_is_current: Callable[[dict, dict], bool] | None = None,   # (item, estado) -> o estado ainda vale?
    skip_current: bool = False,       # True: item com estado atual não é consultado
    max_items: int | None = None,     # teto de itens consultados nesta execução
) -> dict:
    # 1. igual ao collect_datasets de hoje: preflight, list_keys, latest_dataset_states, run_id livre
    # 2. todo = itens sem estado atual (se skip_current) ; skipped = quantos foram pulados
    #    todo = todo[:max_items]; remaining = len(todo_antes_do_corte) - len(todo)
    # 3. todo vazio -> devolve {"status": "unchanged", "run_id", "manifest_key": None, "datasets": [],
    #    "skipped_current": skipped, "remaining": 0, "quota_exhausted": False, "up_to_date": True}
    #    SEM manifest e SEM exigir run_id novo
    # 4. para cada item, na ordem recebida:
    #       entry = _collect_one(...)
    #    StopCollection (ou KeyboardInterrupt) dentro do item:
    #       o item corrente e TODOS os seguintes viram entradas `pending`, com error=str(stop)
    #       ("interrompida pelo operador" no Ctrl+C); o laço termina; o manifest é gravado normalmente
    # 5. manifest e limpeza de órfãos: igual ao collect_datasets de hoje
    # 6. devolve {"status", "run_id", "manifest_key", "datasets", "skipped_current", "remaining",
    #    "quota_exhausted": <parou por QuotaExhausted>, "interrupted": <Ctrl+C>, "up_to_date": False}
```

Mudanças em `_collect_one`:

- `except (StopCollection, KeyboardInterrupt)` **antes** do `except Exception`: apaga o bruto já gravado do item (se houver) e **repropaga**. O `finally` que apaga o temporário continua valendo.
- O `meta` devolvido pelo fetcher pode trazer `entry_extra: dict`; seus campos entram **no topo** da entrada (`changed` e `unchanged`), depois dos campos comuns. `validate_entry` ignora campos desconhecidos.
- Entradas `pending`: `_entry(item, "pending", error=<motivo>)`; `key`, `sha256` e `bytes` ficam nulos.

`dataset_manifest.py` (T004): `DATASET_STATUSES` ganha `pending`; `validate_entry` trata `pending` como `failed` (exige `error`, dispensa o resto); `run_status` devolve `failed` se todas as entradas são `failed`, `partial` se há `failed` ou `pending`, senão `changed`/`unchanged`; `latest_dataset_states` já ignora tudo que não é `changed` e **não muda**.

Ordem e determinismo: o handler entrega os itens ordenados por `dico`; `max_items` corta a partir do início, então retomar sempre continua pela ordem.

## 2. Estado atual e o que a execução consulta (T010)

```python
def is_current(item, state, source) -> bool:
    return (state.get("reference_period") == f"{source['window']['start']}/{source['window']['end']}"
            and state.get("model") == source["model"]
            and state.get("variables_signature") == variables_signature(source))
```

- Sem `--recollect`: `skip_current=True`. Município com estado atual não gera chamada; aparece em `skipped_current`.
- Com `--recollect`: `skip_current=False`. Somente um estado de configuração compatível é comparado pela impressão digital; uma configuração diferente exige `changed`, mesmo com JSON idêntico. Na mesma configuração: igual → `unchanged`; diferente → `changed`.
- Janela, modelo ou variáveis/unidades novos no catálogo: nenhum estado é atual, os 308 voltam a ser trabalho, e os brutos antigos permanecem (constitution V).
- `remaining` (campo do resultado) = municípios sem estado atual que **não** foram tentados por causa de `max_items`. Os `pending` por cota estão no manifest e não entram em `remaining`. A CLI mostra "restantes" como `pending + remaining`.

## 3. Impressão digital (T009)

```python
def fingerprint_open_meteo_response(path: Path) -> str:
    document = json.loads(path.read_text(encoding="utf-8"))
    document.pop("generationtime_ms", None)                      # único campo volátil (research R5)
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

O `sha256` do manifest continua sendo o dos **bytes** do bruto; só o `fingerprint` ignora `generationtime_ms`. Arquivo que não é JSON: o validador já o reprovou antes (a ordem em `_collect_one` é fetch → validação → impressão digital).

## 4. Validação do bruto (T008)

`validate_open_meteo_response(item, path)`; `item` traz `window`, `variables` e `model` (o handler os copia da fonte para cada item). Em ordem; a primeira falha levanta `ValueError` com a mensagem indicada (ela vira `error` no manifest, com o prefixo `validação:`):

| # | Verificação | Mensagem |
| --- | --- | --- |
| 1 | Arquivo não vazio; JSON que é objeto | `resposta vazia` / `resposta não é um objeto JSON` |
| 2 | `error` verdadeiro | `API devolveu erro: <reason>` |
| 3 | `daily` e `daily_units` são objetos | `resposta sem daily` / `resposta sem daily_units` |
| 4 | `daily.time` é exatamente a lista de dias de `window.start` a `window.end` | `dias: esperados <N> (<ini>..<fim>), recebidos <M> (<ini>..<fim>)` |
| 5 | Cada variável do catálogo existe em `daily` com `len == len(time)` | `variável ausente: <id>` / `série com tamanho errado: <id>` |
| 6 | `daily_units[<id>] == unit` do catálogo | `unidade inesperada em <id>: <recebida> (esperada <unit>)` |
| 7 | Cada valor é número ou `null` (nunca texto, nunca bool) | `valor inválido em <id>: <valor>` |
| 8 | Nenhuma variável tem todos os valores nulos | `variável sem nenhum valor: <id>` |
| 9 | `latitude`, `longitude` numéricos e `timezone` texto | `resposta sem coordenadas` / `resposta sem timezone` |

Nulos esparsos **não** reprovam (a fonte pode tê-los; viram lacuna na cobertura). Variáveis extras na resposta são toleradas e ignoradas.

## 5. Cliente e limites de cota (T011, T017)

`make_open_meteo_fetcher(source, *, client=None, sleep=time.sleep, wait_on_limits=True)` devolve `fetch(item, destination) -> meta`. Reutiliza `RateLimiter` (com `min_interval = limits.min_interval_seconds`) e `USER_AGENT` de `_shared/http.py`; **não** usa o `HttpDownloader`, porque ele descarta o corpo das respostas de erro e o `reason` do 429 é o que decide o fluxo.

Requisição (uma por município, janela inteira):

```text
GET <api_url>?latitude=<lat>&longitude=<lon>&start_date=<ini>&end_date=<fim>
             &daily=<ids separados por vírgula>&models=<model>&timezone=<timezone>
Header: User-Agent do projeto ; timeout 60 s
```

Fluxo por chamada (``attempt`` conta só erros de rede e 5xx; esperas de cota têm contador próprio):

```python
for attempt in 1..3:
    limiter.wait()
    try: response = client.get(...)
    except (TimeoutException, TransportError): backoff(2 ** attempt); continue
    if response.status_code == 429:
        kind = classify_limit(response)            # "minute" | "hour" | "day"
        if kind == "day" or not wait_on_limits or waits[kind] >= MAX_WAITS[kind]:
            raise QuotaExhausted(f"cota {NOME[kind]} esgotada ({kind}): {reason}")
        waits[kind] += 1 ; sleep(WAIT_SECONDS[kind]) ; retry sem consumir `attempt`
    elif response.status_code in {408, 500, 502, 503, 504}: backoff(2 ** attempt); continue
    elif response.status_code >= 400: raise DownloadError(f"HTTP {status}: {reason}")   # falha do município
    else: check JSON ; grava atômico em destination ; return {}
raise DownloadError("falhou após 3 tentativas")
```

| Item | Valor |
| --- | --- |
| `classify_limit` | procura, sem diferenciar maiúsculas, `minutely`/`minute` → `minute`; `hourly`/`hour` → `hour`; `daily`/`day` → `day`. **Sem palavra reconhecida → `hour`** (R4) |
| `WAIT_SECONDS` | `minute`: 61 ; `hour`: 3.605 (a janela pode ser deslizante, então espera-se uma hora cheia) |
| `MAX_WAITS` | `minute`: 5 ; `hour`: 1 (por município). Esgotadas, vira `QuotaExhausted` |
| `QuotaExhausted` | **nunca** deixa arquivo em `destination`; o `reason` da API vai na mensagem |
| Gravação | corpo completo em memória (~70 KB) → arquivo temporário no mesmo diretório → `os.replace`/`link` para `destination`; `destination` não pode existir |

Qualquer outro erro (4xx diferente de 429, JSON inválido, HTML) levanta `DownloadError`, que `_collect_one` registra como `failed` do município **sem** parar a coleta.

## 6. O handler (T010)

```python
def collect_open_meteo(catalog, *, municipalities, storage, fetcher, run_id, collected_at_utc, work_dir,
                       validator=None, max_municipalities=None, recollect=False) -> dict:
    source = get_climate_source(catalog, "open_meteo")                     # antes de qualquer rede
    check_municipalities(municipalities, source["expected_municipalities"]) # FR-004: total, dico único, coordenadas
    items = [{**town, "id": town["dico"], "collection_method": "api_json", "origin": source["api_url"],
              "window": source["window"], "variables": source["variables"], "model": source["model"]}
             for town in sorted(municipalities, key=lambda t: t["dico"])]
    reference_period = f'{source["window"]["start"]}/{source["window"]["end"]}'

    def fetch(item, destination):                       # envolve o fetcher injetado
        meta = dict(fetcher(item, destination) or {})
        meta["reference_period"] = reference_period
        meta["entry_extra"] = {"model": source["model"],
                               "requested_lat": item["latitude"], "requested_lon": item["longitude"],
                               **_returned_fields(destination)}   # returned_lat/lon, elevation_m, timezone
        return meta                                      # _returned_fields tolera JSON inválido: o validador reprova

    return collect_items(source, items, source_id="open_meteo", storage=storage, fetcher=fetch,
                         validator=validator or validate_open_meteo_response, run_id=run_id,
                         collected_at_utc=collected_at_utc, work_dir=work_dir,
                         fingerprint=lambda _item, path: fingerprint_open_meteo_response(path),
                         state_is_current=lambda item, state: is_current(item, state, source),
                         skip_current=not recollect, max_items=max_municipalities)
```

O fetcher injetado só escreve o arquivo; quem registra metadados é o handler, a partir da própria resposta, o que mantém os testes com fakes simples.

## 7. Staging (T024, T025)

`read_climate_response(path, *, variables=None)` (T024): lê o JSON e devolve o DataFrame `variable, date, value, unit`.

- `date`: cada texto de `daily.time` vira `datetime.date` por `date.fromisoformat`. **Nenhuma** conversão de fuso, `pd.to_datetime` com `utc=True` ou `tz_localize`.
- `value`: `None` → `NaN` em `float64`. Nenhum `fillna`. Valor `0` legítimo continua `0`.
- `unit`: `daily_units[<variável>]` literal.
- Só as variáveis selecionadas do catálogo, na ordem do documento; extras são ignoradas antes da leitura de valores/unidades; um município completo tem `13 × 730` linhas.

`prepare_climate(root, output_dir, *, processed_at_utc, catalog=None)` (T025) em `pipelines/cli/build_climate.py`:

```python
municipalities = load_municipality_names(silver)         # dico -> nome, 308
states = latest_dataset_states(LocalStorage(root), "open_meteo")
current = {d: s for d, s in states.items() if is_current_state(s, source)}
not_collected = sorted(set(municipalities) - set(current))
# para cada dico atual, em ordem: confere sha256/bytes do bruto (file_digest) -> senão ObservationBuildError-equivalente
with pq.ParquetWriter(output_dir / "climate_daily.parquet", SCHEMA) as writer:   # fluxo, 1 município por vez
    frame = read_climate_response(path)  ;  acrescenta source_id, dico, model, window_*, proveniência
    writer.write_table(pa.Table.from_pandas(frame, schema=SCHEMA))
points = [...]  # T029 (Fase 6): por município atual, haversine(requested, returned); T025 não grava os pontos
```

Falhas: nenhum município atual → erro; bruto ausente ou com `sha256`/tamanho diferente do manifest → erro (`checksum ou tamanho alterado: <key>`).

`haversine_km(lat1, lon1, lat2, lon2)`: raio médio 6371,0088 km, `math` puro.

## 8. Cobertura (T028, T029)

- **Completo** = município com exatamente `expected_days` valores **não nulos** da variável. **Com lacuna** = coletado, com menos. **Não coletado** = sem linhas no staging (sem estado atual).
- `gaps` lista `{dico, missing_days}`, onde `missing_days = expected_days - não_nulos`; os dias exatos ficam consultáveis no staging (`value is null`).
- O relatório cobre **todas** as variáveis do catálogo (via `climate_meta.parquet`), mesmo as sem nenhuma linha.
- `rpt_climate_points` cobre os 308 da dimensão; `collected = false` para os não coletados, com as colunas de ponto nulas.
- Ausência nunca é preenchida, nem por município vizinho que partilhe a mesma célula da grade (R-004).

## Emendas verificadas na execução

- `variables_signature`: SHA-256 do JSON canônico da lista ordenada de pares `(id, unit)`. A ordem declarativa não muda a assinatura. Janela/modelo continuam separados. Estado sem assinatura não é atual.
- O build inclui ambos os CSV e as três tabelas na mesma promoção com rollback (R-013).
