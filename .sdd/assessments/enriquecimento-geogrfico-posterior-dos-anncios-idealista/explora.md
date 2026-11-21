# Assessment Explora: enriquecimento geográfico posterior do Idealista

- **Slug**: `enriquecimento-geogrfico-posterior-dos-anncios-idealista`
- **Criado**: 2026-11-17
- **Origem**: pedido do autor para verificar geocodificação por endereço com Google Maps ou outra biblioteca/provedor.
- **Fase**: Explora concluída. Não há aprovação de implementação, orçamento, provedor ou atribuições novas no lake.

## Ideia Bruta

Depois da importação, extrair endereço/localidade dos anúncios, obter coordenadas e componentes administrativos, e recuperar município/freguesia para o living-recommender. O resultado precisa preservar proveniência e o grau de precisão realmente obtido.

## Evidência a Favor

### Diagnóstico reproduzível do lote real

Snapshot 2026-11, run `20261117T151513906158Z-d5bd7111`, SHA-256 `3d57043b54e30e3ab1143d8e0ddeccd9a2097a566833f2fb1edf7e41b705e0a4`.
Executado `uv run --locked python .sdd/assessments/enriquecimento-geogrfico-posterior-dos-anncios-idealista/diagnose.py`.
Os 74 hashes raw foram verificados. Saída agregada em [diagnostic.json](diagnostic.json); nenhum endereço individual foi versionado ou enviado a provedores.

| Medida | Resultado |
| --- | ---: |
| Anúncios | 18.059 |
| Títulos com indício textual de logradouro | 13.336 (73,8%) |
| Títulos com padrão de código postal português | 24 |
| Anúncios atualmente sem município | 6.371 |
| Desses, títulos com indício de logradouro | 4.682 |
| Candidato municipal único por nomes locais e distrito/ilha | 2.792 |
| Candidato de freguesia único nesse subconjunto | 2.563 |
| Sem candidato exato pelo método local | 3.569 |
| Com candidatos municipais divergentes/ambíguos | 10 |

O indício de logradouro procura palavras como rua, avenida, travessa, estrada, largo, praça, alameda, urbanização e caminho. Não comprova endereço postal completo. A primeira triagem contou 13.243 com uma expressão mais estreita; a versão final inclui variações de urbanização e é reproduzível pelo script.

O candidato local usa somente nomes completos normalizados de município/freguesia, sinônimos já explícitos e restrição ao distrito/ilha da captura. Procura o último segmento do título e o campo Freguesia. Não usa similaridade aproximada nem API. **Os 2.792 são candidatos para auditoria, não recuperação validada ou promessa de ganho. Nenhuma atribuição territorial foi promovida.**

### Capacidade técnica confirmada na documentação

- A [Google Geocoding API](https://developers.google.com/maps/documentation/geocoding/guides-v3/requests-geocoding) aceita endereços e retorna coordenadas, componentes administrativos, tipo do resultado, `location_type` e eventualmente `partial_match`. Pode retornar várias alternativas. Não é necessário fazer reverse geocoding depois de toda consulta se a resposta e a CAOP já atenderem ao objetivo.
- [geopy](https://geopy.readthedocs.io/en/stable/) é um cliente de provedores, não uma base de endereços offline. A consulta Context7 `/geopy/geopy` confirmou filtros de país, delimitação espacial, múltiplos resultados e controle de ritmo para Nominatim. Não cria cobertura ou permissão de armazenamento por si só.
- [GeoPandas](https://geopandas.org/en/stable/gallery/spatial_joins.html), já dependência do projeto, permite cruzar pontos com polígonos administrativos locais. Context7 `/geopandas/geopandas` confirmou `sjoin`, predicados espaciais e necessidade de CRS compatível.
- A CAOP já está disponível no projeto, com nomes, relações DICO/DICOFRE e limites originais ingeridos. Isso permite recuperar município a partir de uma freguesia identificada inequivocamente e validar coordenadas contra códigos oficiais.

## Evidência Contra

### Endereço e precisão

- Não há campo de endereço postal estruturado ou lat/lon nos JSON importados. O endereço está parcialmente embutido no Titulo, misturado a tipo de imóvel, bairro e localidade.
- Muitos anúncios não têm número de porta ou código postal; alguns trazem só uma área. Não enviar o título inteiro indiscriminadamente ao geocoder.
- Uma coordenada retornada pode representar a rua, bairro ou município. Centro da rua não comprova freguesia do imóvel; uma rua ou área pode cruzar limites.
- Google distingue ROOFTOP, RANGE_INTERPOLATED, GEOMETRIC_CENTER e APPROXIMATE. A ausência de `partial_match` não é prova suficiente de que o imóvel foi corretamente identificado.
- [OpenCage](https://opencagedata.com/api#confidence) explica que seu confidence mede principalmente extensão/precisão espacial, não probabilidade de o candidato estar correto. Não aprovar coordenadas apenas por um score alto.
- Campos administrativos dos provedores não devem ser associados cegamente a município/freguesia por posição ou por `city`. A hierarquia varia e pode diferir da CAOP vigente.
- O próprio contexto da captura não comprova endereço de cada imóvel; verificar consistência não substitui a revisão da evidência de endereço.

### Provedores, persistência e custo

| Opção | Avaliação para esta hipótese |
| --- | --- |
| Google Geocoding | Tecnicamente viável. Menor adequação inicial para um lake compartilhado e permanente: o contrato contém restrições de reutilização, cache e mapas. É preciso validar o contrato aplicável ao pipeline, incluindo região de faturamento. |
| OpenCage | Candidato a um piloto: documenta armazenamento permanente. Cobertura/acurácia em nossos endereços ainda não medidas. Produção é paga; trial é apenas para testes. |
| Nominatim próprio ou provedor contratado | Possibilidade com dados OSM e capacidade própria/contratada; avaliar atribuição/licença e operação. A API pública OSMF não deve ser tratada como infraestrutura gratuita para nosso lote mensal. |
| Somente CAOP e nomes | Sem chamadas externas ou coordenadas de imóvel inventadas. Pode recuperar parte da localização administrativa; não fornece geocodificação de rua/porta. |

Fontes atuais, consultadas em 2026-11-17:

- [Google: termos específicos](https://cloud.google.com/maps-platform/terms/maps-service-terms), §6: cache geral temporário de lat/lon de até 30 dias; exceção permanente atual limitada a funcionalidade direta do usuário final, com cache isolado por usuário e sem reutilização entre usuários. Essa exceção não deve ser interpretada automaticamente como autorização de base analítica compartilhada. [Termos EEA](https://cloud.google.com/terms/maps-platform/eea/maps-service-terms) diferem quanto ao uso com mapas e dependem da situação contratual/faturamento.
- [Google: políticas](https://developers.google.com/maps/documentation/geocoding/policies) restringem armazenamento e criação de conteúdo derivado. O exemplo explícito de point-in-polygon com Places não é prova isolada de proibição específica de todo uso da Geocoding API; o uso planejado exige verificar seu enquadramento contratual.
- [Google: preços](https://developers.google.com/maps/billing-and-pricing/pricing): Geocoding tem franquia publicada de 10.000 eventos/mês e primeira faixa paga de US$5/1.000. Exemplo aritmético, não orçamento aprovado: 18.059 consultas, uma por anúncio, com franquia integral disponível, sem retries/outros consumos, resultariam em aproximadamente US$40,30. Conta, créditos, impostos e consumo real não foram verificados; nenhuma chamada foi feita.
- [OpenCage: caching](https://opencagedata.com/api#caching) permite guardar respostas permanentemente. [Trial](https://opencagedata.com/pricing): 2.500 consultas/dia, 1/s, somente testes; não usar o trial como plano recorrente de produção. Permissão de cache não dispensa as obrigações de licença/atribuição dos dados aplicáveis.
- [Nominatim público: política](https://operations.osmfoundation.org/policies/nominatim/): máximo absoluto de 1 consulta/s, User-Agent identificável, atribuição e cache; lotes grandes/recorrentes desencorajados, tarefas periódicas limitadas a 4 consultas/minuto. A política também orienta não enviar material pessoal/confidencial. Regras não se aplicam automaticamente às instâncias próprias ou de terceiros.

### Contexto existente do projeto

A documentação `.docs/fontes_de_dados.md` retirou Google Geocoding do desenho anterior; o risco aceito para distâncias do Google não é aprovação automática de geocodificação de anúncios. A constitution exige fonte declarada, custo explícito, proveniência e proíbe publicar/versionar endereços e coordenadas exatas. Esta exploração não muda essas decisões.

## Abordagem Recomendada para Validar

1. Recuperação administrativa local primeiro: auditar amostra dos 2.792 candidatos e medir erro, sem alterar o lake vigente.
2. Extrair texto de endereço em campo separado, preservando título/contexto originais e sinalizando ausências.
3. Geocodificar somente casos necessários, com Portugal e contexto territorial conhecido; manter alternativas e precisão. Deduplicar consultas com cache compatível com o provedor.
4. Para provedor/licença compatível, cruzar ponto e região de incerteza com CAOP no mesmo CRS. Limites, múltiplos polígonos e candidatos divergentes geram revisão/ausência; nunca escolher o primeiro para preencher uma lacuna.
5. Guardar enriquecimento separado do raw, com provedor, consulta/instante, precisão, versão CAOP, método de associação e status de validação. Coordenadas de rua/bairro devem continuar identificadas como aproximadas; somente agregados saem para o produto.
6. Piloto sugerido, ainda não executado: 100 anúncios estratificados, combinando contexto territorial já conhecido, regionais com rua e casos incompletos/ambíguos. Medir concordância territorial, revisão manual, taxa de rejeição, precisão espacial e custo. Não assumir que o contexto já atribuído é ground truth independente do imóvel.

## Perguntas em Aberto

- Qual a precisão necessária: apenas município/freguesia ou também coordenada do imóvel? A primeira pode ser atendida sem coordenada exata.
- Qual provedor, contrato e orçamento seriam aprovados para um piloto real? Nenhuma chave foi procurada ou usada.
- Qual taxa de erro tolerável e procedimento de revisão para resultados ambíguos?
- Qual o ganho real após auditoria dos candidatos locais e geocodificação da amostra? Ainda não medido.

## Resultado da Exploração

Há viabilidade técnica documentada e evidência concreta no lote para investigar um enriquecimento posterior. A opção recomendada para o próximo experimento é combinar CAOP local com um piloto de geocoder que permita persistência, como candidato OpenCage, mantendo Google como alternativa contratualmente condicionada. Não há veredito de produção, ganho de cobertura aceito, código de pipeline novo ou consumo de API. Próximo passo SDD, caso o autor queira prosseguir: Define com escopo/critério de aceite e decisão do piloto antes de implementar.
