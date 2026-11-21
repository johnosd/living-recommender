# Handoff
## Contexto
J:/living-recommender, Python 3.12/dbt-DuckDB, feature 007 planejada. Próximo: sdd-execute 007-idealista-formato-atual-relatorio. Ler spec, plan, tasks, data-model, quickstart e constitution. O autor pediu adaptação, ingestão real e report; preferência de ritmo consultada por pergunta estruturada.
## Entrega
US1 P1: território explícito e legado. US2 P1: relatório agregado com n>=10. Polish: ingestão e prova local.
## Contratos
Quatro em tests/contracts/test_idealista_current_contract.py. Rodar python -m pytest; verificar check-contract-tests.ps1 -Slug 007-idealista-formato-atual-relatorio. Preservar trava 005 e demais. Stub report.write_report deve ser implementado.
## Armadilhas
Setúbal/Aveiro/Braga/Beja etc são distritos no lote novo quando Município é nulo. Angústias (Horta) e Horta (Matriz) são freguesias rotuladas como município: resolver somente por seed explícita. Não misturar links_localidades com anúncios. Preservar raw anterior e saídas de outras fontes.
## Aceite
Sem achados bloqueantes no Analyze. Executar gates e relatório real; CI remoto e nuvem fora do escopo.
