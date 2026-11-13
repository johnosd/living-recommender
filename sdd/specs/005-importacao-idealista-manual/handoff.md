# Handoff: 005-importacao-idealista-manual

## Contexto
Implementada localmente em 2026-11-13, branch feature/005-importacao-idealista-manual.
Arquivos modificados/novos ainda não commitados; não há alterações preexistentes
misturadas nesta execução. Nenhum dado real foi incluído no Git.

## O que a feature entrega
US1: importação manual de pasta imutável e rastreável, local/S3 simulado.
US2: anúncios tipados únicos, preservando todas as ocorrências e conflitos.
US3: CAOP, seeds explícitas e cobertura; ilhas regionais sem DICO inventado.

## Leitura obrigatória
spec.md, plan.md (estado, riscos e evidência final), tasks.md, data-model.md,
contracts/idealista-cli.md, quickstart.md e docs/runbooks/coletas.md.

## Testes de contrato
Cinco casos em tests/contracts/test_idealista_import_contract.py, travados e verdes.
Conferir com check-contract-tests.ps1 -Slug 005-importacao-idealista-manual.
Travas das features 001–004 também permanecem íntegras. Suíte completa final:
350 passed in 412.66s. Lint passou. Dois modelos e 22 testes dbt passaram tanto
na fixture executada localmente quanto no build real. CI remoto não executado.

## Stubs
Nenhum stub pendente. snapshot.py, normalize.py, territory.py e prepare.py
implementados; CLIs import_idealista_snapshot e build_idealista operacionais.

## Armadilhas
Origem nunca pode se sobrepor ao destino. Último changed é selecionado por
instante UTC real, não texto. Validar inventário/total/fingerprint além do raw.
dbt-duckdb external injeta uma linha NULL para schema vazio: _verify_exports
remove somente esse placeholder comprovado antes da promoção. Não rodar dbt
sem seleção; não trocar lake/silver inteiro. Importação não prova completude
mensal nem qualidade de mercado. Coleta continua manual no outro repositório.

## Pendências
Nenhuma task de implementação. Dados de agosto/2025, não preços atuais.
Sem commit/push, CI remoto, AWS real, agregados ou publicação. Próximo estágio
formal, se solicitado: sdd-converge 005-importacao-idealista-manual.
