# Mobilidade 009 — execução (2026-11-21)

Feature: distância e tempo de carro dos 308 municípios até polos fixos (spec
`.sdd/specs/009-mobilidade-distancias/`, ADR-004). Nenhuma chamada real ao Google foi feita; a coleta real é um gate
do autor.

## Achados duráveis

- **Escopo decidido pelo autor (2026-11-21):** só linha reta e carro (transporte público fora, mas suportado por
  catálogo), e 7 polos: Lisboa, Porto e os aeroportos LIS, OPO, FAO, FNC e PDL. Ampliar é mudança de
  `config/poles.yml` e `config/sources.yml`; só os pares novos são cobrados.
- **Números reais (CAOP 2025 local, build offline):** 308 municípios; 3.562 linhas no staging (2.156 de linha reta,
  1.404 pares de carro `pendente`, 2 identidades: Lisboa e Porto). Municípios só com linha reta: 14 (Porto Santo e as 13
  cidades dos Açores fora de São Miguel). Estimativa de custo: ~1.404 elementos, US$ 0 dentro do teto gratuito de
  10.000 e pior caso ~US$ 7. **Preços não confirmados** (vieram de resumo de busca): a CLI recusa gastar sem
  `pricing_verified_on`.
- **Sanidade da linha reta** (haversine real): Lisboa–Porto 273 km; Lisboa–aeroporto de Lisboa 4 km; Ponta Delgada–PDL 9 km.
- **Coordenadas dos aeroportos:** só o LPPT foi conferido (AIP, ARP 384627N 0090803W). O eAIP (ais.nav.pt) respondeu
  HTTP 503 com `Retry-After: 3600` em 2026-11-21; OPO, FAO, FNC e PDL ficaram `APROXIMADO` no `source_ref` e
  precisam ser conferidos antes da coleta real (erro estimado ~1 km, irrelevante entre municípios).
- **A Routes API não devolve as coordenadas ajustadas à via**; o manifest grava `returned_coordinates: unavailable`
  e só as coordenadas pedidas.
- **HTTP 200 pode trazer erro no elemento** (`status.code != 0`): é falha de coleta, não `sem_rota`; `ROUTE_NOT_FOUND`
  é resposta válida e vira `sem_rota`.
- **A chave pode vazar por eco do servidor ou pela mensagem do `httpx`**: toda string que sai do coletor passa por
  `redact`; o contrato 5 cobre os dois casos. Chave só em cabeçalho, nunca em URL.
- **Um sentinel de chave fictícia começando com `AIza` e 35 caracteres casa com o padrão de chave do Google e
  poderia acionar o gitleaks do CI.** Use sentinelas sem esse prefixo.
- **Fixture que depende do relógio vira bomba-relógio num contrato travado**: a data de partida do transporte no
  fixture é calculada a partir de hoje (terça-feira a ~14 dias).
- **O dbt acusou linhas sem licença** (FR-022); a licença da linha reta vem de `license_id` da `dim_municipality`.
- Os testes antigos que fixam a lista exata de fontes do catálogo (`test_climate_catalog.py`) precisam ser
  atualizados ao acrescentar uma fonte.

## Evidências

- Suíte completa: 705 passed (473 s) ao fechar a Fase 4; os 5 contratos de `tests/contracts/test_mobility_contract.py`
  passaram de primeira ao implementar a fase.
- Build real offline: `uv run --locked python -m pipelines.cli.build_mobility --local --root .data`.
- Estimativa real: `uv run --locked python -m pipelines.cli.collect_mobility --local --root .data` (sem rede, sem chave).

## Coleta real (2026-11-22)

- **Preço conferido** na página oficial (Compute Route Matrix Essentials: US$ 5,00/1.000 elementos até 100 mil; a página lista
  10.000 gratuitos/mês, o autor informou ter 1.000, e o catálogo usa 1.000, o cenário conservador). `pricing_verified_on`
  passou a `2026-11-22`. A página não mostra data de atualização.
- **Chave:** `key_env` agora é `GOOGLE_CV20_API_KEY`. A primeira chave (`GOOGLE_ROUTES_API_KEY`) deu 403 `PERMISSION_DENIED`
  (Routes API não habilitada ou fora da restrição da chave); a segunda funcionou.
- **Resultado:** 1.404 elementos coletados, 0 falhas, 0 `sem_rota`, 0 pendentes (run `20261122T175309191606Z-d38e5992`);
  staging com 3.562 linhas. Lisboa→Porto: 317,5 km e 181 min de carro (273 km em linha reta); LIS 9,8 km do centro de
  Lisboa. Os 2 valores `km = 0` são as identidades (Lisboa e Porto), sem chamada.
- **Pendente:** as coordenadas de OPO, FAO, FNC e PDL continuam aproximadas (R-006/R-010); corrigi-las deixa os pares do polo
  `stale` e exige recoleta (~200 elementos cada). A chave deve ser revogada ou restringida ao terminar.

## Limites

Não há prova de preço, de faixa de cobrança do carro, de aceitação da chave nem de cobertura real do Google. O formato
da resposta usado nos testes vem da documentação pública, não de uma resposta real: na primeira coleta real, conferir
um par conhecido (Lisboa–Porto) contra o Google Maps.
