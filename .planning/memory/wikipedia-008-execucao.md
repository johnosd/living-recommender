# Wikipedia 008 — execução e entrega (2026-11-20)

- Implementados catálogo/CSV, HTTP serial identificado, raw/manifests próprios,
  coleta/retomada e build offline com cinco modelos dbt, cobertura, lock/journal.
- Curadoria por agente: 308 DICO/page IDs, evidência/escopo/URL/revisor. A coleta
  confirmou 308 artigos; nenhuma ausência presumida ou pendência técnica.
- Metadado query e parse oldid devem concordar. Evidência normaliza espaços junto
  à pontuação/parênteses e marcadores de citação. Raw/texto mantêm referências.
- O load_catalog despacha explicitamente para o validador próprio Wikipedia;
  sete fontes antigas mantêm seus contratos. Teste unitário da lista de fontes
  foi atualizado de sete para oito; nenhum teste travado foi editado.
- Parser explícito html.parser/Beautiful Soup 4.15.0. Containers de layout podem
  atravessar seções; folhas pertencem à seção atual, containers têm texto nulo.
  Auditoria reconstruiu exatamente os 308 textos (6.699.736 caracteres).
- 7.028 seções/248.931 blocos; 308 introduções, QIDs e ligações inglesas. Licença
  CC-BY-SA-4.0/atribuição; mídia, declarações Wikidata, EN, indicadores e publicação fora.
- Completo: 20261120T185614436452Z-061ad950; repetição: 20261120T190030045538Z-077e4eb3, 308 unchanged. Raw 616→616;
  build unchanged, lake idêntico; 616 hashes/bytes e 1.319 arquivos anteriores
  preservados, incluindo 308 TXT + notebook legados. Recibos em .data/receipts/wikipedia-proof/.
- Windows: consultar GetExitCodeProcess, pois handle de processo encerrado pode
  continuar válido. Teste encerra subprocesso abruptamente e recupera lock/journal.
- Builds fixam hashes de inputs/código/SQL. Edição durante a execução bloqueia
  promoção; primeiro candidato nacional demonstrou esse gate. Não editar durante provas.
- Gates locais: 543 pytest/433,90 s; Ruff; 5 contratos/8 travas; 5 modelos + 30
  testes dbt. Autor autorizou branch/commit/push/PR em 2026-11-20.
- Entrega: feature/008-ingestao-wikipedia, PR #9 sobre feature/007 em 42a5f59,
  preservando dependências anteriores. Implementação 5f8c72f6307d66c12afa4c2315aa86e6b16f91e7.
  Run 44809254508 aprovou quality/secrets, 542 testes/1 skip específico do
  Windows no Linux em 331,31 s, Ruff e sete builds isolados. Gitleaks sem segredos.
  https://github.com/johnosd/living-recommender/actions/runs/44809254508
- Status Implementada; 43/43 checkboxes, T035/release concluídos. CI do
  fechamento documental consultável nos checks do head final no PR. Recibo privado
  ci-implementation.json em .data/receipts/wikipedia-proof/. Próximo: sdd-converge.

Referências: .sdd/specs/008-ingestao-wikipedia/{plan,tasks,handoff}.md,
.docs/runbooks/coletas.md, config/wikipedia_articles.csv.
