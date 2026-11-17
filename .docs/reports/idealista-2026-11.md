# Relatório Idealista — 2026-11

Fonte: Idealista, extração manual; período informado pelo operador. Licença: `not_granted_by_source`; uso restrito, sem publicação de anúncios.
Run: `20261117T151513906158Z-d5bd7111`. SHA-256 do snapshot: `3d57043b54e30e3ab1143d8e0ddeccd9a2097a566833f2fb1edf7e41b705e0a4`.
Importado em: 2026-11-17T15:15:13Z. Horário original da coleta: desconhecido.

## Volume e qualidade

| Medida | Valor |
| --- | ---: |
| Arquivos JSON | 74 |
| Bytes originais | 19531665 |
| Ocorrências | 18059 |
| Anúncios únicos | 18059 |
| Ocorrências excedentes | 0 |
| IDs com campos divergentes | 0 |
| Conflitos de município | 0 |
| Anúncios mantidos no nível regional | 6371 |
| Freguesia resolvida | 10751 |
| Municipais sem freguesia | 937 |
| Preço ausente ou inválido | 0 |
| Área ausente ou inválida | 0 |
| Tipologia ausente ou inválida | 0 |

## Cobertura e interpretação territorial

54/308 municípios têm anúncios atribuídos; 42 têm pelo menos 10 preços elegíveis.
No formato novo, Município vazio mantém o anúncio regional: distrito/ilha homônimo não vira município. Freguesia explícita é resolvida apenas dentro de um município comprovado por CAOP/seed. No legado, mantém-se a interpretação do arquivo e do título. A hierarquia é contexto da captura, não endereço verificado.
Ausência de amostra municipal não significa ausência de oferta: anúncios regionais não são distribuídos por palpite.
As diferenças de escrita entre freguesias do exportador e CAOP só são aceitas por sinônimos explícitos em idealista_metadata_parish_synonyms.csv. Nomes genéricos ou não resolvidos continuam sem DICOFRE.
O catálogo de links e o número de páginas no arquivo não comprovam esgotamento da oferta ou coleta completa. Arquivos com 60 páginas podem ter truncamento; não há evidência suficiente para certificar completude.

## Preços pedidos no lote

Valores em EUR/mês de anúncios únicos, não rendas de contratos celebrados. Preço ausente/inválido ou com conflito entre duplicatas é excluído. Mediana e quartis usam interpolação linear, somente com n elegível ≥ 10. Nenhum outlier é removido automaticamente. Não há controle aqui de sazonalidade, duração do contrato ou composição dos imóveis.
O resumo do lote mistura territórios e tipologias; não representa a renda mediana de Portugal.

| Território / grupo | Anúncios | n elegível | P25 | Mediana | P75 | Situação |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Lote inteiro (inclui regionais) | 18059 | 18059 | € 1.000,00 | € 1.350,00 | € 2.000,00 | amostra suficiente |

### Por tipologia (lote inteiro)

| Território / grupo | Anúncios | n elegível | P25 | Mediana | P75 | Situação |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| T0 | 1213 | 1213 | € 725,00 | € 850,00 | € 1.000,00 | amostra suficiente |
| T1 | 4265 | 4265 | € 850,00 | € 1.050,00 | € 1.300,00 | amostra suficiente |
| T2 | 6265 | 6265 | € 1.100,00 | € 1.350,00 | € 1.800,00 | amostra suficiente |
| T3 | 4348 | 4348 | € 1.250,00 | € 1.700,00 | € 2.400,00 | amostra suficiente |
| T4+ | 1968 | 1968 | € 1.950,00 | € 3.000,00 | € 6.000,00 | amostra suficiente |

### Municípios com amostra

Todos os municípios, inclusive sem amostra, constam em municipality_stats.csv e statistics.json. O recorte município/tipologia também está em municipality_typology_stats.csv e statistics.json.

| Território / grupo | Anúncios | n elegível | P25 | Mediana | P75 | Situação |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Lisboa | 1793 | 1793 | € 1.590,00 | € 2.070,00 | € 2.950,00 | amostra suficiente |
| Porto | 1746 | 1746 | € 1.000,00 | € 1.250,00 | € 1.620,00 | amostra suficiente |
| Cascais | 1611 | 1611 | € 1.700,00 | € 2.600,00 | € 5.146,00 | amostra suficiente |
| Vila Nova de Gaia | 716 | 716 | € 1.000,00 | € 1.300,00 | € 1.800,00 | amostra suficiente |
| Loulé | 681 | 681 | € 1.400,00 | € 1.950,00 | € 3.300,00 | amostra suficiente |
| Matosinhos | 579 | 579 | € 1.000,00 | € 1.250,00 | € 1.750,00 | amostra suficiente |
| Oeiras | 548 | 548 | € 1.350,00 | € 1.800,00 | € 2.350,00 | amostra suficiente |
| Sintra | 458 | 458 | € 1.150,00 | € 1.400,00 | € 2.200,00 | amostra suficiente |
| Portimão | 357 | 357 | € 900,00 | € 1.200,00 | € 1.500,00 | amostra suficiente |
| Mafra | 308 | 308 | € 1.250,00 | € 1.500,00 | € 1.950,00 | amostra suficiente |
| Loures | 239 | 239 | € 1.200,00 | € 1.400,00 | € 1.775,00 | amostra suficiente |
| Albufeira | 223 | 223 | € 1.000,00 | € 1.350,00 | € 1.999,50 | amostra suficiente |
| Tavira | 221 | 221 | € 950,00 | € 1.200,00 | € 1.600,00 | amostra suficiente |
| Odivelas | 217 | 217 | € 1.200,00 | € 1.450,00 | € 1.850,00 | amostra suficiente |
| Amadora | 192 | 192 | € 1.000,00 | € 1.275,00 | € 1.500,00 | amostra suficiente |
| Lagos | 184 | 184 | € 1.200,00 | € 1.600,00 | € 2.200,00 | amostra suficiente |
| Maia | 170 | 170 | € 975,00 | € 1.150,00 | € 1.460,00 | amostra suficiente |
| Faro | 151 | 151 | € 1.400,00 | € 1.800,00 | € 2.300,00 | amostra suficiente |
| Vila Real de Santo António | 150 | 150 | € 800,00 | € 900,00 | € 1.200,00 | amostra suficiente |
| Silves | 130 | 130 | € 1.012,50 | € 1.495,00 | € 2.337,50 | amostra suficiente |
| Vila Franca de Xira | 94 | 94 | € 1.100,00 | € 1.300,00 | € 1.587,50 | amostra suficiente |
| Póvoa de Varzim | 92 | 92 | € 1.000,00 | € 1.200,00 | € 1.500,00 | amostra suficiente |
| Torres Vedras | 85 | 85 | € 950,00 | € 1.200,00 | € 1.500,00 | amostra suficiente |
| Lagoa | 83 | 83 | € 1.250,00 | € 1.500,00 | € 2.175,00 | amostra suficiente |
| Gondomar | 81 | 81 | € 890,00 | € 1.100,00 | € 1.300,00 | amostra suficiente |
| Olhão | 79 | 79 | € 1.200,00 | € 1.500,00 | € 2.100,00 | amostra suficiente |
| Vila do Conde | 79 | 79 | € 1.000,00 | € 1.300,00 | € 1.800,00 | amostra suficiente |
| Lourinhã | 66 | 66 | € 800,00 | € 1.300,00 | € 1.675,00 | amostra suficiente |
| Aljezur | 51 | 51 | € 1.100,00 | € 1.400,00 | € 2.075,00 | amostra suficiente |
| Valongo | 35 | 35 | € 800,00 | € 980,00 | € 1.150,00 | amostra suficiente |
| Castro Marim | 34 | 34 | € 962,50 | € 1.275,00 | € 1.500,00 | amostra suficiente |
| Vila do Bispo | 28 | 28 | € 980,00 | € 1.250,00 | € 2.050,00 | amostra suficiente |
| Alenquer | 24 | 24 | € 887,50 | € 1.175,00 | € 1.500,00 | amostra suficiente |
| Santo Tirso | 18 | 18 | € 850,00 | € 895,00 | € 1.175,00 | amostra suficiente |
| São Brás de Alportel | 16 | 16 | € 1.375,00 | € 2.300,00 | € 2.725,00 | amostra suficiente |
| Trofa | 15 | 15 | € 1.000,00 | € 1.250,00 | € 1.362,50 | amostra suficiente |
| Azambuja | 13 | 13 | € 750,00 | € 1.000,00 | € 1.250,00 | amostra suficiente |
| Baião | 13 | 13 | € 700,00 | € 750,00 | € 1.500,00 | amostra suficiente |
| Paredes | 13 | 13 | € 850,00 | € 950,00 | € 1.100,00 | amostra suficiente |
| Penafiel | 13 | 13 | € 650,00 | € 800,00 | € 1.400,00 | amostra suficiente |
| Amarante | 12 | 12 | € 800,00 | € 862,50 | € 1.275,00 | amostra suficiente |
| Marco de Canaveses | 11 | 11 | € 725,00 | € 900,00 | € 1.350,00 | amostra suficiente |
| Felgueiras | 8 | 8 | — | — | — | amostra insuficiente |
| Lousada | 8 | 8 | — | — | — | amostra insuficiente |
| Paços de Ferreira | 8 | 8 | — | — | — | amostra insuficiente |
| Arruda dos Vinhos | 7 | 7 | — | — | — | amostra insuficiente |
| Sobral de Monte Agraço | 6 | 6 | — | — | — | amostra insuficiente |
| Cadaval | 5 | 5 | — | — | — | amostra insuficiente |
| Monchique | 5 | 5 | — | — | — | amostra insuficiente |
| Alcoutim | 4 | 4 | — | — | — | amostra insuficiente |
| Horta | 3 | 3 | — | — | — | amostra insuficiente |
| Lajes das Flores | 3 | 3 | — | — | — | amostra insuficiente |
| Madalena | 1 | 1 | — | — | — | amostra insuficiente |
| São Roque do Pico | 1 | 1 | — | — | — | amostra insuficiente |

### Por município e tipologia

Grupos observados, com n total e elegível; anúncios regionais não entram neste recorte.

| Território / grupo | Anúncios | n elegível | P25 | Mediana | P75 | Situação |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Albufeira (0801) / T0 | 13 | 13 | € 800,00 | € 850,00 | € 1.000,00 | amostra suficiente |
| Albufeira (0801) / T1 | 73 | 73 | € 900,00 | € 1.000,00 | € 1.100,00 | amostra suficiente |
| Albufeira (0801) / T2 | 82 | 82 | € 1.312,50 | € 1.537,50 | € 1.967,50 | amostra suficiente |
| Albufeira (0801) / T3 | 37 | 37 | € 1.700,00 | € 2.100,00 | € 2.500,00 | amostra suficiente |
| Albufeira (0801) / T4+ | 18 | 18 | € 2.462,50 | € 3.000,00 | € 5.562,50 | amostra suficiente |
| Alcoutim (0802) / T2 | 3 | 3 | — | — | — | amostra insuficiente |
| Alcoutim (0802) / T3 | 1 | 1 | — | — | — | amostra insuficiente |
| Aljezur (0803) / T0 | 3 | 3 | — | — | — | amostra insuficiente |
| Aljezur (0803) / T1 | 9 | 9 | — | — | — | amostra insuficiente |
| Aljezur (0803) / T2 | 17 | 17 | € 1.150,00 | € 1.250,00 | € 1.400,00 | amostra suficiente |
| Aljezur (0803) / T3 | 14 | 14 | € 1.725,00 | € 2.225,00 | € 2.612,50 | amostra suficiente |
| Aljezur (0803) / T4+ | 8 | 8 | — | — | — | amostra insuficiente |
| Castro Marim (0804) / T1 | 6 | 6 | — | — | — | amostra insuficiente |
| Castro Marim (0804) / T2 | 13 | 13 | € 950,00 | € 1.150,00 | € 1.250,00 | amostra suficiente |
| Castro Marim (0804) / T3 | 10 | 10 | € 1.400,00 | € 1.500,00 | € 1.800,00 | amostra suficiente |
| Castro Marim (0804) / T4+ | 5 | 5 | — | — | — | amostra insuficiente |
| Faro (0805) / T0 | 4 | 4 | — | — | — | amostra insuficiente |
| Faro (0805) / T1 | 18 | 18 | € 925,00 | € 1.120,00 | € 1.252,50 | amostra suficiente |
| Faro (0805) / T2 | 68 | 68 | € 1.397,50 | € 1.625,00 | € 2.150,00 | amostra suficiente |
| Faro (0805) / T3 | 33 | 33 | € 1.600,00 | € 1.950,00 | € 2.400,00 | amostra suficiente |
| Faro (0805) / T4+ | 28 | 28 | € 1.912,50 | € 3.700,00 | € 4.250,00 | amostra suficiente |
| Lagoa (0806) / T1 | 15 | 15 | € 1.067,50 | € 1.200,00 | € 1.500,00 | amostra suficiente |
| Lagoa (0806) / T2 | 37 | 37 | € 1.200,00 | € 1.400,00 | € 1.600,00 | amostra suficiente |
| Lagoa (0806) / T3 | 22 | 22 | € 1.600,00 | € 2.050,00 | € 2.300,00 | amostra suficiente |
| Lagoa (0806) / T4+ | 9 | 9 | — | — | — | amostra insuficiente |
| Lagos (0807) / T0 | 13 | 13 | € 680,00 | € 750,00 | € 900,00 | amostra suficiente |
| Lagos (0807) / T1 | 49 | 49 | € 1.000,00 | € 1.200,00 | € 1.300,00 | amostra suficiente |
| Lagos (0807) / T2 | 64 | 64 | € 1.337,50 | € 1.650,00 | € 2.212,50 | amostra suficiente |
| Lagos (0807) / T3 | 43 | 43 | € 1.645,00 | € 1.900,00 | € 2.370,00 | amostra suficiente |
| Lagos (0807) / T4+ | 15 | 15 | € 2.200,00 | € 3.800,00 | € 4.650,00 | amostra suficiente |
| Loulé (0808) / T0 | 24 | 24 | € 837,50 | € 1.045,00 | € 1.200,00 | amostra suficiente |
| Loulé (0808) / T1 | 136 | 136 | € 1.037,50 | € 1.225,00 | € 1.500,00 | amostra suficiente |
| Loulé (0808) / T2 | 274 | 274 | € 1.500,00 | € 1.785,00 | € 2.200,00 | amostra suficiente |
| Loulé (0808) / T3 | 134 | 134 | € 2.206,25 | € 2.900,00 | € 4.000,00 | amostra suficiente |
| Loulé (0808) / T4+ | 113 | 113 | € 4.000,00 | € 7.000,00 | € 9.000,00 | amostra suficiente |
| Monchique (0809) / T1 | 2 | 2 | — | — | — | amostra insuficiente |
| Monchique (0809) / T2 | 3 | 3 | — | — | — | amostra insuficiente |
| Olhão (0810) / T0 | 3 | 3 | — | — | — | amostra insuficiente |
| Olhão (0810) / T1 | 17 | 17 | € 900,00 | € 1.100,00 | € 1.350,00 | amostra suficiente |
| Olhão (0810) / T2 | 33 | 33 | € 1.250,00 | € 1.500,00 | € 1.800,00 | amostra suficiente |
| Olhão (0810) / T3 | 13 | 13 | € 1.500,00 | € 1.800,00 | € 2.000,00 | amostra suficiente |
| Olhão (0810) / T4+ | 13 | 13 | € 2.550,00 | € 2.900,00 | € 4.000,00 | amostra suficiente |
| Portimão (0811) / T0 | 23 | 23 | € 750,00 | € 850,00 | € 900,00 | amostra suficiente |
| Portimão (0811) / T1 | 162 | 162 | € 850,00 | € 950,00 | € 1.150,00 | amostra suficiente |
| Portimão (0811) / T2 | 115 | 115 | € 1.200,00 | € 1.350,00 | € 1.500,00 | amostra suficiente |
| Portimão (0811) / T3 | 49 | 49 | € 1.500,00 | € 1.750,00 | € 2.300,00 | amostra suficiente |
| Portimão (0811) / T4+ | 8 | 8 | — | — | — | amostra insuficiente |
| São Brás de Alportel (0812) / T0 | 1 | 1 | — | — | — | amostra insuficiente |
| São Brás de Alportel (0812) / T1 | 1 | 1 | — | — | — | amostra insuficiente |
| São Brás de Alportel (0812) / T2 | 4 | 4 | — | — | — | amostra insuficiente |
| São Brás de Alportel (0812) / T3 | 5 | 5 | — | — | — | amostra insuficiente |
| São Brás de Alportel (0812) / T4+ | 5 | 5 | — | — | — | amostra insuficiente |
| Silves (0813) / T0 | 1 | 1 | — | — | — | amostra insuficiente |
| Silves (0813) / T1 | 38 | 38 | € 852,50 | € 950,00 | € 1.250,00 | amostra suficiente |
| Silves (0813) / T2 | 47 | 47 | € 1.200,00 | € 1.600,00 | € 2.000,00 | amostra suficiente |
| Silves (0813) / T3 | 25 | 25 | € 1.400,00 | € 2.500,00 | € 2.900,00 | amostra suficiente |
| Silves (0813) / T4+ | 19 | 19 | € 1.900,00 | € 2.500,00 | € 4.700,00 | amostra suficiente |
| Tavira (0814) / T0 | 11 | 11 | € 750,00 | € 795,00 | € 875,00 | amostra suficiente |
| Tavira (0814) / T1 | 55 | 55 | € 810,00 | € 925,00 | € 1.100,00 | amostra suficiente |
| Tavira (0814) / T2 | 106 | 106 | € 1.000,00 | € 1.250,00 | € 1.437,50 | amostra suficiente |
| Tavira (0814) / T3 | 32 | 32 | € 1.500,00 | € 1.875,00 | € 2.200,00 | amostra suficiente |
| Tavira (0814) / T4+ | 17 | 17 | € 1.950,00 | € 2.300,00 | € 2.500,00 | amostra suficiente |
| Vila do Bispo (0815) / T0 | 2 | 2 | — | — | — | amostra insuficiente |
| Vila do Bispo (0815) / T1 | 9 | 9 | — | — | — | amostra insuficiente |
| Vila do Bispo (0815) / T2 | 8 | 8 | — | — | — | amostra insuficiente |
| Vila do Bispo (0815) / T3 | 7 | 7 | — | — | — | amostra insuficiente |
| Vila do Bispo (0815) / T4+ | 2 | 2 | — | — | — | amostra insuficiente |
| Vila Real de Santo António (0816) / T0 | 7 | 7 | — | — | — | amostra insuficiente |
| Vila Real de Santo António (0816) / T1 | 61 | 61 | € 750,00 | € 800,00 | € 900,00 | amostra suficiente |
| Vila Real de Santo António (0816) / T2 | 58 | 58 | € 883,75 | € 950,00 | € 1.237,50 | amostra suficiente |
| Vila Real de Santo António (0816) / T3 | 17 | 17 | € 1.250,00 | € 1.400,00 | € 1.500,00 | amostra suficiente |
| Vila Real de Santo António (0816) / T4+ | 7 | 7 | — | — | — | amostra insuficiente |
| Alenquer (1101) / T0 | 2 | 2 | — | — | — | amostra insuficiente |
| Alenquer (1101) / T1 | 6 | 6 | — | — | — | amostra insuficiente |
| Alenquer (1101) / T2 | 3 | 3 | — | — | — | amostra insuficiente |
| Alenquer (1101) / T3 | 11 | 11 | € 1.225,00 | € 1.350,00 | € 1.500,00 | amostra suficiente |
| Alenquer (1101) / T4+ | 2 | 2 | — | — | — | amostra insuficiente |
| Arruda dos Vinhos (1102) / T1 | 2 | 2 | — | — | — | amostra insuficiente |
| Arruda dos Vinhos (1102) / T2 | 3 | 3 | — | — | — | amostra insuficiente |
| Arruda dos Vinhos (1102) / T4+ | 2 | 2 | — | — | — | amostra insuficiente |
| Azambuja (1103) / T1 | 2 | 2 | — | — | — | amostra insuficiente |
| Azambuja (1103) / T2 | 5 | 5 | — | — | — | amostra insuficiente |
| Azambuja (1103) / T3 | 4 | 4 | — | — | — | amostra insuficiente |
| Azambuja (1103) / T4+ | 2 | 2 | — | — | — | amostra insuficiente |
| Cadaval (1104) / T1 | 2 | 2 | — | — | — | amostra insuficiente |
| Cadaval (1104) / T2 | 1 | 1 | — | — | — | amostra insuficiente |
| Cadaval (1104) / T3 | 1 | 1 | — | — | — | amostra insuficiente |
| Cadaval (1104) / T4+ | 1 | 1 | — | — | — | amostra insuficiente |
| Cascais (1105) / T0 | 45 | 45 | € 850,00 | € 1.200,00 | € 1.400,00 | amostra suficiente |
| Cascais (1105) / T1 | 239 | 239 | € 1.200,00 | € 1.500,00 | € 1.785,00 | amostra suficiente |
| Cascais (1105) / T2 | 456 | 456 | € 1.650,00 | € 1.985,00 | € 2.750,00 | amostra suficiente |
| Cascais (1105) / T3 | 465 | 465 | € 2.200,00 | € 3.200,00 | € 4.800,00 | amostra suficiente |
| Cascais (1105) / T4+ | 406 | 406 | € 4.412,50 | € 6.950,00 | € 10.375,00 | amostra suficiente |
| Lisboa (1106) / T0 | 56 | 56 | € 968,75 | € 1.137,50 | € 1.350,00 | amostra suficiente |
| Lisboa (1106) / T1 | 474 | 474 | € 1.300,00 | € 1.600,00 | € 2.000,00 | amostra suficiente |
| Lisboa (1106) / T2 | 674 | 674 | € 1.600,00 | € 2.100,00 | € 2.750,00 | amostra suficiente |
| Lisboa (1106) / T3 | 389 | 389 | € 1.980,00 | € 2.485,00 | € 3.800,00 | amostra suficiente |
| Lisboa (1106) / T4+ | 200 | 200 | € 2.300,00 | € 3.550,00 | € 5.000,00 | amostra suficiente |
| Loures (1107) / T0 | 2 | 2 | — | — | — | amostra insuficiente |
| Loures (1107) / T1 | 37 | 37 | € 990,00 | € 1.150,00 | € 1.350,00 | amostra suficiente |
| Loures (1107) / T2 | 109 | 109 | € 1.150,00 | € 1.250,00 | € 1.500,00 | amostra suficiente |
| Loures (1107) / T3 | 67 | 67 | € 1.390,00 | € 1.700,00 | € 2.100,00 | amostra suficiente |
| Loures (1107) / T4+ | 24 | 24 | € 1.837,50 | € 2.300,00 | € 3.150,00 | amostra suficiente |
| Lourinhã (1108) / T0 | 2 | 2 | — | — | — | amostra insuficiente |
| Lourinhã (1108) / T1 | 15 | 15 | € 742,50 | € 800,00 | € 800,00 | amostra suficiente |
| Lourinhã (1108) / T2 | 14 | 14 | € 777,50 | € 975,00 | € 1.137,50 | amostra suficiente |
| Lourinhã (1108) / T3 | 23 | 23 | € 1.300,00 | € 1.500,00 | € 2.200,00 | amostra suficiente |
| Lourinhã (1108) / T4+ | 12 | 12 | € 1.500,00 | € 1.800,00 | € 2.450,00 | amostra suficiente |
| Mafra (1109) / T0 | 7 | 7 | — | — | — | amostra insuficiente |
| Mafra (1109) / T1 | 63 | 63 | € 1.000,00 | € 1.200,00 | € 1.312,50 | amostra suficiente |
| Mafra (1109) / T2 | 128 | 128 | € 1.250,00 | € 1.400,00 | € 1.700,00 | amostra suficiente |
| Mafra (1109) / T3 | 92 | 92 | € 1.487,50 | € 1.897,50 | € 2.500,00 | amostra suficiente |
| Mafra (1109) / T4+ | 18 | 18 | € 1.820,00 | € 1.990,00 | € 2.925,00 | amostra suficiente |
| Oeiras (1110) / T0 | 14 | 14 | € 878,75 | € 970,00 | € 1.087,50 | amostra suficiente |
| Oeiras (1110) / T1 | 96 | 96 | € 1.100,00 | € 1.250,00 | € 1.427,50 | amostra suficiente |
| Oeiras (1110) / T2 | 198 | 198 | € 1.350,00 | € 1.600,00 | € 2.100,00 | amostra suficiente |
| Oeiras (1110) / T3 | 175 | 175 | € 1.800,00 | € 2.300,00 | € 2.699,50 | amostra suficiente |
| Oeiras (1110) / T4+ | 65 | 65 | € 2.200,00 | € 3.100,00 | € 6.500,00 | amostra suficiente |
| Sintra (1111) / T0 | 23 | 23 | € 797,50 | € 900,00 | € 999,00 | amostra suficiente |
| Sintra (1111) / T1 | 86 | 86 | € 950,00 | € 1.050,00 | € 1.200,00 | amostra suficiente |
| Sintra (1111) / T2 | 192 | 192 | € 1.200,00 | € 1.300,00 | € 1.500,00 | amostra suficiente |
| Sintra (1111) / T3 | 98 | 98 | € 1.600,00 | € 2.000,00 | € 2.991,75 | amostra suficiente |
| Sintra (1111) / T4+ | 59 | 59 | € 2.999,50 | € 5.950,00 | € 9.750,00 | amostra suficiente |
| Sobral de Monte Agraço (1112) / T1 | 1 | 1 | — | — | — | amostra insuficiente |
| Sobral de Monte Agraço (1112) / T3 | 2 | 2 | — | — | — | amostra insuficiente |
| Sobral de Monte Agraço (1112) / T4+ | 3 | 3 | — | — | — | amostra insuficiente |
| Torres Vedras (1113) / T0 | 5 | 5 | — | — | — | amostra insuficiente |
| Torres Vedras (1113) / T1 | 12 | 12 | € 700,00 | € 800,00 | € 875,00 | amostra suficiente |
| Torres Vedras (1113) / T2 | 27 | 27 | € 975,00 | € 1.100,00 | € 1.275,00 | amostra suficiente |
| Torres Vedras (1113) / T3 | 32 | 32 | € 1.200,00 | € 1.472,00 | € 2.400,00 | amostra suficiente |
| Torres Vedras (1113) / T4+ | 9 | 9 | — | — | — | amostra insuficiente |
| Vila Franca de Xira (1114) / T1 | 10 | 10 | € 900,00 | € 940,00 | € 961,25 | amostra suficiente |
| Vila Franca de Xira (1114) / T2 | 41 | 41 | € 1.100,00 | € 1.200,00 | € 1.300,00 | amostra suficiente |
| Vila Franca de Xira (1114) / T3 | 38 | 38 | € 1.400,00 | € 1.500,00 | € 2.056,25 | amostra suficiente |
| Vila Franca de Xira (1114) / T4+ | 5 | 5 | — | — | — | amostra insuficiente |
| Amadora (1115) / T0 | 12 | 12 | € 750,00 | € 800,00 | € 880,00 | amostra suficiente |
| Amadora (1115) / T1 | 40 | 40 | € 900,00 | € 1.000,00 | € 1.250,00 | amostra suficiente |
| Amadora (1115) / T2 | 95 | 95 | € 1.150,00 | € 1.225,00 | € 1.400,00 | amostra suficiente |
| Amadora (1115) / T3 | 37 | 37 | € 1.500,00 | € 1.600,00 | € 1.900,00 | amostra suficiente |
| Amadora (1115) / T4+ | 8 | 8 | — | — | — | amostra insuficiente |
| Odivelas (1116) / T0 | 7 | 7 | — | — | — | amostra insuficiente |
| Odivelas (1116) / T1 | 20 | 20 | € 995,00 | € 1.075,00 | € 1.100,00 | amostra suficiente |
| Odivelas (1116) / T2 | 92 | 92 | € 1.200,00 | € 1.350,00 | € 1.550,00 | amostra suficiente |
| Odivelas (1116) / T3 | 77 | 77 | € 1.500,00 | € 1.700,00 | € 2.000,00 | amostra suficiente |
| Odivelas (1116) / T4+ | 21 | 21 | € 2.190,00 | € 3.250,00 | € 4.500,00 | amostra suficiente |
| Amarante (1301) / T0 | 1 | 1 | — | — | — | amostra insuficiente |
| Amarante (1301) / T1 | 2 | 2 | — | — | — | amostra insuficiente |
| Amarante (1301) / T2 | 2 | 2 | — | — | — | amostra insuficiente |
| Amarante (1301) / T3 | 7 | 7 | — | — | — | amostra insuficiente |
| Baião (1302) / T1 | 4 | 4 | — | — | — | amostra insuficiente |
| Baião (1302) / T2 | 7 | 7 | — | — | — | amostra insuficiente |
| Baião (1302) / T3 | 1 | 1 | — | — | — | amostra insuficiente |
| Baião (1302) / T4+ | 1 | 1 | — | — | — | amostra insuficiente |
| Felgueiras (1303) / T1 | 4 | 4 | — | — | — | amostra insuficiente |
| Felgueiras (1303) / T2 | 4 | 4 | — | — | — | amostra insuficiente |
| Gondomar (1304) / T0 | 4 | 4 | — | — | — | amostra insuficiente |
| Gondomar (1304) / T1 | 15 | 15 | € 737,50 | € 800,00 | € 890,00 | amostra suficiente |
| Gondomar (1304) / T2 | 39 | 39 | € 1.000,00 | € 1.100,00 | € 1.212,50 | amostra suficiente |
| Gondomar (1304) / T3 | 15 | 15 | € 1.250,00 | € 1.350,00 | € 1.750,00 | amostra suficiente |
| Gondomar (1304) / T4+ | 8 | 8 | — | — | — | amostra insuficiente |
| Lousada (1305) / T0 | 1 | 1 | — | — | — | amostra insuficiente |
| Lousada (1305) / T1 | 1 | 1 | — | — | — | amostra insuficiente |
| Lousada (1305) / T2 | 1 | 1 | — | — | — | amostra insuficiente |
| Lousada (1305) / T3 | 4 | 4 | — | — | — | amostra insuficiente |
| Lousada (1305) / T4+ | 1 | 1 | — | — | — | amostra insuficiente |
| Maia (1306) / T0 | 12 | 12 | € 695,00 | € 775,00 | € 850,00 | amostra suficiente |
| Maia (1306) / T1 | 57 | 57 | € 890,00 | € 990,00 | € 1.075,00 | amostra suficiente |
| Maia (1306) / T2 | 53 | 53 | € 1.100,00 | € 1.200,00 | € 1.300,00 | amostra suficiente |
| Maia (1306) / T3 | 41 | 41 | € 1.300,00 | € 1.480,00 | € 1.600,00 | amostra suficiente |
| Maia (1306) / T4+ | 7 | 7 | — | — | — | amostra insuficiente |
| Marco de Canaveses (1307) / T2 | 7 | 7 | — | — | — | amostra insuficiente |
| Marco de Canaveses (1307) / T3 | 3 | 3 | — | — | — | amostra insuficiente |
| Marco de Canaveses (1307) / T4+ | 1 | 1 | — | — | — | amostra insuficiente |
| Matosinhos (1308) / T0 | 59 | 59 | € 850,00 | € 900,00 | € 1.000,00 | amostra suficiente |
| Matosinhos (1308) / T1 | 188 | 188 | € 915,00 | € 1.000,00 | € 1.185,00 | amostra suficiente |
| Matosinhos (1308) / T2 | 218 | 218 | € 1.160,00 | € 1.390,00 | € 1.800,00 | amostra suficiente |
| Matosinhos (1308) / T3 | 72 | 72 | € 1.490,00 | € 1.850,00 | € 2.325,00 | amostra suficiente |
| Matosinhos (1308) / T4+ | 42 | 42 | € 2.000,00 | € 2.950,00 | € 4.225,00 | amostra suficiente |
| Paços de Ferreira (1309) / T0 | 1 | 1 | — | — | — | amostra insuficiente |
| Paços de Ferreira (1309) / T1 | 1 | 1 | — | — | — | amostra insuficiente |
| Paços de Ferreira (1309) / T2 | 3 | 3 | — | — | — | amostra insuficiente |
| Paços de Ferreira (1309) / T3 | 3 | 3 | — | — | — | amostra insuficiente |
| Paredes (1310) / T1 | 1 | 1 | — | — | — | amostra insuficiente |
| Paredes (1310) / T2 | 5 | 5 | — | — | — | amostra insuficiente |
| Paredes (1310) / T3 | 6 | 6 | — | — | — | amostra insuficiente |
| Paredes (1310) / T4+ | 1 | 1 | — | — | — | amostra insuficiente |
| Penafiel (1311) / T0 | 1 | 1 | — | — | — | amostra insuficiente |
| Penafiel (1311) / T1 | 2 | 2 | — | — | — | amostra insuficiente |
| Penafiel (1311) / T2 | 5 | 5 | — | — | — | amostra insuficiente |
| Penafiel (1311) / T3 | 5 | 5 | — | — | — | amostra insuficiente |
| Porto (1312) / T0 | 351 | 351 | € 840,00 | € 970,00 | € 1.200,00 | amostra suficiente |
| Porto (1312) / T1 | 636 | 636 | € 950,00 | € 1.100,00 | € 1.300,00 | amostra suficiente |
| Porto (1312) / T2 | 470 | 470 | € 1.250,00 | € 1.500,00 | € 1.800,00 | amostra suficiente |
| Porto (1312) / T3 | 191 | 191 | € 1.500,00 | € 1.995,00 | € 2.350,00 | amostra suficiente |
| Porto (1312) / T4+ | 98 | 98 | € 1.900,00 | € 2.500,00 | € 3.912,50 | amostra suficiente |
| Póvoa de Varzim (1313) / T0 | 3 | 3 | — | — | — | amostra insuficiente |
| Póvoa de Varzim (1313) / T1 | 18 | 18 | € 906,25 | € 1.000,00 | € 1.100,00 | amostra suficiente |
| Póvoa de Varzim (1313) / T2 | 29 | 29 | € 1.000,00 | € 1.000,00 | € 1.200,00 | amostra suficiente |
| Póvoa de Varzim (1313) / T3 | 33 | 33 | € 1.250,00 | € 1.500,00 | € 2.000,00 | amostra suficiente |
| Póvoa de Varzim (1313) / T4+ | 9 | 9 | — | — | — | amostra insuficiente |
| Santo Tirso (1314) / T1 | 6 | 6 | — | — | — | amostra insuficiente |
| Santo Tirso (1314) / T2 | 5 | 5 | — | — | — | amostra insuficiente |
| Santo Tirso (1314) / T3 | 7 | 7 | — | — | — | amostra insuficiente |
| Valongo (1315) / T1 | 9 | 9 | — | — | — | amostra insuficiente |
| Valongo (1315) / T2 | 15 | 15 | € 950,00 | € 1.000,00 | € 1.125,00 | amostra suficiente |
| Valongo (1315) / T3 | 11 | 11 | € 1.025,00 | € 1.200,00 | € 1.400,00 | amostra suficiente |
| Vila do Conde (1316) / T0 | 2 | 2 | — | — | — | amostra insuficiente |
| Vila do Conde (1316) / T1 | 9 | 9 | — | — | — | amostra insuficiente |
| Vila do Conde (1316) / T2 | 32 | 32 | € 986,25 | € 1.100,00 | € 1.300,00 | amostra suficiente |
| Vila do Conde (1316) / T3 | 25 | 25 | € 1.200,00 | € 1.500,00 | € 1.950,00 | amostra suficiente |
| Vila do Conde (1316) / T4+ | 11 | 11 | € 1.875,00 | € 2.500,00 | € 3.500,00 | amostra suficiente |
| Vila Nova de Gaia (1317) / T0 | 50 | 50 | € 812,50 | € 950,00 | € 1.087,50 | amostra suficiente |
| Vila Nova de Gaia (1317) / T1 | 185 | 185 | € 850,00 | € 1.000,00 | € 1.200,00 | amostra suficiente |
| Vila Nova de Gaia (1317) / T2 | 278 | 278 | € 1.150,00 | € 1.350,00 | € 1.687,50 | amostra suficiente |
| Vila Nova de Gaia (1317) / T3 | 152 | 152 | € 1.400,00 | € 1.800,00 | € 2.500,00 | amostra suficiente |
| Vila Nova de Gaia (1317) / T4+ | 51 | 51 | € 2.000,00 | € 2.800,00 | € 3.675,00 | amostra suficiente |
| Trofa (1318) / T1 | 1 | 1 | — | — | — | amostra insuficiente |
| Trofa (1318) / T2 | 6 | 6 | — | — | — | amostra insuficiente |
| Trofa (1318) / T3 | 6 | 6 | — | — | — | amostra insuficiente |
| Trofa (1318) / T4+ | 2 | 2 | — | — | — | amostra insuficiente |
| Madalena (4602) / T3 | 1 | 1 | — | — | — | amostra insuficiente |
| São Roque do Pico (4603) / T1 | 1 | 1 | — | — | — | amostra insuficiente |
| Horta (4701) / T1 | 2 | 2 | — | — | — | amostra insuficiente |
| Horta (4701) / T3 | 1 | 1 | — | — | — | amostra insuficiente |
| Lajes das Flores (4801) / T1 | 3 | 3 | — | — | — | amostra insuficiente |

### Grupos regionais sem município comprovado

Estes anúncios não entram nas tabelas municipais. O recorte está em regional_stats.csv.

| Território / grupo | Anúncios | n elegível | P25 | Mediana | P75 | Situação |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Setúbal | 1725 | 1725 | € 1.100,00 | € 1.350,00 | € 1.900,00 | amostra suficiente |
| Braga | 873 | 873 | € 825,00 | € 1.000,00 | € 1.300,00 | amostra suficiente |
| Leiria | 638 | 638 | € 850,00 | € 1.000,00 | € 1.350,00 | amostra suficiente |
| Coimbra | 608 | 608 | € 680,00 | € 850,00 | € 1.010,00 | amostra suficiente |
| Aveiro | 568 | 568 | € 800,00 | € 1.000,00 | € 1.200,00 | amostra suficiente |
| Madeira (Ilha) | 322 | 322 | € 1.400,00 | € 1.700,00 | € 2.250,00 | amostra suficiente |
| Viana do Castelo | 318 | 318 | € 750,00 | € 900,00 | € 1.287,50 | amostra suficiente |
| Santarém | 309 | 309 | € 800,00 | € 950,00 | € 1.200,00 | amostra suficiente |
| Viseu | 213 | 213 | € 570,00 | € 750,00 | € 950,00 | amostra suficiente |
| Castelo Branco | 193 | 193 | € 525,00 | € 650,00 | € 800,00 | amostra suficiente |
| Évora | 118 | 118 | € 782,50 | € 1.000,00 | € 1.350,00 | amostra suficiente |
| Beja | 105 | 105 | € 780,00 | € 1.000,00 | € 1.300,00 | amostra suficiente |
| Vila Real | 82 | 82 | € 502,50 | € 700,00 | € 850,00 | amostra suficiente |
| Portalegre | 78 | 78 | € 550,00 | € 700,00 | € 950,00 | amostra suficiente |
| São Miguel (Ilha dos Açores) | 73 | 73 | € 1.000,00 | € 1.400,00 | € 1.700,00 | amostra suficiente |
| Guarda | 69 | 69 | € 500,00 | € 600,00 | € 750,00 | amostra suficiente |
| Bragança | 58 | 58 | € 600,00 | € 650,00 | € 750,00 | amostra suficiente |
| Terceira (Ilha dos Açores) | 15 | 15 | € 790,00 | € 850,00 | € 900,00 | amostra suficiente |
| Porto Santo (Ilha) | 6 | 6 | — | — | — | amostra insuficiente |

## Limitações e reprodução

O período é declarado pelo operador; o horário de coleta não é conhecido. Não inferir evolução de preços comparando diretamente com 2025-08: cobertura, granularidade e composição das amostras diferem. O método de coleta do app de origem não é certificado pela importação offline.
Dados individuais ficam privados em .data. Este relatório é local e descritivo; não atualiza publicação ou ranking.
Reproduzir após importar o mesmo manifest: `uv run --locked python -m pipelines.cli.build_idealista --local --snapshot-month 2026-11`.

## Verificações desta execução

- Os 74 arquivos de origem e as 74 cópias raw tiveram SHA-256 conferidos; a segunda importação retornou `unchanged`, sem novos raw.
- Os 324 raw de agosto, os manifests antigos e os 25 arquivos do lake de outras fontes mantiveram seus hashes.
- Uma nova preparação do lote 2025-08 manteve suas contagens anteriores, incluindo 16.117 anúncios únicos, 255 municípios e 8.891 freguesias resolvidas.
- Os 24 passos do dbt real passaram. Totais da cobertura reconciliados e os quartis do lote conferidos independentemente com a biblioteca padrão Python.
- Evidências e cópia das saídas anteriores: `.data/idealista-review-202611/`. Dados individuais continuam ignorados pelo Git. CI remoto, AWS e publicação não foram executados.

Os 937 casos sem freguesia incluem nomes genéricos do município e metadados ausentes; não foram distribuídos entre freguesias por aproximação. Para aumentar a cobertura municipal dos 6.371 regionais, uma coleta futura precisa trazer o município por anúncio ou coletar recortes municipais; preencher somente o distrito não basta.

## Arquivos agregados para análise

- [Todos os municípios](idealista-2026-11-municipality_stats.csv), inclusive os sem amostra.
- [Município por tipologia](idealista-2026-11-municipality_typology_stats.csv).
- [Grupos regionais](idealista-2026-11-regional_stats.csv).
- [Resumo estatístico em JSON](idealista-2026-11-statistics.json).

Validação Phase 4: 43 testes Idealista aprovados e suíte geral com 437 testes aprovados em 493,04 s; ruff geral limpo e sete travas íntegras. Build real regenerado com 24 passos dbt aprovados. Os 308 municípios e 225 grupos município/tipologia foram reconciliados entre JSON/CSV/Markdown. Progresso da feature: 16/17 itens; CI da revisão final pendente (T013). Nenhum commit, push ou publicação nesta retomada.
