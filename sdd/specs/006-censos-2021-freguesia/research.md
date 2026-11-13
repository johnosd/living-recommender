# Research: Censos 2021 por freguesia

Consulta em 2026-11-13. Sondagens de leitura, com User-Agent do projeto e intervalo de 2 s; os resultados estão em `.data/research/censos-plan/` (ignorado pelo Git), fora de `raw/` e sem promoção. Não são uma coleta operacional nem prova de prontidão nacional de todas as faixas.

## R1 — Fonte detalhada e geografia

**Decisão:** fonte principal `0014632`, INE, população residente dos Censos 2021, sexo HM e nacionalidade Total, geografia 2025. Preservar o total e as 18 faixas publicadas. Fonte de fallback `0011719`, geografia censitária anterior, sexo HM, total e 19 grupos quinquenais. As duas têm metadados próprios.

**Justificativa:** `pindicaMeta.jsp?varcd=0014632&lang=PT` retornou versão geográfica `05723`, etária `00708`, sexo `00305` e nacionalidade `04922`. Os códigos de idade são `T,11,12,21,22,31,32,41,42,51,52,61,62,71,72,81,82,91,92`: total; 0–4 até 80–84; 85+. Assim, 25–39 corresponde a `32,41,42`; 65+ a `72,81,82,91,92`. São possibilidades de composição futura, não indicadores a entregar agora.

No fallback `0011719`, metadados retornaram geografia `04479`, idade `02910`, total `T` e códigos `01` a `19`: 0–4 até 85–89 e 90+. Códigos etários iguais entre indicadores NÃO significam idades iguais. Os limites vêm do metadado específico. A divisão anterior tem 3.092 freguesias na consulta de total; não confundir NUTS 2013 com uma comprovação isolada de equivalência de limites.

**Alternativas:** `0014584` só população total, útil como contraprova; BGRI exigiria exploração e agregação espacial desnecessárias para estas contagens. `0014632` sem filtros excedeu o limite da API.

## R2 — Evidência observada e limites

- `0014584`, `Dim1=T&Dim2=lvl@6&Dim3=T`: 3.259 registros em 2021, soma 10.343.066; conjunto de `geocod` coincide exatamente com a `dim_parish` local CAOP 2025 (zero códigos extras/faltantes). Isso comprova cobertura de códigos do total, não identidade espacial em todas as revisões nem detalhe etário nacional.
- `0014632`, `Dim1=S7A2021`, `Dim2=010103,0308FC,310101,420101`, `Dim3=T`, `Dim4=32,41,42,72,81,82,91,92`, `Dim5=T`: 32 observações em 2021, oito faixas por quatro códigos, incluindo código alfanumérico e as ilhas. Resposta válida com valores.
- `0011719`, `Dim1=S7A2021&Dim2=lvl@6&Dim3=T&Dim4=T`: 3.092 registros de total válidos.
- Houve timeout de 35–45 s em consultas amplas. `Dim1=2021` deu erro de código; `S7A2021` consta nos metadados. HTTP 200 pode conter `Sucesso.Falso`.
- `robots.txt` em `www.ine.pt` retornou HTTP 403. Não houve contorno, proxy ou alteração de identidade. Registrar a indisponibilidade; verificar termos e regras públicas antes da coleta operacional, parando caso exista proibição aplicável. O serviço JSON é descrito pelo próprio INE como de acesso livre e gratuito.
- Detalhe espacial da reexpressão oficial e regras de confidencialidade não foram provados pela sondagem. T001 exige verificá-los/documentá-los; falta de evidência não pode virar equivalência por igualdade de código ou população.

**Decisão:** consultas por categoria: 19 de dados + 1 de metadados no principal; 20 + 1 no fallback. 41 itens no catálogo nacional, sem paralelismo de requisições. O fallback é coletado para permitir avaliação completa e ensaio da correspondência; não tem precedência sobre observação oficial compatível.

**Alternativas:** consulta nacional multidimensional única rejeitada por limite de linhas/timeout; consulta por freguesia rejeitada por milhares de chamadas. Se mesmo por faixa houver limite comprovado, emendar o catálogo para lotes municipais com IDs estáveis, preservando as travas; não mudar estratégia silenciosamente.

## R3 — Persistência e seleção de entradas

**Decisão:** reutilizar `collect_datasets`, `LocalStorage`, manifest v2 e a canonicalização de `fingerprint_ine_response`; usar validação específica de censos e impressão digital que inclua também a configuração da consulta. Cada entrada inclui `dataset_snapshot`, `query_signature`, `reference_period=2021` e `geography_version` via `entry_extra` do fetcher. Congelar catálogo uma vez por chamada.

**Justificativa:** o validador municipal exige geocod de 7 caracteres; os censos observados usam DICOFRE de 6, inclusive letras. Não afrouxar o validador municipal. `latest_dataset_states` aceita sucessos de runs parciais: serve para deduplicar bruto, mas NÃO para montar uma entrada preparada coerente.

O build escolhe um único manifest censitário completo (changed/unchanged), resolve os bytes apontados por suas entradas, verifica hashes, assinatura e o vínculo de metadados e congela essa seleção. Se o run mais recente for partial/failed, reprova por padrão; `--run-id` permite selecionar explicitamente um run completo anterior. Nunca juntar estados recentes de execuções diferentes para mascarar a falha. Referências unchanged a brutos anteriores são permitidas pelo próprio manifest completo.

**Alternativas:** reutilizar `collect_ine` diretamente rejeitado por source_id e validação municipais; novo motor de ingestão rejeitado porque os colaboradores existentes já resolvem armazenamento, checksum e isolamento de falhas por item.

## R4 — Preparação e promoção

**Decisão:** Python normaliza e resolve a precedência territorial; dbt-duckdb fixa tipos e testa as saídas Parquet em candidato isolado. Reutilizar `promote_paths` apenas para os caminhos censitários. Relatórios são construídos no candidato antes da promoção, junto das tabelas; nada de escrever CSV depois de trocar as tabelas vigentes.

**Justificativa:** ADR-001 e ADR-002 já fixam camadas e motor. O projeto usa materialização external e env vars por feature. Não criar arquitetura alternativa nem alterar Bronze/Silver inteiros.

**Alternativas:** só Python sem dbt rejeitado por perder os quality gates do projeto; nova publicação Gold/site rejeitada pelo escopo aprovado.

## Fontes consultadas

- [Catálogo oficial 0014632 e CC BY 4.0](https://dados.gov.pt/pt/datasets/populacao-residente-n-o-0014632/).
- [Catálogo oficial quinquenal 0011719](https://dados.gov.pt/pt/datasets/687059028c1cd0da86631eca).
- [Metadados oficiais 0014632](https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp?varcd=0014632&lang=PT) e [0011719](https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp?varcd=0011719&lang=PT), obtidos por HTTP identificado; o navegador de pesquisa não conseguiu abrir todas as páginas do INE.
- [INE: apresentação da API de acesso livre](https://www.ine.pt/ine_novidades/semin/INEWS38/files/assets/common/downloads/publication.pdf).
- Context7: `/duckdb/duckdb-python` (Parquet), `/duckdb/dbt-duckdb` (external/materialização/fontes) e `/pytest-dev/pytest` (tmp_path/collect-only). A busca Context7 por API INE não encontrou documentação correspondente; usadas fontes oficiais acima, sem substituir por documentação de outro INE/país.


## Execução — gate T001 (2026-11-13)

A edição oficial INEWS65 (https://www.ine.pt/ine_novidades/semin/INEWS65/index.html) declara uso da informação estatística sob CC BY 4.0 com fonte identificada; o catálogo oficial de 0014632 confirma a licença. O metadado oficial 0014632 foi relido nesta execução: geografia 05723, descrição geografia 2025 e 19 categorias (total + 18 faixas). O metadado 0011719 preservado na pesquisa informa geografia 04479 e total + 19 faixas. A vinculação à CAOP é validada por códigos/municípios/versão e declaração oficial de geografia, não por igualdade de contagens. O método de reexpressão não foi divulgado nas evidências consultadas e fica registrado como not_disclosed_by_publisher; não se presume repartição espacial. Robots retornou novamente 403, sem regras recuperáveis; o serviço JSON é publicamente apresentado pelo INE como acesso livre, e não foi encontrada proibição aplicável. Coleta limitada, identificada e sem contorno, com atribuição obrigatória. Fonte real completa ainda não foi coletada nesta fase.


### Bloqueio operacional real — 2026-11-13

Suíte final: 399/399 verdes em421,27s; área censos:49/49 em31,24s; lint aprovado; travas001–006 íntegras. Coleta nacional por faixa resultou em timeouts reiterados. O processo foi interrompido após 9 tentativas HTTP registradas; bruto preservado e manifest parcial recuperado em `manifests/censos/20261113T224403345700Z-3d498ac9.json`. Não houve promoção censitária.

Pilotos no indicador0014632: quatro freguesias/total responderam em1,4s; lista128/256/512 códigos gerou erroPLSQL de buffer; lote16 freguesias com19 categorias retornou304 observações em1,5s, e lote32 retornou608 em0,9s. Uma fonte alternativa0014630 foi descartada por ter grupos amplos que não permitem25–39. A alternativa viável exige reabrir D2: lotes explícitos de32 freguesias com todas as categorias, preservando cada resposta original, com201 itens estimados (102 lotes2025 +97 lotes2013 +2 metadados) e novos testes de completude por lote. Decisão pendente do usuário; nenhuma mudança dessa estratégia foi aplicada.

### Emenda operacional aprovada

Após a evidência de timeouts, o usuário aprovou explicitamente reabrir D2 para lotes de32. O catálogo agora congela201 seleções:2 metadados +102 lotes2025 +97 lotes2013. As listas vieram dos dois metadados oficiais preservados no planejamento. Validador exige produto cartesiano exato por lote; preparo exige união exata de cada família.61 testes da área passaram; a revisão independente confirmou compatibilidade histórica e igualdade do universo2025. Prova nacional em execução; resultado deve ser consultado no Estado Atual do plano. O bloqueio relatado acima é histórico, não uma aprovação pendente.

### Prova real concluída após emenda D2 — 2026-11-13

Coleta inicial `20261113T231450079026Z-ddf26aad`:201 chamadas/201 respostas,200 changed e1 metadado unchanged,32.804.869 bytes referenciados,449,406s. Repetição `20261113T232234325869Z-00a1b4a4`:201/201 unchanged,201 chamadas,449.906s,nenhum novo raw. Ambos os manifests estão em `.data/manifests/censos/`;originais,hashes,consultas e revisões da primeira rodada foram conferidos após a segunda. Recibos e auditorias em `.data/receipts/censos-proof/`.

Build real aprovado:3.259 freguesias,308 municípios,19 categorias canônicas e61.921 observações próprias;0 herdadas,0 ausentes. Bronze123.761 linhas;população total2021 de10.343.066. Cobertura regional completa e18 códigos alfanuméricos preservados. Todas as observações têm fonte,licença,território,run e referências raw verificadas. Vinte e dois arquivos vizinhos permaneceram idênticos. dbt:4 modelos e21 testes aprovados. Relatórios: `.data/lake/silver/census_reports/`. Fonte INE,Censos2021,CC-BY-4.0. O método de reexpressão não foi divulgado pelo publicador nas evidências consultadas;essa limitação permanece registrada,sem estimativa do projeto.

Validação local: `uv run --locked python -m pytest -q --basetemp .data/tmp/censos-batches-full` →411 passed em571,46s;2 regressões adicionais (histórico completo41 itens e repetição por lotes) →2 passed em3,37s,fora da coleta inicial dessa suíte. Área censos →61 passed em32,12s antes dessas2 adições. `uv run --locked ruff check pipelines tests` aprovado. Seed/build de CLI em `.data/ci-censos-batches` aprovado;travas001–006 íntegras;revisão independente sem bug material. O CI remoto e seu scan de segredos seguem pendentes de commit/push/PR autorizado;nenhuma execução em nuvem ou publicação foi demonstrada. Não marcar Implementada/Convergida antes do gate restante.
