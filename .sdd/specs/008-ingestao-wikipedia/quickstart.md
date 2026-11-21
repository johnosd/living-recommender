# Quickstart — Wikipedia

Os comandos de coleta, build e fixture estão implementados. Os cinco contratos
passam localmente; a evidência nacional, a suíte final e o gate remoto têm estado
registrado em `plan.md`. Não executar notebook ou importar TXT.

## Preparar ambiente e conferir contratos

PowerShell na raiz `J:/living-recommender`; Python 3.12 e uv. Usar o ambiente
do projeto, sem `--active` mesmo que VIRTUAL_ENV aponte para outro repositório.

```powershell
uv sync --locked
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -q --basetemp .data/tmp/wiki-contracts
uv run --locked python -m pytest tests/unit tests/integration -k wikipedia -q --basetemp .data/tmp/wiki-area
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .planning/scripts/powershell/check-contract-tests.ps1 -Slug 008-ingestao-wikipedia
```

Esperado: cinco contratos verdes, trava íntegra e testes complementares verdes.
Conferir também as sete travas anteriores. O histórico do vermelho por
NotImplementedError permanece registrado no plano; não regravar a trava.

## Fluxo inteiramente offline

Raiz de fixture nova, separada da `.data` real:

```powershell
uv run --locked python -m tests.fixtures.wikipedia.ci_seed --root .data/ci-wikipedia
uv run --locked python -m pipelines.cli.build_wikipedia --local --root .data/ci-wikipedia
```

Conferir cinco tabelas, CSVs/readiness e dbt_run_results; as cinco saídas SQL
e os testes da tag devem passar. Simular dados ausentes, duplicatas, checksum
inválido, revisão divergente e seção atravessada: diagnóstico/reprovação sem
substituir lake válido. Testar morte/interrupção em promoção com journal em
raiz descartável; recuperar antes de novo build. Não usar raiz real como fixture.

## Preparar prova real

Confirmar dimensão CAOP com 308 DICO; `config/wikipedia_articles.csv` completo,
curado e sem pending_review; contato identificável e fonte cadastrada.
Revalidar direitos/atribuição e orientação operacional. A exceção R-001 já
foi autorizada: não perguntar de novo para o mesmo escopo; parar se houver
bloqueio real ou mudança das condições, sem contorno.

Antes do primeiro comando, guardar em `.data/receipts/wikipedia-proof/` o
inventário/hash dos arquivos raw/manifests/lake existentes, sem imprimir
conteúdo individual nem modificar arquivos. Guardar os hashes dos dois
relatórios de auditoria e dos artefatos SDD que devem permanecer intactos.
Não varrer `.env`, credenciais, bancos abertos ou arquivos fora do escopo.

```powershell
uv run --locked python -m pipelines.cli.collect_wikipedia --local --root .data --max-municipalities 5
uv run --locked python -m pipelines.cli.collect_wikipedia --local --root .data --resume-run-id <run-do-lote>
uv run --locked python -m pipelines.cli.build_wikipedia --local --root .data
```

Lote retorna 2 com pendências explícitas; retomar com ID real retornado. Se
houver rate-limit com prazo longo, aguardar o retry_at antes de retomar.
Completar até 308/308 contabilizados, sem falha/identidade pendente. Ausência
editorial precisa de evidência individual; não é aceitação de coleta incompleta.

## Repetição e histórico

```powershell
uv run --locked python -m pipelines.cli.collect_wikipedia --local --root .data
uv run --locked python -m pipelines.cli.build_wikipedia --local --root .data
```

A segunda coleta verifica a fonte, não usa cache eterno. Conteúdo equivalente
reutiliza raw e build não altera lake. Se uma revisão real mudou, não forçar
unchanged: documentar diferença e usar cenário controlado para provar
idempotência. Registrar os dois resultados e hashes, distinguindo verificação
da coleta que originou o conteúdo. Falha recente preserva dados anteriores,
mas o build padrão não a trata como atualização concluída.

Para investigar conscientemente um run completo anterior:

```powershell
uv run --locked python -m pipelines.cli.build_wikipedia --local --root .data --run-id <run-completo>
```

A saída deve informar seleção antiga e última tentativa; não declarar que
resolveu a falha atual. Não apagar locks/backups de processo interrompido
sem conferir PID, journal e hashes. A recuperação não pode remover dados vizinhos.

## Gate final

```powershell
uv run --locked python -m pytest -q --basetemp .data/tmp/wiki-final
uv run --locked ruff check pipelines tests
```

Conferir regressões dos cinco homônimos do legado; introdução original,
vários parágrafos/listas e referências; nenhuma mistura de religião/população
ou município/freguesia; contagem de nós/índice completa e arquivos de outras
fontes idênticos. Atualizar `.docs/fontes_de_dados.md`, runbook e README.
CI remoto do SHA final e scan de segredos são gates separados, no fluxo de
entrega autorizado; prova local não os substitui. Sem hardware, browser,
provedor pago, AWS real ou publicação necessários neste escopo.
