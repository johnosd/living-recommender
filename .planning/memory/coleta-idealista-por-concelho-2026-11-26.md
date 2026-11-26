# Coleta do Idealista por concelho e pausa do ranker (2026-11-26)

## Por que a amostra municipal é pequena

- Novembro de 2026 foi extraído por concelho só em Lisboa, Porto e Faro: a fila do coletor
  (`J:/IdealistaScraper`) só dividia distritos com mais de 1 800 anúncios. Os outros 6 371 anúncios vêm sem
  `Município`; a importação não descarta nada.
- Os concelhos de Lisboa e do Porto foram cortados em 60 páginas (1 793 e 1 746 anúncios; em 2026-11-26 o site
  mostrava 5 786 e 2 721). As medianas desses dois concelhos usam amostra parcial.
- Agosto de 2025 foi extraído por concelho em quase todo o país (278 municípios com anúncios, 101 com 10 ou mais).

## Encaminhamento

- Feature `007-coleta-por-concelho` especificada no repositório do coletor. A primeira coleta com ela é a próxima
  mensal.
- Quando a coleta nova chegar: conferir linhas de correspondência de nomes de município na importação e decidir se o
  registro de completude passa a ser lido aqui.
- Pendente de decisão do autor neste projeto: a spec do coletor aceita paginar apesar do `robots.txt`, com proxy
  opcional e reverificação automática. Isso contraria a constitution IV, a ADR-002 D4 e o plano §3.4.

## Ranker (Fase 4): entrevista pausada

Nenhum arquivo de spec foi criado. Respostas já dadas: primeira spec só com municípios; cobertura mínima de 70%
conforme a ADR-002; aluguel herdado conta igual, sinalizado. Em aberto: nota do aluguel (esperando a coleta nova),
pesos e faixas, sede de distrito.
