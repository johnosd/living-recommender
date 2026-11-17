# Idealista: formato atual e relatório (2026-11-17)

- Origem atual: `J:/IdealistaScraper/.data/municipios/{YYYYMM}`. Catálogo de localidades em pasta separada: não importar `.data` inteira.
- Feature 007 usa metadados Região/Sub-região/Município/Freguesia completos ou legado sem eles. Município nulo significa regional, mesmo com nome de distrito igual ao município. Não resolver freguesia globalmente para fabricar município.
- 58 aliases de escrita revisados na seed `idealista_metadata_parish_synonyms.csv`, exclusivos do formato novo; validação por DICO/DICOFRE. Três aliases de arquivos planos incluem Lagoa (Algarve) e as duas freguesias de Horta. A preparação histórica de 2025-08 conserva suas contagens.
- Lote 2026-11: 74 JSON/19.531.665 bytes/18.059 anúncios únicos, sem IDs repetidos; 54 municípios (42 com n>=10), 6.371 regionais, 10.751 com freguesia, 937 municipais sem freguesia. Não inferir completude nacional ou evolução temporal em relação a 2025-08.
- Relatório: `.docs/reports/idealista-2026-11.md`; saídas correntes locais em `.data/lake/bronze/idealista_reports/`; backup/evidências em `.data/idealista-review-202611/`. Segundo import unchanged; 74 hashes novos, 324 raw antigos, 25 arquivos de outras fontes preservados; dbt real 24/24. Nenhuma publicação ou AWS.
- Mediana/P25/P75 locais com n elegível>=10, excluindo preços conflitantes/inválidos. Mediana de lote €1.350 não é estimativa nacional. Dados individuais só em .data.
- Após migração C:→J:, entrypoints uv do ambiente antigo falharam. `uv sync --locked --reinstall-package dbt-core --reinstall-package pytest --reinstall-package ruff` regenerou-os sem alterar lock; `uv run --locked python -m pytest` funciona também.

Evidências: spec/plan/tasks 007 e `.data/idealista-review-202611/after.json`.

Estado da execução: Implementada localmente, 14/14 itens. Autor autorizou os dois ajustes de estilo no contrato 007 e a atualização do hash. Suíte geral anterior 434 passed; pós-ajuste, 41 testes Idealista aprovados em 25,52 s, ruff geral limpo, sete travas íntegras. CI remoto/publicação não executados.

Atualização após convergência e retomada da Phase 4: progresso 16/17;
recortes JSON/Markdown completados e agregados reais regenerados (308 municípios,
225 grupos município/tipologia, dbt 24/24, 501 hashes protegidos). Estatísticas
anteriores e bytes dos CSV municipais mantidos. Falta T013: CI da revisão final
pelo fluxo autorizado. Ver `idealista-007-convergencia.md` e `plan.md` da 007.
Validação desta retomada: suíte geral 437 passed/493,04 s; regressão dirigida
43 passed/26,46 s; ruff geral e sete travas íntegros. Nenhum commit/push ou
publicação nesta execução.
