# Coletas de dados

Este guia descreve a coleta da CAOP (local ou em S3), a construção das dimensões territoriais, a coleta do Pordata e do INE com o staging de observações e como visualizar os resultados. O contexto está na [spec de ingestão CAOP](../../sdd/specs/001-ingestao-caop/spec.md).

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

## Pordata, INE e observações municipais

A spec [002-ingestao-pordata-ine](../../sdd/specs/002-ingestao-pordata-ine/spec.md) acrescenta quatro comandos. **Antes do `build_observations`, rode o `build_caop`**: o staging resolve cada município contra a dimensão `lake/silver/dim_municipality`.

### Coletar o Pordata (16 CSV)

```powershell
uv run --locked python -m pipelines.cli.collect_pordata --local --root .data
```

Baixa os 16 datasets do catálogo (~82 MB, cerca de 1 minuto por causa do limite de 1 s entre pedidos). Cada dataset tem **estado próprio**: a saída mostra uma linha por dataset (`changed`, `unchanged` ou `failed` com o motivo).

| Status da execução | O que aconteceu | Código de saída |
| --- | --- | --- |
| `changed` | Pelo menos um dataset mudou; os que não mudaram aparecem como `unchanged` e não gravam arquivo. | `0` |
| `unchanged` | Todos os datasets têm o mesmo conteúdo da última coleta válida. Só um manifest novo. | `0` |
| `partial` | Algum dataset falhou (URL morta, HTML no lugar do CSV, coluna ausente), mas os demais foram gravados. A falha fica no manifest com o motivo e nenhum arquivo parcial dela é gravado. | `1` |
| `failed` | Todos falharam. | `1` |

Um dataset que falhou **não** vira estado vigente: na próxima execução bem-sucedida ele é gravado normalmente. Para repetir só depois de corrigir o catálogo, basta rodar o comando de novo. As colunas são validadas **pelo rótulo** (o prefixo numérico varia por dataset), e `--s3 --bucket <b> [--prefix <p>]` troca o destino, como na CAOP.

### Coletar o INE (3 indicadores)

```powershell
uv run --locked python -m pipelines.cli.collect_ine --local --root .data
```

Consulta a API de indicadores do INE (rendas `0014698`, criminalidade `0008074` com as 7 categorias de crime e poder de compra `0014580`), sempre no nível município. A API **não envia `ETag`** e devolve o horário de extração e a ordem das linhas diferentes a cada chamada, então a mudança é detectada por uma impressão digital do conteúdo: repetir o comando sem o INE ter republicado dá `unchanged`. A API é instável (houve timeout de 60 s e uma coleta de 204 s contra 8 s na repetição); a CLI espera até 90 s por pedido e tenta 3 vezes.

### Carregar a planilha do Pordata à mão

O Pordata só oferece o poder de compra por município por um botão do site (não existe URL de download). Exporte-a assim: na página *Municípios › Poder de compra per capita*, use **Exportar para Excel** e guarde o `.xlsx` **fora do repositório** (por exemplo, em `Downloads`). Depois:

```powershell
uv run --locked python -m pipelines.cli.load_pordata_manual --local --root .data --file "C:\caminho\PORDATA_NUTS2013_Poder-de-compra-per-capita.xlsx"
```

A planilha é validada (abas `Quadro` e `Metainformação`, cabeçalho `Âmbito Geográfico | Anos` e exatamente 308 linhas `Município`) e guardada como bruto, com estado e manifest como qualquer outro dataset. O mesmo arquivo de novo dá `unchanged`; um arquivo inválido dá `failed` e código `1`, sem gravar nada. O seu arquivo só é lido, nunca alterado. O mesmo indicador vem também pela API do INE (`ine/poder_compra_per_capita`); os dois ficam como datasets distintos.

### Construir o staging e ver a cobertura

```powershell
uv run --locked python -m pipelines.cli.build_observations --local --root .data
```

Usa o **estado vigente de cada dataset** (confere o `sha256` do bruto), resolve o município de cada linha e roda o dbt em área temporária. Só depois dos testes promove `lake/bronze/stg_observation/` (uma linha por dataset, município, período e filtros) e `lake/bronze/rpt_observation_coverage/`, **sem tocar** na CAOP. O mesmo vale ao contrário: reconstruir a CAOP não apaga as observações.

- **Município:** no Pordata, pelo nome, usando o seed `analytics/dbt/seeds/municipality_synonyms.csv` (5 grafias: `Lagoa`, `Lagoa [R.A.A.]`, `Calheta [R.A.A.]`, `Calheta [R.A.M.]`, `Vila da Praia da Vitória`) ou o nome normalizado quando for único; no INE, pelo código (os 4 últimos caracteres são o `dico`). Um nome sem correspondência **reprova o build** e lista o dataset e os nomes; um homônimo sem sinônimo também.
- **Ausência:** valor ausente fica **nulo com o símbolo da fonte** (`x`, `-`, `...`); nunca vira zero. Os zeros no staging são zeros informados pela fonte.
- **Cobertura:** a saída mostra, por dataset, o último período, quantos dos 308 municípios têm valor nele, quantos não têm e quantas linhas de agregação (Portugal, regiões, NUTS) foram excluídas. O arquivo `.data/lake/bronze/coverage.csv` (separador `;`, abre no Excel) lista os ausentes de cada dataset por código e nome, e o `latest_period_with_data` diz o último período que tem algum valor.

### Licenças e atribuição

- **INE:** CC BY 4.0. Cite "Instituto Nacional de Estatística, IP – Portugal", o indicador e o período, e sinalize dados modificados.
- **Pordata:** os [Termos Legais](https://www.pordata.pt/pt/termos-e-condicoes-de-utilizacao) **não concedem licença de reutilização**; o autor aceitou coletar mesmo assim (risco **R-001** do plano da spec 002). O catálogo registra `license_id: not_granted_by_source`, o bruto fica fora do Git e nunca é redistribuído, e a publicação de qualquer indicador derivado do Pordata deve reavaliar a licença (alternativa: séries equivalentes do INE).

### Onde os arquivos ficam

```text
.data/
├── raw/source=pordata/dataset=<id>/run_id=<run_id>/<id>.csv   (ou .xlsx na carga manual)
├── raw/source=ine/dataset=<id>/run_id=<run_id>/<id>.json
├── manifests/pordata/<run_id>.json   manifests/ine/<run_id>.json
└── lake/bronze/{stg_observation, rpt_observation_coverage}/data.parquet   e   coverage.csv
```

## Estado da verificação

Em 2026-11-04, os três ZIPs oficiais foram coletados em `.data/raw/` e transformados localmente: 308 municípios, 3.259 freguesias e 18 códigos de freguesia com letras. A fixture sintética nacional passou no `dbt build`; a execução real local também passou. Isso não demonstra execução no CI remoto, ainda pendente. O destino S3 foi exercitado só contra um S3 simulado (moto), não contra uma conta AWS real.

Em 2026-11-11, a spec 002 foi verificada contra as fontes reais: os 16 CSV do Pordata (43 s, tamanhos idênticos aos da pesquisa), os 3 indicadores do INE (a segunda e a terceira coletas deram `unchanged`), a planilha do autor (308 municípios × 11 anos) e o `build_observations` contra a Silver real: **1.168.860 observações de 20 datasets**, todos os municípios resolvidos e o lake da CAOP byte a byte intacto. Achados de cobertura: as rendas do INE têm valor em 247 dos 308 municípios em 2025; `ensino_nao_superior` não tem valor em nenhum município em 2024 (o último período com dados é 2023); `ensino_superior` tem 63 em 2025. O CI remoto ainda precisa confirmar os novos passos do dbt.
