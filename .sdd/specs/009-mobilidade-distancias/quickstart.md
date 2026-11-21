# Quickstart — Mobilidade (spec 009)

Verificação manual e offline. **Nenhum passo desta página usa chave real nem rede.** A coleta real do Google
é do autor (seção 4).

## 1. Pré-requisitos

- `uv sync --locked`; branch `feature/009-mobilidade-distancias`.
- `.data/lake/silver/dim_municipality/data.parquet` (CAOP) para os passos reais; o fixture dispensa isso.

## 2. Checagens automatizadas

```powershell
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
uv run --locked python -m pytest tests/contracts/test_mobility_contract.py -q --basetemp .data/tmp/mobility-contracts
powershell -NoProfile -Command "& .\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 009-mobilidade-distancias"
uv run --locked python -m tests.fixtures.mobility.ci_seed --root .data/ci-mobility
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:mobility
```

Esperado: lint limpo, suíte verde, contratos 5/5, trava íntegra, dbt verde.

## 3. Cenário offline ponta a ponta (fixture)

1. Estimar, sem chave:
   `uv run --locked python -m pipelines.cli.collect_mobility --local --root .data/ci-mobility --catalog .data/ci-mobility/catalog.yml`
   Esperado: pares, elementos por modo, teto, custo estimado e pior caso; **zero** chamadas de rede.
2. Tentar gastar sem chave: acrescentar `--execute --confirm-elements <N>`. Esperado: recusa citando
   `GOOGLE_ROUTES_API_KEY`, sem valor nenhum.
3. Construir: `uv run --locked python -m pipelines.cli.build_mobility --local --root .data/ci-mobility`.
   Esperado: linhas `straight_line` para todos os pares; os pares de carro `pendente`.
4. Conferir `lake/bronze/mobility_coverage.csv`: as quatro contagens somam o `expected` de cada modo e polo.

## 4. Coleta real (gate do autor — não faz parte desta feature)

Faça nesta ordem; o comando recusa se algo faltar.

1. Aprovar `config/poles.yml` (FR-003): confirmar a lista e as coordenadas dos aeroportos (`source_ref`).
2. Conferir a tabela de preços e a cota gratuita da Routes API (Compute Route Matrix, `DRIVE` com `TRAFFIC_UNAWARE`) na
   página oficial; atualizar `pricing` e preencher `pricing_verified_on` no catálogo.
3. (Só se habilitar `modes.transit`, hoje desabilitado) atualizar `departure_time` para uma terça-feira útil a até 90 dias, às 08:00 de Lisboa.
4. Criar a chave no Google Cloud: restringir à Routes API, definir orçamento e alerta; guardá-la em `.env`
   (`GOOGLE_ROUTES_API_KEY=...`), que o Git ignora. **Nunca** colar a chave em arquivo versionado, chat ou issue.
5. Estimar: `collect_mobility --local --root .data`. Conferir o total de elementos (~1.404) e o custo.
6. Executar: `collect_mobility --local --root .data --execute --confirm-elements <o número da estimativa>`.
   Se a cota acabar, rode o mesmo comando depois; ele consulta só os pendentes.
7. Construir e auditar: `build_mobility --local --root .data`; ler `mobility_coverage.csv` e
   `mobility_no_route.csv`. `sem_rota` é raro no carro; ilhas sem ligação por estrada são esperadas. Nunca preencha com valor de outro modo.
8. Apagar a chave do `.env` e revogá-la no Google Cloud ao terminar (cálculo único).

## 5. Itens cross-cutting (constitution)

- [ ] Nenhuma chave em Git, fixture, log, manifest, stdout ou erro (`git grep AIza` vazio).
- [ ] `config/sources.yml` e `.docs/fontes_de_dados.md` refletem a fonte, o risco aceito e a atribuição.
- [ ] Custo estimado, teto e confirmação registrados; custo recorrente zero.
- [ ] Bruto imutável: uma recoleta grava revisão nova, sem apagar a anterior.
- [ ] Linhas `sem_rota`/`falha`/`pendente` com `km` e `minutes` nulos.

## Limites de prova

Sem a coleta real não há prova de preço, de faixa de cobrança do carro nem de aceitação da chave. As fixtures validam o formato **documentado** da resposta, não uma resposta
real; na primeira coleta real, o autor confere um par conhecido (Lisboa–Porto) contra o Google Maps.
