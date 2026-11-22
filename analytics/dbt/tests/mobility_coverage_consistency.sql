{{ config(tags=['mobility']) }}
select * from {{ ref('rpt_mobility_coverage') }}
where ok + sem_rota + falha + pendente <> expected or stale > ok + sem_rota
