# Research — Mobilidade (spec 009)

Pesquisa feita em 2026-11-21 por busca na documentação pública da Google Maps Platform. As páginas oficiais
não foram lidas por inteiro: o que vem de resumo de busca está marcado **a confirmar** e é gate do operador
antes da coleta real (R-001 do plano).

## R1. Produto da API: Routes API `computeRouteMatrix`, não o Distance Matrix legado

- **Decisão**: usar `POST https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix`, com a chave no
  cabeçalho `X-Goog-Api-Key` e a máscara de campos no cabeçalho `X-Goog-FieldMask`.
- **Justificativa**: `.docs/fontes_de_dados.md` já aponta a Routes API como substituta do Distance Matrix. A
  cobrança é por **elemento** (origens × destinos) nos dois produtos, então não há ganho em ficar no legado.
  A chave em cabeçalho (e não em query string) evita que ela apareça em URLs, em logs de proxy e em mensagens
  de erro do `httpx` (constitution I).
- **Alternativas**: Distance Matrix legado (rotulado "Legacy"; mesma cobrança por elemento, chave em query
  string); OpenRouteService/GTFS da CP (já registrados como substituição se o Google contestar, ADR-002 D8).
- **Limites encontrados**: até 625 elementos por requisição, 100 em `TRANSIT`; 3.000 elementos por minuto.
  Para `TRANSIT`, `departureTime` pode estar até 7 dias no passado ou 100 dias no futuro.

## R2. Cobrança e custo (a confirmar)

- **Encontrado**: Compute Route Matrix é cobrado por elemento. A busca trouxe três faixas: Essentials com
  teto gratuito mensal de 10.000 e US$ 5,00 por mil depois; Pro com teto de 5.000; Enterprise com teto de
  1.000 e US$ 15,00 por mil. O resumo **não** disse em que faixa cai `TRANSIT` (hoje desabilitado), nem a faixa de uma máscara com
  `duration`; assume-se Essentials para `DRIVE` + `TRAFFIC_UNAWARE`.
- **Estimativa**: ~1.404 pares, só carro (decisão do autor de não calcular transporte público agora), ou 1.404
  elementos (ver `logic/pares-e-estados.md`). Dentro do teto gratuito de 10.000 o custo tende a **US$ 0**.
  Limite superior conservador, sem nenhum teto gratuito: 1.404 × 5/1000 ≈ **US$ 7,0**. Custo **único**; o
  recorrente é zero. (Se o transporte público for habilitado depois, a faixa dele continua a confirmar.)
- **Encaminhamento**: preços e tetos moram no catálogo (`pricing`), não no código, e o operador os confere
  na página oficial de preços e registra `pricing_verified_on` antes de `--execute`. Sem a data, a CLI recusa.

## R3. Formato da resposta e classificação

- A resposta REST é uma **lista JSON** de elementos. Um elemento traz `originIndex`, `destinationIndex`,
  `condition` (`ROUTE_EXISTS` | `ROUTE_NOT_FOUND`), `distanceMeters`, `duration` (string `"900s"`) e, quando
  falha, `status` (`{code, message}`, código gRPC diferente de 0).
- **Classificação**: `ROUTE_EXISTS` com `distanceMeters` e `duration` → `ok`; `ROUTE_NOT_FOUND` → `sem_rota`;
  qualquer elemento com `status.code != 0`, corpo que não seja lista de um elemento, índices diferentes de
  `0/0` ou campos ausentes → **falha** (não grava). HTTP 401/403 → para a execução (autorização).
  HTTP 429 ou `RESOURCE_EXHAUSTED` → `QuotaExhausted`. 5xx/408/timeout → retry com backoff.
- **A API não devolve as coordenadas ajustadas à via.** FR-011 e o edge case "ponto fora de via" da spec
  supõem isso. O plano grava só as coordenadas **pedidas** e registra no manifest `returned_coordinates:
  unavailable`. É um desvio da spec (ver Analyze, A-002).

## R4. Modo e horário

- **Carro**: `travelMode: DRIVE` com `routingPreference: TRAFFIC_UNAWARE`, sem `departureTime`. Evita a faixa
  de tráfego (mais cara) e dá um tempo reprodutível, sem depender do dia da coleta. **Desvio** do FR-007 e do
  ADR-002 D8, que pediam a mesma partida (dia útil, 08:00) para os dois modos; o autor decide (A-001).
- **Transporte público (desabilitado por ora; decisão do autor, 2026-11-21)**: `travelMode: TRANSIT` com `departureTime` fixo no catálogo, num dia útil futuro às
  08:00 de Lisboa. A data precisa estar a ≤ 100 dias da execução, então a CLI a valida **antes** de qualquer
  chamada. Mudar a data depois da coleta invalida (marca como desatualizados) todos os pares de transporte.

## R5. Granularidade da requisição: um par por chamada

- **Decisão**: uma requisição 1×1 por par e modo, um bruto por par.
- **Justificativa**: o estado vigente, a retomada e a recoleta só dos pares novos ou alterados (FR-015,
  FR-024) ficam exatos e reutilizam `collect_items` (spec 003) sem alteração. Pedir uma origem contra vários
  destinos acoplaria pares, e acrescentar um polo repetiria a cobrança dos pares já pagos.
- **Custo da escolha**: ~1.400 chamadas, a ~0,2 s entre elas, ≈ 5 min, muito abaixo de 3.000 elementos por
  minuto. O Google cobra por elemento, então agrupar não custa menos.

## R6. Chave: `.env` e variável de ambiente agora; SSM depois

- FR-010 aceita `.env` local ou SSM. A coleta é local e única, então esta feature lê `GOOGLE_ROUTES_API_KEY`
  do ambiente ou de um `.env` na raiz do repositório (já no `.gitignore`). O caminho SSM
  `/living-recommender/google/distance_key` (ADR-003) fica documentado, sem código, para quando existir AWS.
- Toda mensagem que sai do coletor (erro, manifest, stdout, stderr) passa por uma redação que troca o valor da
  chave por `[REDACTED]`, inclusive o corpo de erro devolvido pelo servidor e a mensagem das exceções do `httpx`.

## R7. Polos: coordenadas e códigos

- **Lista inicial (decisão do autor, 2026-11-21)**: cidades **Lisboa** (`1106`) e **Porto** (`1312`), que usam
  o ponto representativo da CAOP (sem geocodificar), e os aeroportos **LIS, OPO, FAO, FNC e PDL**.
- Aeroportos levam coordenadas próprias e `source_ref`. O executor DEVE conferir cada coordenada contra uma
  fonte pública (AIP/ANA) e registrar a referência; os valores aproximados de partida são LIS 38.7813/-9.1359,
  OPO 41.2481/-8.6814, FAO 37.0144/-7.9659, FNC 32.6979/-16.7745, PDL 37.7412/-25.6979.
- **Para ampliar depois** (por catálogo, sem código): sedes de distrito e capitais regionais, com os códigos
  conferidos em `dim_municipality` em 2026-11-21: Aveiro 0105, Beja 0205, Braga 0303, Bragança 0402,
  Castelo Branco 0502, Coimbra 0603, Évora 0705, Faro 0805, Guarda 0907, Leiria 1009, Portalegre 1214,
  Santarém 1416, Setúbal 1512, Viana do Castelo 1609, Vila Real 1714, Viseu 1823, Funchal 3103,
  Ponta Delgada 4203. O nome do distrito em `district_or_island` é igual ao do município sede nos 18 casos.
