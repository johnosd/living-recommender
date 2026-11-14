# Contrato das CLIs do Idealista manual

## Importação

`python -m pipelines.cli.import_idealista_snapshot --directory <pasta> --snapshot-month YYYY-MM [--local | --s3 --bucket <bucket>] [--root .data] [--catalog <yaml>] [--prefix <prefixo-s3>]`

- Pasta e mês são obrigatórios. `--bucket` e `--prefix` só valem com `--s3`.
- A origem é somente leitura; origem/destino local sobrepostos são rejeitados antes de criar o destino.
- A unidade de ingestão é todo o conjunto de JSON da pasta; subpastas e bytes são preservados.
- `changed` grava brutos sob novo run e um manifest completo. `unchanged` grava somente manifest de verificação, referenciando o run anterior do mesmo mês.
- Erro de validação grava manifest `failed` quando o destino é seguro e utilizável; ele não é lote vigente. Falha de gravação pode deixar raw órfão, nunca selecionado sem manifest `changed`.
- Saída: status, período, run, contagem de arquivos/ocorrências e chave do manifest; não imprime anúncios.

## Build

`python -m pipelines.cli.build_idealista [--local] [--root .data] --snapshot-month YYYY-MM`

- Exige dimensões CAOP locais e importação `changed` válida para o mês.
- Confere inventário, totais e fingerprint do manifest, além dos bytes/hashes de todos os arquivos.
- Escreve no candidato, executa testes dbt e confere os Parquet exportados antes de promover somente os três diretórios definidos no plano.
- Saída: período, ocorrências, IDs, duplicatas, municípios com amostra, regionais, conflitos, freguesias resolvidas/ausentes e diretório dos relatórios.
- Não acessa Idealista, não publica e não executa AWS.

## Códigos de saída

`0`: sucesso (`changed`/`unchanged` na importação, build aprovado).  
`1`: falha de importação/build.  
`2`: uso inválido dos argumentos (argparse).

API Python pública testada: `import_snapshot(catalog, *, storage, directory,
snapshot_month, run_id, imported_at_utc)`, `prepare_snapshot(root, output_dir, *,
snapshot_month, processed_at_utc, file_localities=None, parish_synonyms=None)` e
`build_idealista(root, *, snapshot_month)`. Dados retornados/gerados são descritos em `data-model.md`.
