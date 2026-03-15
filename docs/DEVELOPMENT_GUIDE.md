# Guia de Desenvolvimento

## Stack atual

- Node.js 16+
- HTTP server nativo
- Frontend HTML, CSS e JavaScript sem framework
- Testes com `node:test`

## Principios

- Manter contratos de dominio puros e testaveis
- Priorizar clareza de regras sobre sofisticacao de infraestrutura
- Tratar parser e resolucao de embalagens como modulos independentes

## Convencoes

- ASCII por padrao
- Dados persistidos em `data/`
- Funcoes de dominio sem acoplamento ao transporte HTTP

## Estrategia de evolucao

- Migrar para TypeScript quando o dominio estabilizar
- Substituir persistencia local por banco relacional
- Introduzir servico externo ou crawler para fallback online de embalagens
- Adicionar observabilidade basica por evento de parse, revisao e resolucao

## Versionamento

- `main` para o tronco principal
- features pequenas e incrementais
- testes de dominio obrigatorios para regras novas
