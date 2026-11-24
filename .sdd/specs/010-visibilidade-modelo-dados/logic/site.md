# Lógica: site do dbt docs com lineage entre builds (spec 010, US4)

## Por que um passo extra

O dbt trata `source('caop_silver','dim_municipality')` como um nó de **fonte**, sem ligação com o **modelo**
`dim_municipality` que a produz em outro build. No grafo padrão o autor veria o nó da fonte solto. O site só atende à
US4 se a aresta modelo → fonte aparecer.

## Sequência do comando `dbt_docs_site`

1. `dbt docs generate --empty-catalog` com `DBT_TARGET_PATH=<output>` e `CAOP_DUCKDB_PATH=<output>/never-used.duckdb`
   (o dbt-duckdb abre uma conexão mesmo com catálogo vazio; verificado em 2026-11-22). Gera `index.html`,
   `manifest.json` e um `catalog.json` vazio. Funciona sem lake, sem dados e sem rede.
2. Leia `<output>/manifest.json`, aplique `link_sources_to_models` e regrave.
3. Se `lake_root` tiver tabelas, leia o `catalog.json` vazio que o passo 1 gravou (ele traz `metadata` válido),
   preencha `nodes` com `lake_catalog_json` e regrave. Sem lake: deixe o catálogo vazio.
4. `--serve`: `dbt docs serve --host 127.0.0.1 --port <porta> --no-browser` (só localhost) com a mesma
   `DBT_TARGET_PATH`, e imprima a URL.

Nada disso toca `lake/`, `raw/` nem os builds promovidos (FR-021). A pasta de saída padrão é `.data/dbt-docs`, que
já está no `.gitignore` (`.data/`).

## `link_sources_to_models(manifest) -> dict`

- Copie o manifest (`copy.deepcopy`); nunca altere o dict de entrada.
- Para cada fonte `source.<pacote>.<fonte>.<tabela>` em `manifest["sources"]` cujo `<tabela>` seja o nome de um
  modelo `model.<pacote>.<tabela>`: `parent_map[<id da fonte>]` ganha o id do modelo e `child_map[<id do modelo>]`
  ganha o id da fonte (sem duplicar). Crie as chaves ausentes com lista vazia.
- Fonte sem modelo homônimo: não mexa.
- Sem efeito no `depends_on` dos nós: o grafo do dbt docs é montado a partir de `parent_map`/`child_map`.
  **Risco R-002**: se uma versão futura do dbt docs ignorar esses mapas, a aresta some; a verificação manual do
  `quickstart.md` cobre isso, e o fallback é anotar o modelo produtor na descrição da fonte.

## `lake_catalog_json(model, lake_root, generated_at) -> dict`

Estrutura do `catalog.json` do dbt (`https://schemas.getdbt.com/dbt/catalog/v1.json`), preenchida a partir dos
parquets reais:

```python
{
  "metadata": {...},            # copiado do catálogo vazio gerado pelo dbt; `generated_at` = argumento, em ISO 8601
  "nodes": {
    "model.caop_territory.dim_municipality": {
      "metadata": {"type": "BASE TABLE", "schema": "silver", "name": "dim_municipality", "database": None,
                   "comment": None, "owner": None},
      "columns": {"dico": {"type": "VARCHAR", "index": 1, "name": "dico", "comment": None}, ...},
      "stats": {"has_stats": {"id": "has_stats", "label": "Has Stats?", "value": False, "include": False,
                              "description": "Indicates whether there are statistics for this table"}},
      "unique_id": "model.caop_territory.dim_municipality",
    },
  },
  "sources": {},
  "errors": None,
}
```

- Uma entrada por modelo cujo `<lake_root>/<camada>/<nome>/data.parquet` exista. `type` e `index` vêm do `DESCRIBE`
  do DuckDB sobre o parquet (as colunas reais, **inclusive as não declaradas** no schema.yml).
- Modelo sem parquet: sem entrada (o site mostra só o que o manifest declara).
- Sem `lake_root` ou lake vazio: devolva o catálogo vazio (`nodes == {}`), sem erro.
- Nunca grave valores de dados; só nomes e tipos.
