# Backlog

Painel único de ideias futuras e status de features/bugs geridas pelo
sistema sdd-*. Mantido automaticamente por update-feature-status.ps1 e
update-bug-status.ps1.

## Ideias Futuras

- [Simplificação] Pendentes da revisão de 2026-11-11 (feature 001-ingestao-caop, aguardam decisão do usuário): remover o `--force-check`, que é um no-op documentado (exige emenda de FR-011 e do contrato da CLI); trocar `_canonical_path` por recusa de `:` na chave do storage (exige novo teste de path traversal); remover `strict_metadata` do catálogo (hoje serve só ao catálogo mínimo do contrato travado); adiar a US3/S3 até existir conta AWS; detectar `unchanged` por `HEAD` com ETag/Last-Modified em vez de baixar ~143 MB a cada execução.

## Features

| Slug | Título | Status | Progresso | Última Atualização |
| --- | --- | --- | --- | --- |
| 001-ingestao-caop | Fundação da ingestão e dimensão territorial CAOP | Em Execução | 34/47 tasks | 2026-11-11 |

## Melhorias Ad-hoc

| Data | Área | Resumo |

## Bugs

| Slug | Título | Fase Atual | Veredito/Status | Próximo Passo | Última Atualização |
| --- | --- | --- | --- | --- | --- |
