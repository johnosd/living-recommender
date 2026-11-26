# Lógica: clima (extremos e TCI do `weatherClassifier` legado, adaptados ao Open-Meteo)

Contrato: `test_us1_ac6_fr015_fr016_fr018_tci_bands_and_extreme_days_follow_the_legacy_rules`.
Fonte legada: `MPAlugueisLisboa/src/Weather/weatherClassifier.py` (`is_*_extreme`, `compute_tci_monthly`).

## 1. Variáveis (de `stg_climate_daily`, formato longo `dico, variable, date, value`)

| Legado (WWO) | Aqui (Open-Meteo) |
| --- | --- |
| `tempC` | `temperature_2m_mean` |
| `maxtempC` / `mintempC` | `temperature_2m_max` / `temperature_2m_min` |
| `HeatIndexC` > 40 | `apparent_temperature_max` > 40 |
| `WindChillC` < −5 | `apparent_temperature_min` < −5 |
| `humidity` | `relative_humidity_2m_mean` |
| `precipMM` | `precipitation_sum` |
| `totalSnow_cm` | `snowfall_sum` |
| `sunHour` | `sunshine_duration` ÷ 3600 |
| `windspeedKmph` | `wind_speed_10m_mean` |

A adaptação vai para o `methodology_pt` dos critérios de clima (FR-017).

## 2. Dia extremo (comparações estritas, como no legado)

```text
calor = tmax > 35  ou  aparente_max > 40
frio  = tmin < 1   ou  aparente_min < -5
chuva = precip > 35
neve  = snowfall > 0
extremo = calor ou frio ou chuva ou neve       # o UV do legado não entra (não existe no Open-Meteo)
```

Um dia só conta num tipo se as variáveis daquele tipo existirem. `valid_days` do mês = dias com
`temperature_2m_max` não nulo. `extreme_days_pct = extreme_days ÷ valid_days × 100`.

## 3. TCI mensal (por `dico` × `AAAA-MM`)

```text
tmean = média(temperature_2m_mean); tmax = média(temperature_2m_max); rh = média(relative_humidity_2m_mean)
P = soma(precipitation_sum); S = média(sunshine_duration)/3600; W = média(wind_speed_10m_mean)

faixa_temp(t) = 10 se 20 <= t <= 27
                 7 se 16 <= t < 20 ou 27 < t <= 30
                 5 se 13 <= t < 16 ou 30 < t <= 33
                 3 se 10 <= t < 13 ou 33 < t <= 36
                 0 caso contrário
ajuste(rh) = -1 se rh > 90 ou rh < 30, senão 0      # o legado usa a umidade MÉDIA nos dois (CID e CIA)
CID = faixa_temp(tmean) + ajuste(rh);  CIA = faixa_temp(tmax) + ajuste(rh)
p_index = 10 se P<=30 | 7 se P<=60 | 5 se P<=90 | 3 se P<=120 | 0
s_index = 10 se S>=9  | 7 se S>=7  | 5 se S>=5  | 3 se S>=3   | 0
w_index = 10 se W<15  | 7 se W<25  | 5 se W<35  | 3 se W<45   | 0
TCI = clamp(2*CID + 2*CIA + 0.5*p_index + 0.5*s_index + w_index, 0, 100)     # máximo possível: 60
```

- Mês com menos de **20** `valid_days`: médias, índices e TCI do mês ficam nulos (a janela atual é completa).
- `cid`, `cia`, `p_index`, `s_index` e `w_index` saem como inteiros; `tci` sai como float.
- Nada é arredondado no meio do cálculo (as faixas comparam a média crua).

## 4. Indicadores anuais (`climate_indicators`) sobre a janela coletada

| metric | Cálculo |
| --- | --- |
| `temp_media_anual` | média de `temperature_2m_mean` nos dias válidos da janela |
| `temp_max_anual` | média de `temperature_2m_max` nos dias válidos da janela (FR-014; T044) |
| `temp_min_anual` | média de `temperature_2m_min` nos dias válidos da janela (FR-014; T044) |
| `temp_max_verao` | média de `temperature_2m_max` nos dias de jun, jul e ago |
| `temp_min_inverno` | média de `temperature_2m_min` nos dias de dez, jan e fev |
| `precipitacao_anual` | soma de `precipitation_sum` × 365,25 ÷ dias válidos |
| `sol_horas_dia` | média de `sunshine_duration` ÷ 3600 |
| `dias_<tipo>_pct`, `dias_extremos_pct` | dias do tipo ÷ dias válidos da janela × 100 |
| `tci_anual` | média dos TCI mensais não nulos (como `tci_annual` do legado) |

- `period = "<window_start>/<window_end>"` (ex.: `2024-11-01/2026-10-31`); `dataset_id = "stg_climate_daily"`;
  proveniência do Open-Meteo (licença, atribuição, `usage_restriction`). `is_older_period = False`.
- Município sem nenhum dia: ausente, motivo `sem_dados_clima`.
- A tabela mensal publicada é `gold_municipality_climate_monthly` (a saída de `climate_monthly`, com proveniência).
