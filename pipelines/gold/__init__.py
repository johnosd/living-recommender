"""Camada Gold (spec 011): indicadores municipais e de freguesia, aluguel, clima e o `criteria_catalog`.

Cada módulo recebe tabelas já promovidas no lake (como `pandas.DataFrame`) e devolve tabelas novas, sem ler
nem gravar arquivos; quem lê o lake e grava o resultado é `pipelines.gold.prepare` e a CLI `build_gold`.
"""
