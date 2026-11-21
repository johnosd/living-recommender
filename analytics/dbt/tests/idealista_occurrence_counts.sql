{{ config(tags=['idealista']) }}

with counts as (
    select listing_id, count(*) as occurrences
    from {{ ref('idealista_occurrences') }}
    group by listing_id
)
select coalesce(l.listing_id, c.listing_id) as listing_id
from {{ ref('idealista_listings') }} l
full outer join counts c using (listing_id)
where l.listing_id is null or c.listing_id is null or l.occurrence_count <> c.occurrences
