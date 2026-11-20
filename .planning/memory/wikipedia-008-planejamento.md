# Wikipedia 008 — decisões de planejamento (2026-11-20)

- Escopo aprovado: 308 municípios, português, introdução/texto completo por
  seções, revisão/atribuição e cobertura. EN/QID apenas como metadados;
  coleta/preparo locais. TXT legados ficam no outro projeto. Ver spec 008.
- O autor autorizou explicitamente uma exceção pontual à regra geral
  Disallow:/w/ do robots para query/parse na API oficial de leitura.
  Registro R-001/Constitution Check do plano; não pedir novamente para esse
  mesmo escopo. Não autoriza contorno de bloqueios nem scraping de páginas.
- API observada em 2026-11-20: prop=sections retorna aviso de depreciação;
  prop=tocdata funciona sem aviso, com tocdata.sections/hLevel/tocLevel.
  HTML tem div.mw-heading e heading do índice; não percorrer todos os h2
  como se fossem seções editoriais. Ver research.md R2/R3 e lógica 008.
- Validador genérico api_json exige indicator; manifest v2 não tem ausência
  editorial. Planejado validador/estado próprios Wikipedia, sem mudar sete
  fontes convergidas. Snapshot congelado por ciclo, tentativa recente
  separada do conteúdo válido, preparo offline e journal de promoção.
- Cinco contratos/fixtures dedicados travados, três stubs públicos sem
  implementação. pytest confirma cinco falhas por NotImplementedError;
  63 testes existentes e Ruff global passaram; oito travas íntegras.
- O verificador PowerShell calcula hash Python, mas contagem fica unknown;
  pytest/AST confirmam cinco casos sem skip/xfail/parametrização.
- Não houve coleta nacional, build novo no lake real, dependência instalada,
  commit/push/PR ou implantação. Planejamento não é aceite da ingestão.

Referências: `.sdd/specs/008-ingestao-wikipedia/{spec,plan,tasks,research}.md`,
`logic/coleta-e-texto.md`, `contract-tests.lock` e relatório
`.docs/reports/wikipedia-legado-oportunidades-2026-11-20.md`.
