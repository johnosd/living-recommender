# Regras de coleta, extração e prontidão

## Identidade antes de texto utilizável

1. Validar catálogo, universo e correspondência completa/sem duplicatas.
   Congelar snapshots de catálogo, dimensão e associações; calcular hashes.
2. `pending_review` bloqueia a unidade. `absent` só é concluído com revisão
   humana, buscas/candidatos e evidência. Um título missing não prova ausência.
3. `validated` exige page ID, escopo municipal/combinado e evidência de
   abrangência; confirmar na resposta/trecho normalizado, além de ID e QID
   declarado. Se a evidência deixou de existir, marcar identity_pending,
   não aceitar nem procurar automaticamente outro município.
4. Ausência de pageprops.disambiguation é verificada por presença da chave,
   não por truthiness: a API pode retornar a chave com string vazia.
5. Confirmar query.pageid == parse.pageid == associação.page_id e
   query.revisions[0].revid == parse.revid. Usar metadado da mesma página,
   não a primeira arbitrária de uma lista. Revisão trocada/restrita é erro.
6. QID opcional não é licença para coletar declarações; ligação inglesa é
   metadado observado, não tradução nem prova de equivalência territorial.

Casos de regressão: Cuba/país, Corvo e Gavião/aves, Nazaré/outro país,
Santa Cruz/desambiguação. Artigo sobre cidade e município pode ser curado
como municipality_and_seat; dados de cada abrangência não viram estatísticas.

## Histórico por unidade, coerência por ciclo

```text
congelar contexto
para cada DICO do universo:
    se resume e sucesso já verificado no mesmo contexto/ciclo: reutilizar entry
    se ausência curada: registrar absent + evidência
    senão: obter metadata + parse exato; validar identidade/revisão/evidência
    comparar fingerprint sem confundir assinatura de contexto com hash físico
    para cada role cujo byte já exista no estado anterior: reutilizar referência
    gravar apenas bytes novos validados em raw imutável
    registrar changed/unchanged ou failed; jamais sobrescrever bruto
ao terminar/interromper:
    incluir pending para não tentados
    gravar manifest completo do ciclo; somente este confirma os raw referenciados
    gravar relatório da tentativa fora do lake vigente
```

Falha na gravação de manifest não confirma estado. Órfãos de processo morto
são ignorados; limpeza só por run e depois de auditoria. Falhas recentes têm
precedência no relatório operacional, mesmo se existir conteúdo anterior válido.
Build padrão considera a última tentativa e reprova se incompleta; seleção
antiga explícita não apaga/resolve a falha atual.

Dois runs não devem alterar estado ao mesmo tempo: CLI local com lock exclusivo
por fonte, PID e journal. Na morte do processo, não excluir lock cegamente;
verificar PID, journal e manifests. Core público aceita dependências injetadas,
enquanto a CLI garante single writer e snapshots físicos estáveis.

## Estrutura editorial e normalização

Extrair apenas da raiz `.mw-parser-output`. Remover scripts/styles e controles
de edição/navegação (`mw-editsection`, TOC, navboxes e controles interativos)
por lista explícita versionada. Preservar avisos de licença/atribuição adicional,
referências e legendas textuais; não baixar `img/src`, SVG ou recursos externos.
Conteúdo desconhecido substantivo não pode simplesmente ser descartado.

Normalizar `tocdata.sections[*].hLevel/anchor/index/line` ou
`sections[*].level/anchor/index/line` para um índice comum. Os títulos reais
são correspondidos por anchor e ordem aos headings dentro do corpo, inclusive
wrappers `div.mw-heading`; o h2 do índice não é seção editorial. Índice
incoerente ou heading substantivo não representado exige diagnóstico/falha,
não sucesso completo. Extrair títulos como texto, sem markup de edição.

Criar seção `lead` nível 0 para texto anterior ao primeiro heading editorial.
Manter pilha de seções por nível: ao chegar a heading de nível L, desempilhar
níveis >=L e abrir nova seção. Cada seção tem pai/ordem estáveis. Uma seção
sem blocos continua existindo; o algoritmo nunca usa find_next para lhe
emprestar o parágrafo de outra seção.

Percorrer DOM em ordem, com propriedade única de cada nó textual:

- Parágrafo gera bloco de texto e referências/links inline.
- Listas geram container e filhos; cada item/subitem preserva pai e ordem.
- Tabela gera container → linha → célula; tabela dentro de célula tem outro
  container/ancestral. Usar filhos diretos para linhas/células, nunca todos
  os descendentes como se pertencessem à mesma tabela. Cabeçalhos, colspan,
  rowspan e legendas ficam registrados como contexto, sem tipar indicadores.
- Quando um container tem descendentes, não repetir a concatenação desses
  textos no próprio container. Texto próprio entre filhos vira fragmento
  ordenado; full_text lineariza as folhas uma única vez.
- Tags inline não criam parágrafos separados. Manter whitespace existente,
  normalizar quebras/NBSP de modo documentado e separar blocos/itens/células.
  Não usar `get_text(strip=True)` em toda a árvore; isso cola palavras/listas.
- Links/ref têm href original, texto, bloco e tipo; fragmentos podem apontar
  para referências posteriores. Não resolver links por rede. Texto da lista
  de referências é preservado em sua seção; IDs são auditáveis.

Introdução é a linearização narrativa de lead; infobox e navegação não viram
introdução. full_text inclui texto editorial (inclusive textual de tabelas,
legendas e referências) uma vez. Auditoria de cobertura dos nós textuais após
as exclusões, comparação dos headings com índice e contagens de blocos
detectam perdas. Não usar contagem de caracteres como prova única de completude.
IDs locais são estáveis dentro da mesma entrada/regras; títulos duplicados
usam posição/anchor, nunca título como chave única.

### Containers que abrangem várias seções

A auditoria real encontrou tabelas de layout e blockquote envolvendo headings
em Ferreira do Alentejo, Peniche, Sintra e Vila Real. O container registra a seção
de abertura; cada folha registra a seção atual do seu texto. Containers com
filhos mantêm texto nulo, preservando a hierarquia sem duplicar a concatenação.
A linearização usa títulos e folhas ordenadas por seção/bloco; a reconstrução
foi conferida nos 308 artigos. Consumidores devem agrupar as folhas pelo seu
próprio section_id. O vínculo parent_block_id conserva o contexto físico do DOM
mesmo quando um container atravessa mais de uma seção.

## Preparação e transação local

Verificar todos os arquivos/roles e hashes da entrada selecionada. Construir
Parquet com schemas explícitos; candidato e banco DuckDB isolados. Rodar dbt
somente na tag wikipedia, conferir exportação, contagem, relacionamentos,
prontidão e hashes de dependências ainda iguais.

Processing signature equivalente à vigente, com integridade comprovada:
retornar unchanged sem mover lake; relatório da tentativa nova fica em reports.
Senão gravar journal com destinos/backup/hashes antes de promover caminhos
Wikipedia. Commit só após todos os destinos conferirem; rollback para erros
capturados. Interrupção abrupta deixa journal recuperável e bloqueia outro
build até finalizar/voltar a transação. Nunca substituir bronze/silver inteiros.

## Prontidão

Cada DICO esperado precisa ter exatamente uma linha. `valid` exige identidade
e extração completas + revisão; `absent` exige evidência revisada. Códigos
extras/duplicados/perdidos, falha, identidade pendente, perda de conteúdo,
hash/revisão inválida e input_errors são blockers. Ausência legítima de
introdução/tema não é falha. Recontar do universo; não aceitar apenas o
tamanho da lista como prova de cobertura. Zero artigos com 308 ausências
não se presume aceitável sem evidência individual suficiente.
