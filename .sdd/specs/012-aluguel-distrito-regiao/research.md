# Research: spec 012

Medições de 2026-11-26 sobre `.data/lake` (snapshot do Idealista `2026-11`, 18 059 anúncios com preço), reusando
as regras de `pipelines/gold/rent.py`.

## Achados nos dados

- 25 distritos ou ilhas com anúncios e 7 regiões. Os 18 distritos do continente têm anúncios; só Lisboa, Porto e
  Faro têm `dico`.
- Nenhum distrito aparece em mais de uma região, e nenhum anúncio fica sem distrito ou sem região depois das regras
  de `logic/heranca.md` §2.
- Santarém está no Alentejo e Setúbal na Área Metropolitana de Lisboa (região da fonte, não NUTS II).
- 8 anúncios vêm sem região (Flores, Horta e Pico), todos com `dico`.
- `Horta` aparece como `source_subregion`, mas com `dico` (Ilha do Faial): por isso o `dico` vence o nome.
- Recalculadas por município com a função generalizada, as 324 linhas comparadas batem com a tabela da 011, sem
  divergência (SC-005).
- Medianas por distrito entre 475 e 4 300 €; por região, entre 650 e 3 950 €. Cabem na faixa 100–10 000.

## Cobertura esperada depois da herança

Municípios (308):

| Variante | próprio | distrito | região | ausente |
| --- | --- | --- | --- | --- |
| mediana `ALL` | 42 | 254 | 12 | 0 |
| mediana `T0` | 14 | 167 | 108 | 19 |
| mediana `T1` | 26 | 262 | 20 | 0 |
| mediana `T2` | 31 | 251 | 26 | 0 |
| mediana `T3` | 31 | 263 | 14 | 0 |
| mediana `T4+` | 18 | 230 | 41 | 19 |
| €/m² `ALL` | 41 | 255 | 12 | 0 |

Freguesias (3 259):

| Variante | freguesia | município | distrito | região |
| --- | --- | --- | --- | --- |
| mediana `ALL` | 135 | 284 | 2 777 | 63 |
| mediana `T2` | 87 | 186 | 2 667 | 319 |
| €/m² `ALL` | 134 | 278 | 2 784 | 63 |

## Decisões

### Região do distrito: derivada do snapshot

- **Decisão:** a região vem dos anúncios do snapshot vigente, com a região autónoma como reserva nas ilhas e falha
  se um distrito tiver duas.
- **Justificativa:** é o texto da FR-003 e da FR-005, e não cria um mapa mantido à mão.
- **Alternativa considerada:** seed fixa distrito → região. Cobriria um distrito sem anúncios num snapshot parcial,
  mas duplica a hierarquia da fonte. Ver R-001.

### Correspondência das ilhas: seed CSV

- **Decisão:** `analytics/dbt/seeds/idealista_island_aliases.csv`, no padrão das seeds de sinônimos.
- **Justificativa:** constitution III pede junção resolvida por seeds explícitas.
- **Alternativa considerada:** constante em Python (como no protótipo do notebook).

### Nível de origem: coluna nova `origin_level`

- **Decisão:** não reusar `territorial_inheritance`.
- **Justificativa:** essa coluna já guarda o `coverage_status` dos Censos (`own`, `inherited`, `missing`). Misturar
  os dois sentidos quebraria quem lê a coluna.
- **Alternativa considerada:** `territorial_inheritance = distrito|regiao`, citada no texto de entrada da spec.

### Relação com a CAOP: teste singular

- **Decisão:** teste dbt singular para `district_or_island`, sem `relationships`.
- **Justificativa:** o `modeldocs` desenha todo `relationships` como chave estrangeira para uma chave única, e
  `district_or_island` se repete em `dim_municipality`.
