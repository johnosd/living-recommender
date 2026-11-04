# Research — ingestão CAOP

## R1. Publicação e contrato da fonte

**Decisão:** cadastrar os três downloads da CAOP2025 (Continente, RAA e RAM) como URLs configuráveis, com `version=2025`, `reference_period=2025` e `license_id=CC-BY-4.0`; confirmar o aviso/licença no momento da execução e não codificar URLs no coletor.

**Justificativa:** a [página oficial da DGT](https://www.dgterritorio.gov.pt/atividades/cartografia/cartografia-tematica/caop) publica a edição 2025 e três GeoPackages. A [página de dados abertos](https://www.dgterritorio.gov.pt/dados-abertos) declara CC BY 4.0 para downloads do Centro de Dados. A edição é 2025 embora a aprovação/publicação tenha ocorrido em 2026: não confundir versão, data de publicação, coleta e processamento.

**Alternativas:** descobrir dinamicamente o último link na página a cada run tornaria o coletor dependente do HTML. Manter links no catálogo torna a mudança auditável.

**Incerteza a fechar no início de US1/US2:** inspecionar um arquivo real de cada região com `pyogrio.list_layers` e ler os campos/CRS; o modelo [conceitual](https://github.com/dgterritorio/caop/blob/master/documentacao/docs/modelo_de_dados.md) e de [implementação](https://github.com/dgterritorio/caop/blob/master/documentacao/docs/implementacao_modelo.md) não substitui a inspeção do GeoPackage distribuído. Registrar o mapeamento constatado no código e numa fixture sintética, sem versionar o download real.

**Revisão do catálogo (2026-11-04):** a página oficial da DGT ainda apresenta a CAOP2025 e os três links GeoPackage usados em `config/sources.yml`: `CAOP_Continente_2025-gpkg.zip`, `CAOP_RAA_2025-gpkg.zip` e `CAOP_RAM_2025-gpkg.zip`, sob `geo2.dgterritorio.gov.pt/caop/`. A [página de dados abertos da DGT](https://www.dgterritorio.gov.pt/dados-abertos) informa CC-BY 4.0 e exige menção à DGT. Esta revisão confirma URLs e metadados de publicação, não o schema interno nem a validade dos bytes dos três arquivos; essa inspeção permanece para T011.

**Inspeção real T011 (2026-11-04):** os três ZIPs oficiais foram baixados para `.data/caop-inspection/` (ignorado pelo Git). O ZIP dos Açores contém **dois** GeoPackages. `pyogrio.list_layers`/`read_info` confirmou:

| Arquivo | Camadas de município/freguesia | CRS | Municípios | Freguesias |
| --- | --- | --- | ---: | ---: |
| Continente_CAOP2025.gpkg | `cont_municipios` / `cont_freguesias` | EPSG:3763 | 278 | 3049 |
| ArqAcores_GCentral_GOriental_CAOP2025.gpkg | `raa_cen_ori_municipios` / `raa_cen_ori_freguesias` | EPSG:5015 | 16 | 144 |
| ArqAcores_GOcidental_CAOP2025.gpkg | `raa_oci_municipios` / `raa_oci_freguesias` | EPSG:5014 | 3 | 12 |
| ArqMadeira_CAOP2025.gpkg | `ram_municipios` / `ram_freguesias` | EPSG:5016 | 11 | 54 |

As camadas têm `dtmn`/`municipio` e `dtmnfr`/`freguesia`, respectivamente, mais `distrito_ilha`; os códigos são texto. Total observado: 308 municípios e 3259 freguesias. **Divergência de aceite para US2:** 18 `dtmnfr` do Continente terminam em letras (`0302FA`–`0302FN`, `0308FA`–`0308FE`); são códigos da própria fonte e aparecem no [Despacho n.º 660/2025](https://files.diariodarepublica.pt/2s/2025/05/097000000/0002500132.pdf). `schema.py` valida seis caracteres com quatro dígitos iniciais e dois alfanuméricos finais, preservando esses códigos. A exigência de `dicofre` estritamente de seis dígitos em US2/AC1 e `data-model.md` precisa de decisão antes da transformação; não descartar nem inventar códigos.

## R2. Normalização geoespacial

**Decisão:** usar GeoPandas/Pyogrio para ler os GeoPackages, inspecionar CRS, agrupar polígonos por código e calcular áreas em CRS métrico apropriado à região. Obter o ponto com `representative_point()` no polígono dissolvido e transformar esse ponto para WGS84. Guardar a geometria de verificação no staging Bronze; expor apenas atributos, área e ponto na Silver. O normalizador Python é uma etapa de preparo do formato geográfico; dbt-duckdb executa os modelos de Bronze/Silver e os testes.

**Justificativa:** a [documentação do GeoPandas](https://github.com/geopandas/geopandas/blob/main/doc/source/docs/user_guide/data_structures.rst) distingue `representative_point()` do centroide e garante que o ponto fica no polígono. O [modelo DGT](https://github.com/dgterritorio/caop/blob/master/documentacao/docs/implementacao_modelo.md) descreve CRS separados para Continente, Madeira e grupos dos Açores; os EPSG efetivos devem ser lidos dos arquivos. Calcular `area` em WGS84 produziria graus quadrados.

**Alternativas:** centroide geométrico pode cair fora de multipolígonos; calcular tudo em um único CRS métrico perde adequação regional. Um pipeline PostGIS contraria o motor já escolhido no ADR-001.

## R3. dbt e materialização

**Decisão:** configurar dbt Core + dbt-duckdb para ler o Parquet preparado localmente, executar staging Bronze e dimensões Silver, materializadas em Parquet. Selecionar explicitamente o último manifest `changed` válido, em vez de descobrir arquivos pelo maior nome de pasta. O build local trabalha em área temporária e só promove saídas Silver após `dbt build` e validação geoespacial.

**Justificativa:** o [adapter dbt-duckdb](https://github.com/duckdb/dbt-duckdb/blob/master/README.md) lê Parquet externo e oferece materialização `external`; esta não é incremental. O [dbt](https://docs.getdbt.com/docs/build/data-tests) oferece testes de chave e relacionamento. Reprocessamento completo é aceitável para o volume previsto no ADR-001.

**Alternativas:** dimensão incremental/histórica traz `valid_from`/`valid_to` que a spec explicitamente exclui.

## R4. S3 e falhas

**Decisão:** baixar e validar tudo antes de gravar `raw/`; usar prefixo exclusivo por `run_id`, escrita sem sobrescrita, manifest `changed` como marcador de conclusão e limpeza de objetos do run se uma falha capturada ocorrer. Antes do download, testar permissões de escrita e remoção em prefixo de prova separado. No S3, um crash pode deixar objetos órfãos sem manifest; o leitor deve ignorá-los e a operação de recuperação deve removê-los.

**Justificativa:** S3 não oferece transação atômica para vários objetos. O [SDK Boto3](https://github.com/boto/boto3/blob/develop/docs/source/guide/quickstart.rst) permite gravação de objeto; a verificação do bucket, por si só, não demonstra permissão de escrita. O contrato da spec exige que falhas tratadas não deixem arquivos parciais; a visibilidade lógica depende de manifest `changed`.

**Alternativas:** gravar diretamente durante o download expõe arquivos incompletos; usar só `head_bucket` não prova escrita. Uma cópia de três objetos no S3 também não é uma operação atômica.
