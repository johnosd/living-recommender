# Lógica travada: coleta, seleção e território

## Coleta

```text
coletar(catalogo, storage, downloader, validator, run_id, agora, work_dir):
  validar entrada de catálogo e três URLs; checar destino antes de rede
  para cada região: baixar em work_dir com timeout/backoff; SHA-256; validar ZIP/GeoPackage/camadas/campos
  comparar par ordenado (região, sha256) com último manifest `changed`
  se igual: gravar manifest `unchanged` apontando à versão anterior; retornar
  gravar os três arquivos imutáveis no prefixo exclusivo do run
  gravar manifest `changed` somente depois das três gravações confirmadas
  em falha tratada: remover objetos raw deste run, gravar manifest `failed`, falhar comando
```

`--force-check` força a ida à fonte, não o status `changed`. Uma tentativa `failed`/`unchanged` nunca vira entrada da transformação. Em S3, um crash entre objetos pode deixar órfãos físicos sem manifest; nenhum leitor pode tratá-los como versão válida. Uma rotina de recuperação identifica e remove prefixos órfãos.

## Transformação

1. Selecionar o último manifest `changed` válido da CAOP (ordenar por `collected_at_utc`, desempatar por `run_id`) e verificar checksums dos três arquivos.
2. Descompactar em diretório temporário seguro, inspecionar as camadas do GeoPackage e aplicar o mapeamento confirmado da edição. Ignorar entidades auxiliares sem código territorial válido; nunca inventar códigos ou nomes.
3. Agregar todas as partes de cada freguesia por `dicofre`; associar o município pelo código/hierarquia oficial. Agregar polígonos municipais de suas freguesias ou usar geometria municipal oficial se presente e consistente. Se houver divergência, falhar e registrar o caso.
4. Calcular área no CRS métrico da região de origem. Para partes dos Açores que usam referenciais distintos, calcular por grupo antes de somar. Calcular `representative_point()` no polígono dissolvido e transformar o ponto para EPSG:4326; testar contenção contra geometria de origem. Converter m² para km².
5. Preservar `official_name`; `normalized_name = lower(sem_acento(trim(colapsar_espacos(nome))))`, sem usar nome como chave. Escrever Parquet de entrada, executar modelos dbt Bronze/Silver e testes dbt + verificação espacial. Só promover saídas após todos os testes passarem.

Não há histórico SCD2 nesta feature. O `source_run_id` liga cada dimensão ao bruto e separa versão da fonte de data de processamento.
