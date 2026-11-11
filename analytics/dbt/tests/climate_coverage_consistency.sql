{{ config(tags=['climate']) }}
select * from {{ ref('rpt_climate_coverage') }}
where municipalities_complete + municipalities_with_gaps + municipalities_not_collected <> municipalities_expected
    or municipalities_collected <> municipalities_complete + municipalities_with_gaps
    or missing_days_total < 0
