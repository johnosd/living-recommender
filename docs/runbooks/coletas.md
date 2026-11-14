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

### Coletar o Pordata (17 CSV)

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

## Clima Open-Meteo (spec 003)

Requer a Silver da CAOP em `.data/lake/silver`, com os 308 pontos representativos. O catálogo fixa `era5`, 13 variáveis diárias e 2024-11-01 a 2026-10-31 (730 dias). Uma chamada HTTP por município pode pesar dezenas de chamadas na cota; estima-se concluir em cerca de três dias, a confirmar pela fonte. Sem chave ou serviço AWS nesta execução.

```powershell
# Primeiro lote; não consulta os municípios já atuais.
uv run --locked python -m pipelines.cli.collect_open_meteo --local --max-municipalities 5 --no-wait
# Retomar. --no-wait salva pendências em vez de esperar minuto/hora.
uv run --locked python -m pipelines.cli.collect_open_meteo --local --no-wait
# Gerar staging e relatórios; cobertura parcial é válida.
uv run --locked python -m pipelines.cli.build_climate --local
# Reconsultar até 3 municípios para detectar revisão da mesma janela.
uv run --locked python -m pipelines.cli.collect_open_meteo --local --recollect --max-municipalities 3 --no-wait
```

O código `0` significa sucesso, lote concluído ou nada a coletar; `1` significa falha de dado/configuração; `2` significa pendências por cota ou Ctrl+C, com manifest salvo. Falha vence pendência no código de saída. Sem `--no-wait`, o limite por minuto espera 61 s até cinco vezes; por hora espera 3.605 s uma vez; diário pausa imediatamente. O limite de lote não cria `pending` artificial. `--silver` permite selecionar a dimensão local, inclusive com destino `--s3`.

O estado atual compara janela, modelo e assinatura das variáveis/unidades. Mudar qualquer um desses itens gera nova coleta, sem sobrescrever o bruto anterior; reordenar variáveis não exige recoleta. Sem mudança e sem `--recollect`, não há chamada nem manifest novo. A impressão digital ignora apenas `generationtime_ms`; o SHA-256 continua auditando os bytes originais. Os meses finais podem ser reanálise preliminar e mudar numa recoleta legítima.

```text
.data/raw/source=open_meteo/dataset=<dico>/run_id=<run>/<dico>.json
.data/manifests/open_meteo/<run>.json
.data/lake/bronze/{stg_climate_daily,rpt_climate_coverage,rpt_climate_points}/data.parquet
.data/lake/bronze/{climate_coverage,climate_points}.csv
```

Os CSV usam `;` e UTF-8 com BOM para abrir no Excel. A promoção dos dois CSV e das três tabelas tem rollback; feche os arquivos no Excel antes de reconstruir. `missing_days_total` soma dias nulos dos municípios coletados; não coletados são listados à parte, por código e nome. O relatório de pontos mostra distância > 25 km e elevação 0 m para revisão, sem corrigir, deslocar o ponto ou herdar dados dos vizinhos. A resolução de ~25 km e uma série de apenas 24 meses limitam seu uso como indicador de clima.

Ctrl+C preserva os municípios concluídos e marca o atual e os seguintes como pendentes. Encerramento forçado pode deixar brutos órfãos, que não são estado e são ignorados na retomada. Não apague manifests nem dados de outras fontes para retomar. O build usa o target dbt `climate` com uma thread e limite de 384 MB no DuckDB (o target `local` das outras fontes é preservado). Confere checksum e tamanho antes de transformar; uma falha dbt preserva a versão anterior, e CAOP/Pordata/INE não são promovidos por esse comando.

Licença e atribuição: Open-Meteo.com (CC BY 4.0); reanálise ERA5, Copernicus Climate Change Service/ECMWF. O plano gratuito da API permite uso não comercial: risco aceito R-001; migrar para plano comercial é gate da futura fase comercial. Nenhum bruto real entra no Git.

O [quickstart da 003](../../sdd/specs/003-ingestao-clima-open-meteo/quickstart.md) descreve o cenário offline. Para fixtures, use o catálogo gerado explicitamente: `build_climate --local --root .data/ci-climate --catalog .data/ci-climate/catalog.yml`.

## Correspondência de freguesias 2013→2025 (spec 004)

Pré-requisito: `dim_parish` construída (`uv run --locked python -m pipelines.cli.build_caop --local`). Nenhuma chave, nenhum `.env`.

```powershell
uv run --locked python -m pipelines.cli.collect_parish_crosswalk --local
uv run --locked python -m pipelines.cli.build_parish_crosswalk --local
```

A coleta baixa as duas planilhas do INE (`smi.ine.pt/Versao/Download/9160` e `/10698`, 233 KB no total, 1 requisição por segundo) e as guarda como bruto imutável. Cada planilha é validada antes de entrar (aba e colunas do catálogo, códigos de 6 caracteres `[0-9A-Z]`); uma que falhe fica `failed` com o motivo e **não bloqueia a outra**. Repetir sem mudança na fonte dá `unchanged` e não grava bruto novo. Os links `Versao/Download/N` não têm estabilidade garantida: se passarem a devolver HTML ou outro arquivo, a falha é explícita.

O build deriva a correspondência, **verifica a cobertura** e só então roda o dbt e promove. A saída resume os pares por natureza (`one_to_one`, `one_to_many`, `many_to_one`, `many_to_many`) e os sinais `herdado`, `origem parcial`, `nome alterado` e `município alterado`.

**Cobertura reprovada.** Se alguma freguesia da `dim_parish` não tiver origem, ou algum código de 2013 não tiver destino, ou algum destino não existir na `dim_parish`, o comando sai com código 1, lista os códigos e **não promove nada**: a tabela anterior continua byte a byte igual. Isso acontece, por exemplo, quando sai uma CAOP nova e a tabela do INE ainda não a cobre; a correção é estender a correspondência (outra entrega), nunca ignorar o erro. Os mesmos testes rodam de novo no dbt como segunda camada.

```text
.data/raw/source=ine_parish_crosswalk/dataset=<reorganizacao_2013|reposicao_2025>/run_id=<run>/<id>.xlsx
.data/manifests/ine_parish_crosswalk/<run>.json
.data/lake/silver/xwalk_parish_2013_2025/data.parquet
.data/lake/silver/rpt_parish_crosswalk_coverage/data.parquet
.data/lake/silver/parish_crosswalk_report.csv
.data/lake/silver/parish_crosswalk_review.csv
```

O **CSV do relatório** (`parish_crosswalk_report.csv`, `;`, UTF-8 com BOM) é a versão legível do `rpt_parish_crosswalk_coverage`: uma linha por natureza mais `all`, com as contagens, a versão da CAOP, a data da coleta e a atribuição repetidas em todas as linhas. O CSV de revisão (`;`, UTF-8 com BOM, abre no Excel) lista os pares que não são um-para-um ou que têm algum sinal. A **herança é só um sinal**: nada é repartido entre as freguesias novas. `name_changed` é verdadeiro na maior parte das uniões desfeitas (o nome da união difere do nome restaurado); use `relation` e `inherited` para decidir. O marcador `(parte)` da fonte é textual; o relatório mostra quantas linhas o têm (11 na fonte de hoje) para denunciar uma mudança de texto do INE.

Licença e atribuição: Instituto Nacional de Estatística, IP – Portugal. A licença específica das duas planilhas é **assumida** `CC-BY-4.0`, como a da fonte `ine`, e ainda precisa ser confirmada nos termos do INE (plan R-002). Nenhuma planilha real entra no Git.

O [quickstart da 004](../../sdd/specs/004-correspondencia-freguesias/quickstart.md) descreve o cenário offline com a fixture (`tests.fixtures.parish_crosswalk.ci_seed`).

## Estado da verificação

Em 2026-11-04, os três ZIPs oficiais foram coletados em `.data/raw/` e transformados localmente: 308 municípios, 3.259 freguesias e 18 códigos de freguesia com letras. A fixture sintética nacional passou no `dbt build`; a execução real local também passou. Isso não demonstra execução no CI remoto, ainda pendente. O destino S3 foi exercitado só contra um S3 simulado (moto), não contra uma conta AWS real.

Em 2026-11-11, a spec 002 foi verificada contra as fontes reais: os 16 CSV do Pordata (43 s, tamanhos idênticos aos da pesquisa), os 3 indicadores do INE (a segunda e a terceira coletas deram `unchanged`), a planilha do autor (308 municípios × 11 anos) e o `build_observations` contra a Silver real: **1.168.860 observações de 20 datasets**, todos os municípios resolvidos e o lake da CAOP byte a byte intacto. Achados de cobertura: as rendas do INE têm valor em 247 dos 308 municípios em 2025; `ensino_nao_superior` não tem valor em nenhum município em 2024 (o último período com dados é 2023); `ensino_superior` tem 63 em 2025. O CI remoto ainda precisa confirmar os novos passos do dbt.

Em 2026-11-11, a spec 003 passou nos 210 testes offline, nos três builds dbt isolados (CAOP 31/31, observações 17/17, clima 23/23) e no volume sintético de 2.922.920 linhas: 555,90 MiB de pico amostrado da árvore de processos. Na fonte real, foram coletados **71/308 municípios**, com 3 recoletas `unchanged`; a cota horária encerrou o lote com **237 pendentes** e nenhum `failed`. O build real produziu **673.790 linhas**, sem lacunas nos coletados, e preservou os 7 arquivos dos outros lakes. Os 237 restantes seguem pendentes. O CI remoto foi confirmado em seguida no [PR #3](https://github.com/johnosd/living-recommender/pull/3), em rascunho: quality e secrets/gitleaks verdes no [run 43107887816](https://github.com/johnosd/living-recommender/actions/runs/43107887816), commit afa0903; 209 testes verdes e 1 específico de Windows dispensado no Linux. Retome o mesmo comando `collect_open_meteo --local --no-wait` quando a cota estiver disponível e depois rode `build_climate --local`.

Na retomada às 21:53 e 22:00 UTC, a API ainda retornou limite horário; a CLI saiu com código 2, pulou os 71 municípios atuais e não gravou bruto novo. Não presumir liberação na virada da hora; a resposta da fonte determina quando é possível avançar. T037 permanece aberta até completar os 308 municípios.

Atualização de 2026-11-11, 22:41 UTC: a retomada coletou mais 148 municípios, sem falha de dado; um HTTP 502 foi recuperado. O estado vigente passou a **219/308**, com **89 pendentes**, **2.078.310 linhas**, nenhuma lacuna nos coletados e **12.685.102 bytes** de bruto. O build parcial passou e os 7 arquivos das outras fontes mantiveram SHA-256. Os pontos de Vila Franca de Xira e Alcochete retornaram elevação 0 m; nenhum ponto excedeu 25 km de divergência. O 429 horário informou reset em **23:00:30 UTC / 20:00:30 Brasília**.

Para aguardar e retomar automaticamente: `uv run --locked python -m pipelines.cli.collect_open_meteo --local --continuous`. O supervisor salva um manifest a cada 10 municípios e antes de esperar por cota, mantém o limitador entre lotes e consulta apenas os pendentes. Prefere `Retry-After` e depois `X-RateLimit-Reset`; sem informação válida, usa o fallback conservador do tipo de cota. Falhas temporárias recebem espera exponencial de 2 a 60 s com jitter de até 1 s, sem teto de tentativas no modo contínuo; um prazo maior informado pelo servidor prevalece. Erros permanentes encerram com falha; Ctrl+C encerra com progresso salvo. Os modos anteriores mantêm suas regras; não combinar `--continuous` com `--no-wait`, `--recollect` ou `--max-municipalities`. Após terminar, executar `build_climate --local`.

Nesta operação local, o supervisor está em segundo plano e chama o build automaticamente quando a coleta terminar. Evidências ignoradas pelo Git: `.data/climate-continuous-status.json`, `.data/climate-continuous.log` e `.data/climate-continuous-errors.log`. `phase: completed` e `returncode: 0` indicam que coleta, build e verificação local terminaram; o status documental de T037 ainda deve ser conferido antes de marcar Implementada. A operação depende da máquina ligada e conectada, sem serviço externo ou publicação automática.

**Estado final conferido em 2026-11-12 UTC:** coleta concluída, nenhum processo ativo, **308/308 municípios e 2.922.920 linhas**, todas as 13 variáveis sem lacunas. Bruto: 17.821.354 bytes; outros 7 arquivos preservados. O build automático terminou com erro de PATH (`dbt` não encontrado); foi recuperado com `uv run --locked python -m pipelines.cli.build_climate --local`, seguido da verificação completa. O status operacional agora registra `completed`, incluindo a recuperação. Uma nova execução da coleta confirma 308/308 atuais, sem rede. O relatório sinaliza Sesimbra a 30,06 km e elevação 0 m em Vila Franca de Xira, Alcochete e Setúbal. Esses alertas não são lacunas nem falhas da coleta. T037 concluída; o CI remoto continua sendo o de afa0903, anterior aos últimos commits locais.

Em 2026-11-12, a spec 004 foi verificada contra o INE real: as duas planilhas (205.543 e 27.382 bytes) foram coletadas, a segunda coleta deu `unchanged` nas duas e o `build_parish_crosswalk` contra a `dim_parish` real (CAOP 2025) gerou **3.260 pares** cobrindo **3.259 de 3.259 freguesias** (2.957 um-para-um, 301 um-para-muitos, 2 muitos-para-muitos; herdado 303, origem parcial 8, nome alterado 297, município alterado 0). Os SHA-256 de `dim_parish`, `dim_municipality`, `stg_observation` e `stg_climate_daily` ficaram idênticos. O detalhe está no `research.md` da spec. O CI remoto ainda precisa confirmar o novo passo do dbt.


## Idealista: importar extração manual (spec 005)

A coleta continua manual no projeto `IdealistaScraper`. Este importador recebe
somente a pasta de JSON; não acessa o Idealista, não executa o scraper e não
precisa de API ou chave. Os arquivos da origem não são alterados nem movidos.

Na raiz do living-recommender:

```powershell
uv run --locked python -m pipelines.cli.import_idealista_snapshot --local --directory "C:/Users/johns/Documents/Projetos/IdealistaScraper/Bases/202508" --snapshot-month 2025-08
uv run --locked python -m pipelines.cli.build_idealista --local --snapshot-month 2025-08
```

Para outra extração, indicar a nova pasta e seu mês `YYYY-MM`. O período deve
ser informado pelo operador: a pasta 202508 significa agosto/2025, e a hora
original de coleta permanece desconhecida. A data de importação é outra coluna.
O build exige `dim_municipality` e `dim_parish` locais da CAOP.

### Saídas e repetição

- `raw/source=idealista/snapshot=2025-08/run_id=<run>/`: cópia byte a byte dos JSON com as subpastas originais.
- `manifests/idealista/<run>.json`: inventário com origem, mês, instante de importação, contagens, licença e hashes.
- `lake/bronze/idealista_occurrences/data.parquet`: todas as ocorrências tipadas e sua proveniência.
- `lake/silver/idealista_listings/data.parquet`: um anúncio por ID no snapshot escolhido, com contagem de repetições e sinais de conflito.
- `lake/bronze/idealista_reports/summary.json`: resumo do build.
- `lake/bronze/idealista_reports/coverage.csv`: todos os 308 municípios, inclusive os sem amostra, e as regiões coletadas.
- `lake/bronze/idealista_reports/duplicates.csv`: anúncios repetidos, ocorrência escolhida e campos divergentes.
- `lake/bronze/idealista_reports/dbt_run_results.json`: resultado dos modelos e testes dbt daquele build.

Os CSV usam `;` e UTF-8 com BOM para abrir no Excel. DICO/DICOFRE são códigos
textuais: preserve os zeros iniciais ao importar o CSV. Todos esses dados ficam
em `.data/`, ignorada pelo Git. **São dados privados de processamento, não arquivos
publicáveis.** A publicação futura será somente de agregados e terá gate próprio.

Repetir a mesma pasta e mês retorna `unchanged`, grava um manifest de verificação
e não duplica raw. Mudança de conteúdo, inclusão ou remoção de arquivo gera outro
run. O manifest `changed` completo é o commit do lote; falhas não viram lote vigente.
Um snapshot vazio/incompleto não é prova de que não há imóveis: confira contagens
e cobertura antes de usar os resultados. O build local seleciona o mês indicado;
os brutos dos demais meses continuam preservados.

A CLI de importação também aceita `--s3 --bucket <bucket>` e o mesmo layout,
verificado com moto; **não foi feita importação em AWS real**. O build desta spec
continua local.

### Regras de normalização e território

Preço português vira número (ex.: `1.200,50€/mês` → `1200.5`); valor ausente ou
não interpretável fica nulo com sinal. Preço baixo não é multiplicado. Área
fica em m²; T4, T5 e maiores recebem categoria `T4+`, mantendo `bedrooms` original.
Links, imagens, descrições e dados do anunciante não passam às tabelas normalizadas.

A primeira ocorrência por caminho relativo e posição é escolhida de forma
estável, sem presumir que seja a mais recente. Todas as ocorrências continuam
em Bronze e raw. Divergências de preço/área/quartos/território são sinalizadas;
conflito de município deixa DICO/DICOFRE nulos, e conflito só de freguesia deixa
DICOFRE nulo. Não há mistura de IDs entre meses.

O nome do arquivo resolve município. Exceções, freguesias de Lisboa e regiões
insulares estão em `analytics/dbt/seeds/idealista_file_localities.csv`. Arquivo
municipal desconhecido reprova o build. Freguesia do título só casa por nome
completo normalizado dentro do município, ou por sinônimo explícito em
`analytics/dbt/seeds/parish_synonyms.csv` (inicialmente só o cabeçalho). Sem casamento,
fica nula e entra no relatório. Não há geocodificação nem comparação aproximada.

Os hashes e a consistência do manifest são verificados antes de processar.
O build roda `dbt build --select tag:idealista` em candidato isolado e só promove
os três diretórios desta feature depois dos testes. Falha mantém a base anterior.
Tabela vazia é exportada com zero linhas, removendo somente o placeholder nulo
que o adapter dbt-duckdb usa internamente para representar schema vazio.

### Evidência local de 2026-11-13

Importação real da pasta 202508: **324 JSON, 16.566.429 bytes, 17.472 ocorrências,
16.117 IDs únicos e 1.355 ocorrências excedentes**. A repetição foi `unchanged`,
sem novos brutos. Build real: **255/308 municípios com amostra**, 53 sem amostra,
**189 anúncios regionais** das ilhas, **8.891 com freguesia resolvida** e 7.037
anúncios municipais sem freguesia resolvida. Nenhum conflito nos campos comparados,
nenhum preço ausente/inválido; isso não comprova qualidade de mercado nem atualidade.

Os **324 hashes da origem e das cópias conferiram**; os **16 arquivos preexistentes
do lake mantiveram seus hashes**. Os 24 passos dbt do build real passaram.
Evidências locais ignoradas: `.data/idealista-import-evidence-before.json` e
`.data/idealista-import-evidence-after.json`. CI remoto, AWS real, publicação e
agregados não estão comprovados por esta execução. O período continua **2025-08**.

Gate final local da spec 005: ruff limpo e **350 testes passando** em 412,66 s. Cinco travas de contrato íntegras; revisão independente das correções sem novo achado. O fluxo novo de fixture/dbt do CI foi executado localmente (24/24 passos), sem execução remota nesta sessão.


## Censos 2021 por freguesia (spec 006)

Coleta de201 datasets oficiais (2 metadados e199 lotes de até32 freguesias, todas as idades por lote), de forma sequencial, identificada e com intervalo mínimo de 2 s. Edição sempre 2021: indicador principal 0014632, geografia 2025, total + 18 faixas; fallback 0011719, geografia anterior, total + 19 faixas. Fonte CC BY 4.0; citar INE. Códigos etários variam por indicador e são interpretados pelos metadados, nunca pelo número isolado.

```powershell
uv run --locked python -m pipelines.cli.collect_censos --local --root .data
uv run --locked python -m pipelines.cli.build_censos --local --root .data
```

D2 foi emendada com aprovação do autor após timeouts nacionais: seletores explícitos em `config/sources.yml`, com102 lotes2025 (3.259 códigos) e97 lotes2013 (3.092 códigos). Cada resposta deve conter todos os pares freguesia/faixa solicitados; a união deve cobrir exatamente o universo oficial, sem sobreposição. Alterações desse universo exigem revisão do catálogo; o build falha em vez de ocultar lacunas.

Originais em `raw/source=censos/`, manifest em `manifests/censos/`. O checksum identifica bytes, e a impressão digital compara conteúdo e seletores sem DataExtracao. Cada entrada guarda snapshot da configuração; mudanças posteriores do catálogo não alteram a reconstrução desse run. A data de extração/revisão não substitui 2021.

O build funciona sem rede e escolhe um único manifest completo, verificando hashes e revisões por família. Se a última coleta falhou ou ficou parcial, o default reprova e mantém a vigente. Para selecionar conscientemente um run completo anterior:

```powershell
uv run --locked python -m pipelines.cli.build_censos --local --root .data --run-id <run-completo>
```

Saídas: Bronze `census_age_category`, `census_observation`; Silver `census_parish_observation`, `census_coverage`. Relatórios em `lake/silver/census_reports/{coverage.csv,summary.csv,readiness.json,orphans.csv}`. `summary.csv` conta observações próprias/herdadas/ausentes por país, região e município; não soma habitantes herdados. Dado oficial compatível tem prioridade, ausência oficial documentada permite fallback, e confidencialidade não permite revelar um valor por outra origem. A faixa 85+ legada só combina idades 85–89 e 90+ da mesma origem publicada. Não são calculados percentuais, densidade ou ranking.

Todo build usa candidato e lock exclusivo em `.build/censos`. Erros de prontidão/dbt/exportação/promoção preservam a versão válida anterior e deixam diagnóstico em `reports/censos/<build-id>/failure.json`. Um lock existente impede novo build: antes de remover APENAS esse arquivo, confirme que o PID não está ativo, leia o build_id e examine candidatos/backups `.previous-*`. Interrupção abrupta durante as trocas exige inspeção; o helper não promete transação contra queda do processo. Não apague diretórios de outras fontes nem o raw. Destinos resolvidos para fora da raiz (incluindo junctions) são recusados.

Se todas as trocas terminaram e os bytes da vigente coincidem com o candidato validado, uma falha posterior de limpeza de backups gera aviso de manutenção e `maintenance.json`, sem invalidar a versão. Preserve esses backups até verificar a manutenção; não confundir aviso de limpeza com falha de qualidade.

Validação sem rede: `python -m tests.fixtures.censos2021.ci_seed --root .data/ci-censos` (sob `uv run --locked`) em raiz de fixture nova; depois `python -m pipelines.cli.build_censos --local --root .data/ci-censos`. Não usar a raiz real como fixture. Contratos são travados: `check-contract-tests.ps1 -Slug 006-censos-2021-freguesia`; suíte completa: `uv run --locked python -m pytest -q --basetemp .pytest_tmp`.

A prova nacional real e o CI remoto têm evidências distintas das fixtures locais; consultar o checkpoint vigente da spec 006 para o resultado efetivamente demonstrado.

### Prova real concluída após emenda D2 — 2026-11-13

Coleta inicial `20261113T231450079026Z-ddf26aad`:201 chamadas/201 respostas,200 changed e1 metadado unchanged,32.804.869 bytes referenciados,449,406s. Repetição `20261113T232234325869Z-00a1b4a4`:201/201 unchanged,201 chamadas,449.906s,nenhum novo raw. Ambos os manifests estão em `.data/manifests/censos/`;originais,hashes,consultas e revisões da primeira rodada foram conferidos após a segunda. Recibos e auditorias em `.data/receipts/censos-proof/`.

Build real aprovado:3.259 freguesias,308 municípios,19 categorias canônicas e61.921 observações próprias;0 herdadas,0 ausentes. Bronze123.761 linhas;população total2021 de10.343.066. Cobertura regional completa e18 códigos alfanuméricos preservados. Todas as observações têm fonte,licença,território,run e referências raw verificadas. Vinte e dois arquivos vizinhos permaneceram idênticos. dbt:4 modelos e21 testes aprovados. Relatórios: `.data/lake/silver/census_reports/`. Fonte INE,Censos2021,CC-BY-4.0. O método de reexpressão não foi divulgado pelo publicador nas evidências consultadas;essa limitação permanece registrada,sem estimativa do projeto.

Validação local: `uv run --locked python -m pytest -q --basetemp .data/tmp/censos-batches-full` →411 passed em571,46s;2 regressões adicionais (histórico completo41 itens e repetição por lotes) →2 passed em3,37s,fora da coleta inicial dessa suíte. Área censos →61 passed em32,12s antes dessas2 adições. `uv run --locked ruff check pipelines tests` aprovado. Seed/build de CLI em `.data/ci-censos-batches` aprovado;travas001–006 íntegras;revisão independente sem bug material. O CI remoto e seu scan de segredos seguem pendentes de commit/push/PR autorizado;nenhuma execução em nuvem ou publicação foi demonstrada. Não marcar Implementada/Convergida antes do gate restante.
