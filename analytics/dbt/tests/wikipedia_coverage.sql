{{ config(tags=['wikipedia']) }}
with issues as (
  select 'missing_municipality' as issue from {{ source('caop_silver', 'dim_municipality') }} d
    left join {{ ref('wikipedia_coverage') }} c using(dico) where c.dico is null
  union all
  select 'municipality_name_mismatch' from {{ ref('wikipedia_coverage') }} c
    join {{ source('caop_silver', 'dim_municipality') }} d using(dico)
    where c.official_name is null or c.official_name <> d.official_name
  union all
  select 'unready' from {{ ref('wikipedia_coverage') }} where status not in ('valid','absent')
    or (status = 'valid' and (not identity_validated or not extraction_complete or revision_id is null))
    or (status = 'absent' and (reason is null or absence_evidence_json is null or absence_evidence_json = 'null'))
  union all
  select 'article_coverage_missing' from {{ ref('wikipedia_coverage') }} c
    left join {{ ref('wikipedia_article') }} a using(dico)
    where (c.status = 'valid' and a.dico is null) or (c.status = 'absent' and a.dico is not null)
  union all
  select 'section_count_mismatch' from {{ ref('wikipedia_coverage') }} c
    left join (select dico, count(*) n from {{ ref('wikipedia_section') }} group by dico) s using(dico)
    where c.section_count <> coalesce(s.n, 0)
  union all
  select 'block_count_mismatch' from {{ ref('wikipedia_coverage') }} c
    left join (select dico, count(*) n from {{ ref('wikipedia_block') }} group by dico) b using(dico)
    where c.block_count <> coalesce(b.n, 0)
)
select * from issues
