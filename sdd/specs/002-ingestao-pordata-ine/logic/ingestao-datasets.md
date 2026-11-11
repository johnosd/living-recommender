# Lógica travada: coleta por dataset, impressão digital, resolução e cobertura

## 1. Coleta por dataset (`collect_datasets`)

```text
collect_datasets(catalog, source_id, storage, fetcher, validator, run_id, collected_at_utc, work_dir, fingerprint=None):
  source = catálogo[source_id] com `datasets` não vazio         # senão DatasetCollectionError (antes de qualquer rede)
  run_id válido e sem manifest/raw já existentes                # idem
  preflight do destino, se existir; list_keys() uma única vez   # falha → DatasetCollectionError("destino…")
  estado = estado_vigente_por_dataset(storage, source_id)       # lê os manifests UMA vez
  para cada dataset do catálogo:                                # sequencial; o fetcher respeita o rate limit
    tente:
      fetcher(dataset, work_dir/arquivo)                        # baixa para o temporário
      validator(dataset, work_dir/arquivo)                      # reprova HTML, vazio, colunas ausentes
      fp = (fingerprint or sha256_dos_bytes)(dataset, arquivo)
      se estado[dataset].fingerprint == fp: entrada = unchanged (aponta ao bruto anterior; NÃO grava)
      senão: storage.put_file(chave_nova, arquivo); entrada = changed
    exceto Exception como e:
      apaga a chave nova deste dataset, se já gravada; entrada = failed(erro = "<etapa>: <e>")
  status da execução = changed | unchanged | partial | failed    # ver data-model.md
  storage.put(manifest)                                          # sempre, mesmo com falhas
  retorna {status, run_id, manifest_key, datasets:[…]}           # NÃO levanta exceção por falha de dataset
```

- **Uma falha de dataset não propaga.** O CLI traduz `partial`/`failed` em código de saída `1`.
- **Estado vigente por dataset**: a entrada `changed` mais recente daquele `dataset_id` em qualquer manifest da fonte (inclusive `partial`). `failed` e `unchanged` nunca são estado, mas o `unchanged` herda `key`/`sha256` do estado.
- O bruto de um dataset só é gravado **depois** de validado e de comparado; o manifest vem por último.
- Se o `put_file` do dataset falhar, nenhuma chave dele fica gravada e os datasets seguintes continuam.

## 2. Impressão digital do INE

```text
fingerprint_ine_response(path):
  doc = json.load(path)                      # lista com 1 objeto
  para cada objeto: remover a chave "DataExtracao"     # horário da chamada; muda sempre
  retornar sha256( json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":")) )
```

`DataUltimoAtualizacao` **permanece** na impressão digital: se o INE republicar o indicador, o conteúdo muda e o dataset vira `changed`. Só `DataExtracao` é descartada. O bruto guardado é o arquivo original, com `DataExtracao`.

## 3. Validação por formato (o `validator` real)

- **CSV (Pordata):** UTF-8; primeira linha com os rótulos esperados **após remover o prefixo numérico** (`^\s*(Max\. )?\d+\.\s*`) e espaços; não começa com `<` nem tem `content-type` HTML; pelo menos uma linha com `Âmbito Geográfico = Município`. Colunas extras são permitidas (o dataset 1 tem `Nome País (Europa)`).
- **JSON (INE):** `Sucesso.Verdadeiro[0].Msg == "OK"`; `IndicadorCod` igual ao pedido; `Dados` não vazio; pelo menos uma entrada com `geocod` de 7 caracteres.
- **XLSX (carga manual):** abre com `openpyxl` em modo somente leitura; abas `Quadro` e `Metainformação`; uma linha de cabeçalho com `Anos` e colunas de ano; exatamente 308 linhas com âmbito `Município`.

## 4. Transformação para o Parquet longo (`prepare`, em Python)

- **CSV Pordata:** localizar as colunas pelos rótulos; manter só `Âmbito Geográfico = Município`; contar as demais como `aggregate_rows_excluded`; `value` vazio → nulo; `unit` = `Escala` sem espaços nas pontas; `period` = `int(Ano)`.
- **JSON INE:** para cada período e cada entrada de `Dados`: `source_name = geocod`; `value = float(valor)` se existir, senão nulo; `symbol = sinal_conv`; `filter_1 = dim_3_t` (categoria) quando existir; `unit` vem dos metadados do catálogo; `period = int(chave do período)`.
- **XLSX:** linhas de `Município` apenas; cada coluna de ano vira uma observação; `unit = "Número índice (Portugal = 100)"`; células vazias → nulo.
- Nenhum valor é inventado: ausente na fonte → `value` nulo + `symbol`.

## 5. Resolução do município

```text
resolve_municipality_names(names, municipalities, synonyms) -> {nome: dico}
  para cada nome:
    se nome em synonyms:           dico = synonyms[nome]  (precisa existir em municipalities, senão não resolvido)
    senão: candidatos = {dico : normalize_name(official_name) == normalize_name(nome)}
           se len(candidatos) == 1: dico = o único candidato
           senão:                   não resolvido            # zero OU ambíguo
  se houver não resolvidos: levantar UnresolvedMunicipalities(names=sorted(não resolvidos))
```

- `Lagoa` está em `synonyms` (→ `0806`); sem a entrada, falharia por ambiguidade. Isso é intencional: a ambiguidade nunca é resolvida por palpite.
- INE: `dico = geocod[-4:]`, e o resultado precisa estar em `municipalities`; senão o dataset reprova.

## 6. Cobertura

Para cada dataset: `latest_period = max(period)`; `municipalities_with_value` = municípios com ≥ 1 observação de `value` não nulo nesse período; `missing_dico` = os 308 menos esses. Ausente permanece ausente: o relatório lista e conta, nada é preenchido.

## 7. Promoção

Construir em `<root>/.build/observations/<uuid>/`; rodar `dbt build` selecionando só os modelos novos; promover **apenas** `lake/bronze/stg_observation` e `lake/bronze/rpt_observation_coverage` com `os.replace`, mantendo backup e desfazendo se uma das duas falhar. Não tocar em `lake/bronze/stg_caop_*` nem em `lake/silver/*`.
