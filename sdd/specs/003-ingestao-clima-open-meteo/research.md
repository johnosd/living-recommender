# Research: Ingestão de clima Open-Meteo

Medições e consultas de 2026-11-11. As sondagens usaram a API pública sem credenciais, um ponto por vez, uma semana de dados, e nenhum dado do projeto foi enviado.

## R1. Modelo de reanálise

**Decisão:** `models=era5`, fixado no catálogo e registrado em cada entrada do manifest.

**Justificativa:** sondagem em Lisboa (38.72, -9.14), 2025-01-01 a 2025-01-03, com as 13 variáveis da spec:

| Modelo | Grade | Variáveis completas (de 13) | Observação |
| --- | --- | --- | --- |
| `era5_land` | 0,1° (~11 km) | **4** (temperatura média, máxima e mínima; umidade) | `null` em sensação térmica (3), precipitação, neve, sol, vento médio, vento máximo e rajada |
| `era5` | 0,25° (~25 km) | **13** | Ponto pedido (38.72, -9.14) → grade (38.75, -9.25) |
| `best_match` | mistura | 13 | Grade e valores diferem dos dois acima (38.699, -9.196); combina modelos, então a série não é reproduzível nem homogênea |

O `era5_land` não serve ao conjunto base. O `best_match` entrega as 13 mas não declara um modelo, o que fere a rastreabilidade (constitution III). O `era5` é completo e explícito.

**Consequência:** a resolução é de ~25 km. Municípios vizinhos podem cair na mesma célula e receber séries idênticas, e o relevo fino (Serra da Estrela, Madeira) fica suavizado. Isso é uma limitação da fonte, registrada em R-004 do plano e visível no relatório de pontos.

**Alternativas consideradas:** `era5_land` (descartado: variáveis nulas); `best_match` (descartado: não reprodutível); `ecmwf_ifs` (9 km, desde 2017, não é reanálise); duas chamadas, `era5_land` para temperatura e `era5` para o resto (descartado: dobra a cota e mistura grades no mesmo município).

## R2. Fuso horário e dia calendário

**Decisão:** `timezone=auto` em toda requisição; a data da observação é o texto `time` da resposta, sem conversão.

**Justificativa:** a sondagem confirmou `Europe/Lisbon` (Lisboa), `Atlantic/Madeira` (Funchal, offset 0) e `Atlantic/Azores` (Ponta Delgada e Corvo, offset −3600 s). Com `timezone=auto` a fonte já agrega o dia no fuso do município e devolve `time` como data local (`2025-03-29`). Converter ou reinterpretar essa data deslocaria dias nas ilhas.

**Alternativas consideradas:** `timezone=UTC` com conversão posterior (descartado: o dia agregado em UTC não é o dia local); um fuso por região no catálogo (descartado: reimplementa o que a fonte já faz).

## R3. Peso das requisições e cota

**Decisão:** uma requisição por município cobrindo a janela inteira; controle de cota por classificação do HTTP 429 e retomada (D4, D5 do plano).

**Justificativa:** da página de preços do Open-Meteo (consultada em 2026-11-11): plano gratuito com 600 chamadas/min, 5.000/h, 10.000/dia e 300.000/mês; uma requisição pesa 1 chamada, e mais se pedir mais de 10 variáveis ou mais de 2 semanas. A página dá os exemplos "15 variáveis em 2 semanas = 1,5" e "4 semanas = 3,0".

Estimativa para 1 município, 24 meses, 13 variáveis: a regra publicada (dias ÷ 14 × variáveis ÷ 10) dá ~68 chamadas, e a leitura dos exemplos acima sugere até ~100. Para os 308 municípios: **21 mil a 31 mil chamadas**, ou seja, 3 execuções diárias; a cota por hora (5.000) limita a ~50 a 70 municípios por hora. **O peso real não é exposto pela API**; é medido na primeira coleta real (SC-008, T037).

**Alternativas consideradas:** uma requisição por ano ou por trimestre (descartado: mais requisições e nenhuma economia de cota, pois o peso é proporcional aos dias); reduzir para 10 variáveis (descartado: a spec fixa 13); chave comercial (descartado: custo e fora do escopo).

## R4. Texto das respostas 429 (não verificado)

**Decisão:** classificar o `reason` do corpo JSON por palavra-chave (`minutely`, `hourly`, `daily`, sem diferenciar maiúsculas); um 429 sem palavra reconhecida é tratado como limite **horário** (espera e, se persistir, pausa).

**Justificativa:** o formato `{"error": true, "reason": "Daily API request limit exceeded. Please try again tomorrow."}` e as variantes "Minutely…" e "Hourly…" são o que a documentação e a comunidade descrevem, mas **não foi possível provocar um 429 para confirmar** sem gastar a cota. Os testes usam esses textos como fixture (`tests/fixtures/open_meteo/responses.py`). O comportamento padrão para um texto inesperado é seguro: espera e depois pausa com `pending`, nunca falha o município.

**Verificação:** na primeira coleta real (T037), se a cota diária for atingida, registrar o texto real e ajustar a fixture em uma emenda.

## R5. Metadados voláteis da resposta

**Decisão:** a impressão digital é o SHA-256 do JSON canônico (chaves ordenadas, separadores compactos) da resposta **sem `generationtime_ms`**.

**Justificativa:** nas sondagens, `generationtime_ms` variou de 0,08 a 166 ms entre chamadas equivalentes; os demais campos (`latitude`, `longitude`, `elevation`, `timezone`, `daily_units`, `daily`) foram estáveis. O bruto gravado mantém os bytes originais, inclusive esse campo.

**Alternativas consideradas:** `sha256` dos bytes (descartado: toda recoleta viraria `changed`); comparar só `daily` (descartado: mudança de grade ou fuso passaria despercebida).

## R6. Ponto devolvido e células de mar

**Decisão:** guardar as coordenadas pedidas e as devolvidas, mais a elevação, e sinalizar no relatório de pontos a distância acima de um limite do catálogo (`point_divergence_km: 25`). Nenhuma correção automática.

**Justificativa:** a grade do `era5` desloca o ponto em até ~17,6 km (meia diagonal de 0,25° a 38° N). No Corvo, o ponto pedido (39.67, -31.10) virou (39.75, -31.00), a ~12 km, com `elevation: 0.0`, o que indica célula de mar. A distância sozinha não pega esse caso; por isso o relatório mostra também a elevação. O limite de 25 km sinaliza deslocamentos acima do esperado para a grade (por exemplo, uma mudança de modelo), e a elevação zero fica visível para revisão humana.

**Alternativas consideradas:** mover o ponto para terra (descartado: fora de escopo e altera a identidade da consulta); reprovar o município (descartado: a ausência não é erro do dado).

## R7. Ferramentas e dependências

**Decisão:** nenhuma dependência nova. `httpx` (cliente e `MockTransport` nos testes), `pandas`/`pyarrow` (staging), `dbt-duckdb` (testes e relatórios) e `moto` (S3) já estão no `pyproject.toml`. A distância entre pontos usa haversine em Python puro.

**Justificativa:** o cliente oficial `openmeteo-requests` não traz o que o projeto precisa (classificação de cota, `MockTransport`, mesmo `HttpDownloader`/`RateLimiter`) e adicionaria o `flatbuffers`. O JSON basta e é o formato guardado no bruto.

## R8. Reutilização do coletor da spec 002

**Decisão:** extrair o miolo de `collect_datasets` para `collect_items` (compartilhado) e acrescentar `pending`, parada limpa, "estado atual" e campos extras na entrada. `collect_datasets` vira um invólucro de `collect_items` com o mesmo comportamento.

**Justificativa:** o estado por unidade, o manifest v2, a impressão digital e a tolerância a falha são exatamente o que a coleta por município precisa. O contrato travado da spec 002 (5 testes) e os 140 testes existentes protegem a refatoração. A alternativa, copiar a lógica, duplicaria ~100 linhas e duas versões do estado vigente.

**Alternativas consideradas:** um coletor independente (descartado: duplicação); inflar o catálogo com 308 "datasets" (descartado: o catálogo declara fontes e variáveis, não unidades territoriais, e `get_dataset_source` exigiria `origin` por município).

## Verificação real durante a execução — 2026-11-11

- Smoke: `collect_open_meteo --local --max-municipalities 5 --no-wait`, 5 municípios `changed`, sem falhas, manifest `20261111T211829262830Z-36cc8a22.json`.
- Recoleta de três: `--recollect --max-municipalities 3 --no-wait`, 3 `unchanged`, sem bruto novo, manifest `20261111T212008362763Z-905bcdf9.json`.
- Continuação: `collect_open_meteo --local --no-wait`, 66 novos `changed`, 237 `pending`, os 5 atuais pulados, zero `failed`; manifest `20261111T212026185704Z-07fed17b.json`. Estado acumulado: **71/308** atuais, 237 faltantes, 4.094.681 bytes de bruto vigente.
- R4 parcialmente confirmado: o HTTP 429 horário trouxe exatamente `Hourly API request limit exceeded. Please try again in the next hour.`, igual à fixture sintética travada `HOUR_LIMIT`. A coleta parou e gravou as pendências. Minuto e dia ainda não foram observados na fonte real; nenhuma fixture travada foi alterada.
- R3: 74 consultas concluídas (71 iniciais + 3 recoletas) antes dessa pausa horária. O peso faturável não é exposto pela API e tentativas de transporte não foram instrumentadas; não tratar essa contagem como medição direta da cota ponderada. Ainda faltam os demais municípios e os limites de outro dia para concluir SC-008/T037.
- Build real parcial: **673.790 observações**, 71 municípios completos nas 13 variáveis, sem lacunas, 237 não coletados; nenhum ponto >25 km e nenhum com elevação 0 m nesse subconjunto. Os 7 arquivos das outras tabelas CAOP/observações permaneceram byte a byte iguais (SHA-256 antes/depois).
- Atribuição Open-Meteo/ERA5, restrição de uso não comercial e CC-BY-4.0 conferidas nos manifests e nas 673.790 linhas reais. Brutos e relatórios reais estão só em `.data/`, ignorada pelo Git.

Esses resultados são prova local parcial da fonte. Não demonstram 308/308, S3 real, CI remoto, deploy ou publicação.

## Retomada e CI remoto — 2026-11-11, 22:03 UTC

Retomadas `collect_open_meteo --local --no-wait` às 21:53 e 22:00 UTC devolveram código 2, com 71 municípios já atuais pulados e 237 pending por `Hourly API request limit exceeded. Please try again in the next hour.`. Nenhum bruto novo foi gravado; o estado vigente e as 673.790 observações existentes permanecem válidos. A virada da hora UTC não demonstrou liberação da cota; seu instante exato continua desconhecido.

CI remoto confirmado separadamente da coleta: [PR #3](https://github.com/johnosd/living-recommender/pull/3) em rascunho, autorizado pelo autor, e [run 43107887816](https://github.com/johnosd/living-recommender/actions/runs/43107887816) no commit afa0903. Quality: 209 passed, 1 skipped específico de Windows, lint e três builds dbt verdes (31/31, 17/17, 23/23). Secrets: gitleaks v8.30.1, 17 commits examinados, sem achados. O status de T037 continua pendente até 308/308; a verificação remota não amplia a cobertura real de 71 municípios.
