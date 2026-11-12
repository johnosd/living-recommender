# Fontes de dados: inventário do legado e proposta de coleta

> Complementa as §5 e §6 do [plano](plano_plataforma_recomendacao_portugal.md) e segue o [ADR-002](../sdd/adr/ADR-002-arquitetura-base-mvp.md) (D3, D4 e D8). Análise feita em 2026-11-03 sobre o repositório `MPAlugueisLisboa` (e o `IdealistaScraper`, no caso da coleta de imóveis de 2023).

## 1. Resumo

O legado tem **14 processos de captura**, todos rodados à mão em notebooks ou scripts. Cada um grava em `Bases/` com caminho relativo (`..\\..\\Bases`), muitas vezes depois de um `os.chdir`. Nenhum guarda versão nem período de referência, e os arquivos novos sobrescrevem os antigos. A junção entre fontes é feita pelo **nome do município sem acento** (`unidecode`), sem código oficial. Quatro processos têm chaves de API no código.

Na proposta, cada fonte vira um **coletor declarado em `config/sources.yml`**. Os coletores rodam como Lambda (ou como CLI, no caso manual) e gravam em `raw/` imutável, com manifest e checksum. A chave territorial passa a ser o **código DICO/DICOFRE da CAOP**. Saem do projeto o GADM (licença) e o Google Geocoding, substituído pelos centroides da CAOP. As distâncias de carro e transporte público do Google são calculadas **uma vez** e guardadas (risco de termos aceito), e o Google Places vira consulta online no navegador.

## 2. Inventário do legado

### 2.1 Visão geral

| # | Processo | Fonte | Código | Método | Grava em | Estado |
|---|---|---|---|---|---|---|
| L1 | Download Pordata/INE por catálogo | Pordata (blob `ffmspstdlspub01`), pordata.pt, ine.pt | `src/PordataPt/1-PorDataDownload.ipynb` + `pordataFiles.json` | HTTP GET com User-Agent de navegador | `Bases/PorData/<categoria>/`, `Bases/InePt/<categoria>/` | Funciona; URLs frágeis |
| L2 | Descoberta de links Pordata "outros" | pordata.pt (página de documentos) | `src/PordataPt/2-PorDataDownload_outros.ipynb` | Scraping HTML (BeautifulSoup) | Pretendia `Bases/PorData/outros/` | **Com bug:** grava a lista de links num *arquivo* chamado `outros` e não baixa nada |
| L3 | Base de municípios Pordata | `EstatisticasPortDataGeral.xlsx` (download manual) | `src/Notebooks/1 -Cria Base Municipios.ipynb` | Leitura do Excel e filtro "Município" | `Bases/Municipios/Municipios.csv` (308 linhas, sem acentos) | Legado do TCC |
| L4 | Lista mestre de municípios | Manual (origem não documentada) | — | Planilha | `Bases/Municipios/portugalMunicipios.csv` (`Regiao,Cidades`, 309 linhas) | Usada por L5, L7 e L10; sem código oficial |
| L5 | Clima WWO | World Weather Online (premium `past-weather`) | `src/Notebooks/0 - ApiClima.ipynb`, `src/Weather/worldWeatherApi.py` (lib `wwo_hist`) | API por **nome** `Cidade,Portugal`, diário, checkpoint em `done.txt` | `Bases/Clima/worldWeatherApi/<Cidade>,Portugal.csv` (309) → `Processados/` (339) → `ranking/` | Período de 2024-06-30 a 2025-06-30; **5 chaves no código, em rodízio** |
| L5b | Clima WWO (versão antiga) | WWO | `src/Notebooks/3 - Clima.ipynb` (`weather_py`) | Igual, ano de 2021 | `Bases/Clima/BasesClimaOrigem/` → `BaseClimaMensal.csv`, `RankingClima.csv`, `Municipios_geo_clima.csv` | Obsoleto |
| L6 | Clima Open-Meteo | `archive-api.open-meteo.com` | `src/tests/test_openMeteoApi.ipynb` | API por lat/lon, diário, com cache | `Bases/Clima/openMeteoApi/<pais>_<municipio>_clima.csv` | **Protótipo**: 3 pontos (Marília, Lisboa, Porto) |
| L7 | Geocodificação e rotas Google | Google Geocoding + Directions | `src/Geocoding/geocoding.py`, `src/Notebooks/0 - Geocoding.ipynb` | API por nome; rotas de carro e transporte público até Lisboa e Porto | `Bases/Geocoding/portugalMunicipiosGeo.csv`, `portugalMunicipiosGeoDistances.csv` | Chave no código; ver §2.2 |
| L8 | Geocodificação Nominatim | OSM Nominatim (geopy) | `src/Notebooks/2 - Geocode.ipynb` | geopy por nome; distância geodésica | `Bases/Municipios/Municipios_Geo.csv` | Obsoleto |
| L9 | Pontos de interesse Google Places | Google Places Nearby | `src/Notebooks/0 - GeoPlaces.ipynb` | Raio de 2 km por coordenada | Só em memória | Protótipo com coordenadas do **Brasil**; chave no código |
| L10 | Textos da Wikipedia | `pt.wikipedia.org` (API `query` + `parse`) | `src/wikipedia/wikipediaApi.ipynb` | Título = nome da cidade; HTML → texto (BeautifulSoup) | `Bases/Wikipedia/<Cidade>.txt` (308) | Sem User-Agent e sem tratar homônimos; ver §2.2 |
| L11 | Imóveis 2023 (TCC) | idealista.pt | `IdealistaScraper/IdealistaScraper.py` (Selenium, cookies, proxy) | Scraping automatizado | `Bases/Imoveis/Fato/Distritos/<distrito>-distrito.csv` (16), `Bases/Imoveis/Detalhes/BaseDetalhesImovel.csv` | **Descontinuado**; proxy e credenciais no código |
| L12 | Imóveis 2025 (extensão) | idealista.pt | Extensão Chrome MV3 (repo `IdealistaScraper`) | Coleta manual no navegador | `Bases/idealista/202508/<regiao>/<distrito>/*.json` (324) → `base_processada/base_imoveis*.csv` | Processador `idealistaProcessData.py` **não compila** (`import re'`) |
| L13 | Limites administrativos | GADM 4.1, Natural Earth | — (download manual) | Shapefiles | `Bases/Geocoding/files/` | GADM com licença restritiva; ver §2.2 |
| L14 | INE: rendas medianas e criminalidade | ine.pt (`clientFiles/…xls`) | Via catálogo do L1 | Link de exportação | `Bases/InePt/{moradia,seguranca}/` | Links de exportação gerados pelo site, sem estabilidade garantida |

### 2.2 Detalhe por fonte

**Pordata (L1, L2, L3).** O catálogo `pordataFiles.json` tem 24 entradas em 10 categorias:

| Categoria | Arquivos |
|---|---|
| Segurança | 559, 560 e INE "Taxa de criminalidade" |
| Saúde | 464 (farmácias), 470 (hospitais) |
| População | 1 (residentes por sexo e grupo etário), 4 (densidade) |
| Educação | 375 (superior), 379 (não superior) |
| Emprego | 439, 445, 447 e o 845, que foi baixado à mão e não está no catálogo |
| Migrações | 354 (estrangeiros residentes) |
| Economia | 294, 295 e dois `.xlsx` de poder de compra |
| Cultura | 623 (cinemas), 631 (espetáculos) |
| Moradia | 978, 980 e INE "Valor mediano das rendas" |
| Salários | 581, 582 |

- **Formato dos CSV:** formato longo, com as colunas `01. Ano, 02. Nome Região (Portugal), 03. Âmbito Geográfico, 04–06. Filtros, 07. Escala, 08. Símbolo, 09. Valor`. A região vem só como **nome**, sem código.
- **Processamento:** o `PorDataProcess.py` (2.265 linhas) pivota tudo numa base larga (`Bases/PorData/base_agregada/estatisticas_agregadas.csv`). Essa saída tem **bug de formatação**: números gravados com locale (`"2.024,00"` no campo `Ano`).
- **URLs do blob:** os caminhos `Modelo_<n>/<id>.csv` são internos do site. Podem mudar sem aviso.

**WWO (L5).**
- **Consulta por nome:** a API recebe `Cidade,Portugal` sem acentos, e quem resolve a localização é o próprio WWO. Isso dá margem a ambiguidade (Lagoa e Calheta existem nos Açores, na Madeira e no continente).
- **Chaves:** o rodízio de 5 chaves sugere contornar limites de contas trial. O plano já define **uma chave**, guardada como segredo.
- **Cobertura:** um único ano.

**Google (L7, L9).** Os termos da Google Maps Platform restringem guardar e redistribuir resultados de forma permanente. Publicar distâncias e coordenadas vindas dela num site público não é compatível. Além disso, as coordenadas eram resolvidas por nome, sujeitas a homônimos.

**Wikipedia (L10).**
- **Homônimos:** o título da página é o nome cru. `Lagoa.txt`, por exemplo, aponta para `pt.wikipedia.org/wiki/Lagoa`, que tende a ser uma página de desambiguação.
- **Política de uso:** a Wikimedia exige um User-Agent descritivo, que não é enviado.
- **Licença e revisão:** o texto é CC BY-SA, então precisa de atribuição e do id de revisão, que não é guardado.

**Imóveis 2023 (L11).** O `BaseDetalhesImovel.csv` traz `Endereco`, `Latitude`, `Longitude` e `ad_owner_commercialName`, ou seja, dados de terceiros por anúncio. O tratamento (notebook 5) multiplica por 1.000 preços abaixo de 175, uma heurística sem validação. A coleta usou proxy e cookies, contra o código de conduta (§3.4 do plano).

**GADM (L13).** A licença do GADM permite só uso acadêmico e não comercial, e não permite redistribuição. A CAOP (DGT) é a fonte oficial e cobre freguesias com códigos.

### 2.3 Problemas transversais

1. **Junção por nome sem acento:** a `unidecode` em vários pontos e as grafias diferentes entre fontes causam perdas silenciosas no `merge`.
2. **Sem histórico:** cada execução sobrescreve a anterior, e não há data de coleta, período de referência nem checksum.
3. **Dependência do diretório de trabalho:** `os.chdir` e caminhos `..\\..\\Bases` só funcionam a partir da pasta do notebook.
4. **Segredos no código:** WWO, Google (L7, L9) e, no outro repositório, o login do Idealista e o proxy.
5. **Dados no Git:** CSV, XLS, shapefiles e JSON brutos versionados no próprio repositório.
6. **Sem validação de schema:** uma mudança de coluna na fonte só aparece como erro mais adiante, ou nem aparece.

## 3. Proposta

### 3.1 Princípios

- **Uma fonte, um coletor e uma entrada no catálogo.** O `config/sources.yml` é a fonte da verdade sobre URL, licença, frequência e método.
- **O coletor só busca e guarda.** Ele grava os bytes como vieram em `raw/` e escreve o manifest. A normalização acontece depois (bronze no dbt ou num normalizador Python, quando o formato exigir).
- **Chave territorial oficial.** Todo dado é ligado a `dico`/`dicofre` por seeds de sinônimos no dbt. Um nome de município sem correspondência falha o build.
- **Idempotência.** Se o checksum for igual ao do último run, o status é `unchanged` e nada é republicado.
- **Boa conduta.** User-Agent identificado (`living-recommender/0.x (+contato)`), limite de requisições, retries com backoff e respeito aos termos de cada fonte.
- **Execução local idêntica.** `--local` grava em `./.data/` com o mesmo layout do S3, para desenvolver sem AWS.

### 3.2 Catálogo de fontes (`config/sources.yml`)

**Formato implementado** (spec 001, fonte `caop`): o arquivo tem a chave raiz `sources`, um mapa em que a chave é o `source_id`. Os campos obrigatórios são `id`, `publisher`, `responsible_party`, `license_id`, `collection_method`, `frequency`, `territorial_level`, `version`, `reference_period` e `urls`. Para a CAOP, `urls` é um mapa por região (`continente`, `acores`, `madeira`) com URLs HTTPS. Um coletor recusa qualquer fonte que não esteja no catálogo.

```yaml
sources:
  caop:
    id: caop
    publisher: Direção-Geral do Território
    responsible_party: living-recommender
    license_id: CC-BY-4.0
    attribution: "Fonte: Direção-Geral do Território (DGT), CAOP2025"
    collection_method: http_download
    frequency: annual_or_on_demand
    territorial_level: municipality_and_parish
    version: "2025"
    reference_period: "2025"
    urls:
      continente: https://geo2.dgterritorio.gov.pt/caop/CAOP_Continente_2025-gpkg.zip
      acores: https://geo2.dgterritorio.gov.pt/caop/CAOP_RAA_2025-gpkg.zip
      madeira: https://geo2.dgterritorio.gov.pt/caop/CAOP_RAM_2025-gpkg.zip
```

A validação do catálogo (`pipelines/collectors/_shared/catalog.py`) tem três caminhos: `get_source` (CAOP, com as três regiões em `urls`) e `get_dataset_source` (fontes com `datasets` independentes, como `pordata` e `ine`, da spec 002), que valida fonte e datasets antes de qualquer rede e deixa cada dataset herdar `expected_labels`, `name_column` e `api_url` da fonte. As entradas `pordata` e `ine` reais estão em `config/sources.yml`: 16 CSV por HTTP e a planilha de poder de compra por carga manual (`manual_upload`) no Pordata, e 3 indicadores (`api_json`) no INE. O Pordata usa `license_id: not_granted_by_source` (risco aceito, R-001); o INE, `CC-BY-4.0`. A spec 003 acrescenta `get_climate_source`, com janela, modelo, variáveis e unidades declarados e validação antes da rede. `open_meteo` está implementada localmente: `era5`, 13 variáveis diárias e janela fixa de 24 meses (2024-11-01 a 2026-10-31). O catálogo real inclui atribuição Open-Meteo/ERA5, restrição não comercial e os limites de taxa. A spec 004 acrescenta `ine_parish_crosswalk`, uma fonte de `datasets` (`format: xlsx`) cujas entradas declaram a aba (`sheet`), o `role` e o mapa `papel → rótulo` das colunas (`columns`); os rótulos são comparados normalizados e nunca por posição, e a aba é exigida pelo catálogo.

O schema completo e versionado das quatro fontes está em `config/sources.yml`; não há cópia parcial de uma proposta neste documento.


### 3.3 Desenho por fonte

| Fonte (`source_id`) | Substitui | Como coleta | Gatilho | Runtime | Destino em `raw/` | Chave territorial | Observações |
|---|---|---|---|---|---|---|---|
| `caop` | L4, L13, parte do L7/L8 | Download do GeoPackage oficial da DGT | Anual / sob demanda (`ingest_reference`) | ECS (GDAL; o arquivo é grande para Lambda) | `source=caop/version=<ano>/` | É a própria dimensão (`dico`, `dicofre`) | Gera `dim_municipality`, `dim_parish`, pontos representativos, áreas, TopoJSON e a correspondência 2013→2025. **Entregue pela spec 001:** `raw/`, Bronze e as duas dimensões Silver, com área em km² e ponto dentro do polígono (`representative_point`, não o centroide geométrico). O TopoJSON fica para uma spec futura; a correspondência de freguesias 2013→2025 veio da spec 004 (fonte `ine_parish_crosswalk`, abaixo). Atribuição: "Fonte: Direção-Geral do Território (DGT), CAOP2025", CC-BY-4.0. Para reprocessar, basta rodar `build_caop`; ele sempre parte do último manifest `changed`. Objetos S3 sem manifest `changed` são órfãos de um crash e podem ser apagados (`delete_prefix`) |
| `pordata` | L1, L2, L3 | GET dos 16 CSV do catálogo, cada um com estado próprio (`unchanged` por `sha256`); `ETag`/`Last-Modified` são só registrados no manifest, sem GET condicional por ora. A planilha de poder de compra entra por **carga manual** (`load_pordata_manual`), porque o site só a oferece por um botão JavaScript | Mensal | Lambda | `source=pordata/dataset=<id>/run_id=<run>/<arquivo>` | Nome → `dico` por seed | Colunas validadas pelo rótulo (o prefixo numérico varia por dataset). **Licença não concedida** pelos Termos Legais (risco aceito, R-001). O dataset 845 segue sem URL. L2 (descoberta de links) não é migrado: datasets novos entram no catálogo por PR |
| `ine` | L14 | **API JSON de indicadores do INE**, por código de indicador (`varcd`), em vez dos links `clientFiles` | Mensal (as rendas locais saem por trimestre) | Lambda | `source=ine/dataset=<id>/run_id=<run>/<id>.json` | Código geográfico da API: os 4 últimos caracteres são o `dico` (308 de 308 conferem com a CAOP) | Mapeados na spec 002: rendas `0014698` (€/m², anual), criminalidade `0008074` (‰, com as 7 categorias de crime) e poder de compra per capita `0014580` (bienal), todos por município (`Dim2=lvl@5`); freguesia fica fora. A API não envia `ETag`, devolve `DataExtracao` e a ordem das linhas variáveis, então a mudança é detectada por uma impressão digital canônica. **Cobertura das rendas: 247 dos 308 municípios em 2025** (222 em 2020), porque o INE só publica unidades com contratos suficientes. **Entra na v0** como referência oficial do aluguel, ao lado do Idealista (§5) |
| `aima` | — (novo) | Download do **Relatório de Migrações e Asilo** (PDF anual da AIMA) e extração das tabelas de estrangeiros residentes por nacionalidade | Anual | ECS ou CLI local (extração de PDF) | `source=aima/rma=<ano>/relatorio.pdf` + `tabelas.csv` extraídas | Nome do município (ou distrito) → `dico` por seed | **Condicional:** só entra se houver dado **por município**. Indicadores: % de brasileiros, % de lusófonos (CPLP), % do total de estrangeiros. Se o relatório só trouxer distritos, a fonte é descartada (§5) |
| `sns` | — (novo) | Portal **SNS Transparência**: download do indicador de utentes inscritos sem médico de família, por ACES | Mensal | Lambda | `source=sns/release=<data>/…/utentes_sem_mf.csv` | ACES → `dico` por seed `aces_municipios` (um ACES cobre vários municípios) | **Condicional:** só entra se a extração for estável (download ou API, não scraping de painel). Indicador: % de utentes sem médico de família no ACES, herdado pelos municípios do ACES e sinalizado como tal (§5) |
| `censos` | — (novo) | Download dos quadros por freguesia do **censo mais recente** (hoje o de 2021; o próximo é o de 2031) | A cada novo censo | Lambda | `source=censos/edicao=<ano>/…` | `dicofre` (divisão de 2013) → correspondência | Base dos indicadores próprios das freguesias. Entre censos, só há estimativas anuais por município (INE) |
| `open_meteo` | L6, parte do L5 | API `archive`, `era5`, 13 variáveis diárias, 24 meses, ponto representativo CAOP (não centroide) | CLI local; trimestral previsto | Local nesta spec; ECS/lotes em implantação futura (a cota não cabe no Lambda) | `source=open_meteo/dataset=<dico>/run_id=<run>/<dico>.json` | `dico` direto | **Implementada pela spec 003:** coleta retomável por cota, manifest por município, `--recollect`, `--max-municipalities`, staging diário e cobertura/pontos Bronze. Janela/modelo/variáveis/unidades novos provocam nova coleta; ausência é preservada. Grade ~25 km; 24 meses não são normais climáticas. Plano gratuito não comercial: risco aceito R-001, sem publicação. Coleta real completa e CI remoto têm evidência separada no runbook |
| `ine_parish_crosswalk` | — (novo) | Download das **duas planilhas oficiais do INE** que ligam as freguesias antes de 2013 à divisão de 2013 (tabela A) e às 302 freguesias repostas em 2025 (tabela B): `smi.ine.pt/Versao/Download/9160` e `/10698`. Cada uma é uma tabela do catálogo, com estado próprio (`unchanged` por `sha256`) | Sob demanda (nova CAOP ou nova lei) | CLI local; Lambda no futuro | `source=ine_parish_crosswalk/dataset=<id>/run_id=<run>/<id>.xlsx` | `dicofre` de 2013 → `dicofre` de 2025 (CAOP) | **Implementada pela spec 004:** `build_parish_crosswalk` encadeia A e B pelo código pré-2013 e gera `lake/silver/xwalk_parish_2013_2025`, uma linha por par, com a natureza da relação (`one_to_one`, `one_to_many`, `many_to_one`, `many_to_many`) e os sinais `inherited`, `partial_origin`, `name_changed` e `municipality_changed`. **Sem pesos**: a herança é só um sinal. Um gate reprova a promoção se a `dim_parish` não for coberta por inteiro. O relatório de cobertura sai em Parquet e em CSV legível (`parish_crosswalk_report.csv`, com versão da CAOP, data da coleta e atribuição em todas as linhas), mais um CSV de revisão dos pares que não são um-para-um. Códigos aceitam letras (`0308FC`) e as planilhas trazem células numéricas de 6 dígitos (normalizadas). Referência (2026-11-12): 3.260 pares; 2.957 um-para-um, 301 um-para-muitos, 2 muitos-para-muitos. Licença assumida `CC-BY-4.0` (como a fonte `ine`), a confirmar. Os links `Versao/Download/N` não têm estabilidade garantida: mudança vira falha explícita |
| `wwo` | L5 | API `past-weather` com **uma chave** (de teste) em SSM, por **lat/lon do centroide** (não por nome) | Sob demanda | Lambda | `source=wwo/period=<ini>_<fim>/…/<dico>.csv` | `dico` direto | **Fallback** do Open-Meteo, mantido enquanto a chave de teste valer. Coletor e dados históricos preservados. Nada de rodízio de chaves |
| `google_distances` | L7 | **Cálculo único** com a CLI `compute-distances`, rodada localmente: Google Distance Matrix nos modos `driving` e `transit` (com `departure_time` fixo num dia útil às 08:00), do centroide CAOP de cada município até os polos relevantes. A linha reta é calculada sem API (haversine) | **Uma vez.** Só roda de novo se a lista de polos ou a CAOP mudar | CLI local; chave em `.env`/SSM | `source=google_distances/run=<data>/distances.csv` + manifest | `dico` | **Entra na v1.** O usuário escolhe o modo na interface. Saída: `dico, polo, modo, km, minutos, calculado_em`. Polos por município: os nacionais mais a sede do próprio distrito (cerca de 8), o que dá ~2.500 pares × 2 modos ≈ 5 mil elementos (confirmar a cota gratuita vigente). Sem rota possível (ilhas, sem transporte): `null` com bandeira. As freguesias herdam a distância do município. **Risco aceito:** ver nota abaixo |
| `wikipedia` | L10 | **Igual ao legado por enquanto**: API `query` + `parse` por nome do município, empacotada como coletor (User-Agent identificado, gravação em `raw/` com manifest) | Mensal | Lambda | `source=wikipedia/rev=<data>/…/<municipio>.txt` | Nome → `dico` por seed | Atribuição CC BY-SA. Homônimos (Lagoa, Calheta) ficam como problema conhecido, tratados na seed |
| `idealista` | L11, L12 | Extensão manual mais a CLI `upload-snapshot` (§6.3 do plano), validada contra JSON Schema | Mensal, manual | CLI local → S3 | `source=idealista/snapshot=<aaaa-mm>/run_id=…/*.json` | Nome do arquivo e título → `dico`/`dicofre` por seed | Código de conduta (§3.4). Só agregados publicados. Quando a API oficial chegar, entra um coletor Lambda com o mesmo contrato Silver |
| `pois` (Fase B) | L9 | Extrato OSM da Geofabrik (Portugal) filtrado por tags (`amenity=hospital/pharmacy/school…`) | Trimestral | ECS | `source=osm/extract=<data>/…` | Ponto → `dicofre` por interseção espacial | Para saúde e educação por freguesia (§8.3 do plano). Licença ODbL com atribuição |
| `google_places` (online, Fase B) | L9 | **Sem coleta.** O navegador consulta o Google Places diretamente quando a pessoa abre a ficha de um município ou freguesia e pede "serviços próximos". O resultado é exibido com atribuição do Google e não é gravado | Sob demanda, por clique | Navegador (Maps JavaScript API) | — | Coordenadas do centroide | Chave por BYOK ([ADR-003](../sdd/adr/ADR-003-byok-apis-externas.md)): a do visitante ou, se o autor habilitar, a do projeto, restrita por domínio (HTTP referrer) e com teto diário de cota. Ativado por clique, com aviso de que a consulta vai ao Google |

**Saem do projeto:** o Google Geocoding (L7), substituído pelos centroides da CAOP; o GADM e o Natural Earth (L13), por licença e por serem dispensáveis com a CAOP; e o scraper Selenium (L11), pelo código de conduta.

**Ficam com o Google:**
- **Distâncias de carro e transporte público:** calculadas uma vez e guardadas.
- **Places:** consulta online no navegador, sem gravar nada.

> **Risco aceito: distâncias do Google guardadas.** Os termos da Google Maps Platform restringem guardar e exibir resultados fora de um mapa Google. Guardar a matriz de distâncias e exibi-la num site com mapa MapLibre contraria esses termos. O autor aceitou o risco em 2026-11-03 para evitar a complexidade de um motor de rotas próprio. Mitigações: execução única e de volume baixo; atribuição "Tempos de viagem: Google"; e substituição documentada (OpenRouteService para carro e GTFS da CP para comboio) caso o Google conteste ou o projeto entre na Fase B comercial.

### 3.4 Estrutura do código

**Implementado** (spec 001, fonte `caop`; spec 002, fontes `pordata` e `ine`):

```text
pipelines/
  collectors/
    _shared/
      catalog.py             # lê e valida config/sources.yml
      http.py                # HttpDownloader: User-Agent, timeout, rate limit, retry com backoff
      manifest.py            # manifest versionado, SHA-256, último `changed`
      storage.py             # LocalStorage (mesmo layout de chaves do S3)
      storage_s3.py          # S3Storage (escrita condicional, sem sobrescrever)
      datasets.py            # collect_datasets(): fontes com vários datasets, estado e falha por dataset (spec 002)
      dataset_manifest.py    # manifest v2 (datasets[]) e estado vigente por dataset
      municipality.py        # resolve_municipality_names(): nome → dico (sinônimo ou nome único)
      observations.py        # esquema do Parquet longo de observações
    pordata/                 # validate.py (CSV pelo rótulo), xlsx.py (planilha manual), transform.py, handler.py, manual.py
    ine/                     # fingerprint.py (JSON canônico), validate.py, fetch.py, transform.py, handler.py
    parish_crosswalk/        # layout.py (leitura da planilha), validate.py, transform.py, derive.py, coverage.py, handler.py (spec 004)
    caop/
      handler.py             # collect_caop(): fronteira pública, dependências injetadas
      schema.py              # validação do ZIP/GeoPackage; extração e seleção de camadas
      transform.py           # GeoPackage → Parquet (área, ponto representativo, WGS84)
      names.py               # normalização única de nomes
  cli/
    collect_caop.py          # --local | --s3 --bucket [--prefix]
    build_caop.py            # raw → Bronze/Silver, com promoção após os testes
    view_caop.py             # explorador HTML e CSVs
    collect_pordata.py       # 16 CSV por HTTP; falha de um dataset não bloqueia os outros
    collect_ine.py           # 3 indicadores da API JSON
    load_pordata_manual.py   # planilha de poder de compra exportada à mão
    build_observations.py    # estado vigente → stg_observation + cobertura (coverage.csv)
    collect_open_meteo.py    # município, janela/modelo/variáveis, cota e retomada
    build_climate.py         # staging diário, cobertura e pontos; promoção com rollback
    collect_parish_crosswalk.py  # 2 planilhas do INE; falha de uma não bloqueia a outra
    build_parish_crosswalk.py    # deriva, verifica a cobertura da dim_parish, dbt e promove por caminho
analytics/dbt/
  models/staging/stg_caop_{municipalities,parishes}.sql
  models/marts/dim_{municipality,parish}.sql
  models/bronze/stg_observation.sql, rpt_observation_coverage.sql   # tag `observations`
  models/climate/{stg_climate_daily,rpt_climate_coverage,rpt_climate_points}.sql  # tag climate
  models/crosswalk/{xwalk_parish_2013_2025,rpt_parish_crosswalk_coverage}.sql    # tag parish_crosswalk
  seeds/municipality_synonyms.csv                                  # 5 grafias que exigem sinônimo
tests/{contracts,unit,integration,fixtures}/   # sem rede; S3 simulado com moto
```

**Previsto** para as próximas fontes:

```text
pipelines/collectors/censos2021/  wwo/  wikipedia/
pipelines/cli/upload_snapshot.py   # Idealista manual
config/poles.yml                   # Lisboa, Porto, Faro, aeroportos, sedes de distrito
analytics/dbt/seeds/parish_synonyms.csv   # a correspondência 2013→2025 NÃO é seed: é a tabela Silver da spec 004
analytics/dbt/models/staging/stg_<fonte>__<dataset>.sql
```

**Fronteira de um coletor.** Em vez de uma classe com `check()`/`extract()`, a spec 001 adotou uma função com dependências injetadas, o que permite testá-la sem rede e trocar o destino sem mudar a lógica:

```python
def collect_caop(
    catalog, *, storage, downloader, validator, run_id, collected_at_utc, work_dir
) -> dict: ...
# storage:    LocalStorage ou S3Storage (put, put_file, get, delete, list_keys, preflight)
# downloader: (url, destino) -> baixa um arquivo; HttpDownloader em produção
# validator:  (região, arquivo) -> levanta exceção se o bruto for inválido
```

Para fontes com vários datasets independentes (`pordata`, `ine`), a spec 002 acrescentou `collect_datasets(catalog, source_id, *, storage, fetcher, validator, run_id, collected_at_utc, work_dir, fingerprint=None, dataset_ids=None)`: o estado vigente, a validação e a falha são **por dataset** (`partial` quando algum falha, sem bloquear os demais), e `fingerprint` permite comparar o conteúdo sem o que varia a cada chamada (no INE, o horário de extração e a ordem das linhas).

A função baixa e valida tudo antes de gravar o `raw/`, compara os checksums com o último manifest `changed` (`unchanged` não grava bruto novo) e escreve o manifest `changed` ou `failed`. A forma da interface será revista quando o Pordata, o segundo coletor, validar o padrão.

### 3.5 Destino das regras de negócio do legado

| Lógica legada | Para onde vai |
|---|---|
| `PorDataProcess.py` (pivot largo, 2.265 linhas) | Staging dbt por dataset em formato **longo** (`dico, indicador, periodo, valor, unidade`). O pivot largo deixa de existir, porque o `criteria_catalog` aponta para indicadores longos |
| `weatherClassifier.py` (score climático, TCI) | Modelo `gold_climate` no dbt (SQL) ou função Python testada no ECS, com golden tests contra a saída legada de 2024–2025 |
| Notebook 3 (ranking de clima por quartis) | Descartado; substituído pelo modo "clima preferido" do ranker |
| `geocoding.py` (rotas e conversões de texto) | Descartado; substituído pelo `gold_distances` |
| `idealistaProcessData.py` (extração de município e freguesia, conversão numérica) | Staging dbt do Idealista e seed `parish_synonyms`. Regras reescritas com testes, partindo do snapshot 2025-08 |
| Notebook 5 (outliers IQR por distrito, correção ×1000) | Outliers por IQR no **município** dentro do dbt, com contagem dos excluídos. A correção ×1000 não é migrada; casos assim viram teste de qualidade |

### 3.6 Migração do histórico legado

| Dado legado | Leva para `raw/`? | Como |
|---|---|---|
| Idealista 2025-08 (324 JSON) | **Sim** | `upload-snapshot --month 2025-08 --operator <autor> --note backfill` |
| WWO 2024-06-30 → 2025-06-30 (309 CSV) | **Sim**, como backfill | Upload único para `source=wwo/period=2024-06-30_2025-06-30/`, com o manifest marcando `join_key: nome_wwo`. A resolução para `dico` vai pela seed de sinônimos |
| Open-Meteo (3 cidades) | Não | Coletado de novo para todos os municípios |
| Pordata/INE | Não | Baixados de novo (versões mais recentes) |
| Wikipedia (308 TXT) | **Sim**, como backfill | Upload único para `source=wikipedia/rev=<data-legado>/`; as coletas seguintes usam o mesmo processo |
| Google Geocoding/Directions | **Não** | Termos de uso; substituído pela CAOP e pelo haversine |
| Imóveis 2023 (L11) | **Não** | Contém dados de terceiros por anúncio e veio de uma coleta fora do código de conduta. Fica fora do repositório novo; quando muito, serve de referência pessoal offline |
| GADM / Natural Earth | **Não** | Licença; substituídos pela CAOP |

## 4. Decisões (revisão de 2026-11-03)

| Tema | Decisão |
|---|---|
| Clima | Open-Meteo como fonte principal; spec 003 implementa `era5`, 13 variáveis diárias de 24 meses por município. Sem WWO, normais de 30 anos, score ou Silver/Gold nesta entrega |
| WWO | Chave de teste; mantido como **fallback**, sem remover coletor nem histórico |
| Distâncias | Três modos (linha reta, carro e transporte público), **na v1**. Carro e transporte vêm do Google Distance Matrix, **calculados uma vez e guardados** (risco aceito). A linha reta é calculada por haversine. A alternativa com `r5py` + GTFS foi rejeitada por complexidade |
| Wikipedia | Mantém o processo do legado por enquanto |
| Códigos do INE | Mapear os indicadores usados (tarefa da Fase 2) |
| Censos | Usar sempre o censo mais recente (hoje o de 2021) |
| Pontos de interesse | OSM como base (Fase B), validado contra listas oficiais (SNS, escolas). O Google Places fica como **enriquecimento online** no navegador, sob demanda e sem gravar |

**A confirmar antes de rodar as distâncias:**
- a tabela de preços e a cota gratuita vigentes do Distance Matrix (ou da Routes API, que o substitui);
- a lista final de polos em `config/poles.yml`.

## 5. Fontes adicionais (só as de grande impacto)

Critério de entrada: a fonte precisa (a) cobrir um fator de decisão de peso para o público-alvo (imigrantes que alugam) **e** (b) diferenciar de verdade os municípios, ou cobrir uma lacuna dos dados atuais.

| Fonte | Por que entra | Condição |
|---|---|---|
| **INE: Rendas da Habitação ao nível local** (série revista em 2026 com dados da AT) | O aluguel é o critério nº 1. O Idealista só tem n ≥ 10 em cerca de 195 localidades. O INE dá uma mediana oficial de novos contratos para 247 dos 308 municípios em 2025 (222 em 2020; só publica unidades com contratos suficientes) e para parte das freguesias, e o legado já usava a versão XLS | Entra na v0, via a API do INE (`source_id: ine`) |
| **AIMA: estrangeiros por nacionalidade** | "Onde vivem brasileiros e lusófonos" é decisivo para o público. Os dados atuais (Pordata 354) só dão o total de estrangeiros | Entra **só se** houver dado por **município**. Se for só por distrito, fica fora, porque não diferencia o ranking |
| **SNS: utentes sem médico de família** | O acesso a médico de família é uma das maiores preocupações de quem chega, e varia muito entre regiões | Entra **se** for possível extrair por ACES de forma estável e mapear os ACES para municípios |

**Avaliadas e deixadas de fora por impacto baixo:**
- **ANACOM:** a cobertura de alta velocidade já passa de 95% dos alojamentos e quase não diferencia os municípios.
- **TIPAU e DEGURBA:** a população e a densidade já indicam se o lugar é urbano.
- **IMI e IRS municipal:** pesam pouco para quem aluga.
- **RNAL:** é redundante com o aluguel.
- **Combustíveis:** a variação de preço entre municípios é pequena.
- **Incêndios, qualidade do ar, costa e altitude, GTFS, CORINE e InfoEscolas:** são úteis, mas secundárias. Podem ser reavaliadas na Fase B.
