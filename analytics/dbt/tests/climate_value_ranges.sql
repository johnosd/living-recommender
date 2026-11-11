{{ config(tags=['climate']) }}
select * from {{ ref('stg_climate_daily') }}
where value is not null and (
    not isfinite(value)
    or (variable = 'relative_humidity_2m_mean' and (value < 0 or value > 100))
    or (variable in ('precipitation_sum', 'snowfall_sum') and value < 0)
    or (variable = 'sunshine_duration' and (value < 0 or value > 86400))
    or (variable in ('wind_speed_10m_mean', 'wind_speed_10m_max', 'wind_gusts_10m_max') and value < 0)
    or (variable like 'temperature_2m_%' and (value < -60 or value > 60))
    or (variable like 'apparent_temperature_%' and (value < -80 or value > 70))
)
