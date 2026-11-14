# Importação de snapshots manuais do Idealista — Implementation Plan

**Slug**: `005-importacao-idealista-manual` | **Date**: 2026-11-13 | **Spec**: `spec.md`

**Goal:** importar a extração manual 202508 e preparar anúncios únicos rastreáveis.
**Architecture:** cópia validada em raw, normalizador Python, modelos dbt-duckdb
externos em Bronze/Silver e promoção por caminhos após os testes. Operação local.
**Tech Stack:** Python 3.12, pandas/pyarrow, PyYAML, dbt-duckdb, pytest e ruff existentes.
**Execution:** sdd-execute e executing-plans, em sequência na mesma sessão autorizada.

## Summary
O usuário aprovou o desenho de copiar a extração manual, registrar manifest,
normalizar e resolver os territórios. Não criar scraper nem acessar a rede.
Abordagens: cópia solta foi rejeitada por não oferecer repetição rastreável;
API foi adiada pelo autor; importador de pasta foi o fluxo aprovado.

## Technical Context
Storage existente LocalStorage/S3Storage para importação; build somente local.
Reutilizar normalize_name, load_catalog, file_digest e promote_paths. O manifest
CAOP exige três regiões, portanto esta fonte precisa de manifest próprio.
Escala medida: 324 JSON, 17.472 ocorrências, 16.117 IDs, 16.566.429 bytes.
Sem dependências novas, recurso pago ou custo recorrente externo.

## Decisões Invariantes
- D1: mês YYYY-MM obrigatório; collected_at_utc nulo, imported_at_utc separado.
- D2: validar cópias temporárias de todos os arquivos antes de gravar raw;
  manifest changed é o commit do lote. Mesmo mês/conjunto de caminhos e hashes é unchanged.
- D3: raw preserva bytes/subpastas e contém todas as ocorrências. Links, imagens,
  descrições e anunciante não passam à base normalizada; nenhum anúncio publicado.
- D4: primeira ocorrência ordenada por caminho e posição é canônica; demais são
  auditadas. Preço/área/tipologia diferentes marcam conflito sem escolher maior/menor.
- D5: divergência municipal entre duplicatas mantém DICO/DICOFRE nulos com
  locality_level=conflict. Divergência só de freguesia remove apenas DICOFRE.
- D6: região das ilhas só por seed explícita. Municípios exatos normalizados e
  únicos são aceitos; exceções e freguesias de Lisboa vêm de seed por região/arquivo.
  Freguesia do título só casa por nome completo ou sinônimo no mesmo DICO.
- D7: promover somente lake/bronze/idealista_occurrences,
  lake/silver/idealista_listings e lake/bronze/idealista_reports. Agregados ficam para depois.
- D8: importação não decide se uma extração manual é completa. Contagens e cobertura
  ficam visíveis; este build não publica nem substitui qualquer versão do produto.

## Constitution Check
| Princípio | Pré-Design | Pós-Design | Evidência |
| --- | --- | --- | --- |
| I Segredos | PASS | PASS | sem chave, fixture sintética, raw ignorado |
| II Núcleo estático | PASS | PASS | nenhuma API em tempo de uso |
| III Dados honestos | PASS | PASS | nulos, CAOP, período, conflitos e cobertura |
| IV Coleta responsável | PASS | PASS | catálogo, manual, risco já aceito ADR-002 D4 |
| V Bruto imutável | PASS | PASS | hashes, unchanged e promoção por caminho |
| VI Privacidade | PASS | PASS | sem publicação e sem dados reais no Git |
| VII Custo | PASS | PASS | execução local, custo externo zero |

## Project Structure
- pipelines/collectors/idealista/{snapshot,normalize,territory,prepare}.py
- pipelines/cli/{import_idealista_snapshot,build_idealista}.py
- config/sources.yml; analytics/dbt/seeds/{idealista_file_localities,parish_synonyms}.csv
- analytics/dbt/models/idealista/; analytics/dbt/tests/idealista_*.sql
- tests/contracts/test_idealista_import_contract.py; tests/unit/test_idealista.py;
  tests/integration/test_idealista_build.py; tests/fixtures/idealista/
- sdd/specs/005-importacao-idealista-manual/; docs/runbooks/coletas.md

## Complexity Tracking
Sem nova decisão arquitetural. Regional com DICO nulo é exceção explícita de
nível territorial, não associação municipal inventada; não entra no agregado municipal.

## Estratégia de Testes
Contratos primeiro, depois unitários de normalização/território e integração dbt.
Fixture sintética sem rede. Execução real e hashes são evidência local distinta do CI.

```powershell
uv run --locked python -m pytest -q --basetemp .data/test-tmp-idealista tests/contracts/test_idealista_import_contract.py tests/unit/test_idealista.py tests/integration/test_idealista_build.py
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 005-importacao-idealista-manual
```

### Testes de Contrato
Cinco casos em tests/contracts/test_idealista_import_contract.py; contagem Python
conferida pelo pytest (o script registra unknown). Mapeamento: US1 raw/unchanged
→ FR-001/002/003; lote inválido → FR-004; unique/typed/regional → FR-005/006/007/009;
unknown municipality → FR-007; tampered raw → FR-008. Vermelho esperado nos cinco:
NotImplementedError do stub import_snapshot. Stubs prepare/snapshot não travados.

## Review Focus
Pasta vazia e tipos inválidos; repetição com arquivo removido; nomes territoriais
ambíguos e ilhas; conflito de ID/preço/território; falha dbt/tamper preservando base.

## Estado Atual

| Área | Estado |
| --- | --- |
| US1 | Concluída: importador, catálogo, CLI local/S3 simulado |
| US2/US3 | Concluídas: normalização, CAOP, duplicatas, dbt e relatórios |
| Execução real | Importação/build e hashes concluídos; 324 originais e 16 arquivos anteriores preservados; 24 passos dbt verdes |
| Validação final local | ruff limpo; suíte completa 350/350; 24 passos dbt reais e 24 sintéticos; cinco travas íntegras |
| CI remoto | Não executado nesta sessão |

## Riscos e Decisões

| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |
| R-001 | snapshot antigo | não representa preço atual | Resolvido: período 2025-08 explícito |
| R-002 | arquivo insular regional | sem município comprovado | Resolvido: seed e nulos |
| R-003 | duplicatas conflitantes | escolha não prova recência | Resolvido: ordem estável e relatório |
| R-004 | termos do Idealista | restrição de reutilização | risco já aceito ADR-002 D4, sem publicação |
| R-005 | Manifest alterado/truncado | perda silenciosa de registros | Resolvido: validar inventário, caminhos únicos, total e fingerprint antes da seleção |
| R-006 | Ordenação textual de horário UTC | lote vigente errado com frações de segundo | Resolvido: comparar datetime UTC; regressão reproduzida antes do ajuste |
| R-007 | Destino dentro da origem | manifest de falha poderia alterar origem | Resolvido: rejeitar overlap antes de criar storage/manifest; regressões função e CLI |
| R-008 | dbt-duckdb external insere linha nula em resultado vazio | consumidores Parquet veriam anúncio fantasma | Resolvido: conferir exportações e substituir somente o placeholder vazio pelo Parquet tipado de zero linhas, após os testes dbt; integração verde |
| R-009 | Falhas na primeira tentativa de suíte | catálogo alterado durante uma execução em curso | Resolvido: Não é baseline: execução descartada como prova; gate final roda com código estável |
| R-010 | Teste antigo fixava as cinco fontes | suíte completa: 349 verdes e 1 falha causada pela sexta fonte | Resolvido: expectativa de test_real_catalog_and_existing_sources inclui idealista; 6 testes de catálogo verdes; suíte completa final 350/350 verdes |

## Execution Notes
| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |
| 2026-11-13 | Planejamento | Escopo aprovado no chat, spec/plano e cinco contratos; vermelho confirmado por NotImplementedError, trava gravada. Analyze sem bloqueio. | Implementação |
| 2026-11-13 | US1 | Importação de pasta, bytes preservados, mês, manifest e unchanged; local e S3/moto equivalentes. | Build |
| 2026-11-13 | US2/US3 | Normalização, seeds, deduplicação e conflitos, cobertura, testes dbt, promoção por caminho e rollback; 29 testes focados verdes antes dos 2 de importação/moto. | Execução real |
| 2026-11-13 | Revisão | Revisor independente encontrou R-005/006/007; reproduzidos e corrigidos com regressões. Detectado e corrigido R-008 no teste vazio. | Reverificação final |
| 2026-11-13 | Real | 324 JSON importados; 17.472 ocorrências, 16.117 IDs, 255 municípios, 189 regionais, 8.891 freguesias resolvidas; repetição unchanged. | Hashes conferidos |
| 2026-11-13 | Gate final | Suíte completa final: 350 verdes em 412,66 s; ruff limpo; 24 passos dbt reais e 24 sintéticos, cinco travas íntegras. Teste antigo de catálogo atualizado para seis fontes. | CI remoto e publicação fora desta execução |

**PRÓXIMO**: nenhuma task de implementação pendente. Convergência SDD e integração Git podem ser tratadas quando solicitadas; sem CI remoto, push ou publicação nesta sessão.

## Arquivos Principais
- pipelines/collectors/idealista/, pipelines/cli/import_idealista_snapshot.py e build_idealista.py.
- analytics/dbt/models/idealista/, seeds e testes; docs/runbooks/coletas.md.

## Cuidados para Retomada
- Não alterar a origem nem copiar cookies/scripts do projeto legado.
- Não tocar em contratos de outras features. Rodar dbt somente tag:idealista.
- Sem commit/push/publicação nesta execução; entrega revisável no workspace.

## Documentação técnica consultada

Via Context7: pandas-dev/pandas (Parquet e tipos anuláveis) e duckdb/dbt-duckdb (materialização external). O comportamento de tabela vazia foi confirmado também no external.sql do adapter instalado, linhas 70–145.

### Checkpoint de integridade e revisão

324 hashes origem/raw iguais; 16 arquivos anteriores do lake inalterados; 324 JSON raw após repetição unchanged. Evidência em .data/idealista-import-evidence-after.json. Revisão independente confirmou correções dos três achados e exportação vazia, sem novos achados. Lint passou; 31 testes focados passaram (29 de contrato/unitário/build e 2 de importação/moto).

### Checkpoint do gate final

O fluxo novo do CI foi executado localmente com a fixture e os artefatos isolados: 2 modelos e 22 testes dbt, PASS=24/WARN=0/ERROR=0. A suíte completa encontrou somente R-010 (349 verdes e 1 falha); o teste de catálogo foi atualizado, sem alterar produção nem contratos, e seus 6 casos passaram. Nova suíte completa em curso.


## Resultado da implementação

Implementada localmente em 2026-11-13. Todas as 12 caixas de tasks/release estão
concluídas. A segunda execução completa passou: `350 passed in 412.66s`;
`uv run --locked ruff check pipelines tests` passou. A implementação foi revisada
por um agente independente e os três achados foram corrigidos e reverificados.

Aceite: FR-001–004 → importação, contratos US1, unidade e S3/moto;
FR-005/006 → normalização/deduplicação, contratos e integração;
FR-007/009 → resolução CAOP, seeds e relatórios com cobertura/ausências;
FR-008 → inventário/checksums, falha dbt/tamper e preservação das saídas.
SC-001/002/003/005 → importação/build reais e inventário de hashes;
SC-004 → suíte de 350 testes e travas de contrato.

Prova local: 324 arquivos e 16.566.429 bytes copiados, 17.472 ocorrências,
16.117 IDs, 1.355 repetições, 255 municípios com amostra, 189 regionais,
8.891 freguesias resolvidas e 7.037 municipais sem freguesia. Nenhum conflito
nos campos normalizados. Origem e 16 arquivos anteriores do lake preservados.
Os anúncios continuam privados; o período é 2025-08. Sem agregados, publicação,
AWS real ou prova de CI remoto. Convergência formal não executada nesta sessão.


## Resultado Final

**Convergida em 2026-11-13**. Esta auditoria confrontou a implementação com
FR-001–009, SC-001–005, US1–US3, D1–D8 e a constitution. Nenhuma lacuna acionável
foi encontrada. `tasks.md` foi preservado byte a byte, sem nova fase ou task.

### Entrega confirmada

Importação manual parametrizada por pasta/mês, cópia imutável de JSON com
subpastas, manifest por run, validação de inventário e hashes, repetição unchanged,
normalização sem imputação, deduplicação determinística com todas as ocorrências
auditáveis, CAOP/seeds e regiões explícitas, cobertura e promoção dos três
diretórios da feature somente depois dos testes dbt. A coleta permanece fora
deste projeto e nenhuma chamada ao Idealista foi feita na auditoria.

### Evidência revalidada

- `check-prerequisites.ps1 -Stage converge -Slug 005-importacao-idealista-manual -Json`: PASS.
- `check-contract-tests.ps1 -Slug 005-importacao-idealista-manual`: trava íntegra; cinco contratos incluídos na seleção abaixo.
- `uv run --locked ruff check pipelines tests`: passou.
- `uv run --locked python -m pytest -q --basetemp .data/converge-005-tests tests/contracts/test_idealista_import_contract.py tests/unit/test_idealista.py tests/integration/test_idealista_build.py tests/integration/test_idealista_import.py tests/unit/test_climate_catalog.py`: **37 passaram em 19,33 s**, sem rede, incluindo build dbt sintético e S3/moto.
- A suíte completa **350/350**, executada no sdd-execute e registrada em Resultado da implementação, foi mantida como evidência anterior; não foi repetida nem apresentada como nova execução nesta auditoria.
- Parquet real: 17.472 ocorrências, 16.117 IDs únicos, 1.355 ocorrências excedentes, período 2025-08; contagens por ID batem entre Bronze/Silver.
- Os 324 JSON, 16.566.429 bytes e seus hashes batem entre raw, inventário da importação e a extração externa localizada atualmente. Os 16 arquivos preexistentes do lake mantêm seus hashes.
- Cobertura: 308 municípios no relatório, 255 com amostra, 189 anúncios regionais e 8.891 com freguesia resolvida. A soma da cobertura bate com os anúncios únicos. Coleta original continua sem horário presumido.
- O artefato do build real tem 24 passos aprovados (2 modelos e 22 testes dbt). Os dois builds sintéticos desta auditoria, inclusive snapshot vazio, também têm 24 passos aprovados cada.
- Cenários adicionais pela interface pública confirmaram D5: conflito municipal deixa DICO/DICOFRE nulos; conflito só de freguesia preserva DICO e remove DICOFRE. Não houve edição de código para executar esses cenários.
- Evidência local da auditoria: `.data/converge-005-evidence.json` (ignorada pelo Git).

### Desvios e decisões confirmados

As decisões acumuladas R-005–R-008/R-010 estão implementadas: inventário completo
do manifest, seleção por instante UTC, rejeição de origem/destino sobrepostos e
tratamento do placeholder nulo de exportação vazia. Esses ajustes preservam o
escopo e não introduzem coleta automática nem publicação. R-001–R-003 têm suas
mitigações confirmadas; R-009 é histórico de uma execução descartada, substituída
pela suíte completa válida registrada. R-004 permanece risco aceito de termos,
sem afirmar autorização de reutilização ou publicação.

### Origem externa e documentação

O caminho histórico `IdealistaScraper/Bases/202508` não está disponível atualmente.
A extração foi localizada em
`C:/Users/johns/Documents/Projetos/IdealistaScraper/.data/202508`, com **os mesmos
324 caminhos relativos e hashes**. Isso é mudança externa de localização, não
lacuna do importador, que aceita qualquer pasta. O manifest original não foi
alterado: `source_directory` conserva a proveniência histórica. O README recebeu
somente a orientação do caminho atual em `--directory`. Quickstart, runbook e
registros da execução anterior mantêm o caminho histórico; para repetir esses
comandos com o estado externo atual, substitua o argumento pelo caminho acima.

### Limites e gates externos

Convergida significa aderência do escopo local auditado, não publicação ou
aprovação de CI remoto. Permanecem externos: commit/PR e execução remota dos jobs
Python e gitleaks (Quality Gates 1 e I da constitution). A configuração desses
jobs foi conferida, mas não constitui prova remota. AWS real, agregados,
publicação e API oficial continuam fora desta entrega. O período de dados é
agosto/2025, não preços atuais. Não houve commit, push ou publicação na auditoria.
