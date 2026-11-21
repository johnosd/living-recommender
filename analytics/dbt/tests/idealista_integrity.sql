{{ config(tags=['idealista']) }}

select listing_id
from {{ ref('idealista_listings') }} l
left join {{ source('caop_silver', 'dim_parish') }} p using (dicofre)
where (l.locality_level in ('municipio', 'freguesia') and l.dico is null)
   or (l.locality_level in ('regiao', 'conflict') and (l.dico is not null or l.dicofre is not null))
   or (l.dicofre is not null and p.dico <> l.dico)
   or l.occurrence_count <> l.duplicate_count + 1
   or l.duplicate_count < 0
   or l.asking_rent_eur <= 0
   or l.area_m2 <= 0
   or l.bedrooms < 0
   or l.collected_at_utc is not null
   or length(l.raw_sha256) <> 64
