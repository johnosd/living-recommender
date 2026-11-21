# Data Model
Raw e manifest v1 permanecem sem alteração. Ocorrências e anúncios únicos adicionam source_subregion, source_municipality e source_parish (texto anulável); source_region passa a Região no formato novo. Sem campos pessoais novos. coverage.csv continua 308 municípios mais grupos regionais. municipality_stats.csv contém dico/name/n_listings/n_eligible/P25/mediana/P75/status e proveniência; municipality_typology_stats.csv adiciona tipologia. statistics.json e report.md descrevem apenas agregados. Preço conflitante excluído; n elegível <10 suprime os três quartis.

Phase 4: `statistics.json` inclui os arrays `municipality_stats` (todos os
municípios da dimensão, inclusive sem amostra) e `municipality_typology_stats`
(apenas grupos observados, incluindo tipologia não informada). Os registros
usam os mesmos campos e valores dos CSV correspondentes; quartis ausentes são
`null`. As chaves anteriores do JSON permanecem preservadas. O Markdown inclui
também o recorte município/tipologia, identificando nome, DICO e tipologia,
sem IDs de anúncios. Anúncios regionais continuam fora dos dois recortes.
