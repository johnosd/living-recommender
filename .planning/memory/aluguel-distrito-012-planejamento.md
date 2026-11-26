# Aluguel por distrito e região (012) — achados do planejamento (2026-11-26)

Feature: `.sdd/specs/012-aluguel-distrito-regiao/`. Medições sobre `.data/lake`, snapshot `2026-11`.

## Achados duráveis sobre os dados do Idealista

- Só Lisboa, Porto e Faro têm anúncios com `dico`; os outros 15 distritos do continente e as ilhas vêm com
  `source_subregion` e `source_region`. Todo distrito cai em uma única região da fonte.
- A região da fonte não é a NUTS II: Santarém está no Alentejo e Setúbal na Área Metropolitana de Lisboa.
- `source_subregion` nem sempre é o distrito do CAOP: aparece `Horta` (município da Ilha do Faial), com `dico`.
  Quando há `dico`, ele manda. Sem `dico`, as ilhas precisam de correspondência explícita de nomes.
- 8 anúncios têm `source_region` nula (Flores, Horta, Pico), todos com `dico`. O formato antigo pode gravar `""`
  (`TerritoryResolver.resolve_file`).
- Recalcular as estatísticas por município com a regra generalizada reproduz a tabela da 011 sem divergência
  (324 linhas comparadas).

## Armadilha de teste

`tests/unit/test_gold_parish.py::test_parish_normalization_ignores_inherited_values` (011) monta um perfil
"municipal" com a coluna `origin` da freguesia. Filtrar a normalização por `origin` no município quebra o teste;
o ajuste é no teste. Evidência: implementação descartável rodada em cópia, com 17 verdes e só esse vermelho.

## Tempo da suíte

A suíte completa levou 11 min 31 s (836 testes, 2026-11-26): passa do teto de 10 min de um comando em primeiro
plano; rode em segundo plano.
