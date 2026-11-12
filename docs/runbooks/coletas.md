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
