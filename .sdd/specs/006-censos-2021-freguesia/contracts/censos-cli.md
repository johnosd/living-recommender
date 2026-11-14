# Contract: comandos e fronteiras públicas dos Censos

## Collection (a implementar)

`uv run --locked python -m pipelines.cli.collect_censos --local --root .data`

Mesmos argumentos de destino/catálogo dos coletores existentes (`_common.add_destination_arguments`), sem provisionar AWS; testes S3 podem usar moto. `--catalog <arquivo>` permite fonte controlada. Fonte `censos`, um run novo por comando. Sem segredo/chave. No handler injetar storage/downloader como no stub; network só na CLI.

Resultado público: `{status, run_id, manifest_key, datasets}` do manifest v2. Cada item acrescenta snapshot/assinatura/geografia/edição. Status changed/unchanged/partial/failed; não lançar por falha individual. Catálogo/destino inválido antes da execução pode lançar DatasetCollectionError. CLI usa `_common.exit_code`, saída legível por dataset e mensagem de erro útil. Não usar só HTTP 200 como sucesso.

## Preparation and build (a implementar)

`uv run --locked python -m pipelines.cli.build_censos --local --root .data [--run-id <run-completo>]`

Somente local nesta entrega. Sucesso exit 0; falha de entrada, prontidão, dbt ou promoção exit 1; erro de argumentos exit 2. Reportar edição, geografia, run selecionado, freguesias esperadas, quantidades own/inherited/missing e diretório dos relatórios. `--run-id` escolhe o manifest da coleta, não uma nova data censitária.

Default: o manifest mais recente deve ser completo, não esconder falha recente escolhendo automaticamente uma versão antiga. `unchanged` é completo e reutiliza brutos anteriores apontados no manifest. Nunca consultar INE durante o build.

## Public data operations

As assinaturas dos quatro stubs são a superfície dos contratos executáveis. Os DataFrames de leitor/align seguem data-model.md. Nomes públicos fixos: source_dicofre, geography_version, period, age_code, age_min, age_max, is_total, value, value_status; na saída territorial, dicofre, dico, coverage_status, reason e origem. `assess_censos_coverage` retorna ready (bool), blockers (lista de códigos), expected_observations (int), counts (dict own/inherited/missing). Validação de estrutura lança ValueError ou subclasse.

No contrato de cobertura, prepared já é a saída normalizada e validada; a orquestração fornece os input_errors detectados antes. Sua contagem não depende de dados reais nem de número nacional fixo.
