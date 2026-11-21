{{ config(tags=['mobility']) }}
-- constitution III: km e minutes só existem em `ok`; a linha reta não tem tempo; sem_rota explica o motivo.
select * from {{ ref('stg_municipality_pole_distance') }}
where (status = 'ok' and km is null)
    or (status <> 'ok' and (km is not null or minutes is not null))
    or (status = 'ok' and mode <> 'straight_line' and minutes is null)
    or (mode = 'straight_line' and (minutes is not null or status <> 'ok'))
    or (status = 'sem_rota' and no_route_reason is null)
    or (status = 'falha' and error is null)
