# Research: Correspondência de freguesias 2013→2025

Medições feitas em 2026-11-12 sobre as duas planilhas reais do INE e a `dim_parish` local (CAOP 2025, 3.259 freguesias). Nada disso está no Git: os brutos ficam em `.data/` (ignorado) e as planilhas inspecionadas, fora do repositório.

## Fatos medidos

| Item | Tabela A (`…/Versao/Download/9160`) | Tabela B (`…/Versao/Download/10698`) |
| --- | --- | --- |
| Arquivo | `CorrespondenciasAntes-Depois-R2013.xlsx`, 205.543 bytes | `Codificação_FR_Repostas 2025_2013_Julho.xlsx`, 27.382 bytes |
| Resposta HTTP | 200, `application/octet-stream`, sem `ETag` | 200, `application/octet-stream`, sem `ETag` |
| Aba | `Correspondências 2013` (única) | `Sheet1` (única) |
| Cabeçalho (linha 1) | `Código` · `Freguesias antes da Reorganização` · `Freguesias - Reorganização de 2013` · `Código Novo` | `Código - Freguesias antes da reorganização administrativa de 2013` · `Designação - Freguesias antes …` · `Designação - Município` · `Código -  Freguesias repostas em 2025` (**dois espaços**) · `Designação - Freguesias repostas em 2025` |
| Linhas de dado | 4.266 (4.260 códigos pré-2013 distintos; 3.092 códigos de 2013) | 302 (302 códigos pré-2013; 302 códigos de 2025) |
| Colunas além das mapeadas | 36 colunas vazias | 3 colunas vazias; a coluna H traz uma legenda em **uma** linha de dado |
| Linhas que não são dado | 0 (última linha é `490101 Corvo`) | 0 |
| Células de código **numéricas** (`int`) | 50 (4 na col. 1, 46 na col. 4) | 1 (col. 1) |
| Numéricas com menos de 6 dígitos | 0 | 0 |
| Códigos de destino alfanuméricos (`0308FC`) | 20 | 11 |
| Designações com espaço nas pontas | 4 | — |
| Marcador `(parte)` na designação pré-2013 | 11 linhas (6 códigos pré-2013) | 0 |

`dim_parish`: 3.241 códigos só com dígitos e 18 alfanuméricos.

## Derivação testada nos dados reais

Protótipo (fora do repositório) com a regra "pré-2013 ausente da tabela B mantém o código de 2013":

- **3.260 pares** (código de 2013, código de 2025); 3.092 códigos de 2013 distintos e 3.259 códigos de 2025 distintos.
- Natureza da relação **calculada por par**: 2.957 um-para-um, 301 um-para-muitos, 2 muitos-para-muitos, **0** muitos-para-um isolado. Os 2 muitos-para-muitos são os pares da freguesia de Bicos (códigos de 2013 `021118` e `021122` → `021123`).
- Sinais: **303** pares com herança (301 + 2 muitos-para-muitos), **8** com origem parcial, **0** com mudança de município e **297** com mudança de nome (designações de 2013 e de 2025 diferentes, a regra de R4/data-model). Toda linha da tabela B existe na A (0 fora) e nenhum código de 2013 tem mais de uma designação, então as duas regras de consistência da derivação não reprovam a fonte real.
- Cobertura contra a `dim_parish`: **0** destinos fora da dimensão e **0** freguesias da dimensão sem origem.

## Decisões

### R1. As células numéricas existem; a regra "número é erro" da spec precisa de refinamento
**Decisão:** uma célula numérica inteira com **exatamente 6 dígitos** é aceita e normalizada para texto (e contada em `numeric_codes_normalized`); numérica com menos de 6 dígitos reprova (zero à esquerda perdido); numérica com mais de 6, decimal ou negativa reprova.
**Justificativa:** as planilhas reais têm 51 células inteiras, todas com 6 dígitos (nenhuma perdeu zero à esquerda; os códigos que começam por zero estão guardados como texto). Aplicar "número é erro" literalmente reprovaria a coleta real. O texto da spec já limita o erro a "zeros perdidos"; esta decisão só o torna operacional.
**Alternativas:** reprovar todo número (descartada: quebra a fonte real); aceitar qualquer número e completar com zeros (descartada: é correção silenciosa, exatamente o que a spec proíbe).

### R2. Código válido é `[0-9A-Z]{6}`, não 6 dígitos
**Decisão:** códigos de 2013 e de 2025 aceitam letras maiúsculas e dígitos; o padrão é o mesmo para as três gerações. Minúscula, espaço interno ou tamanho diferente reprovam.
**Justificativa:** o INE criou códigos como `0308FC` (31 linhas nas planilhas, 18 já na `dim_parish`). A spec diz "6 caracteres", o que cobre isso.
**Alternativas:** `\d{6}` (descartada: reprova a fonte real); validar letras só nos destinos (descartada: três regras por coluna sem ganho).

### R3. Localizar colunas por rótulo normalizado e a aba pelo catálogo
**Decisão:** comparar rótulos após NFC, colapso de espaços e `casefold` (o rótulo da tabela B tem dois espaços). O catálogo declara a aba (`Correspondências 2013`, `Sheet1`) e o mapa `papel → rótulo`; a posição das colunas nunca é usada. O cabeçalho precisa estar na linha 1.
**Justificativa:** padrão da spec 002 (D4), e a tabela B usa o nome genérico `Sheet1`: se o INE renomear a aba, a falha é explícita.
**Alternativas:** usar a primeira aba (descartada: aceitaria uma planilha errada com as mesmas colunas); ler por posição (descartada: a spec 002 mostrou que as posições variam).

### R4. Natureza da relação calculada por par
**Decisão:** para cada par (c13, c25), `destinos(c13)` = nº de códigos de 2025 distintos ligados a c13 e `origens(c25)` = nº de códigos de 2013 distintos ligados a c25. Um-para-um se ambos valem 1; um-para-muitos se só `destinos > 1`; muitos-para-um se só `origens > 1`; muitos-para-muitos se ambos > 1. A herança vale quando `destinos(c13) > 1`.
**Justificativa:** o FR-009 diz "os dois casos no mesmo conjunto de pares", ambíguo entre par e componente conexo. Por par é determinístico, local e dá à herança a mesma definição do FR-010. Nos dados reais, Bicos gera dois pares muitos-para-muitos e os pares "irmãos" de Colos e Vale de Santiago ficam um-para-muitos.
**Alternativas:** componente conexo (descartada: um par inofensivo passaria a ser muitos-para-muitos só por pertencer ao componente).

### R5. Marcador de origem parcial é textual
**Decisão:** `partial_origin` é verdadeiro quando a designação pré-2013 da linha da tabela A termina em `(parte)` (sem diferenciar maiúsculas). O relatório mostra quantas linhas e quantos pares têm o marcador (hoje 11 linhas e 8 pares).
**Justificativa:** é o único sinal que a fonte dá. Se o INE mudar o texto, o marcador some em silêncio; por isso a contagem aparece no relatório e fica em T026 como valor de referência.
**Alternativas:** inferir parcialidade por duplicidade do código pré-2013 (descartada: o código `110633` aparece duas vezes e só uma é "(parte)").

### R6. Derivação em Python; o dbt testa e materializa
**Decisão:** `derive_parish_crosswalk` é uma função pandas determinística. O dbt lê o Parquet preparado, fixa tipos, aplica os testes e materializa a tabela e o relatório, como a spec 002 fez com a resolução de município.
**Justificativa:** a função é o contrato testável sem rede e sem dbt; o dbt continua sendo a barreira de qualidade antes da promoção.
**Alternativas:** derivar em SQL (descartada: os contratos exigiriam rodar o dbt; a regra "não reposta mantém o código" fica mais legível em Python).

### R7. Onde o resultado mora
**Decisão:** `lake/silver/xwalk_parish_2013_2025/data.parquet` e `lake/silver/rpt_parish_crosswalk_coverage/data.parquet`, promovidos por caminho; um CSV de revisão `lake/silver/parish_crosswalk_review.csv` lista os pares que não são um-para-um.
**Justificativa:** a correspondência é uma tabela territorial, vizinha da `dim_parish`. A promoção por caminho (`_promote.py`) já impede apagar tabelas de outras features.
**Alternativas:** `lake/bronze` (descartada: não é staging de observações); seed do dbt (descartada na entrevista: sem manifest nem detecção de mudança).

## Não verificado
- A licença específica das duas planilhas (R-002 do plano) e se os termos do INE permitem o download automatizado.
- Se o Censos 2021 usa os códigos de 2013: fica para a spec do `censos`.
- A estabilidade dos links `Versao/Download/N`: só uma observação (2026-11-12).
- As ~303 mudanças de 2026 citadas por fonte secundária: fora de escopo.

## Verificação real — 2026-11-12 (T026)

Coleta HTTP e build reais contra o INE e a `dim_parish` real (CAOP 2025), no Windows, com o console em cp1252.

| Item | Esperado (pesquisa) | Obtido |
| --- | --- | --- |
| Bruto A / B | 205.543 / 27.382 bytes | 205.543 / 27.382 bytes |
| 2ª coleta (SC-003) | `unchanged` nas duas | `unchanged` nas duas; 2 arquivos em `raw/` |
| Pares | 3.260 | 3.260 (todos únicos) |
| Códigos de 2013 / de 2025 | 3.092 / 3.259 | 3.092 / 3.259 |
| um-para-um / um-para-muitos / muitos-para-um / muitos-para-muitos | 2.957 / 301 / 0 / 2 | 2.957 / 301 / 0 / 2 |
| Códigos de 2013 com um só destino / com mais de um (SC-002) | 2.957 / 135 | 2.957 / 135 |
| Códigos de 2025 com mais de uma origem (SC-002) | 1 | 1 (`021123`, Bicos) |
| herdado / origem parcial / nome alterado / município alterado | 303 / 8 / 297 / 0 | 303 / 8 / 297 / 0 |
| Cobertura da `dim_parish` (SC-001) | 3.259 de 3.259 | 3.259 de 3.259 |
| Células numéricas normalizadas / linhas com `(parte)` | 51 / 11 | 51 / 11 |
| Linhas lidas (A + B) | 4.266 + 302 | 4.568 (nenhuma legenda ignorada) |
| SHA-256 de `dim_parish`, `dim_municipality`, `stg_observation`, `stg_climate_daily` (SC-006) | iguais | iguais antes e depois |
| CSV de revisão | pares não um-para-um ou com sinal | 309 linhas: 301 um-para-muitos, 6 um-para-um com origem parcial, 2 muitos-para-muitos |

Nenhuma divergência com a referência. Os 6 um-para-um do CSV são os de origem parcial da região de Lisboa (Parque das Nações, Moscavide e Portela, Sacavém e Prior Velho, Alfragide, Águas Livres, Venteira).

**Achado do T026:** o resumo do build imprimia `→`, que não existe em cp1252 (console do Windows). O build terminava, mas o `print` levantava `UnicodeEncodeError`. Os testes não o pegavam porque `capsys` usa UTF-8. Corrigido (o texto agora usa "para") e coberto por `test_cli_output_can_be_printed_on_a_windows_console`, que confere `.encode("cp1252")` das saídas de sucesso e de falha.
