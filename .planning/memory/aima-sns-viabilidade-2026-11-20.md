# AIMA/SNS — avaliação factual e decisões do autor

Avaliação em `.sdd/assessments/viabilidade-das-fontes-aima-sns/`, veredito
needs-clarification por enquadramento de reutilização SNS ainda não fechado.
Não tratar a autorização robots como licença do dado. Nenhuma mensagem enviada,
nenhum coletor/catálogo/lake alterado nesta avaliação.

- O inventário antigo subestimou o Pordata 354: a dimensão `filter_1` preserva
  nacionalidade no bruto e no `stg_observation` vigente. Ano 2023/Brasil:
  308 DICO, 308 valores, soma 368.391; Lisboa 1106=33.407. Dataset municipal:
  103.488 linhas, 2008–2023. Moçambique nulo e ausência de Timor-Leste/Guiné
  Equatorial impedem chamar a soma de categorias disponíveis de CPLP completa.
- INE 0013219 consultado: último ano 2023, atualização 2024-09-20; 308
  categorias municipais, dez países específicos + Outros + Total. Não confundir
  com 0013193 (pedidos de estatuto, fluxo). Não há atualização temporal provada.
- RMA AIMA 2025: 71 páginas, setembro/2026; nacionalidade/gênero e concelho/gênero
  em tabelas separadas, anexo como imagem; nenhuma nacionalidade × concelho
  encontrada. Adenda 2024: nove páginas, texto extraível, 308 pares distrito/
  concelho e soma 1.543.697; ainda sem pipeline/validação DICO. Não equiparar
  o universo administrativo ampliado AIMA à série de estatuto legal INE/Pordata.
- Autor escolheu reaproveitar Pordata/avaliar INE e manter AIMA opcional;
  SNS nativo por ULS, associação municipal só com evidência e ausências explícitas.
- Autor aceitou exceção específica SNS a Disallow:/api/ (Constitution IV),
  somente leitura oficial, identificação, consultas seriais limitadas e respeito
  a bloqueios; licença como gate separado. Registro R-001 no explora.md.
- Depois da autorização: três consultas SNS sem chave/HTTP200 (metadata, amostra5,
  export JSON completo). 234 registros únicos =39 ULS×2 nacionalidades×3 meses,
  julho–setembro/2026; somas e taxas conferem em todos. Denominador das taxas é
  elegíveis menos sem médico por opção. Dados processados 2026-11-02; modified
  2026-08-11 não representa a última referência da série.
- Dataset antigo descontinuado: quebra em julho/2026, não concatenar métodos.
  Universo continental; Lisboa e outros municípios podem envolver várias ULS.
  Não atribuir taxa municipal por nome/sede ou média inventada.
- Licença null e license_url null nos metadados reais; registro exato no
  dados.gov.pt diz Licença não especificada. Termos remetem à legislação;
  não presumir CC BY genérica. Rascunho de esclarecimento pronto, não enviado.

Provas privadas em `.data/receipts/aima-sns-assessment/`; PDFs completos,
renderizações, HTML/robots, metadados e export/auditoria. Nenhuma prova de
implantação, coleta agendada, publicação ou cobertura municipal SNS completa.
