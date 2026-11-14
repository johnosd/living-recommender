# Contrato da CLI CAOP

Superfície: `uv run --locked python -m pipelines.cli.collect_caop`.

## Coleta

`--local --root <diretorio>` usa armazenamento local, sem credenciais. `--s3 --bucket <bucket> [--prefix <prefixo>]` usa S3. `--force-check` repete a verificação/download, mas nunca transforma conteúdo idêntico em `changed`. Seleção de destino é exclusiva; valores padrão e mensagens de ajuda devem ser documentados na própria CLI. O comando lê `config/sources.yml`, recusa fonte ausente e produz `run_id` único.

Saída normal: resumo legível com `status`, versão, três regiões/arquivos e caminho/chave do manifest. `changed` e `unchanged` saem com código 0. Falha de rede, arquivo inválido ou destino sem permissão sai com código não zero e informa a etapa e o arquivo/campo relevante, sem expor segredo. Falha após iniciar a tentativa registra manifest `failed`; falha no pré-teste de destino pode ocorrer antes de qualquer gravação, conforme US3/AC2.

## Transformação

`uv run --locked python -m pipelines.cli.build_caop --local --root <diretorio>` seleciona o último manifest `changed` válido, prepara o staging, roda `dbt build` e as verificações geométricas. O comando relata `source_run_id`, versão CAOP e locais dos Parquets Bronze/Silver; falha de qualidade sai com código não zero e não promove dimensões novas. Não publica Gold/`published/vN`.

## Invariantes

O mesmo `run_id` nunca sobrescreve chaves existentes. A ordem de comparação é a do último manifest `changed` bem-sucedido, não a da última tentativa. Os três downloads são uma unidade lógica: nenhum manifest `changed` aponta para conjunto incompleto.
