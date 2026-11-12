{{ config(tags=['climate']) }}
select low.dico, low.date, low.value as tmin, high.value as tmax
from {{ ref('stg_climate_daily') }} low
join {{ ref('stg_climate_daily') }} high using (dico, date)
where low.variable = 'temperature_2m_min' and high.variable = 'temperature_2m_max'
    and low.value > high.value
