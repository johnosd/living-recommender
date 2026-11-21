# Data Model — Wikipedia

Modelo local versionado; schema `wikipedia-parquet-2` inclui official_name na cobertura.
Não é contrato de publicação. Tipos Parquet explícitos,
inclusive para tabelas vazias. DICO é string de quatro caracteres, nunca inteiro.

## Catálogo e correspondências

`config/sources.yml`: fonte `wikipedia`, método `api_json`, idioma `pt`,
frequência pretendida mensal, universo 308, `CC-BY-SA-4.0`, URL/atribuição,
endpoint, identidade/contato, intervalo mínimo 1 s, timeout 30 s,
até 3 tentativas, backoff inicial 2 s e `maxlag=5`. Registrar a exceção
`008-R-001-authorized-2026-11-20`. Validação própria em `wikipedia/catalog.py`;
catálogo alternativo explícito pode definir universo menor para fixtures,
sem condicionamento da implementação a ambiente de teste.

`config/wikipedia_articles.csv`: uma linha por DICO, campos:

| Campo | Regra |
| --- | --- |
| dico | Único, corresponde à dimensão selecionada |
| status | `validated`, `absent` ou `pending_review` |
| page_id, title | Obrigatórios em validated; page ID é a identidade principal |
| expected_wikidata_id | Opcional; quando declarado deve conferir |
| scope | `municipality`, `municipality_and_seat`; `seat_only`/`other` não aceitos |
| evidence_quote | Trecho curto da evidência de identidade/abrangência, conferido no conteúdo atual |
| evidence_url, evidence_note | Origem consultada e justificativa; ausência exige busca/candidatos documentados |
| reviewed_at_utc, reviewer | Curadoria identificada, sem inventar revisão/data da fonte |

Título/nome, QID e existência isolados não validam identidade. Curadoria deve
resolver homônimos com distrito/ilha e comprovar abrangência; página só da sede
fica pendente. Valores ausentes não viram zero. CSV não contém textos completos.

## Manifest próprio

`manifests/wikipedia/<run_id>.json`, `schema_version=1`, `source_id=wikipedia`.
Não passa pelo resolvedor genérico v2. Campos do envelope:

`run_id`, `cycle_id`, `parent_run_id`, `checked_at_utc`, `status`, `language`,
`license_id`, `license_url`, `attribution`, `territory_hash`, `territory_snapshot`,
`catalog_snapshot`, `associations_snapshot`, `association_set_hash`, `entries`.

Snapshots são deep copies congelados antes da primeira chamada, com hashing
canônico documentado. `catalog_snapshot` contém a configuração da fonte
wikipedia resolvida (sem o wrapper sources). Hash físico da dimensão e lista DICO/nome/versão preservam
o contexto; a CLI confere dependências antes/depois. Associações mudadas não
podem ser usadas no meio de uma invocação ou de uma retomada do mesmo ciclo.

Cada entry inclui `dico`, `status`, `association_hash`, `scope`, `page_id`,
`canonical_title`, `requested_title`, cadeia de redirecionamentos, `revision_id`,
`revision_at_utc`, `permanent_url`, `wikidata_id`, `english_url`, `fingerprint`,
`files`, `verified_in_run`, `checked_at_utc`, `last_changed_run_id`, `reason`,
`error`, `absence_evidence` e referência opcional à versão válida anterior.

Estados por município: `changed`, `unchanged`, `absent`, `failed`, `pending`.
Identidade não resolvida é `failed` com código `identity_pending`, não ausência.
Um manifest parcial representa todos os DICO, inclusive os não tentados.
Envelope: `failed` se nenhuma unidade foi concluída com sucesso; `partial` se
há failed/pending e algum resultado concluído; `changed` se completo com nova
origem/associação/ausência revisada; `unchanged` se completo e equivalente.
Ausências justificadas são resultados concluídos, não brutos textuais.

`files`: role `metadata`/`content`, chave, SHA-256, bytes, run de origem e
`raw_collected_at_utc`; a nova `checked_at_utc` não substitui esse horário.
Brutos novos em `raw/source=wikipedia/dico=<dico>/run_id=<run>/<role>.json`.
Cada role byte a byte igual à referência anterior é reutilizado, mesmo se
outro role ou a associação mudou. Resultado equivalente não duplica arquivos.
Respostas inválidas podem ficar em diagnóstico privado, nunca como artigo válido.

## Estado, ciclo e conteúdo

Estado de conteúdo e última tentativa são índices diferentes derivados dos
manifests. Nova execução padrão verifica a fonte para todos; `--resume-run-id`
retoma só pendentes/falhas de um ciclo fixado e mantém a data de verificação dos
sucessos anteriores. Manifest novo sempre recebe run ID próprio e cobre o universo.
Run IDs são validados e nunca viram caminhos sem validação.

Fingerprint de conteúdo usa identidade/revisão, corpo parse normalizado,
metadados relevantes e associação/território. Hashes físicos provam os bytes;
timestamps da tentativa e avisos operacionais não provocam falsa mudança.
Chaves ignoradas na canonização precisam de lista explícita e testes. Não
ignorar HTML, idioma, revisão, referências ou metadado editorial como se fossem
voláteis. Nova renderização da mesma revisão pode ser changed.

## Saídas preparadas e dbt

| Modelo/tag `wikipedia` | Destino | Conteúdo/chave |
| --- | --- | --- |
| wikipedia_revision | `lake/bronze/wikipedia_revision/data.parquet` | Um artigo aceito por DICO: identidade/revisão/roles raw, fingerprints e contexto; sem HTML duplicado |
| wikipedia_article | `lake/silver/wikipedia_article/data.parquet` | DICO, page ID, revisão, scope, introdução, full_text, QID/inglês, licença/atribuição, origem e processing_signature |
| wikipedia_section | `lake/silver/wikipedia_section/data.parquet` | `(dico, section_id)`, pai, ordem, título original, nível, anchor, vazio explícito; seção sintética lead |
| wikipedia_block | `lake/silver/wikipedia_block/data.parquet` | `(dico, block_id)`, section_id, pai, ordem, kind, text e links_json; containers sem duplicação de texto |
| wikipedia_coverage | `lake/silver/wikipedia_coverage/data.parquet` | Uma linha por DICO, official_name da dimensão congelada, status de preparo, identidade, motivo, contagens, disponibilidade de introdução/temas e origem |

Essas cinco tabelas recebem tipos, chaves e relacionamentos dbt; nenhuma
unidade herda texto de vizinha. Estados da cobertura: `valid`, `absent`,
`failed`, `pending`, `identity_pending`, `extraction_failed`.

`extract_article(metadata, parsed)` retorna introdução, full_text, sections,
blocks e metadados; não usa rede. Blocks têm IDs únicos, ordem estável,
section_id e parent_block_id. Links incluem href original, texto e tipo;
esquemas perigosos não viram links navegáveis, mas a origem permanece no bruto.
Referências de fragmento são mantidas; resolve-se URL relativa em campo adicional
sem substituir href original. Conteúdo não será inserido como HTML executável.

Relatórios de candidato/base em `lake/silver/wikipedia_reports/`:
`coverage.csv`, `sections.csv`, `readiness.json`, `summary.json`, `dbt_run_results.json`.
CSV `;`, UTF-8 BOM. Ausência de tema é aferida por título de seção, sem
classificador semântico. Temas/títulos são inventariados dinamicamente.

Relatórios de tentativas atuais ficam separados em
`reports/wikipedia/collection/<run>/` e de build em
`reports/wikipedia/build/<build_id>/`. Assim o build `unchanged` não substitui
o lake apenas para atualizar um horário; a tentativa recente continua visível.
O relatório da coleta usa estados brutos e não declara extração pronta antes
do build; a prontidão textual só é calculada sobre a preparação validada.

Processing signature: fingerprints editoriais + hashes dimensão/associações
+ versões do extrator/schema + versão de parser resolvida. Exclui horário de
checagem, build ID e nome do candidato. Somente assinatura equivalente e
integridade verificada permitem pular promoção. Falha de nova tentativa nunca
some pelo reaproveitamento de uma versão antiga.

## Seleção, prontidão e promoção

Default: examinar a última tentativa; se parcial/falhou, gerar diagnóstico e
reprovar a promoção. `--run-id` permite selecionar conscientemente um run
anterior completo; informar seleção antiga e última tentativa, sem declarar
que resolveu a falha atual. Nunca montar implicitamente um mosaico de fontes.

Construção offline em `.build/wikipedia/<build_id>/`, lock exclusivo com
PID/build ID e hashes das dependências. dbt isolado com seleção da tag,
exportação/qualidade verificadas antes de promover somente os seis caminhos
Wikipedia (cinco tabelas + relatórios). Journal por transação lista destinos,
backups e hashes: recuperação concluída ou rollback antes de aceitar outro build.
`promote_paths` sozinho não garante transação contra morte do processo.

O arquivo persistente `.locks/wikipedia.guard` recebe exclusão não bloqueante
do SO (msvcrt no Windows; flock no Linux). Ele protege também a recuperação e
a liberação de `.locks/wikipedia.json`, que mantém PID/token para diagnóstico.
O SO libera a exclusão quando o processo morre; nunca apagar o guard, pois
outros processos podem manter o arquivo aberto. Journal continua separado.

Destinos/junctions/candidatos precisam permanecer sob a raiz autorizada.
Falha de limpeza após commit só é manutenção se todos os hashes promoveram;
caso contrário é falha com vigente anterior restaurada/recoverable. Não apagar
raw, manifests, backups não verificados nem diretórios de outras fontes.
