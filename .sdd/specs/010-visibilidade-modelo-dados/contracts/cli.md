# Contrato das CLIs (spec 010)

Três comandos, um por artefato (SC-009). Todos rodam com `uv run --locked python -m pipelines.cli.<nome>`, a partir da
raiz do repositório, sem rede e sem chave.

## 1. `model_docs` — documento (A)

```
python -m pipelines.cli.model_docs [--check] [--output .docs/modelo_de_dados.md]
                                   [--manifest PATH] [--sources config/sources.yml]
```

| Opção | Efeito |
|---|---|
| (nenhuma) | roda `dbt parse`, gera o documento e grava em `--output` (LF, UTF-8) |
| `--check` | gera em memória e compara com `--output` ignorando `\r\n`; **não grava** |
| `--manifest PATH` | usa um `manifest.json` já pronto em vez de rodar `dbt parse` (usado pelos testes) |
| `--sources` | caminho do `config/sources.yml` |

Saída: uma linha com o número de tabelas e relacionamentos (`Modelo de dados: 25 tabelas, 15 relacionamentos -> ...`).
Códigos: `0` ok; `1` documento ausente ou defasado em `--check`, ou `ModelError` (a mensagem cita arquivo, modelo e
alvo); `2` uso, `dbt` ausente ou falha do `dbt parse`.

Mensagem de defasagem (stdout ou stderr, o teste lê os dois):
`.docs/modelo_de_dados.md está desatualizado. Rode: uv run --locked python -m pipelines.cli.model_docs`.

## 2. `lake_catalog` — catálogo DuckDB (B)

```
python -m pipelines.cli.lake_catalog [--root .data] [--output .data/catalog.duckdb] [--manifest PATH]
```

- `--root`: raiz que contém `lake/` e `manifests/` (mesma convenção das CLIs de build).
- `--manifest PATH`: manifest do dbt já pronto; sem ele, roda `dbt parse`.
- Grava em um arquivo temporário ao lado de `--output` e troca por `os.replace` ao final. Se a troca falhar porque
  um cliente SQL (DBeaver, DuckDB UI) mantém o arquivo aberto, termina com código `1` e a mensagem
  `feche o cliente SQL que está usando <arquivo> e rode de novo`, sem apagar o catálogo anterior.
- Saída (exemplo): tabelas `ok`, `nao_construida`, `sem_modelo`, entradas ignoradas (CSV e pastas de relatório do
  lake), manifests lidos e ignorados, tamanho do arquivo. Termina com código `0` mesmo com tabelas não construídas.
- Nunca abre arquivo do lake ou dos manifests para escrita.

## 3. `dbt_docs_site` — site do dbt docs (C)

```
python -m pipelines.cli.dbt_docs_site [--root .data] [--output .data/dbt-docs] [--serve] [--port 8741]
```

- Sequência em `logic/site.md`. Sem `--serve`: gera e imprime o caminho do `index.html`.
- `--serve`: serve só em `127.0.0.1` e imprime a URL; `Ctrl+C` encerra.
- Códigos: `0` ok; `1` `ModelError` ou falha do dbt; `2` uso.
