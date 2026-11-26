{{ config(tags=['gold']) }}
-- Constitution III / SC-006: nenhuma estatística de aluguel com menos de 10 anúncios, no município, no distrito e na
-- região (spec 012).
with areas as (
    select 'municipio' as level, dico as territory, typology, n_listings, n_outliers, n_eligible, n_eur_m2,
           rent_median, rent_p25, rent_p75, eur_m2_median
    from {{ ref('gold_rent_by_municipality_typology') }}
    union all
    select 'distrito', district_or_island, typology, n_listings, n_outliers, n_eligible, n_eur_m2,
           rent_median, rent_p25, rent_p75, eur_m2_median
    from {{ ref('gold_rent_by_district_typology') }}
    union all
    select 'regiao', source_region, typology, n_listings, n_outliers, n_eligible, n_eur_m2,
           rent_median, rent_p25, rent_p75, eur_m2_median
    from {{ ref('gold_rent_by_region_typology') }}
)
select level, territory, typology, n_eligible, n_eur_m2, rent_median, eur_m2_median
from areas
where (n_eligible < 10 and (rent_median is not null or rent_p25 is not null or rent_p75 is not null))
   or (n_eur_m2 < 10 and eur_m2_median is not null)
   or (n_eligible >= 10 and rent_median is null)
   or n_listings <> n_eligible + n_outliers
