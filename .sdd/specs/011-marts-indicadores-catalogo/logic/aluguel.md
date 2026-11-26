# Lógica: aluguel descritivo (Idealista) com outliers por IQR

Contrato: `test_us1_fr009_fr010_fr011_fr012_rent_marks_iqr_outliers_without_deleting_and_needs_ten_listings`.

## 1. Entrada e elegibilidade

`idealista_listings` (silver): um anúncio por `listing_id` no snapshot vigente (`snapshot_month` máximo).
Entra no município se `dico` não é nulo (os `regiao` ficam fora de **todo** agregado). Um preço é válido se
`asking_rent_eur` não é nulo. Anúncios com `has_conflict` já chegam com o território nulo.

## 2. Outliers (por município × tipologia; nunca apaga)

```text
para cada grupo (dico, typology) com typology não nula:
  precos = asking_rent_eur válidos do grupo
  se len(precos) >= 10:
      q1, q3 = percentis 25 e 75 (interpolação linear)
      outlier = preco < q1 - 1.5*(q3-q1)  ou  preco > q3 + 1.5*(q3-q1)
  senão: nenhum outlier (grupo pequeno)
```

A marca existe só em memória (não vai ao lake: anúncio não é publicável, constitution IV/VI). Ficam visíveis
as contagens `n_listings` (com preço válido, inclusive outliers), `n_outliers` e `n_eligible` (sem outliers).

## 3. Estatísticas (por município × `ALL`, `T0`, `T1`, `T2`, `T3`, `T4+`)

```text
eligible(g) = anúncios do grupo com preço válido e não marcados
              (ALL = todos os anúncios do município: os marcados no seu grupo de tipologia ficam fora;
               os de tipologia nula entram só no ALL)
se n_eligible >= 10:  rent_median, rent_p25, rent_p75 = percentis 50/25/75 (linear); sample_status "suficiente"
se 1 <= n_eligible < 10: nulos; sample_status "amostra_insuficiente"
se n_eligible == 0: nulos; sample_status "sem_anuncios"
eur_m2 = asking_rent_eur / area_m2 dos elegíveis com 10 <= area_m2 <= 1000 (plano §7.3)
n_eur_m2 = quantos; eur_m2_median só com n_eur_m2 >= 10
```

- Sempre saem as 6 linhas por município de `municipalities`, inclusive sem anúncios (n = 0).
- `rent_coverage` (igual nas 6 linhas do município):
  `propria` se `ALL.n_eligible >= 10`; `insuficiente` se `1..9`; `regional_only` se não há anúncio
  municipal, o município está numa região autónoma (`autonomous_region` não nulo) e existem anúncios
  `regiao` com `source_region` dessa região (`Madeira` ↔ Região Autónoma da Madeira, `Açores` ↔ Região
  Autónoma dos Açores); `sem_anuncios` nos demais.
- Proveniência: `snapshot_month`, `source_id = "idealista"`, `license_id` e `attribution` do snapshot.

## 4. Freguesia (`parish_rent_stats`, P3)

Mesmo cálculo, com o grupo `(dicofre, typology)`, só para anúncios com `dicofre` não nulo. A marca de
outlier é **a do grupo municipal** (não se recalcula IQR por freguesia, que teria grupos pequenos demais).
Uma linha por freguesia de `dim_parish` × 6 variantes. `rent_coverage` da freguesia:
`propria` / `insuficiente` / `sem_anuncios`.

## 5. Indicadores de custo (linhas de `gold_*_indicator`)

`custo_aluguel_mediana` (variantes ALL e T0..T4+) = `rent_median`; `custo_aluguel_m2` (ALL) = `eur_m2_median`.
Ausente com motivo `amostra_insuficiente` (1..9), `sem_anuncios` (0) ou `regional_only`. `period = snapshot_month`.
