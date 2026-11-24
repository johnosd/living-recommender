# Modelo de dados: tabelas, relacionamentos e como consultá-los

Este guia mostra como enxergar o que existe no lake: o documento gerado, o catálogo DuckDB e o site do dbt. Os três
partem dos `schema.yml` do dbt (`analytics/dbt/models/*/schema.yml`), que são a fonte única. A especificação está em
[.sdd/specs/010-visibilidade-modelo-dados](../../.sdd/specs/010-visibilidade-modelo-dados/spec.md).

Todos os comandos rodam na raiz do repositório, sem rede e sem chave, depois de `uv sync --locked`.

## Documento: `.docs/modelo_de_dados.md`

Diagrama de relacionamentos (Mermaid), dicionário de dados de cada tabela e a lista do que ainda falta descrever.
O GitHub e o VS Code (com a extensão do Mermaid) mostram o diagrama.

```powershell
uv run --locked python -m pipelines.cli.model_docs           # gera .docs/modelo_de_dados.md
uv run --locked python -m pipelines.cli.model_docs --check   # só confere; sai com 1 se estiver defasado
```

- Gere de novo sempre que mudar um `schema.yml` (descrição, tipo, teste ou relacionamento) e commite o resultado.
- O documento não tem data, caminho local nem valor de dado, então regerar sem mudança não altera o arquivo.
- Em Windows o Git pode converter o arquivo para CRLF; o `--check` ignora essa diferença.

### Quando o CI acusar defasagem

O passo `Check data model document` do CI falha com a mensagem
`.docs/modelo_de_dados.md está desatualizado. Rode: uv run --locked python -m pipelines.cli.model_docs`.
Rode o comando, confira o `git diff` do documento (deve refletir só o que você mudou) e commite.

### Quando o comando falha com "Modelo de dados inconsistente"

Um teste `relationships` aponta para uma tabela que não é modelo do dbt. A mensagem diz o arquivo yml, o modelo e o
destino; corrija o `to:` do teste ou crie o modelo. O documento nunca é gerado pela metade.

### Como ler as lacunas

- **Sem descrição**: tabelas e colunas declaradas sem texto. Nada é inventado: sem evidência, a lacuna fica visível.
- **Chaves territoriais sem relacionamento declarado**: colunas `dico`/`dicofre` que não têm teste `relationships`
  nem são a chave da própria tabela.
- Só aparecem as colunas **declaradas** no `schema.yml`; as colunas reais do lake estão no catálogo
  (`meta.columns`) e no site do dbt.

## Catálogo DuckDB: `.data/catalog.duckdb`

Um arquivo único para consultar todas as tabelas do lake (bronze e silver) com SQL, sem copiar dado: as views leem os
parquets atuais a cada consulta. Fica em `.data/`, fora do Git.

```powershell
uv run --locked python -m pipelines.cli.lake_catalog --root .data
```

O resumo mostra quantas tabelas estão `ok`, `não construídas` (modelo sem parquet) e `sem modelo` (parquet sem modelo
no dbt), as entradas do lake que não são tabelas (CSV e pastas de relatório) e os manifests lidos.

### O que tem dentro

| Schema | Conteúdo |
| --- | --- |
| `bronze`, `silver` | uma view por tabela do lake, com o mesmo nome do modelo dbt |
| `meta.tables` | camada, tabela, domínio, tipo (`principal`/`relatorio`), `status`, descrição, fontes e `row_count` |
| `meta.columns` | união das colunas declaradas no `schema.yml` e das reais do parquet, com `type_actual`, `type_declared`, `declared`, `in_lake`, descrição e testes |
| `meta.relationships` | os relacionamentos declarados (testes `relationships` do dbt) |
| `meta.raw_runs` | inventário do `raw/`: uma linha por coleta (manifest) com fonte, data, licença e checksums |

`row_count` é a contagem no instante da geração; as views sempre refletem o dado atual.

### Consultas de exemplo

```sql
-- o que existe
select layer, table_name, status, row_count from meta.tables order by 1, 2;

-- cruzar duas fontes (sem configurar nada)
select d.official_name, count(*) as observacoes
from bronze.stg_observation o join silver.dim_municipality d using (dico)
group by 1 order by 2 desc limit 10;

-- colunas reais que o schema.yml ainda não declara, ou com tipo diferente do declarado
select layer, table_name, column_name, type_actual, type_declared
from meta.columns
where in_lake and (not declared or lower(type_actual) <> lower(type_declared))
order by 1, 2, column_name;

-- coletas do raw, da mais recente para a mais antiga
select source_id, run_id, status, collected_at_utc from meta.raw_runs order by collected_at_utc desc nulls last;
```

### Como abrir

**DuckDB UI** (verificado com duckdb 2.0.0). A UI vive enquanto a sessão estiver aberta; a primeira execução baixa a
extensão `ui` e por isso precisa de rede:

```powershell
uv run --locked python -c "import duckdb; c = duckdb.connect('.data/catalog.duckdb', read_only=True); c.execute('CALL start_ui()'); input('UI em http://localhost:4213 - Enter para encerrar')"
```

Abra `http://localhost:4213`; o catálogo aparece como um banco anexado na lista da esquerda. O comando `duckdb -ui` só serve se o
CLI do DuckDB estiver instalado (não é dependência do projeto).

**Terminal (verificado).** Sem interface, direto no PowerShell. O `PYTHONUTF8=1` evita erro de acentos na tabela:

```powershell
$env:PYTHONUTF8 = "1"
uv run --locked python -c "import duckdb; duckdb.connect('.data/catalog.duckdb', read_only=True).sql('select * from silver.dim_municipality limit 20').show(max_rows=20)"
```

Troque o SQL entre aspas simples por qualquer consulta dos exemplos acima.

**Se a UI mostrar "Failed to resolve app state ... `_duckdb_ui.main.current_notebook_id`"**: a UI não conseguiu criar o estado
interno dela (seus notebooks). Não foi possível reproduzir esse erro fora do navegador, então a causa não está confirmada.
Feche a UI anterior (`Ctrl+C` no terminal que a iniciou; "UI already running in a different DuckDB instance" indica
que ainda há uma aberta) e use o terminal ou o DBeaver, que não dependem dela.

**DBeaver**: nova conexão, driver **DuckDB**, caminho do arquivo `.data/catalog.duckdb` (use o caminho absoluto na sua
máquina). Marque a conexão como somente leitura.

O script [`.docs/sql/catalogo_tabelas.sql`](../sql/catalogo_tabelas.sql) lista todas as tabelas, relacionamentos, colunas e fontes, e traz uma amostra de 10 linhas de cada tabela. No DBeaver, abra o arquivo (*File > Open File*) e execute com `Alt+X`.

### Cuidados

- **Feche o cliente antes de regenerar.** No Windows o arquivo aberto no DBeaver ou na UI não pode ser trocado. O
  comando termina com código 1, mostra "Feche o cliente SQL que está usando ..." e mantém o catálogo anterior.
- **Gere de novo se mover `.data/`**: as views guardam o caminho absoluto dos parquets.
- O catálogo é só leitura: o comando nunca escreve em `raw/`, `lake/` nem `manifests/`.
- Tabelas `não construídas` não têm view; construa a fonte (`build_*`) e gere o catálogo de novo.

## Site do dbt: lineage e catálogo navegável

O site do `dbt docs` mostra os modelos, as colunas com descrição e o grafo de dependências. Como cada fonte é
construída num build isolado, o dbt não liga a fonte `caop_silver.dim_municipality` ao modelo `dim_municipality`; o
comando faz essa ligação no manifest do site para o grafo mostrar quem depende de quem. Ele também desenha uma aresta
para cada relacionamento declarado (teste `relationships`), porque vários modelos leem o parquet de outro build direto,
sem `ref` nem `source` (por exemplo, `stg_municipality_pole_distance` → `dim_municipality`). Essas arestas mostram
relacionamentos declarados, não dependências de SQL. Se houver lake, o catálogo do
site traz também as colunas reais de cada tabela, inclusive as ainda não declaradas.

```powershell
uv run --locked python -m pipelines.cli.dbt_docs_site --root .data          # gera .data/dbt-docs/
uv run --locked python -m pipelines.cli.dbt_docs_site --root .data --serve  # gera e serve em http://127.0.0.1:8741
```

- O site **é local e não é publicado**. O `--serve` escuta só em `127.0.0.1`; `Ctrl+C` encerra. Use `--port` para
  trocar a porta; a padrão é 8741 porque a 8080 costuma estar com Docker ou WSL. Abra exatamente
  `http://127.0.0.1:8741`: `localhost` pode cair em outro programa (IPv6 `::1`). Se a porta estiver ocupada, o
  comando avisa e não sobe.
- Para achar o grafo de uma tabela: abra o modelo na lista da esquerda (`bronze`/`silver` ou pelo nome) e clique no
  ícone de grafo no canto inferior direito da página. Em `dim_municipality` devem aparecer, ligados ao modelo, a fonte
  `caop_silver.dim_municipality` e os modelos que dependem dela (mobilidade, clima, Wikipedia e outros).
- Funciona sem lake e sem rede; sem lake, o catálogo do site fica vazio e só valem os dados do `schema.yml`.
- O comando só escreve dentro de `--output` (padrão `.data/dbt-docs`); não toca `raw/`, `lake/` nem `.data/ci`.
- Gere de novo depois de mudar um `schema.yml`.
