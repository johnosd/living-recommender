# Contrato: `config/criteria.yml` e as tabelas do catálogo

Superfície consumida pela Fase 4 (ranker e configurador). Esta feature **não** exporta `criteria.json`
nem `published/vN`; o contrato abaixo é o que existe no lake (`lake/gold/`) e no arquivo versionado.

## 1. Arquivo `config/criteria.yml`

```yaml
schema_version: 1
categories:                      # ordem = ordem de exibição
  - {id: custo, label_pt: Custo, label_en: Cost}
criteria:
  - id: cultura_cinemas_10k      # estável, snake_case ASCII, único
    category: cultura            # id de `categories`
    label_pt: Recintos de cinema por 10 mil habitantes
    label_en: Cinemas per 10,000 residents
    unit: recintos por 10 mil hab.
    direction: maior_melhor      # maior_melhor | menor_melhor | faixa_alvo
    levels: [municipio]          # municipio e/ou freguesia
    modes: [peso, faixa]         # peso | faixa | opcao
    default_range: [null, null]  # [mín, máx] padrão do slider; null = aberto
    weight: 0.5                  # peso interno na categoria, 0 a 1
    status: disponivel           # disponivel | fonte_pendente
    pending_reason: null         # obrigatório (texto) quando fonte_pendente
    methodology_pt: Recintos (Pordata 623) ÷ residentes do mesmo ano × 10 000.
    options: null                # obrigatório quando `opcao` está em modes (ver §1.3)
    compute: {...}               # nível município (§1.2)
    compute_parish: {...}        # opcional; sem ele, a freguesia herda o valor do município
```

### 1.1 Validação (`load_criteria`, `catalog_tables`)

Toda violação levanta `CriteriaError`. A mensagem **cita o id entre aspas simples** (`'a2'`, `'custo'`).

- ids de critério e de categoria únicos; `category` existe em `categories`.
- `direction`, `levels`, `modes`, `status` só com os valores listados; `levels` e `modes` não vazios.
- `fonte_pendente` exige `pending_reason`; `disponivel` exige `compute`.
- Em cada categoria, a soma de `weight` dos critérios `disponivel` com `weight > 0` é 1 (tolerância 1e-9).
  Uma categoria só com pesos 0 é inválida. Critérios com peso 0 servem só como filtro (`modes: [faixa]`).
- `opcao` em `modes` exige `options` com pelo menos 2 itens, e cada item tem `id`, `label_pt`, `label_en`
  e `range: [mín|null, máx|null]`.
- `default_range`, quando os dois lados existem, tem mín ≤ máx.
- Em `catalog_tables`: um critério `disponivel` sem nenhum valor não nulo, em algum nível que declara,
  levanta `CriteriaError` (para `freguesia`, só conta valor com `origin = proprio`).

### 1.2 `compute`

| `kind` | Campos | Significado |
| --- | --- | --- |
| `observation` | `source_id`, `dataset_id`, `filters` (lista de dicts `filter_1..3`), `dash_is_zero` (bool), e no máximo um entre `per_population`, `share` e `presence` | Numerador = soma das linhas de `filters` no mesmo período. Chave ausente no dict = `""`. A comparação ignora espaços duplicados e NBSP (`\xa0`). Ver `logic/indicadores.md`. |
| `observation` + `per_population` | `{scale, age_groups}` | Numerador ÷ população residente do mesmo município e período × `scale`. `age_groups: null` = `filter_1=Total, filter_2=Total` de `populacao_residente_sexo_idade`; senão, soma das faixas `filter_2` listadas (com `filter_1=Total`). |
| `observation` + `share` | `{filters, scale}` | Numerador ÷ linha `filters` do **mesmo dataset**, mesmo período × `scale`. |
| `observation` + `presence: true` | — | 1 se o numerador > 0, senão 0. |
| `climate` | `metric` | Um de: `temp_media_anual`, `temp_max_verao`, `temp_min_inverno`, `precipitacao_anual`, `sol_horas_dia`, `dias_calor_pct`, `dias_frio_pct`, `dias_chuva_pct`, `dias_neve_pct`, `dias_extremos_pct`, `tci_anual` (`logic/clima.md`). |
| `mobility` | `mode` (`straight_line` / `driving`), `measure` (`km` / `minutes`), e `pole_id` **ou** `nearest_kind` | Polo fixo ou o mais próximo do tipo (`logic/indicadores.md`, Mobilidade). `minutes` só com `driving`. |
| `rent` | `metric` (`median` / `eur_m2_median`), `variants` (lista de `ALL`, `T0`...`T4+`) | Lê as estatísticas de aluguel (`logic/aluguel.md`); uma linha por variante. |
| `census` (só em `compute_parish`) | `metric` (`residentes` / `pct_25_39` / `pct_65_mais` / `densidade`) | Censos 2021 da freguesia (`census_parish_observation`) e área da CAOP. |

### 1.3 Opções categóricas

`range` é semiaberto `[mín, máx)`, e `null` abre o lado. Exemplo (porte):

```yaml
options:
  - {id: vila, label_pt: Vila, label_en: Town, range: [null, 20000]}
  - {id: cidade_media, label_pt: Cidade média, label_en: Mid-sized city, range: [20000, 100000]}
  - {id: grande_centro, label_pt: Grande centro, label_en: Large city, range: [100000, null]}
```

## 2. `catalog_tables(criteria, indicators) -> (catalogo, normalizacao)`

- `indicators`: `{"municipio": DataFrame, "freguesia": DataFrame}`, nas colunas de `data-model.md`; a chave
  `freguesia` é opcional até a P3.
- **`catalogo`**: uma linha por critério do YAML (inclusive pendentes), nas colunas de
  `gold_criteria_catalog` (`data-model.md`).
- **`normalizacao`**: uma linha por critério `disponivel` × nível declarado × variante com pelo menos um
  valor. `n`, `min`, `p5`, `p95` e `max` vêm dos valores não nulos (na freguesia, só `origin = proprio`);
  os percentis usam interpolação linear (`numpy.percentile` padrão, igual ao `quantile_cont` do DuckDB).
  `is_degenerate = p5 == p95`.
- **`catalog_version`**: os 12 primeiros hex do SHA-256 do JSON canônico (`sort_keys`, separadores
  compactos, floats com `repr`) de `{schema_version, categories, criteria, normalizacao}`. Entram as linhas
  de normalização ordenadas por (`criterion_id`, `level`, `variant`). O mesmo YAML e os mesmos valores dão
  a mesma versão; qualquer mudança dá uma versão nova (FR-022). `processed_at_utc` não entra no hash.

## 3. Catálogo inicial (o executor transcreve para `config/criteria.yml`)

Abreviações: **P** = `per_population`, **S** = `share`, **Pr** = `presence`, `dz` = `dash_is_zero: true`.
Pop = `populacao_residente_sexo_idade`. Os pesos e as faixas são provisórios (R-003); são dados e mudam
sem código.

| id | cat. | direção | modos | peso | compute | unidade |
| --- | --- | --- | --- | --- | --- | --- |
| custo_aluguel_mediana | custo | menor_melhor | peso, faixa | 0,6 | rent median, variants ALL,T0..T4+; parish: rent median | €/mês |
| custo_aluguel_m2 | custo | menor_melhor | peso, faixa | 0,2 | rent eur_m2_median, ALL; parish: idem | €/m²/mês |
| custo_renda_ine_m2 | custo | menor_melhor | peso, faixa | 0,2 | ine rendas_novos_contratos, filters [{}] | €/m² |
| clima_temp_media_anual | clima | faixa_alvo | peso, faixa, opcao | 0,3 | climate temp_media_anual; options fresco [null,14.5), ameno [14.5,17), quente [17,null) | °C |
| clima_temp_max_verao | clima | menor_melhor | peso, faixa | 0,1 | climate temp_max_verao | °C |
| clima_temp_min_inverno | clima | maior_melhor | peso, faixa | 0,1 | climate temp_min_inverno | °C |
| clima_precipitacao_anual | clima | menor_melhor | peso, faixa | 0,1 | climate precipitacao_anual | mm/ano |
| clima_sol_horas_dia | clima | maior_melhor | peso, faixa | 0,1 | climate sol_horas_dia | h/dia |
| clima_dias_extremos_pct | clima | menor_melhor | peso, faixa | 0,1 | climate dias_extremos_pct | % dos dias |
| clima_tci_anual | clima | maior_melhor | peso, faixa | 0,2 | climate tci_anual | índice 0–100 |
| clima_dias_calor_pct / _frio_ / _chuva_ / _neve_ | clima | menor_melhor | faixa | 0 | climate dias_<tipo>_pct | % dos dias |
| cultura_cinemas_10k | cultura | maior_melhor | peso, faixa | 0,5 | pordata recintos_cinema, dz, P 10000 | por 10 mil hab. |
| cultura_espetaculos_10k | cultura | maior_melhor | peso, faixa | 0,5 | pordata sessoes_espetaculos_ao_vivo, dz, P 10000 | por 10 mil hab. |
| economia_poder_compra | economia | maior_melhor | peso, faixa | 0,7 | ine poder_compra_per_capita | índice (PT = 100) |
| economia_agencias_bancarias_10k | economia | maior_melhor | peso, faixa | 0,3 | pordata agencias_bancarias, dz, P 10000 | por 10 mil hab. |
| emprego_desemprego_100 | emprego | menor_melhor | peso, faixa | 0,5 | pordata desemprego_registado filters [{filter_1: Total}], dz, P 100 age_groups 15–19 … 60–64 | por 100 residentes de 15–64 |
| emprego_ganho_medio_mensal | emprego | maior_melhor | peso, faixa | 0,5 | pordata ganho_medio_mensal | €/mês |
| emprego_setor_<letra>_pct (A, B, C, D, E, F, G, H, I, J, L, M, N, P, Q, R, S) | emprego | faixa_alvo | faixa | 0 | pordata pessoal_ao_servico_empresas filters [{filter_1: "<letra>. <rótulo>"}], dz, S {filter_1: Total} × 100 | % do pessoal ao serviço |
| educacao_escolas_1000_jovens | educacao | maior_melhor | peso, faixa | 0,6 | pordata ensino_nao_superior filters [{filter_1: Total, filter_2: Total}], dz, P 1000 age_groups 0–4 … 15–19 | por mil residentes de 0–19 |
| educacao_ensino_superior | educacao | maior_melhor | peso | 0,4 | pordata ensino_superior filters [{filter_1: Total}], dz, Pr | 1 = há, 0 = não há |
| populacao_residentes | populacao | faixa_alvo | opcao, faixa | 0,5 | Pop [{filter_1: Total, filter_2: Total}], dz; options vila / cidade_media / grande_centro (§1.3); parish: census residentes | residentes |
| populacao_pct_25_39 | populacao | maior_melhor | peso, faixa | 0,25 | Pop 25–29 + 30–34 + 35–39, dz, S {Total, Total} × 100; parish: census pct_25_39 | % |
| populacao_pct_65_mais | populacao | menor_melhor | peso, faixa | 0,25 | Pop 65–69 … 85 ou mais, dz, S × 100; parish: census pct_65_mais | % |
| populacao_densidade | populacao | faixa_alvo | faixa | 0 | pordata densidade_populacional; parish: census densidade | hab./km² |
| comunidade_estrangeira_pct | comunidade | maior_melhor | peso, faixa | 0,5 | pordata populacao_estrangeira_residente [{filter_1: Total}], dz, P 100 | % dos residentes |
| comunidade_brasileira_pct | comunidade | maior_melhor | peso, faixa | 0,5 | idem com [{filter_1: "2.1. Brasil"}] | % dos residentes |
| saude_hospitais | saude | maior_melhor | peso, faixa | 0,5 | pordata hospitais [{filter_1: Total}], dz | hospitais |
| saude_farmacias_10k | saude | maior_melhor | peso, faixa | 0,5 | pordata farmacias, dz, P 10000 | por 10 mil hab. |
| seguranca_taxa_criminalidade | seguranca | menor_melhor | peso, faixa | 0,5 | ine taxa_criminalidade [{filter_1: Total}] | ‰ |
| seguranca_crimes_pessoas_1000 | seguranca | menor_melhor | peso, faixa | 0,5 | pordata crimes_por_categoria [{filter_1: "1. Contra as pessoas"}], dz, P 1000 | por mil hab. |
| distancia_lisboa_carro_min | distancia | menor_melhor | peso, faixa | 0,25 | mobility driving minutes pole lisboa | min |
| distancia_porto_carro_min | distancia | menor_melhor | peso, faixa | 0,25 | mobility driving minutes pole porto | min |
| distancia_aeroporto_carro_min | distancia | menor_melhor | peso, faixa | 0,5 | mobility driving minutes nearest aeroporto | min |
| distancia_{lisboa,porto,aeroporto}_carro_km | distancia | menor_melhor | faixa | 0 | mobility driving km | km |
| distancia_{lisboa,porto,aeroporto}_km | distancia | menor_melhor | faixa | 0 | mobility straight_line km | km (linha reta) |
| distancia_sede_distrito_km | distancia | menor_melhor | faixa | 0 | **fonte_pendente**: "polos de sede de distrito não configurados em config/poles.yml (spec 009); exige recoleta" | km |
| mercado_fogos_concluidos_1000 | mercado | maior_melhor | peso, faixa | 1,0 | pordata fogos_concluidos [{filter_1: Total}], dz, P 1000 | por mil hab. |

Categorias, em ordem: custo, clima, cultura, economia, emprego, educacao, populacao, comunidade, saude,
seguranca, distancia, mercado. Rótulos EN: Cost, Climate, Culture, Economy, Jobs and wages, Education,
Population, Foreign community, Health, Safety, Distances, Housing market.

Rótulos dos critérios: o executor escreve `label_pt`, `label_en` e `methodology_pt` (fórmula, dataset
Pordata/INE com número da tabela, período e regra do `-`). Os rótulos de `emprego_setor_*` repetem a seção
CAE. Os rótulos `filter_1` das seções CAE estão em `stg_observation` como `"A. \xa0Agricultura, …"`: com a
normalização de espaços, o YAML usa `"A. Agricultura, produção animal, caça, floresta e pesca"`.
