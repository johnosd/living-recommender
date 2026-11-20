# Wikipedia 008 — convergência pendente (2026-11-20)

Auditoria do SHA `87903e94f54a7abae367cdf521466492491e58f2`, branch
`feature/008-ingestao-wikipedia`, PR #9 sobre feature/007. O aceite de execução
43/43 foi reaberto por três achados reproduzidos; agora são 43/46 itens.
Fonte da verdade: Phase 8 de `.sdd/specs/008-ingestao-wikipedia/tasks.md`.

- **C-001 / HIGH / T037:** `source_lock` remove o lock após checar o PID,
  sem tornar a recuperação órfã exclusiva. Dois chamadores podem ler o mesmo
  lock morto; A adquire outro e B apaga o lock ativo de A. Reprodução com
  interleaving controlado em raiz temporária permitiu dois proprietários
  simultâneos. FR-024 e D12 exigem exclusão mútua também nessa recuperação.
  Regressão existente de processo morto é sequencial e não cobre essa disputa.
- **C-002 / MEDIUM / T038:** US4/AC1 exige DICO e nome do município no
  relatório. Schema/CSV de cobertura não trazem official_name; canonical_title
  é o título do artigo. Obter nome da dimensão congelada por DICO para todos
  os estados; ajustar preparo/modelo/relatório e testes não travados.
- **C-003 / LOW / T039:** contrato público de extração, linhas 70–71, promete
  WikipediaError. extract_article lança ValueError nas validações, sem ser
  instância da classe pública. Corrigir preservando compatibilidade ValueError
  e testar consumidores que capturam WikipediaError.

Evidência confirmada nesta auditoria: cinco contratos verdes/0,36 s, oito
travas íntegras, 101 testes da área/8,66 s e Ruff aprovado. CI do SHA auditado:
run 44810598252, quality/secrets verdes, 542 testes/1 skip Windows no Linux e
sete builds isolados. Reconferidas 616 referências raw por bytes/SHA-256;
cobertura vigente 308 DICO únicos, 308 valid e 308 artigos. Nenhuma recoleta
nem alteração no código, no lake ou no legado foi feita por esta auditoria.

Próximo passo: sdd-execute para T037–T039, seguido de nova convergência.
As fases 1–7 e plan.md permanecem como histórico da execução anterior;
status vigente em spec/backlog: Convergência Pendente. Não declarar convergida
com base apenas nos testes/CI verdes anteriores a essas regressões.
