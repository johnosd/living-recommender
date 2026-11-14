# Research — ingestão Pordata e INE

Todas as medições abaixo foram feitas em **2026-11-11** contra as fontes reais, com requisições espaçadas e um User-Agent genérico de pesquisa. Os arquivos baixados ficaram fora do repositório.

## R1. Pordata: URLs, formato e variações dos CSV

**Decisão:** coletar os 16 CSV pelas URLs do blob `https://ffmspstdlspub01.blob.core.windows.net/data/Modelo_<N>/<id>.csv`, e validar as colunas **pelo rótulo, ignorando o prefixo numérico**.

**Evidência:** os 16 URLs responderam `200` (`text/csv`), todos com `ETag` e `Last-Modified`. Tamanhos: 1 → 44,9 MB; 379 → 14,7 MB; 978 → 6,7 MB; 354 → 6,0 MB; os demais abaixo de 3 MB (total ≈ 82 MB). Todos em UTF-8, separador vírgula, sem BOM.

O prefixo numérico das colunas **muda entre datasets**: `Escala` é `07` ou `08`, `Símbolo` é `08` ou `09`, o dataset 4 tem uma coluna chamada `Max. 08. Escala` e os datasets 1 e 559 têm a coluna extra `Nome País (Europa)` (10 colunas em vez de 9). Posição e prefixo não servem de chave; o rótulo (`Ano`, `Nome Região (Portugal)`, `Âmbito Geográfico`, `Filtro 1..3`, `Escala`, `Símbolo`, `Valor`) serve.

- **Linha municipal:** `Âmbito Geográfico = "Município"`. As linhas de agregação (Portugal, regiões, distritos, países) têm o âmbito **vazio**. Só esses dois valores aparecem nos 16 datasets.
- **Chave:** `(município, ano, filtros 1–3)` é única em todos os 16 datasets (0 duplicatas).
- **Ano** é inteiro simples e o decimal usa ponto. O `"2.024,00"` do legado nasceu no processamento, não na fonte.
- **Símbolos** observados: `r` (revisto), `x` (confidencial/indisponível), `-` (nulo), `...` (não disponível), `Pro` (provisório) e `Quebra de série`. Em `r`, `Pro` e `Quebra de série` o valor existe; em `x`, `-` e `...` o valor vem vazio.
- **Unidade** vem em `Escala`, com espaço inicial (`" pessoas"`, `" euros"`).

**Alternativa rejeitada:** validar por posição de coluna (como o `pordataFiles.json` do legado implicitamente fazia) quebraria em 2 dos 16 datasets.

## R2. Pordata: a planilha de poder de compra

**Fatos:** a URL do legado (`…/sites/default/files/2024-06/Municipios_Poder-de-compra-per-capita.xlsx`) devolve **302 → página "notfound"**. A página do indicador (`/municipios/poder+de+compra+per+capita-118`) oferece o export só por `javascript:__doPostBack(…)`, sem URL de download. A tabela `118.csv` do blob (`Modelo_7`) é outra tabela (energia, Eurostat), então **não existe CSV estável** para esse indicador.

**Decisão do autor:** carga manual do Excel exportado (`PORDATA_NUTS2013_Poder-de-compra-per-capita.xlsx`) **e** o indicador equivalente pela API do INE.

**Layout da planilha** (arquivo real do autor, não versionado): três abas (`Quadro`, `Metainformação`, `Alterações NUTS`). Na aba `Quadro`, a linha 12 é o cabeçalho (`Âmbito Geográfico`, `Anos`, depois os anos 1993 a 2021, em 11 colunas). A coluna A é o âmbito (`NUTS 2013`, `NUTS I`, `NUTS II`, `NUTS III`, `Município`) e a B é o território. São 308 linhas municipais, todas numéricas em 2021. O rodapé traz a legenda de símbolos e "Dados obtidos em https:www.pordata.pt a 29-02-2024".

**Leitor de Excel:** o projeto não tem `openpyxl`. **Decisão:** adicionar `openpyxl` (modo somente leitura). Um parser próprio com `zipfile` + XML funcionou na pesquisa em ~25 linhas, mas duplicaria um leitor bem conhecido e quebraria com fórmulas, datas ou strings embutidas de outra exportação. Uma dependência é mais simples de manter que código próprio.

## R3. INE: a API de indicadores

**Endpoints** (`https://www.ine.pt/ine/json_indicador/`): `pindica.jsp` (dados), `pindicaMeta.jsp` (metadados). `xml_indic.jsp` deu timeout de 60 s.

**Parâmetros que funcionam:** `op=2&varcd=<cod>&Dim1=T&Dim2=lvl@5&lang=PT`. `Dim1=T` traz todos os períodos; `Dim2=lvl@5` traz só o nível município (308). Na criminalidade, `Dim3=T` traz **só a categoria "Total"**; os códigos reais são `T,1,2,3,4,5,6` (`Dim3=T,1,2,3,4,5,6` traz as 7 categorias).

| Indicador | Código | Periodicidade | Períodos | Unidade | Atualizado | Municípios com valor |
|---|---|---|---|---|---|---|
| Rendas da habitação (mediana de novos contratos, Metodologia 2026, NUTS 2024) | `0014698` | Anual | 2020–2025 | €/m² | 2026-09-29 | 222 (2020) a 247 (2025) de 308 |
| Taxa de criminalidade por categoria de crime (NUTS 2013) | `0008074` | Anual | 2011–2022 | ‰ | 2026-06-30 | 308 em todos os anos |
| Poder de compra per capita (NUTS 2024) | `0014580` | Bienal | 2023 | índice (Portugal = 100) | 2025-11-06 | 308 (2023) |

A resposta de `0014698` também expõe 291 freguesias (nível 6); ficam fora do escopo e não são pedidas (`lvl@5`).

**Estrutura:** `[ {IndicadorCod, IndicadorDsg, MetaInfUrl, DataExtracao, DataUltimoAtualizacao, UltimoPref, Dados:{<período>:[{geocod, geodsg, valor?, ind_string, sinal_conv?, sinal_conv_desc?, dim_3?}]}, Sucesso} ]`. Ausência vem como `sinal_conv: "-"` ("Dado nulo ou não aplicável") sem o campo `valor`.

**Problema de idempotência:** a resposta inclui `DataExtracao` (horário da chamada) e a API **não envia `ETag` nem `Last-Modified`**. O `sha256` do arquivo bruto muda a cada chamada, então a comparação por checksum bruto, usada na CAOP, daria sempre `changed`. **Decisão:** a detecção de mudança do INE usa uma **impressão digital canônica** do JSON sem `DataExtracao`; o bruto guardado continua sendo a resposta original. `DataUltimoAtualizacao` é registrada no manifest como data de publicação.

**Instabilidade:** 2 dos 6 pedidos de metadados deram timeout de 60 s e os de dados levaram 3 a 6 s. A coleta precisa de timeout generoso (≥ 90 s), retentativas com espera crescente e limite de taxa.

**Alternativas rejeitadas:** os `.xls` `clientFiles` do legado (links gerados pelo site, sem estabilidade); `HEAD` condicional (a API não envia validadores).

## R4. Resolução territorial

**Pordata:** os **308 nomes municipais distintos aparecem nos 16 CSV** e na planilha. Contra a `normalized_name` da CAOP (Silver real), 303 casam diretamente e restam 5 casos:

| Grafia da fonte | `dico` | Motivo |
|---|---|---|
| `Lagoa` | `0806` | existe também `4201`; o nome normalizado `lagoa` é **ambíguo** na CAOP |
| `Lagoa [R.A.A.]` | `4201` | sufixo de região |
| `Calheta [R.A.A.]` | `4501` | a CAOP chama de "Calheta de São Jorge" |
| `Calheta [R.A.M.]` | `3101` | sufixo de região |
| `Vila da Praia da Vitória` | `4302` | a CAOP chama de "Praia da Vitória" |

**INE:** o `geocod` municipal tem 7 caracteres e **os 4 últimos são o `dico`** (`11A0109` → `0109`; `3003109` → `3109`). Os 308 códigos de cada um dos 3 indicadores conferem com a Silver da CAOP (308 de 308, nenhum fora). Resolver por código é determinístico e dispensa sinônimos.

**Decisão:** nome → seed de sinônimos (5 linhas) mais casamento exato do nome normalizado **somente se for único**; código → sufixo de 4 caracteres, validado contra a dimensão.

## R5. Cobertura real

As rendas do INE **não cobrem os 308**: 247 com valor em 2025 e 222 em 2020 (o INE só publica unidades com ≥ 33 contratos novos; as séries trimestrais são só para municípios com mais de 100 mil habitantes). O `.docs/fontes_de_dados.md` afirma que o INE dá a mediana "para todos os municípios", o que é impreciso. A ausência fica explícita (`sinal_conv: "-"`); o relatório de cobertura mede isso.

## R6. Licenças

- **INE:** a informação estatística é reutilizável sob **CC BY 4.0**, citando "Instituto Nacional de Estatística, IP – Portugal", a informação estatística e o período de referência; dados modificados devem ser sinalizados como tal ([termos do INE](https://www.ine.pt/xportal/xmain?xpid=INE&xpgid=ine_pufs_termos&contexto=up&xlang=pt)).
- **Pordata:** os [Termos Legais](https://www.pordata.pt/pt/termos-e-condicoes-de-utilizacao) **não concedem licença de reutilização** e não citam Creative Commons. A cláusula 5.4 pede que se evite "a reprodução, a comercialização, a transmissão ou a colocação à disposição do público desses conteúdos", e a 5.2 afirma a proteção por direito de autor. A página diz que os dados vêm do INE, do Eurostat e de outras fontes oficiais. O `.docs` assumia "uso livre com citação" sem fonte que o confirme.

**Decisão do autor (2026-11-11):** coletar mesmo assim. Registrado como risco aceito (R-001), conforme a constitution IV.

## R7. dbt-duckdb

Conforme a [documentação do adapter](https://github.com/duckdb/dbt-duckdb/blob/master/README.md): a materialização `external` aceita `options` repassadas ao `COPY` do DuckDB (incluindo `partition_by`), e uma `source` aceita `external_location`. O staging pode ser **um único modelo** particionado por `dataset_id`, em vez de 20 modelos, e a dimensão `dim_municipality` da spec 001 entra como `source` apontando para o Parquet já promovido.

## R8. Código existente que precisa mudar (achados na exploração)

- `HttpDownloader._stream` ([http.py](../../../pipelines/collectors/_shared/http.py)) só aceita ZIP (`PK\x03\x04`) e rejeita `text/html` com mensagem de GeoPackage. O CSV e o JSON precisam de outra checagem do primeiro bloco.
- `catalog.validate_source` e `manifest.validate_changed` são específicos da CAOP (`REGIONS`, três arquivos). Os contratos e manifests da CAOP **não podem mudar**.
- `build_caop._promote` troca os diretórios `lake/bronze` e `lake/silver` **inteiros**. Reaproveitá-lo para o staging novo **apagaria o Bronze e a Silver da CAOP**. É preciso promover só `lake/bronze/stg_observation/` e `lake/bronze/rpt_observation_coverage/`.
- `latest_changed` é por fonte e lê `files[]`; o estado por dataset precisa de outra função.
