# Data Model

Manifest em manifests/idealista/<run>.json: schema_version, source_id, run_id,
source_run_id, status, snapshot_month/reference_period, collected_at_utc=null,
imported_at_utc, source_directory, publisher, responsible_party, collection_method,
license_id, attribution, snapshot_sha256, files[], records, error.
Cada arquivo: relative_path, key, sha256, bytes, records. Somente changed é lote vigente.

raw/source=idealista/snapshot=<YYYY-MM>/run_id=<run>/<caminho original>.
Bronze occurrences: identificador e ordem de origem, território, campos tipados e
proveniência. Silver listings: uma linha por listing_id com occurrence_count,
duplicate_count, has_conflict, conflict_fields e procedência da ocorrência escolhida.
Os campos comuns incluem source_id, snapshot_month, dico/dicofre, locality_level,
locality_raw, parish_match_method, typology, bedrooms, area_m2, asking_rent_eur,
quality_flags, source_run_id, raw_key, raw_sha256, source_row, collected_at_utc,
imported_at_utc, processed_at_utc, license_id, attribution e source_region.

Relatórios: summary.json, coverage.csv e duplicates.csv dentro de
lake/bronze/idealista_reports. Coverage contém todos os municípios CAOP, inclusive
sem amostra, e as regiões insulares explicitamente coletadas. Nenhum dado publicado.


## Tipos e regras

DICO/DICOFRE e IDs são strings, preservando zeros. Preço e área são Float64
anuláveis; quartos e posição de origem são Int64 anuláveis; has_conflict é booleano.
quality_flags e conflict_fields são listas textuais separadas por `|`, vazias
quando nenhum sinal existe. `occurrence_count` inclui a ocorrência escolhida;
`duplicate_count` é occurrence_count - 1. Linhas únicas são ordenadas por listing_id.

O summary também contém snapshot_sha256, raw_bytes, municípios esperados/com
amostra, regionais, conflitos territoriais, freguesias resolvidas e ausentes,
campos inválidos e os instantes de importação/processamento. O relatório CSV é
uma visão local de cobertura, sem estimar mediana nem sugerir amostra suficiente.

O diretório de relatórios inclui dbt_run_results.json para comprovar o gate local.
O manifest é validado integralmente antes da leitura: chaves dentro do snapshot,
caminhos sem repetição, SHA-256 válido, tamanho positivo, contagens inteiras não
negativas, total coerente e fingerprint recomputado. Ele detecta inconsistências
acidentais, não é uma assinatura criptográfica contra alteração deliberada.
