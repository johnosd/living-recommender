# Modelo de dados — CAOP vigente

## Fonte catalogada

`config/sources.yml`: `id=caop`, publicador DGT, contato/identificação do projeto, `license_id`, `collection_method=http_download`, frequência anual/sob demanda, nível territorial, versão, período de referência e mapa de URLs `{continente, acores, madeira}`. URLs e versão são dados de configuração revisados quando a DGT publica nova edição.

## Execução e manifest

`run_id` único por tentativa; `collected_at_utc` em UTC; `status ∈ {changed, unchanged, failed}`. Um JSON em `manifests/caop/<run_id>.json` inclui `schema_version`, `source_id`, `source_url` (mapa por região), `source_release_date` ou versão, `reference_period`, `collection_method`, `license_id`, `files[{key, sha256, bytes, record_count?}]`, `error`. `unchanged` registra a verificação, mas não cria novos arquivos `raw`. `failed` não é candidato à transformação. A data de processamento pertence à execução da transformação e não define a versão da CAOP.

## Raw

Três arquivos originais, sem alteração de bytes, em `raw/source=caop/version=<ano>/run_id=<id>/<regiao>.gpkg.zip`. O manifest `changed` é a referência para leitura; prefixos sem esse manifest são órfãos, não versões válidas. O mesmo layout de chaves existe sob `.data/` e no bucket S3.

## Bronze

`lake/bronze/stg_caop_municipalities/` e `lake/bronze/stg_caop_parishes/` em Parquet. Contêm códigos como texto, nomes oficiais, região/distrito, geometria de verificação (WKB ou representação equivalente), CRS original e os campos de proveniência (`source_run_id`, `caop_version`, `reference_period`, `license_id`). O normalizador lê GeoPackages e produz Parquet intermediário para dbt; dbt valida/materializa o staging Bronze. O mapeamento de camadas e colunas é fechado após inspecionar a edição real, conforme `research.md` R1.

## Silver

- `dim_municipality`: `dico` texto de 4 dígitos e único; `official_name`, `normalized_name`, `district_or_island`, `autonomous_region` (nulo no continente), `area_km2` positiva, `representative_lat`, `representative_lon`, `caop_version`, `source_run_id`, `reference_period`, `license_id`.
- `dim_parish`: `dicofre` texto de 6 caracteres e único (`[0-9]{4}[0-9A-Z]{2}`), copiado do `dtmnfr` oficial sem converter os sufixos alfanuméricos; `dico` texto de 4 dígitos, os mesmos campos de nome/território/área/ponto/proveniência, e `parish_type` quando a fonte informar.

Cada dimensão contém apenas a edição vigente selecionada. Não há colunas `valid_from`/`valid_to`, crosswalk, sinônimos nem modelos Gold nesta feature. A geometria original/dissolvida é mantida no staging para provar que o ponto representativo está dentro do território; não é publicada.

## Integridade

308 municípios; uma linha por `dicofre` distinto válido na edição; unicidade e formato das chaves; `dicofre[:4] == dico`; cada freguesia referencia município existente; área positiva; nomes e ponto não nulos; ponto dentro do polígono, inclusive multipartes; nomes homônimos discriminados por código/região. Falha de qualquer teste impede promoção do resultado Silver.
