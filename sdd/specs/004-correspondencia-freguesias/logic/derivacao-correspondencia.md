# Lógica: leitura, derivação e cobertura da correspondência

Fronteiras públicas (stubs em `pipelines/collectors/parish_crosswalk/`). Os contratos travados em `tests/contracts/test_parish_crosswalk_contract.py` definem o resultado; este documento explica o **como** e os pontos em que um executor erraria.

## 1. Leitura da planilha (`layout.py` → `validate.py` e `transform.py`)

`layout.py` (T004) é a única parte que abre a planilha; `validate_crosswalk_table` e `read_crosswalk_table` apenas a usam.

```python
def load_rows(dataset, path) -> tuple[list[dict], dict]:
    # 1. openpyxl.load_workbook(path, read_only=True, data_only=True); fechar no finally.
    #    OSError/InvalidFileException/BadZipFile/KeyError -> CrosswalkSchemaError("o arquivo não é uma planilha xlsx válida")
    # 2. aba: dataset["sheet"] comparada normalizada (NFC, strip, casefold); ausente -> "aba ausente: <nome>"
    # 3. cabeçalho = linha 1; índice por rótulo normalizado (colapsar \s+ em " "); cada valor de dataset["columns"]
    #    precisa existir -> senão "coluna ausente: <rótulo>". Nunca por posição.
    # 4. para cada linha seguinte:
    #       cells = {papel: célula}                       # só as colunas mapeadas; as demais são ignoradas
    #       se todas as mapeadas são None/"" -> pular em silêncio (linha vazia; NÃO conta em ignored_rows)
    #       se a coluna pre_code é texto não vazio que NÃO é código e TODAS as outras mapeadas estão vazias -> legenda:
    #           ignored_rows += 1; continue
    #       senão normalizar todos os códigos (pre_code e code) com normalize_code(); qualquer erro reprova a tabela
    #       nomes: strip e colapsar espaços; None vira ""
    # 5. devolve as linhas e {"rows_read", "ignored_rows", "numeric_codes_normalized", "partial_rows"}
```

```python
CODE = re.compile(r"[0-9A-Z]{6}")

def normalize_code(value, *, where) -> tuple[str, bool]:      # (código, era_numérico)
    if isinstance(value, bool): erro
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        text = str(int(value))
        if len(text) != 6: erro f"código numérico com {len(text)} dígitos (zero à esquerda perdido): {value} em {where}"
        return text, True
    if isinstance(value, str):
        text = value.strip()
        if CODE.fullmatch(text): return text, False
    erro f"código inválido: {value!r} em {where}"                 # a mensagem SEMPRE traz o valor ofensivo
```

Pontos que o contrato trava:

- Número de 6 dígitos vira texto e conta em `numeric_codes_normalized` (cada **célula**, não cada linha: a linha `110640`/`110658` conta 2).
- `10103` (5 dígitos) reprova com `10103` na mensagem.
- `("ZZ", "Lixo", "Lixo", "9")` tem dado nas outras colunas, então **não** é legenda: reprova com `ZZ` na mensagem.
- `("Fonte: INE, 2013", None, None, None)` é legenda: ignorada e contada.
- `partial_origin` (só tabela A) = `re.search(r"\(parte\)\s*$", pre_name, re.I)`; `partial_rows` conta as linhas com o marcador.
- Não é erro a tabela ter linhas repetidas (o código `110633` aparece duas vezes na tabela A real).

`validate_crosswalk_table` = `load_rows` + exigir pelo menos uma linha de dado + (papel B) nenhum outro requisito. Qualquer exceção vira `CrosswalkSchemaError`. HTML chega aqui como "não é uma planilha" (o downloader já recusa antes com `xlsx_content_check`).

## 2. Coleta (`handler.py`)

Igual a `collect_pordata`, só trocando validador e fonte:

```python
def collect_parish_crosswalk(catalog, *, storage, downloader, run_id, collected_at_utc, work_dir,
                             validator=validate_crosswalk_table):
    def fetcher(dataset, destination):
        downloader(dataset["origin"], destination)
        return dict(getattr(downloader, "last_headers", None) or {})
    return collect_datasets(catalog, SOURCE_ID, storage=storage, fetcher=fetcher, validator=validator,
                            run_id=run_id, collected_at_utc=collected_at_utc, work_dir=work_dir)
```

Não alterar `datasets.py`. O sufixo `.xlsx` vem de `format: xlsx` (a URL `Versao/Download/9160` não tem extensão). A CLI usa `HttpDownloader(content_check=xlsx_content_check, timeout=120.0, rate_limiter=RateLimiter(1.0))`.

## 3. Derivação (`derive.py`)

```python
def derive_parish_crosswalk(table_a, table_b) -> DataFrame:
    # chain: cada linha da A (pre_code, name_2013, code_2013, partial_origin) recebe o destino de 2025 pela B
    chain = A.merge(B[["pre_code", "code_2025", "name_2025"]], on="pre_code", how="left")
    chain["dicofre_2025"] = chain["code_2025"].fillna(chain["code_2013"])   # NÃO reposta: mantém o código de 2013
    chain["name_2025"]    = chain["name_2025"].fillna(chain["name_2013"])   # e a designação de 2013
    # B pode ter pre_code ausente na A? -> erro (a B só repõe o que a A conhece)
    # par: agrupar por (code_2013, dicofre_2025)
    pair = chain.groupby(["code_2013", "dicofre_2025"], as_index=False).agg(
        name_2013=("name_2013", "first"),          # o nome de 2013 é o mesmo para todo o código
        name_2025=("name_2025", "first"),
        partial_origin=("partial_origin", "any"),
        pre2013_codes=("pre_code", lambda s: sorted(set(s))),
    )
    dest   = pair.groupby("code_2013")["dicofre_2025"].transform("nunique")
    origin = pair.groupby("dicofre_2025")["code_2013"].transform("nunique")
    relation = one_to_one if dest == 1 and origin == 1 else one_to_many if dest > 1 and origin == 1 \
               else many_to_one if dest == 1 and origin > 1 else many_to_many
    inherited = dest > 1
    name_changed = norm(name_2013) != norm(name_2025)      # norm = NFC + espaços colapsados + casefold
    municipality_changed = code_2013[:4] != dicofre_2025[:4]
    # ordenar por (dicofre_2013, dicofre_2025) e renomear code_2013 -> dicofre_2013
```

Armadilhas:

- **Merge por `pre_code` com duplicatas na A**: o código `021113` aparece duas vezes (a freguesia foi repartida), cada linha com um `code_2013` diferente. O `merge` deve ficar **na granularidade da linha da A**; agrupar só depois. Fazer `drop_duplicates("pre_code")` na A apaga um dos pares.
- **`partial_origin` é do par, não do código pré-2013**: `110633` gera dois pares; só o de `110662` tem o marcador.
- **`name_2013` de um código de 2013** é a designação da tabela A; se houver mais de um valor para o mesmo `code_2013` (INE inconsistente), reprovar com a lista (não escolher um).
- **Determinismo**: ordenar sempre as saídas (`pre2013_codes` e as linhas) e tratar a entrada como conjunto; inverter as linhas das duas tabelas não pode mudar nada.
- **Tipos**: `inherited`, `partial_origin`, `name_changed`, `municipality_changed` são `bool` Python/NumPy; `pre2013_codes` é lista de `str`. O Parquet depois fixa os tipos (`varchar[]`).
- Nada de pesos, áreas ou população: a herança é só um sinal (FR-010).

## 4. Cobertura (`coverage.py`)

```python
def verify_coverage(crosswalk, dim_parish_codes, codes_2013):
    destinations = set(crosswalk["dicofre_2025"]); origins_2013 = set(crosswalk["dicofre_2013"])
    without_origin      = sorted(set(dim_parish_codes) - destinations)     # freguesia vigente sem origem
    without_destination = sorted(set(codes_2013) - origins_2013)           # código de 2013 sem destino
    unknown             = sorted(destinations - set(dim_parish_codes))     # destino fora da dimensão
    if any: raise CrosswalkCoverageError(mensagem com as três listas, cada código impresso)
```

A mensagem lista os códigos (e, no build, os nomes da `dim_parish` quando conhecidos). Os três atributos são sempre listas ordenadas, vazias quando não há problema. Roda **antes** do dbt: em caso de erro, nada é promovido e a tabela anterior continua intacta.

## 5. Build (`pipelines/cli/build_parish_crosswalk.py`)

```text
1. raiz resolvida; exigir lake/silver/dim_parish/data.parquet (senão: "execute build_caop primeiro")
2. estados = latest_dataset_states(storage, "ine_parish_crosswalk"); exigir as DUAS tabelas, com o bruto no
   disco e sha256/bytes conferindo (como collect_inputs de build_observations); senão informar qual falta
3. ler as duas (read_crosswalk_table), derivar, verify_coverage(crosswalk, dim_codes, set(A.code_2013))
4. candidate = .data/.build/parish_crosswalk/<uuid>; gravar prepared/crosswalk.parquet (+ proveniência)
5. dbt build --select tag:parish_crosswalk, com XWALK_BUILD_DIR, XWALK_PREPARED_DIR, OBS_SILVER_DIR, CAOP_DUCKDB_PATH
6. promote_paths(root, candidate, ("lake/silver/xwalk_parish_2013_2025", "lake/silver/rpt_parish_crosswalk_coverage"))
7. escrever lake/silver/parish_crosswalk_review.csv e lake/silver/parish_crosswalk_report.csv a partir do promovido; imprimir o resumo
```

Qualquer falha antes do passo 6 deixa `lake/silver` como estava (constitution V). O diretório temporário é removido no `finally`.
