# Feature Specification: Importação de snapshots manuais do Idealista

**Slug**: `005-importacao-idealista-manual`  
**Created**: 2026-11-13  
**Status**: Convergida

## Escopo

O autor aprovou importar `IdealistaScraper/Bases/202508`. A coleta continua manual
no projeto de origem. Incluído: cópia imutável de JSON e subpastas, manifest,
hashes, validação, normalização, deduplicação rastreável, resolução CAOP,
cobertura e execução real. Aceitar qualquer pasta indicada e mês explícito.
Fora de escopo: scraper, rede, alterações no IdealistaScraper, nuvem, API oficial,
agregados de aluguel, Gold, publicação, interface e preços atuais.

## User Scenarios & Testing

### US1 — Importar a extração manual (P1)
O operador indica pasta e mês. Os bytes originais são copiados sem alterar a
origem. Repetição idêntica é unchanged. JSON com lista vazia é permitido;
pasta sem JSON é inválida. Falha não substitui o lote completo anterior.

### US2 — Preparar anúncios únicos (P1)
Preço, tipologia e área viram campos tipados, preservando nulos. Uma linha por
ID e mês, com referência a todas as ocorrências e sinalização de conflitos.

### US3 — Conferir cobertura territorial (P1)
Município vem do arquivo; freguesia pode vir do arquivo de Lisboa ou do último
trecho do título, por casamento exato normalizado dentro do município.
Arquivos explicitamente regionais das ilhas continuam regionais. Freguesia
sem casamento gera aviso; município desconhecido reprova o build.

## Functional Requirements

- **FR-001**: DEVE copiar somente os JSON da pasta indicada, preservando bytes e caminhos relativos, sem editar ou mover a origem.
- **FR-002**: DEVE registrar fonte, responsável, método manual, licença/restrição, mês, instante da importação, run, contagem, tamanho e SHA-256 por arquivo. Hora de coleta desconhecida permanece nula.
- **FR-003**: DEVE detectar repetição por conjunto ordenado de caminhos e hashes, por mês; conteúdo diferente gera novo run sem sobrescrever raw. Falha não vira lote vigente.
- **FR-004**: DEVE validar lista de objetos com IDs não vazios e tipos de preço/tipologia/área, rejeitando JSON inválido, symlinks, caminhos inseguros e pasta vazia.
- **FR-005**: DEVE normalizar preço português sem multiplicações heurísticas, tipologia T0–T3/T4+ e área, preservando nulos e sinalizando valores não interpretáveis; manter quartos originais.
- **FR-006**: DEVE escolher uma ocorrência por ID e mês deterministicamente por caminho e posição, sem presumir recência, e manter todas as ocorrências e conflitos auditáveis.
- **FR-007**: DEVE usar CAOP e seeds. Regional declarado aceita DICO nulo; município desconhecido reprova; freguesia não resolvida fica nula e é contada. Divergência territorial entre duplicatas não pode inventar precisão.
- **FR-008**: DEVE verificar hashes antes do build e promover apenas tabelas desta feature após testes dbt. Falha preserva as saídas anteriores e as outras fontes.
- **FR-009**: DEVE gerar relatório legível de período, cobertura, ausências, duplicatas e conflitos. Anúncios individuais ficam locais, fora do Git e sem publicação.

## Key Entities
Snapshot mensal; arquivo; manifest; ocorrência; anúncio único; cobertura;
seed de correspondências de arquivos e seed de sinônimos de freguesias.

## Success Criteria

- **SC-001**: Preservar os 324 arquivos e 16.566.429 bytes de 202508 com hashes iguais aos da origem; repetir sem novos brutos.
- **SC-002**: 17.472 ocorrências geram 16.117 anúncios únicos e 1.355 ocorrências excedentes, todas auditáveis.
- **SC-003**: Nenhuma associação municipal por palpite; regionais e freguesias ausentes explícitos.
- **SC-004**: Testes sem rede de repetição, erros, nulos, conflitos, território e preservação de saída.
- **SC-005**: Período 2025-08 separado da importação atual; origem e outras fontes inalteradas.

## Clarifications

### Sessão 2026-11-13
- O autor informou que a coleta permanece manual e indicou a extração 202508.
- O autor aprovou com “faça isso” o fluxo de cópia, manifest, normalização, resolução e deduplicação; agregados ficam para depois.

## Assumptions
O período é informado pelo operador, não comprova a hora da coleta. As dimensões
CAOP locais existem. Nenhuma chamada externa é necessária.
