{{ config(tags=['wikipedia']) }}
with issues as (
  select 'duplicate_section' as issue from {{ ref('wikipedia_section') }} group by dico, section_id having count(*) <> 1
  union all
  select 'duplicate_block' from {{ ref('wikipedia_block') }} group by dico, block_id having count(*) <> 1
  union all
  select 'block_section_missing' from {{ ref('wikipedia_block') }} b
    left join {{ ref('wikipedia_section') }} s on b.dico = s.dico and b.section_id = s.section_id where s.dico is null
  union all
  select 'block_parent_missing' from {{ ref('wikipedia_block') }} b
    left join {{ ref('wikipedia_block') }} p on b.dico = p.dico and b.parent_block_id = p.block_id
    where b.parent_block_id is not null and (p.dico is null or p.block_order >= b.block_order)
  union all
  select 'section_parent_missing' from {{ ref('wikipedia_section') }} s
    left join {{ ref('wikipedia_section') }} p on s.dico = p.dico and s.parent_section_id = p.section_id
    where s.parent_section_id is not null and (p.dico is null or p.level >= s.level or p.section_order >= s.section_order)
  union all
  select 'revision_mismatch' from {{ ref('wikipedia_article') }} a
    join {{ ref('wikipedia_revision') }} r using(dico)
    where a.revision_id <> r.revision_id or a.page_id <> r.page_id or a.revision_id < 1 or a.page_id < 1
  union all
  select 'level_invalid' from {{ ref('wikipedia_section') }} where level < 0 or level > 6
  union all
  select 'empty_text' from {{ ref('wikipedia_article') }} where length(trim(full_text)) = 0
)
select * from issues
