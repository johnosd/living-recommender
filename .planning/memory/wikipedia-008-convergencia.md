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

## Execução posterior — T037–T039 corrigidas

O veredito pendente acima é histórico. Código corrigido em 3574232 no mesmo
PR #9; spec/backlog Implementada, 46/46. Guard persistente do SO protege a
recuperação/liberação do JSON; não remover .locks/wikipedia.guard. Regressão
com dois processos reais validada no Windows e no Linux. No Windows, obter o
PID por os.getpid() no trabalhador: Popen.pid pode ser o launcher do ambiente.

Cobertura Parquet/CSV contém official_name da dimensão congelada por DICO,
incluindo ausência/pendência/falha. Schema wikipedia-parquet-2; dbt confere nome.
WikipediaError vem de errors.py e continua disponível pelo handler, subclasse
de ValueError; erros de entrada/estrutura conservam a causa original.

Evidências novas: 554 testes completos/473,34 s; área 112/10,70 s; Ruff,
cinco contratos e oito travas; dbt fixture/nacional: 5 modelos + 31 testes.
Build 20261120T225853282336Z-1a5fa083 promoted/118,476 s, 308 nomes corretos
e textos idênticos; repetição 20261120T230129034273Z-909ab812 unchanged/107,599 s,
bytes/mtime dos 11 arquivos vigentes iguais. Preservados 1.938 arquivos e
616 raw, sem nova coleta. Recibos phase8-*.json na pasta privada de provas.

CI do código corrigido: run 44833850654, SHA
35742325ea4e62751d30063f796ac9dd9ae73bcb, quality/secrets verdes, 553 testes
e 1 skip Windows no Linux/229,68 s, sete builds isolados, nenhum segredo.
CI do fechamento documental acompanha o head final do PR. Próximo: nova
sdd-converge para auditar as correções; não foi executada automaticamente.

## Segunda convergência — limpa

Auditoria de 2026-11-20 no SHA 19666659bc151e2b64803207fec4462e8466088f:
C-001/T037, C-002/T038 e C-003/T039 resolvidas, sem novas lacunas. Spec/backlog
Convergida, 46/46; tasks.md preservado byte a byte (SHA-256
0fdcbc1a37947bbed3acF4bd39d2eecA3aedc43938a1cb2ebe33869da517bfcf).
Resultado Final anexado ao plano; README atualizado cirurgicamente.

Verificação nova: 39 testes direcionados, Ruff, cinco contratos sem skips e
oito travas íntegras. CI exato run 44834787238 quality/secrets aprovado,
553 testes/um skip Windows no Linux, sete builds e gitleaks sem segredos.
Reconferidos 308 textos por folhas/seções, 308 nomes oficiais Parquet/CSV,
616 referências brutas e 1.938 arquivos protegidos. Assinatura vigente igual
à do código auditado. Nenhuma recoleta ou alteração de código/dados/legado.
O PR #9 permanece sobre feature/007, sem merge; os checks do novo fechamento
documental devem ser conferidos no SHA final, sem substituir a prova do código.
