# Data Model: visibilidade do modelo de dados (spec 010)

Não há tabela nova no lake nem mudança em modelo dbt (só `description`, `data_type` e `meta` nos `schema.yml`).
Este documento descreve (1) as estruturas em memória, (2) o arquivo DuckDB do catálogo e (3) o que muda nos `schema.yml`.

## 1. Estruturas em memória (`pipelines/modeldocs/model.py`)

Já criadas como stubs pelo `sdd-plan`: `Column`, `Table`, `Relationship`, `DataModel`, `ModelError`. Todas
`@dataclass(frozen=True)`. Campos e regras de preenchimento em `logic/documento.md` §1 e §2.

## 2. Catálogo DuckDB (`.data/catalog.duckdb`)

Um arquivo, gerado por `build_catalog`. Três tipos de objeto.

### 2.1 Views sobre o lake

| Objeto | Definição |
|---|---|
| `bronze.<tabela>`, `silver.<tabela>` | `CREATE VIEW ... AS SELECT * FROM read_parquet('<caminho absoluto>/<camada>/<tabela>/data.parquet')` |

- Só são tabelas os arquivos `<lake_root>/<camada>/<tabela>/data.parquet` das camadas `bronze` e `silver`.
- O caminho é absoluto, calculado na geração. Mover `.data/` exige gerar de novo (R-004).
- A view lê o parquet atual a cada consulta: depois de um build, o catálogo já reflete o dado novo (FR-013).
- Nada é copiado, então o arquivo fica pequeno (SC-005).

### 2.2 Tabelas de metadados (schema `meta`)

Gravadas na geração; refletem o manifest do dbt e o lake naquele instante.

`meta.tables`

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `layer` | VARCHAR | `bronze`, `silver` ou `n/d` |
| `table_name` | VARCHAR | nome da tabela |
| `domain` | VARCHAR | primeira tag do modelo, ou `n/d` |
| `kind` | VARCHAR | `principal` ou `relatorio`; `n/d` para tabela sem modelo |
| `status` | VARCHAR | `ok`, `nao_construida` (modelo sem parquet) ou `sem_modelo` (parquet sem modelo) |
| `description` | VARCHAR | descrição do modelo ou NULL |
| `source_ids` | VARCHAR[] | `meta.source_ids` do modelo |
| `row_count` | BIGINT | contagem no instante da geração; NULL se `status != ok` |

`meta.columns`

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `layer`, `table_name` | VARCHAR | chave da tabela |
| `column_name` | VARCHAR | coluna |
| `position` | INTEGER | posição real no parquet; NULL se só declarada |
| `type_actual` | VARCHAR | tipo do DuckDB no parquet; NULL se a tabela não foi construída |
| `type_declared` | VARCHAR | `data_type` do schema.yml ou NULL |
| `declared` | BOOLEAN | a coluna existe no schema.yml |
| `in_lake` | BOOLEAN | a coluna existe no parquet |
| `description` | VARCHAR | descrição ou NULL |
| `tests` | VARCHAR[] | testes dbt da coluna |

Uma linha por coluna da **união** de declaradas e reais. É daqui que sai a checagem de completude do US3:
`declared = false` (coluna real sem declaração) e `type_declared <> type_actual` são as lacunas.

`meta.relationships`: `from_table`, `from_column`, `to_table`, `to_column`, `origin_file`.

### 2.3 Inventário do `raw/` (`meta.raw_runs`)

Uma linha por arquivo `<manifests_root>/<source_id>/<run_id>.json` legível.

| Coluna | Origem |
|---|---|
| `source_id`, `run_id`, `status` | campos do manifest (`status` NULL se ausente) |
| `collected_at_utc` | primeiro não nulo entre `collected_at_utc`, `checked_at_utc`, `imported_at_utc` |
| `license_id`, `reference_period` | campos do manifest, NULL se ausentes |
| `checksums` | VARCHAR[] com **todo** valor de chave `sha256` encontrado em qualquer profundidade do JSON (`files[]`, `datasets[]`, `entries[].files[]`, `snapshot_sha256`) |
| `manifest_file` | caminho do manifest relativo a `manifests_root`, com `/` |

Hoje são 43 manifests de 9 fontes, com `status` em `changed`, `unchanged` e `partial`. Manifest ilegível (JSON
inválido) não derruba a geração: conta como ignorado e aparece no resumo do comando.

## 3. Mudanças nos `schema.yml` (US3)

Para as 18 tabelas principais, em `analytics/dbt/models/<domínio>/schema.yml`:

```yaml
- name: stg_municipality_pole_distance
  description: >            # já existe
  meta:
    source_ids: [caop, google_distances]   # novo: fontes de config/sources.yml que alimentam a tabela
  columns:
    - name: km
      description: Distância em quilômetros; só existe em status ok.   # novo
      data_type: double                                                # novo, igual ao tipo real do parquet
      data_tests: [...]                                                # existente, não mexer
```

- Declarar **todas** as colunas reais da tabela, na ordem do parquet.
- `data_type` em minúsculas, igual ao `type_actual` do DuckDB em minúsculas (`varchar`, `double`, `date`, `boolean`,
  `bigint`, `timestamp`...). Sem `contract: enforced`: é só documentação.
- Não alterar os `data_tests` existentes nem os `.sql`.
- Relatórios (`rpt_*`, `*_coverage`) ficam como estão, salvo as 3 tabelas da Wikipedia sem descrição de tabela.
