# Logic: precedência, herança e prontidão

## Public boundaries

Interfaces públicas implementadas, não travadas em `pipelines/collectors/censos2021/`: `collect_censos(catalog, *, storage, downloader, run_id, collected_at_utc, work_dir) -> dict`; `read_censos_response(dataset, path, metadata) -> DataFrame`; `align_censos(observations, parishes, crosswalk, *, categories, target_version) -> DataFrame`; `assess_censos_coverage(prepared, parishes, categories, *, input_errors=()) -> dict`.

O leitor conserva código oficial de idade e limites. Um estágio explícito de harmonização entre leitor e align converte categorias por limites, preservando em Bronze as observações originais. Assinatura planejada `harmonize_age_categories(observations, categories) -> DataFrame`, em `transform.py`. `target_version` deve coincidir com uma única `parishes.caop_version`; fallback só entende origem 2013 e destino 2025 nesta entrega. Inputs desconhecidos reprovam.

## L1 — Coleta e snapshot

1. Validar e copiar o catálogo resolvido antes da primeira requisição.
2. Cada fetch produz entry_extra com snapshot, assinatura estável dos parâmetros/geografia/versões declaradas, reference_period 2021 e URL efetiva.
3. Cada item é validado antes de persistir. Dados exigem Sucesso.Verdadeiro, indicador correto, Dados contendo só 2021, sexo/nacionalidade totais, idade solicitada, códigos oficiais e valores válidos; metadados usam IndicadorNome/Dimensoes, não exigem Dados.
4. Fingerprint = hash da assinatura + JSON canônico sem DataExtracao. Revisão/alteração etária/geográfica é material. Não ignorar campos estatísticos.
5. Compartilhar o coletor genérico com validação específica, sem alterar semântica dos outros coletores.

## L2 — Compatibilidade e precedência por observação

Compatibilidade precisa de: versão declarada oficial, códigos válidos no universo apropriado, vínculo documental à geografia CAOP e método oficial de reexpressão registrado (ou indicação explícita de que o método não foi divulgado, com fonte que estabeleça a geografia). Não inferir método. Se a equivalência necessária não está demonstrada, não classificar como own.

Para cada destino × categoria:

```text
se existe observação oficial compatível de mesma precedência:
    conflito de valores/metadados -> erro, não aceitar vencedor arbitrário
    usar valor ou estado oficial (inclusive supressão); não fazer fallback para revelar valor oculto
senão, se ausência na geografia principal tem evidência oficial:
    avaliar pares da correspondência compatível 2013 -> 2025
    par completo um-para-um e sem origem parcial -> own com proveniência de correspondência
    par um-para-muitos sem origem parcial e sem múltiplas origens do destino -> inherited, valor integral da união
    qualquer origem parcial/muitos-para-muitos/múltiplas origens sem equivalência -> missing/territorial_ambiguity
    sem par/origem publicada -> missing com motivo oficialmente documentado
senão:
    missing_record -> bloqueio; não fabricar not_published
```

Nunca somar origens territoriais automaticamente, nem usar a dimensão de destino para fingir que o valor integral da união é exclusivo de uma freguesia. Troca de município usa o DICO do destino; origem sem município conhecido é erro; origem com município conhecido e sem freguesia de destino gera aviso auditado. Crosswalk com `partial_origin=true` bloqueia inferência mesmo em relação rotulada one_to_one. `name_changed` não prova mudança territorial.

As fixtures públicas do contrato 4 contêm observações principais só para parte do universo, para exercitar a resolução; na orquestração real, o gate de completude das entradas antecede align e impede mascarar uma consulta perdida. A função de align não faz coleta nem presume prontidão das entradas.

## L3 — Readiness

`expected = set(parishes.dicofre) × set(categories.age_code)`; period fixo 2021. Comparar chaves exatas, não apenas quantidades. Duplicação, extras, lacunas e estados inválidos geram blockers. `counts` soma observações por coverage_status, não pessoas. `missing_record` indica chave esperada que nem chegou à saída; `unexplained_absence` é missing sem motivo aceitável. Propagar input_errors de coleta/validação.

Motivos aceitos para ausência: `territorial_ambiguity`, `official_suppression`, `official_not_applicable`, `official_not_published` com evidência vinculada. Método territorial desconhecido só permite ausência documentada, nunca precisão inventada. Falta de faixa nos metadados selecionados, limites insuficientes para 25–39/65+, coleta falhada, hash inválido, perda de registro ou categoria não verificada bloqueiam conclusão. Contrato 5 usa universo etário reduzido para testar cobertura; o gate de seleção etária nacional é adicional em T008/T009.

## L4 — Build, isolamento e preservação

`prepare_censos(root: Path, candidate: Path, *, run_id: str | None = None, catalog_path: Path | None = None) -> dict` em `prepare.py` resolve um manifest completo e verifica suas referências; não consulta a rede. Não requer o catálogo atual para reconstruir snapshots antigos; usa snapshot persistido, validando uma eventual seleção explícita.

`build_censos(root: Path = Path('.data'), *, run_id: str | None = None) -> dict` em `pipelines/cli/build_censos.py`:

1. Resolver caminhos canônicos Windows e verificar dimensões/versões; obter lock exclusivo de build censitário por raiz, com erro claro se ocupado e sem remover lock alheio automaticamente.
2. Criar candidato em `root/.build/censos/<uuid>` após verificar confinamento dos caminhos. Congelar hashes das dependências, construir Bronze/Silver e relatórios inteiros no candidato.
3. Reprovar se readiness false. Rodar dbt `--select tag:censos`, com DB/target/log exclusivos do candidato. As dependências territoriais são somente leitura; verificar que seus hashes não mudaram até a promoção.
4. Validar presença de TODOS os caminhos previstos (promote_paths ignora ausentes; a feature deve reprová-los antes). Promover somente as quatro tabelas e o diretório census_reports com rollback em erro de rename.
5. Liberar lock próprio; limpar somente candidato próprio após conferir caminhos. Não apagar raw, dimensões ou saídas de outras fontes. Falha guarda diagnóstico em `.data/reports/censos/<build-id>/`, separado de census_reports vigente.

O helper existente fornece rollback em falhas de movimentação; não promete transação ACID contra queda do processo nem leitura concorrente. Registro de build em andamento interrompido exige diagnóstico e recuperação documentada antes de nova promoção. Não criar nova publicação/current.json neste escopo.


## Execução — proteção pós-promoção (T025/R-008)

O adapter local da006 calcula hashes dos arquivos candidatos antes de promover. Se o helper compartilhado falha na limpeza de backups após mover TODOS os caminhos, o build só considera a versão aceita quando nenhum caminho promovido permanece no candidato e todos os bytes vigentes coincidem com os hashes esperados. Nesse caso, registra aviso de manutenção em reports/censos e stderr; não reescreve relatórios vigentes depois da promoção. Qualquer falha anterior continua reprovando e exercitando rollback. O helper compartilhado permanece intacto. Limpeza de candidato/lock próprio também é manutenção, sem mascarar a exceção principal.
