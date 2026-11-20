# Contrato público — Wikipedia

## Comandos locais a implementar

```powershell
uv run --locked python -m pipelines.cli.collect_wikipedia --local --root .data
uv run --locked python -m pipelines.cli.collect_wikipedia --local --root .data --max-municipalities 5
uv run --locked python -m pipelines.cli.collect_wikipedia --local --root .data --resume-run-id <run>
uv run --locked python -m pipelines.cli.build_wikipedia --local --root .data
uv run --locked python -m pipelines.cli.build_wikipedia --local --root .data --run-id <run-completo>
```

Coletor: `--catalog <yaml>`, `--associations <csv>`, `--silver <diretório>` e
`--contact <URL-ou-email>` opcionais quando o catálogo já tem esses valores.
Sem contato identificável, falha antes da rede. Default catalog/configuração
do projeto; root `.data`; Silver `root/lake/silver`. Não expor `--s3` neste
escopo local. Função pública usa storage injetável, sem tornar AWS um aceite.

Default reconsulta todos os municípios, respeitando `--max-municipalities`.
Limite é lote, não sucesso nacional: não tentados ficam pending, saída 2.
Resume cria um run novo de mesmo cycle_id, usando os snapshots do anterior;
mudança no catálogo/dimensão/correspondência exige nova execução padrão.
Resume não combina com max-municipalities nesta primeira versão; evitar
ambiguidade de qual conjunto já foi concluído. Ctrl+C grava progresso e pendências.

Coleta: saída 0 para ciclo completo changed/unchanged, inclusive ausência
justificada; 1 para configuração/identidade/falha permanente; 2 para interrupção,
limite de lote ou espera da fonte que exige retomada. Falha permanente vence 2.
Build: 0 para promoted/unchanged com prontidão válida; 1 se entrada, integridade,
dependência, lock, prontidão, dbt ou promoção reprovou. Manutenção após commit
verificado é aviso, não falsa falha de dados. Não existe `--force` para ignorar gates.

O coletor imprime run/cycle, changed/unchanged/absent/failed/pending, caminho
do manifest e relatório. Build imprime run selecionado, última tentativa,
artigos válidos, ausências e bloqueadores, resultado de promoção e relatórios.

## Interface injetável de coleta

```python
collect_wikipedia(catalog, *, municipalities, associations, territory_hash,
                  storage, fetcher, run_id, collected_at_utc, work_dir,
                  resume_manifest=None, max_municipalities=None) -> dict
```

`municipalities`: lista DICO, official_name, versão CAOP. `territory_hash` é
SHA-256 do arquivo da dimensão lido pela CLI. Associações conforme data-model.
Não alterar argumentos do chamador. Snapshots deep-copy feitos uma vez.

`fetcher(association) -> {"metadata": bytes, "content": bytes}` fornece
respostas oficiais intactas; metadados usam `query.pages[]`, corpo `parse`.
O coletor valida antes de escrever e não usa `fetcher` para inferir ausência.
Resposta de erro/falha vira entry failed, sem apagar outros sucessos.
Não mockar collect_wikipedia em seus próprios contratos.

Retorno: `status`, `manifest_key`, `entries`, `run_id`, `cycle_id`.
Cada artigo aceito tem page_id, revision_id, scope, association_hash,
permanent_url e files de roles metadata/content, além dos campos do modelo.
Manifest deve ter source_id, license_id, language, territory_hash e
associations_snapshot. Não mudar o schema v2 das outras fontes.

## Interface offline de texto

```python
extract_article(metadata: dict, parsed: dict) -> dict
```

Recebe JSON decodificado, sem modificá-lo. Retorna `introduction`, `full_text`,
`sections`, `blocks`, `page_id`, `revision_id`, `wikidata_id`, `english_url`.
Normaliza tocdata atual e sections legado; comportamento detalhado em
`logic/coleta-e-texto.md`. Erro de estrutura/revisão é `WikipediaError`,
subclasse ValueError, nunca artigo vazio aceito silenciosamente.

## Interface de prontidão

```python
assess_wikipedia_coverage(municipalities, entries, *, input_errors=()) -> dict
```

Retorna `ready`, `blockers` (códigos legíveis), `expected_municipalities`,
`counts` (somente estados presentes), e rows do relatório quando necessário.
`valid` exige identity_validated e extraction_complete verdadeiros + revisão;
`absent` exige reason e ausência curada com evidence_url/note/reviewer/data.
Faltante, duplicata, código extra, falha atual, identidade não validada,
extração incompleta e input_errors reprovam. previous_valid_revision_id
não converte failed em valid. A mera ausência de introdução/tema não reprova
se for confirmada no artigo e a extração estiver completa.

## HTTP de produção

Somente HTTPS/host pt.wikipedia.org/path /w/api.php, GET query/parse com
parâmetros codificados via httpx; sem seguir links de artigos ou mídia.
Usar `query` por pageids (título apenas para curadoria/redirecionamento),
`prop=info|revisions|pageprops|langlinks`, `rvprop=ids|timestamp`,
`inprop=url`, `lllang=en`, `llprop=url`, `redirects=1`, formatversion 2.
Tratar paginação/continuação antes de declarar os metadados completos.
Não pedir nomes de usuários, comentários de edições, imagens ou estatísticas.

Parse: `oldid` fixado e `prop=text|tocdata|revid|properties|links|externallinks`.
Validar namespace 0, ID esperado, revisão e QID quando declarado; metadados
atuais e evidência de escopo precisam conferir. Registrar redirects; destino
fora da identidade curada fica pending_review/failed, sem autoaprovar.

Timeout 30 s, máximo 3 tentativas por request, série com intervalo mínimo
1 s, maxlag 5 e backoff 2,4 s. HTTP 429/503 e erro maxlag HTTP200 respeitam
Retry-After (segundos ou data). Se espera exigida exceder 60 s, salvar
pending/retry_at e encerrar com 2; nunca truncar o prazo e tentar antes.
403 e bloqueios permanentes encerram chamadas desse run, registrando o
atual failed e demais pending. Repetição é decisão posterior, sem troca de
IP, identidade ou endpoint. Tratamento específico vive em wikipedia/fetch.py.
