{{ config(tags=['gold']) }}
-- Constitution III / SC-006: nenhuma estatística de aluguel com menos de 10 anúncios.
select dico, typology, n_eligible, n_eur_m2, rent_median, eur_m2_median
from {{ ref('gold_rent_by_municipality_typology') }}
where (n_eligible < 10 and (rent_median is not null or rent_p25 is not null or rent_p75 is not null))
   or (n_eur_m2 < 10 and eur_m2_median is not null)
   or (n_eligible >= 10 and rent_median is null)
   or n_listings <> n_eligible + n_outliers
