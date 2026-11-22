# Lógica — pares elegíveis, identidade, estados e obsolescência

Um executor que errar aqui gasta dinheiro à toa ou publica valor inventado. Leia inteiro antes de codar.

## 1. Municípios e polos (entradas já resolvidas)

Município (`load_mobility_municipalities`, lido de `lake/silver/dim_municipality`):
`{dico, name, latitude, longitude, district_or_island, autonomous_region, routing_group}`.

`routing_group`: `autonomous_region` nula → `continente`; contém `Madeira` → `madeira`; contém `Açores` →
`acores`; qualquer outro valor → erro (nunca presumir). `NaN` do pandas vira `None`.

Polo resolvido (`resolve_poles`): `{pole_id, name, kind, routing_group, scope, latitude, longitude, dico?,
district_or_island?, source_ref?}`. Para `kind` em `cidade | sede_distrito | capital_regional` o `dico` é
obrigatório, e `latitude`/`longitude`/`district_or_island` vêm do município (o YAML **não** pode trazer
coordenadas nesses tipos). Para `aeroporto`, `latitude`, `longitude` e `source_ref` são obrigatórios e `dico`
é proibido.

## 2. Elegibilidade para os modos do Google

```python
def eligible(town, pole) -> bool:
    if town["routing_group"] != pole["routing_group"]:
        return False
    match pole["scope"]:
        case "national":  return True                                   # só polos do continente
        case "district":  return town["district_or_island"] == pole["district_or_island"]
        case "island":    return town["district_or_island"] == pole["district_or_island"]
```

- `national` só é válido com `routing_group == continente` (o validador recusa nas ilhas).
- `district` só é válido para `sede_distrito`; `island` só para `capital_regional` e `aeroporto` das ilhas.
  Um aeroporto de ilha usa `scope: island` e `district_or_island` declarado no YAML (a ilha dele).
- A linha reta ignora a elegibilidade: vale para **todo** par município × polo (FR-006).

Resultado esperado no catálogo real inicial de 7 polos (conferir no `estimate`, **~1.404 pares consultados por
modo habilitado, ou seja, 1.404 elementos só com carro**): continente 5 polos nacionais × 278 − 2 identidades (Lisboa e Porto) = 1.388; Madeira (FNC) 10;
São Miguel (PDL) 6. Terceira, Graciosa, Flores, Santa Maria, São Jorge, Corvo, Pico, Faial e Porto Santo ficam
só com linha reta, porque não há polo na ilha. O relatório os mostra como "sem polo elegível", não como falha.
O escopo `district` continua implementado e testado, mas **sem uso** no catálogo inicial.

## 3. Identidade

Se `town["dico"] == pole["dico"]` (o par é o município do próprio polo), o par é **identidade**: não é
consultado, vira linha `ok` com `km = 0.0`, `minutes = 0.0`, `method = "identity"` e `source_run_id` nulo.
É exato porque origem e destino usam o mesmo ponto. Aeroportos nunca são identidade.

## 4. Item de coleta e estado

- `pair_id(dico, pole_id, mode) = f"{dico}--{pole_id}--{mode}"`; `mode` ∈ modos habilitados no catálogo (hoje só `driving`; `transit` é suportado). É o `id` do item
  de `collect_items` e o `dataset_id` no manifest. `pole_id` casa `[a-z0-9_]+` (sem `--`).
- Os itens são ordenados por `id` (o contrato depende dessa ordem).
- **Assinatura do par** (`pair_signature`): SHA-256 do JSON canônico de
  `{origin: [lat, lon], destination: [lat, lon], mode, travel_mode, routing_preference, departure_time,
  api_url, field_mask}`. Vai em `entry_extra.pair_signature` de cada entrada `changed`.
- Estado vigente do par = entrada `changed` mais recente (`latest_dataset_states`, spec 002/003).
  `is_current_state(item, state)` é `state["pair_signature"] == pair_signature(item)`.
- **Atual**: estado existe e a assinatura confere. **Desatualizado (`stale`)**: estado existe, assinatura
  difere. **Novo**: sem estado.
- `collect_items(skip_current=True, state_is_current=...)` pula os atuais e reconsulta desatualizados e novos.
  A reconsulta grava uma **nova revisão** em outro `run_id`; a anterior permanece no bruto (constitution V).

## 5. Estado de cada linha (`build_distance_rows`)

Para cada par esperado e modo habilitado `driving` (e `transit`, se habilitado), incluindo identidade:

| Situação | `status` | `km` / `minutes` | `no_route_reason` |
|---|---|---|---|
| identidade | `ok` | `0.0` / `0.0` | nulo |
| estado vigente, `condition == ROUTE_EXISTS` | `ok` | `distanceMeters/1000` / `duration_s/60` | nulo |
| estado vigente, `condition == ROUTE_NOT_FOUND` | `sem_rota` | nulo / nulo | `ROUTE_NOT_FOUND` |
| sem estado e a **última tentativa** do par foi `failed` | `falha` | nulo / nulo | nulo (erro vai em `error`) |
| sem estado e sem tentativa falha (inclui `pending`) | `pendente` | nulo / nulo | nulo |

- "Última tentativa": entre os manifests da fonte, a entrada mais recente do par (qualquer status). Um estado
  `changed` existente vence uma falha mais antiga; uma falha **mais nova** que o estado não o apaga (o estado
  continua o vigente) e não vira `falha`.
- `stale = True` quando o par tem estado, mas a assinatura atual difere. A linha mantém o valor antigo e
  `status` do estado; só a bandeira muda. Linhas de identidade e de `straight_line` têm `stale = False`.
- `straight_line`: `status = ok`, `minutes = None` sempre (não se aplica), `stale = False`, `method = "haversine"`.
- Nunca preencher `km`/`minutes` fora das linhas `ok`. Nunca copiar valor de outro modo.

## 6. Cálculo do valor a partir do bruto

`duration` vem como string `"<n>s"`; `minutes = n / 60` sem arredondar. `distanceMeters` é inteiro;
`km = distanceMeters / 1000`. Os valores no staging não são arredondados (a apresentação decide).

## 7. Estimativa (`estimate_run`)

```python
pairs   = route_pairs(towns, poles)                    # ambos os modos, com identity
queried = [p for p in pairs if not p["identity"]]
new     = [p for p in queried if no state for p]
stale   = [p for p in queried if state exists and not current]
elements = Counter(mode for p in new + stale)
free_cost  = Σ_mode max(0, elements[mode] - free_monthly[mode]) * usd_per_1000[mode] / 1000
worst_cost = Σ_mode elements[mode] * usd_per_1000[mode] / 1000
```

Retorna `pairs_total, identity, new, stale, elements (dict por modo), elements_total, ceiling,
cost_usd_estimate (= free_cost), cost_usd_worst_case (= worst_cost)`. O contrato exige esses nomes.
O teto gratuito é **mensal**: se o operador já gastou parte dele no mês, a estimativa subestima; o aviso fica
no texto da CLI.
