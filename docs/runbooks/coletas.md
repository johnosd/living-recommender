# Coletas de dados

Este guia descreve a coleta da CAOP (local ou em S3), a construção das dimensões territoriais e como visualizar os resultados. O contexto está na [spec de ingestão CAOP](../../sdd/specs/001-ingestao-caop/spec.md).

## Pré-requisitos

- Abrir o PowerShell na raiz do repositório.
- Ter `uv` disponível. O projeto usa Python 3.12, indicado em `.python-version`.
- Ter acesso à internet para a coleta real da [DGT](https://www.dgterritorio.gov.pt/atividades/cartografia/cartografia-tematica/caop). O modo local não precisa de credenciais AWS.

Instale as dependências fixadas no lockfile uma vez:

```powershell
uv sync --locked
```

As URLs, a versão e a licença da fonte ficam em [config/sources.yml](../../config/sources.yml). Confira esse catálogo quando a DGT publicar uma nova edição.

## Coletar a CAOP localmente

Na raiz do repositório, execute:

```powershell
uv run --locked python -m pipelines.cli.collect_caop --local --root .data
```

O comando baixa os ZIPs oficiais de Continente, Açores e Madeira, valida os GeoPackages e compara o SHA-256 de cada arquivo com a última coleta `changed`. O download não carrega os arquivos inteiros na memória. A CLI imprime o status, o `run_id`, os três arquivos e a chave do manifest.

`--local` é o destino padrão; `--root .data` também é o padrão. Para escolher outra pasta local, troque o valor de `--root`. Por exemplo:

```powershell
uv run --locked python -m pipelines.cli.collect_caop --local --root .data/caop-teste
```

É possível passar `--force-check`. Na implementação atual, toda execução já baixa e verifica os três arquivos; essa opção não força um novo `changed` quando os checksums continuam iguais.

## Coletar para um bucket S3

O mesmo comando grava no S3 com as **mesmas chaves** do modo local (`raw/…` e `manifests/caop/…`):

```powershell
uv run --locked python -m pipelines.cli.collect_caop --s3 --bucket <bucket> [--prefix <prefixo>]
```

- `--local` e `--s3` são exclusivos, e `--bucket`/`--prefix` só valem com `--s3`. Com `--prefix ambiente/dev`, todas as chaves ficam sob `ambiente/dev/`.
- As credenciais vêm só da cadeia padrão da AWS (variáveis de ambiente, perfil ou papel IAM). Nenhuma é lida de arquivo do repositório. O modo local continua sem exigir credenciais.
- Antes de baixar qualquer ZIP, a CLI grava e apaga uma chave de prova (`.probe/…`). Se o bucket não existir ou não aceitar escrita, o comando falha logo, com `destino sem permissão ou inacessível`, sem baixar nada e sem criar manifest.
- A escrita é condicional (`IfNoneMatch`): o S3 recusa gravar sobre uma chave que já existe, como o `os.link` do modo local.
- O S3 não grava três objetos de forma atômica. Se a falha for capturada, a CLI apaga os arquivos do run e registra um manifest `failed`. Se o processo for morto no meio, podem sobrar ZIPs sem manifest; nenhum leitor os trata como coleta válida, e só o manifest `changed` marca uma coleta como completa.
- `--root` continua indicando a pasta local, usada aqui só para os arquivos temporários do download.
- Esta fase foi validada contra um S3 simulado (moto). Nenhuma execução em conta AWS real foi feita.

O `build_caop` ainda lê apenas do disco local; construir a partir do S3 não faz parte desta feature.

## Onde os arquivos ficam

Com `--root .data`, uma coleta nova grava:

```text
.data/
├── raw/source=caop/version=2025/run_id=<run_id>/
│   ├── continente.gpkg.zip
│   ├── acores.gpkg.zip
│   └── madeira.gpkg.zip
└── manifests/caop/<run_id>.json
```

O ZIP dos Açores contém dois GeoPackages, embora seja **um** dos três arquivos raw. Os bytes dos ZIPs são guardados como vieram da DGT. O nome `version=2025` é a edição da fonte; `run_id` identifica a tentativa de coleta. A data de processamento das futuras dimensões é separada desses dois valores.

O manifest guarda as URLs por região, versão, período de referência, licença, horário da coleta, status e checksum/tamanho por arquivo. Para listar os manifests e arquivos raw no PowerShell:

```powershell
Get-ChildItem .data/manifests/caop
Get-ChildItem .data/raw/source=caop -Recurse -File
```

A pasta `.data/` é ignorada pelo Git. Se escolher uma raiz fora dela, mantenha os dados brutos fora do versionamento.

## Interpretar o resultado

| Status | O que aconteceu | Arquivos gravados nesse run |
| --- | --- | --- |
| `changed` | Os três arquivos foram validados e o conteúdo difere da última coleta válida. | Três ZIPs em `raw/` e um manifest. |
| `unchanged` | Os três checksums são iguais aos da última coleta `changed`. | Só um novo manifest de verificação; o raw anterior é reutilizado. |
| `failed` | Houve falha após iniciar a tentativa, como download interrompido ou GeoPackage inválido. | Manifest com o erro; nenhum raw parcial daquele run. |

O comando retorna código `0` para `changed` e `unchanged`, e código diferente de `0` para erro. Erros de catálogo ou de permissão detectados antes da tentativa podem sair sem manifest.

## Construir e visualizar as tabelas

Depois de uma coleta `changed`, execute na raiz do repositório:

```powershell
uv run --locked python -m pipelines.cli.build_caop --local --root .data
uv run --locked python -m pipelines.cli.view_caop --root .data
```

O primeiro comando verifica os checksums do último manifest `changed`, prepara os GeoPackages e roda os modelos e testes dbt. Só depois dos testes a saída é promovida. Os Parquets ficam em `.data/lake/bronze/` e `.data/lake/silver/`. A Silver tem duas tabelas: `dim_municipality` (um município por linha) e `dim_parish` (uma freguesia por linha). O campo `dico` liga cada freguesia ao seu município. O campo `dicofre` guarda o código da freguesia como texto, inclusive sufixos alfanuméricos oficiais.

O segundo comando cria arquivos para inspeção, sem internet e sem alterar a Silver:

- `.data/explore/caop.html`: abra no navegador, busque um município e veja suas freguesias;
- `.data/explore/municipios.csv` e `.data/explore/freguesias.csv`: abra no Excel para ver todas as colunas e linhas.

No PowerShell, você pode abrir diretamente:

```powershell
Start-Process .data/explore/caop.html
```

Os dados são arquivos Parquet locais, não um servidor de banco de dados. O explorador e os CSVs são gerados desses arquivos e ficam em `.data/`, ignorada pelo Git. A edição da fonte (`caop_version`), a coleta (`source_run_id` e `collected_at_utc`) e o processamento (`processed_at_utc`) são informações separadas.

## Estado da verificação

Em 2026-11-04, os três ZIPs oficiais foram coletados em `.data/raw/` e transformados localmente: 308 municípios, 3.259 freguesias e 18 códigos de freguesia com letras. A fixture sintética nacional passou no `dbt build`; a execução real local também passou. Isso não demonstra execução no CI remoto, ainda pendente. O destino S3 foi exercitado só contra um S3 simulado (moto), não contra uma conta AWS real.
