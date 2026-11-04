# ADR-003: BYOK (Bring Your Own Key) para APIs externas

## Status

Aceita

## Data

2026-11-03

## Contexto

O living-recommender roda como site estático e calcula o ranking no navegador ([ADR-002](ADR-002-arquitetura-base-mvp.md), D1). Algumas funcionalidades dependem de APIs pagas ou com cota, que cobram por requisição:

- **Google Places:** serviços próximos, consultados online ([fontes_de_dados.md](../../.docs/fontes_de_dados.md) §3.3).
- **APIs de LLM** (Google Gemini, Anthropic, OpenAI…): possíveis funções futuras, como resumir a ficha de um município, explicar uma recomendação ou responder perguntas.
- **Fontes do pipeline** que exigem chave: WWO (fallback do clima) e Google Distance Matrix (cálculo único).

No piloto, o orçamento é de menos de US$ 10/mês ([ADR-002](ADR-002-arquitetura-base-mvp.md)). Uma chave do projeto exposta a um público anônimo cria um custo variável sem teto natural, além do risco de abuso. O autor quer evitar esse custo e, ao mesmo tempo, poder ligar uma chave própria facilmente quando precisar.

## Decisão

**Todas as integrações com APIs externas que usam chave seguem BYOK por padrão.** A chave pertence a quem usa a funcionalidade, e o projeto não paga por consumo de terceiros.

### Dois contextos de chave

| Contexto | Quem fornece a chave | Onde fica | Exemplos |
|---|---|---|---|
| **Online (navegador)** | O **visitante** (BYOK) ou, opcionalmente, o **projeto** | No navegador do visitante (`sessionStorage` por padrão; `localStorage` só se ele marcar "lembrar neste dispositivo") | Google Places, LLMs |
| **Pipeline (lote)** | O **autor**, como operador | SSM Parameter Store (na AWS) ou `.env` local, que o Git ignora | WWO, Google Distance Matrix |

### Ordem de resolução no navegador

Para cada funcionalidade que precisa de chave:

1. **Chave do visitante (BYOK)**, se ele informou uma.
2. **Chave do projeto**, se o autor habilitou essa funcionalidade em `config/providers.yml` e o provedor permite chave pública restrita (por exemplo, uma chave Google com restrição de HTTP referrer e teto de cota).
3. **Funcionalidade desativada**, com uma explicação do que ela faz e de como ativá-la com uma chave própria.

**O núcleo do produto não depende de chave:** ranking, mapa, fichas e infográfico funcionam sem nenhuma.

### Configuração (`config/providers.yml`)

```yaml
providers:
  google_places:
    capability: nearby_services
    modes: [byok, project_browser]   # project_browser só com chave restrita por referrer + cota
    project_key_enabled: false       # o autor liga quando quiser
  gemini:
    capability: llm
    modes: [byok]                    # chave de LLM do projeto nunca vai ao navegador
  anthropic:
    capability: llm
    modes: [byok]
pipeline_secrets:                    # resolvidos no SSM; nunca no Git
  wwo: /living-recommender/wwo/api_key
  google_distance: /living-recommender/google/distance_key
```

No frontend, uma camada `packages/providers/` define uma interface por capacidade (`NearbyServicesProvider`, `LlmProvider`). Cada provedor implementa essa interface, e trocar ou acrescentar um provedor não mexe no restante do site.

### Regras de segurança

- A chave do visitante **nunca é enviada a um servidor do projeto**, que não existe no MVP, nem aparece em logs, URLs ou links compartilhados (a URL guarda só preferências).
- O site é entregue com **CSP estrita**: `connect-src` lista apenas os provedores habilitados, e o site não carrega scripts de terceiros nem analytics.
- A interface **orienta o visitante** a criar uma chave restrita: restrição de domínio no Google, limite de gasto no provedor de LLM e um botão "apagar chave".
- **Chave de LLM do projeto não vai para o navegador.** Se o autor quiser oferecer LLM com chave própria, isso exige um proxy (Lambda com limite de uso), tratado como evolução abaixo.
- As chaves do pipeline seguem a regra do ADR-002 (D9): SSM ou `.env` local, nunca no Git.

## Alternativas Consideradas

### Chave do projeto para todos os visitantes

- O projeto paga todo o consumo online.
- **Rejeitada:** o custo varia com o tráfego anônimo e não tem teto natural. Uma chave exposta no navegador pode ser extraída e usada fora do site. No piloto, isso ameaça a meta de menos de US$ 10/mês.

### Proxy próprio (Lambda) guardando a chave do projeto

- O navegador chama uma Lambda, que injeta a chave e repassa a chamada ao provedor.
- **Rejeitada no piloto:** reintroduz o servidor que o ADR-002 (D1) evitou, com limitação de taxa, autenticação anti-abuso e custo por requisição. Fica como caminho de evolução.

### BYOK com a chave guardada num servidor do projeto (contas de usuário)

- O visitante cadastra a chave uma vez e usa em vários dispositivos.
- **Rejeitada:** exige contas, banco de dados e custódia de segredos de terceiros, contra a privacidade por padrão e o "sem cadastro" do produto.

### Não oferecer funcionalidades pagas

- Usar só dados estáticos.
- **Rejeitada:** perde o enriquecimento online (Places) e as funções de LLM que o autor quer experimentar. Com BYOK, elas existem sem custo para o projeto.

## Consequências

### Positivas

- O custo do projeto com APIs online é zero no piloto.
- O autor liga a chave do projeto por configuração quando quiser (por exemplo, para demonstrações), sem mudar código.
- Novos provedores (outro LLM, outro serviço de mapas) entram como uma implementação da interface.
- A chave do visitante fica só com ele; o projeto não guarda segredos de terceiros.

### Negativas

- **Atrito de uso:** a maioria dos visitantes não terá chave, então as funções com BYOK serão usadas por poucos. Elas precisam ser complementos, nunca o centro do produto.
- **Google Places com BYOK:** a chave do visitante precisa aceitar o domínio do site na restrição de referrer, o que dá trabalho para um usuário leigo. Na prática, essa funcionalidade tende a usar a chave do projeto, restrita e com cota.
- **CORS e navegador:** nem todo provedor aceita chamadas diretas do navegador, ou exige uma opção explícita para isso. É preciso verificar provedor por provedor antes de integrar.
- **Risco de XSS:** uma falha no site exporia a chave guardada no navegador. A mitigação é a CSP estrita, a ausência de scripts de terceiros e o `sessionStorage` como padrão.

### Caminho de Migração / Evolução Futura

| Gatilho | Evolução |
|---|---|
| O autor quer oferecer LLM sem exigir chave do visitante | Lambda proxy com chave no SSM, limite por IP e por dia e orçamento no AWS Budgets, via ADR próprio |
| Fase B comercial com uso recorrente | Reavaliar a chave do projeto com cobrança ou cota por usuário (exige contas) |
| Provedor sem suporte a chamada do navegador | Proxy mínimo só para esse provedor, ou descartá-lo |

A interface `packages/providers/` e o `config/providers.yml` não mudam nessas evoluções. Só muda o modo (`byok` → `project_proxy`).
