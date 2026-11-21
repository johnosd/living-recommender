# ADR-004: Mobilidade — linha reta e carro pela Routes API, sem transporte público na v1

## Status

Aceita. Atualiza a decisão de mobilidade do [ADR-002](ADR-002-arquitetura-base-mvp.md) (D8, atualização de
2026-11-03); o restante do ADR-002 continua valendo. Dois pontos dependem de conferência do autor antes da
coleta real: as coordenadas dos aeroportos e o preço vigente do Google (ver Consequências).

## Data

2026-11-21

## Contexto

O ADR-002 D8 (atualização de 2026-11-03) definiu três modos de mobilidade na v1: linha reta (haversine), carro e
transporte público, com tempos do Google Distance Matrix calculados **uma única vez** e guardados, e polos
fixos "Lisboa, Porto, Faro, aeroportos e sede de distrito". O autor aceitou o risco de termos de uso do Google
(constitution IV).

Ao planejar a spec 009 (`.sdd/specs/009-mobilidade-distancias/`), a pesquisa e o desenho mostraram:

- o Distance Matrix é o produto **legado**; a Routes API `computeRouteMatrix` o substitui e cobra igualmente
  por **elemento** (origem × destino);
- a cobrança e o limite de elementos por requisição dependem do modo. O **transporte público** exige
  `departureTime` futuro (no máximo ~100 dias), tem limite menor por requisição (100) e uma faixa de preço que
  **não foi possível confirmar**; a data fixa, além disso, expira e invalida os pares já pagos se for trocada;
- a lista completa de polos (25) elevava o cálculo a ~3.800 elementos e a um custo incerto, para um ganho
  pequeno sobre o que a linha reta e os aeroportos já entregam;
- o autor decidiu, em 2026-11-21, começar enxuto: **só cidades como Lisboa e Porto e aeroportos**, e **só o
  carro** entre os modos do Google.

## Decisão

1. **Modos da v1: linha reta e carro.** O transporte público **não** é calculado agora. O código aceita os
   modos por catálogo (`modes` em `config/sources.yml`) e os contratos de teste exercitam o `transit`, mas o
   catálogo real habilita só `driving`. Habilitá-lo depois é **mudança de catálogo**; só os pares novos são
   cobrados.
2. **Produto: Routes API v2 `computeRouteMatrix`**, em vez do Distance Matrix legado, com **uma requisição 1×1
   por par e modo**. Chave em cabeçalho (`X-Goog-Api-Key`), nunca em URL. O estado vigente, a retomada e a
   cobrança só dos pares novos ou alterados ficam exatos por par.
3. **Carro sem tráfego e sem horário de partida** (`routingPreference: TRAFFIC_UNAWARE`). Isso substitui o
   "horário de partida fixo num dia útil às 08:00" do ADR-002 para o carro: o tempo é reprodutível, não depende
   do dia da coleta e fica na faixa mais barata. Se o transporte público for habilitado, ele usa `departureTime`
   fixo no catálogo (dia útil, 08:00 de Lisboa).
4. **Polos iniciais: 7** — as cidades **Lisboa** e **Porto** e os aeroportos **LIS, OPO, FAO, FNC e PDL**.
   Sedes de distrito, capitais regionais, Faro como cidade e os aeroportos de Terceira, Santa Maria e Porto Santo
   ficam fora por ora e entram por mudança de `config/poles.yml`. A elegibilidade das rotas é: polo nacional
   para o continente, e polo da **mesma ilha** para Madeira e Açores. As demais ilhas ficam só com linha reta.
5. **Cálculo único e custo controlado.** Estimativa primeiro, sem rede e sem chave; gastar exige
   `--execute --confirm-elements N`, teto por execução e `pricing_verified_on` preenchido. Custo estimado
   **US$ 0** (~1.404 elementos, dentro do teto gratuito mensal de 10.000), limite superior conservador **~US$ 7**,
   custo recorrente zero. Valores a confirmar na página oficial de preços antes da coleta.
6. **Mantém-se o risco aceito** do ADR-002 sobre guardar tempos do Google, com atribuição "Tempos de viagem:
   Google" em toda linha e a substituição documentada (OpenRouteService para carro; GTFS da CP para comboio).
   A chave segue o [ADR-003](ADR-003-byok-apis-externas.md) (pipeline: `.env` ou SSM).

## Alternativas Consideradas

### Manter os três modos do ADR-002 D8 (linha reta, carro e transporte público)

- Calcular também o transporte público com `departureTime` fixo.
- **Rejeitada para agora:** a faixa de preço do `TRANSIT` não foi confirmada; a data de partida expira (≤ ~100
  dias) e trocá-la invalida os pares pagos; e a cobertura em municípios rurais tende a ser baixa (`ROUTE_NOT_FOUND`),
  o que entrega pouco por elemento pago. O modo continua suportado, então a rejeição é reversível.

### Permanecer no Distance Matrix legado

- Mesmo conceito, API antiga, chave em query string.
- **Rejeitada:** é o produto marcado como legado, a cobrança por elemento é a mesma, e a chave em URL aumenta o
  risco de vazamento em logs e mensagens de erro (constitution I).

### Matriz por município (uma origem contra vários polos) em vez de um par por requisição

- Menos requisições HTTP.
- **Rejeitada:** acoplaria pares; acrescentar um polo recobraria os pares já pagos; e uma falha derrubaria o grupo.
  O Google cobra por elemento, então agrupar não custa menos.

### Lista completa de 25 polos (todas as sedes de distrito e capitais regionais)

- Mais referências por município.
- **Rejeitada por ora:** ~3.800 elementos e custo menos previsível, para um ganho pequeno sobre linha reta mais
  aeroportos. Os escopos `district` e `island` continuam no código; ampliar é mudança de catálogo.

### Motor de rotas próprio (`r5py` + OSM + GTFS da CP) ou OpenRouteService

- Sem termos de uso do Google.
- **Rejeitada para agora:** já era considerada complexa demais no ADR-002; permanece como substituição se o
  Google contestar ou se o projeto entrar na Fase B comercial.

## Consequências

### Positivas

- Custo único praticamente zero e limite superior de ~US$ 7, com recorrente zero.
- Some a dependência de uma data de partida que expira e de uma faixa de preço incerta.
- Retomada, idempotência e recobrança por par exatas; adicionar polo ou modo cobra só o que é novo.
- A chave nunca entra em URL; toda saída do coletor é redigida.

### Negativas

- **O usuário final não vê tempo de transporte público**, que o ADR-002 previa na v1; a interface deve ocultar
  esse modo (o seletor terá linha reta e carro).
- Menos polos: sem sede de distrito, o filtro "perto da capital do meu distrito" não existe na v1.
- Nove ilhas (oito dos Açores e Porto Santo) ficam sem rota de carro, só com linha reta.
- A API não devolve as coordenadas ajustadas à via; só as coordenadas pedidas ficam registradas.
- Preço, faixa de cobrança do carro e coordenadas dos aeroportos **ainda não foram conferidos** em fonte oficial;
  a CLI recusa gastar sem `pricing_verified_on`.
- O risco de termos de uso do Google continua aceito, não eliminado.

### Caminho de Migração / Evolução Futura

- **Habilitar o transporte público:** acrescentar `modes.transit` (com `departure_time` válido) ao catálogo e
  rodar a CLI; só os pares de transporte são cobrados. Antes, confirmar a faixa de preço do `TRANSIT`.
- **Ampliar os polos:** acrescentar sedes de distrito, capitais regionais ou aeroportos a `config/poles.yml`;
  só os pares novos são cobrados.
- **Trocar de provedor:** se o Google contestar o uso, ou na Fase B comercial, substituir por OpenRouteService
  (carro) e GTFS da CP (comboio), mantendo o staging e o contrato do coletor.
