# Data Model: Censos 2021 por freguesia

## Catalog and collection

Fonte `censos` em `config/sources.yml`, publisher INE, responsável do projeto, licença CC-BY-4.0 com URL/atribuição verificadas, frequência por nova edição/revisão, nível freguesia. Campos da fonte seguem `get_dataset_source`; 201 datasets nacionais (2 metadados,102 lotes2025 e97 lotes2013), IDs estáveis por geografia/lote, sem incluir hora de coleta.

Dados principais: indicador `0014632`, geografia `2025`, 19 categorias (T + 18). Fallback: `0011719`, geografia `2013`, 20 categorias (T + 19). Cada família inclui um dataset `role=metadata`, `collection_method=http_download`, `format=json`, URL `pindicaMeta.jsp?varcd=<indicador>&lang=PT`. Dados: `role=data`, `api_json`, `api_url=pindica.jsp`, `params` completos incluindo `S7A2021`, lista explícita de até32 freguesias em Dim2, sexo T, todas as idades da família em Dim4 e nacionalidade T apenas no principal; `parish_codes`, `age_codes`, `metadata_dataset_id`, `reference_period`, `geography_version`.

`raw/source=censos/dataset=<id>/run_id=<run>/<id>.json`; `manifests/censos/<run>.json`. Manifest v2 preserva sha256 dos bytes e fingerprint semântico; entrada inclui URL real em `origin`, snapshot resolvido do dataset, assinatura dos seletores, edição/geografia e vínculo de metadados. O fingerprint inclui snapshot/seletores, mantendo DataExtracao como único campo volátil ignorado. `DataUltimaAtualizacao` de metadados e `DataUltimoAtualizacao` observado nos dados são lidos explicitamente, sem substituir edição 2021.

O catálogo congela códigos oficiais extraídos dos metadados das duas famílias em2026-11-13. A validação de cada resposta exige o produto cartesiano completo `parish_codes × age_codes`, sem duplicatas ou extras. O preparo exige que a união dos lotes coincida exatamente com todas as freguesias e idades declaradas nos metadados; códigos2025 devem coincidir com a CAOP vigente. Mudança de universo reprova até revisão explícita do catálogo. Snapshots anteriores com `age_code` singular/`lvl@6` continuam reconstruíveis sem consultar o catálogo atual. Não se fabrica JSON nacional concatenado: cada resposta original permanece separada em raw.

## Prepared and persisted tables

Entradas intermediárias em `.data/.build/censos/<uuid>/prepared/`; não são saídas vigentes.

### census_age_category — Bronze

Uma linha por `(indicator, source_age_code)` dos metadados selecionados. Campos: `dataset_id` do metadado, indicador, geografia, `source_age_code`, `label`, `age_min`, `age_max` (limites inclusivos, nulo para extremo aberto), `is_total`, `is_unknown`, versão classificatória, raw_key/sha256, run/coleta/processamento, licença e atribuição. Total tem limites nulos e is_total=true; idade ignorada só se existir oficialmente.

### census_observation — Bronze

Uma linha por `(dataset_id, source_dicofre, period, age_code)`. Campos: identificadores oficiais de origem, `indicator`, `geography_version`, `period=2021`, `age_code` oficial, limites/is_total, `value` BIGINT anulável, `value_status` em observed/suppressed/not_applicable/not_published, símbolo original, motivo, proveniência do bruto e metadado, assinatura de consulta, licença, atribuição, momentos e revisão da fonte. Não apagar as duas faixas antigas 85–89 e 90+ ao harmonizar.

### census_parish_observation — Silver

Uma linha por `(dicofre, period, age_code)` no universo vigente × categorias canônicas. Categorias canônicas: `T,0_4,5_9,10_14,15_19,20_24,25_29,30_34,35_39,40_44,45_49,50_54,55_59,60_64,65_69,70_74,75_79,80_84,85_plus` (19); havendo idade ignorada publicada, preservá-la como categoria adicional separada e documentada, sem usá-la nos recortes etários.

Campos: `dicofre`, `dico`, região derivada da dimensão, `caop_version`, `period`, `age_code` canônico, limites/is_total, `value`, `value_status`, `coverage_status` own/inherited/missing, `reason`, `source_dicofre`, geografia/indicador de origem, códigos das categorias originais (lista), `relation`, `partial_origin`, referências de observações/metadados/execuções/hashes/licença/atribuição, versão e hashes das dependências territoriais, coleta/processamento.

Na fronteira pública `align_censos`, `categories` é a lista já harmonizada; a saída respeita os códigos nela recebidos (as fixtures menores não precisam representar as 19 categorias nacionais). Herança pode diferir entre total e faixas: não exigir coerência por destino entre observações com suportes territoriais diferentes.

### census_coverage — Silver and reports

Uma linha por freguesia/categoria, reproduzindo status, motivo e proveniência da Silver; CSV legível em `lake/silver/census_reports/coverage.csv`, resumos por país/região/município em `summary.csv` e `readiness.json`. JSON inclui `ready`, `blockers`, `expected_observations`, `counts` (quantidade de observações own/inherited/missing), execuções selecionadas e evidência de compatibilidade. Resumos contam cobertura, sem somar valores herdados. Auditoria de origens sem destino em `orphans.csv`, mesmo vazio com cabeçalhos.

Saídas Parquet: `lake/bronze/census_age_category/data.parquet`, `lake/bronze/census_observation/data.parquet`, `lake/silver/census_parish_observation/data.parquet`, `lake/silver/census_coverage/data.parquet`. Diretório `census_reports` entra na mesma transação de promoção.

## Validation rules

- Chaves únicas, DICO/DICOFRE string oficiais, edição 2021, contagem inteira não negativa; observed exige valor, suppressed exige nulo e símbolo. Município precisa existir na dimensão municipal; freguesia de origem sem destino fica em auditoria, não é descartada.
- Metadados e dados precisam concordar em indicador/seletores/categorias. Coordenadas, nomes ou igualdade de população não substituem evidência territorial.
- Ausência de registro de uma consulta esperada é defeito; só criar not_published a partir de evidência oficial registrada. Não transformar omissão em ausência legítima.
- Reconciliação etária por território/geografia/indicador de origem: todas as faixas mutuamente exclusivas + ignorados = total, salvo regras estatísticas oficiais documentadas. Nunca comparar o total próprio 2025 com faixas herdadas da união como se tivessem o mesmo denominador.
- Faixa 85_plus do fallback pode somar 85–89 + 90+ do MESMO território, período e origem, sem supressão; isso é harmonização etária, não soma territorial. Se um termo é suprimido, preservar ausência/confidencialidade; não derivar por diferença do total.
- A cardinalidade exigida vem das dimensões/categorias selecionadas, não de uma constante 3.259. A preparação exige uma única versão CAOP compatível e evita misturar revisões incompatíveis da mesma família.
