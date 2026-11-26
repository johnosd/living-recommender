# Lógica: indicadores de observações (Pordata/INE) e de mobilidade

Contratos: `test_us1_ac1_ac4_..._dash_rule` (observações) e `test_us1_ac5_..._google_attribution`
(mobilidade), em `tests/contracts/test_gold_indicators_contract.py`.

## 1. Observações — `municipal_indicators(observations, municipalities, criteria)`

Entrada: `stg_observation` (todas as colunas). Saída: **uma linha por município de `municipalities` × critério
`disponivel` com `compute.kind == "observation"`**, com `variant = ""`. Um município sem nenhum dado também
sai, como ausente.

```text
para cada critério c, município m:
  linhas(c) = observações com dataset_id = c.dataset_id e (filter_1, filter_2, filter_3) em c.filters
              (comparação após normalizar espaços: NBSP -> espaço, colapsar, strip; chave ausente = "")
  valor_linha(o) = o.value                 se o.value não é nulo
                   0.0                     se o.value é nulo e o.symbol == "-" e c.dash_is_zero   # R-001
                   nulo (motivo "simbolo_fonte:<symbol>")  se nulo com símbolo
                   nulo (motivo "sem_publicacao")          se nulo sem símbolo
  num(m, p) = soma de valor_linha nas partes de c.filters em (m, p); nulo se faltar QUALQUER parte
  P(m) = { p : num(m, p) não nulo }
  latest_dataset = max de P(m) sobre todos os m (o "período nacional"); str(ano)
  se P(m) vazio:
      ausente; motivo = motivo da linha do período mais recente de m, ou "sem_publicacao" se m não tem linha
  senão p* = max P(m):
      denominador (se per_population/share):
         per_population: soma das faixas de população de (m, p*) com a mesma regra valor_linha (dz = True)
         share:          linha c.share.filters do mesmo dataset em (m, p*)
         nulo ou 0      -> ausente, motivo "sem_denominador" (o período fica registrado)
      valor = num × scale ÷ denominador   (ou num, sem denominador)
      presence: valor = 1.0 se num > 0, senão 0.0
      value_status = "zero_convencao_fonte" se alguma parte usou a regra do "-" e o valor é 0, senão "observado"
      period = str(p*); is_older_period = p* < latest_dataset
```

- `source_symbol`: o símbolo da parte do numerador em `p*` (`-`, `r`, `Pro`, `Quebra de série`...); se
  houver mais de um, os distintos juntos com `|`. É informativo: valores com `r`/`Pro` continuam
  `observado`.
- Proveniência: `source_id`, `dataset_id`, `license_id` e `attribution` vêm da linha do numerador;
  `usage_restriction` é nula no Pordata e no INE.
- `dataset_latest_period` e `is_older_period` existem também nas linhas ausentes (o `is_older_period` fica
  `False` quando não há período).
- Datasets de contagem (com `dash_is_zero: true` no catálogo): recintos, sessões, agências, desemprego,
  escolas, ensino superior, farmácias, hospitais, crimes, fogos, pessoal ao serviço, população estrangeira e
  população residente. Taxas, índices e médias (ganho médio, densidade, taxa de criminalidade, rendas INE,
  poder de compra) nunca usam a regra.

## 2. Mobilidade — `mobility_indicators(distances, poles, municipalities, criteria)`

Entrada: `stg_municipality_pole_distance` e `dim_mobility_pole`. Saída: uma linha por município × critério
`disponivel` com `compute.kind == "mobility"`, com `variant = ""`.

```text
pares(m, c) = linhas de distances com dico = m e mode = c.mode e
              (pole_id = c.pole_id   | pole_id em poles com kind = c.nearest_kind)
sem linhas                           -> ausente, motivo "sem_par_elegivel"   (ex.: ilha sem rota até Lisboa)
nearest_kind e algum par em falha/pendente -> ausente, motivo "par_falha" / "par_pendente"
                                        (o par que falhou poderia ser o mais próximo: não escolher outro)
pole_id fixo e o par não é ok        -> ausente, motivo "par_falha" / "par_pendente" / "sem_rota"
senão: pares ok (os sem_rota são ignorados no nearest); escolhido = o de menor c.measure
       (empate: menor pole_id). valor = escolhido[c.measure]; se só houver sem_rota: ausente "sem_rota"
```

- O valor 0 do próprio polo (`method = identity`) é `observado`.
- Proveniência copiada do par escolhido (ou do primeiro par elegível, na ausência): `source_id`, `license_id`,
  `attribution`, `usage_restriction`; `period = reference_period`; `is_stale = stale`. O carro leva
  "Tempos de viagem: Google" e a restrição do Google (FR-008); a linha reta leva a atribuição da CAOP.
- `dataset_id = "stg_municipality_pole_distance"`; `dataset_latest_period = period`; `is_older_period = False`.
- Pares `stale` são usados e contados no mart de qualidade (`stale`).

## 3. Campos comuns da linha de indicador

Colunas e códigos fechados: `data-model.md`. `missing_reason` só existe quando `value` é nulo, e todo valor
nulo tem motivo. Códigos: `simbolo_fonte:<s>`, `sem_publicacao`, `sem_denominador`, `sem_par_elegivel`,
`sem_rota`, `par_falha`, `par_pendente`, `amostra_insuficiente`, `sem_anuncios`, `regional_only`,
`sem_dados_clima`.
