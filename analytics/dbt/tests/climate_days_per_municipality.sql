{{ config(tags=['climate']) }}
with meta as (
    select * from read_parquet('{{ env_var('CLIMATE_PREPARED_DIR', '.data/ci-climate/prepared') }}/climate_meta.parquet')
)
select s.dico, s.variable, count(*) as days
from {{ ref('stg_climate_daily') }} s
join meta m using (variable)
group by s.dico, s.variable, m.expected_days, m.window_start, m.window_end
having count(*) <> m.expected_days or min(s.date) <> m.window_start or max(s.date) <> m.window_end
