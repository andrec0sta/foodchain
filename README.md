# Diet Shopping Assistant

MVP de um assistente de compras para plano nutricional, com foco inicial em uso individual no Brasil.

## Estado atual

O projeto ja possui um MVP funcional de ponta a ponta para:

- receber plano nutricional por texto ou PDF
- extrair texto do PDF
- filtrar parte do ruido mais comum
- identificar refeicoes e opcoes
- priorizar a primeira opcao e a primeira alternativa em linhas com exclusividade
- permitir revisao manual antes de gerar a lista
- consolidar necessidades semanais e sugerir embalagens de compra

## O que existe nesta versao

- Ingestao de plano por texto ou upload de arquivo
- Extracao de texto de PDF com `pypdf` e fallback simples
- Parsing inicial de alimentos, quantidades e frequencia semanal
- Revisao manual dos itens extraidos
- Geracao de lista de compras semanal com embalagens comerciais
- Persistencia local simples do ultimo plano revisado e de ajustes de embalagem

## Regras de parsing implementadas

- Ignora metadados comuns como nome, objetivo, validade e textos de apoio
- Ignora suplementacao e tabelas de troca/frutas
- Considera apenas `Opcao 1` quando ha blocos com varias opcoes
- Em linhas com `ou`, utiliza a primeira alternativa
- Replica o almoco no jantar quando o plano explicita que o jantar segue as mesmas opcoes e quantidades
- Mantem itens ambiguos para revisao manual quando necessario

## Limitacoes conhecidas

- Algumas linhas ainda podem misturar dois contextos, como item + subtitulo de grupo
- Medidas caseiras como `concha`, `colher`, `pegador` ainda nao sao convertidas de forma confiavel para gramas/ml
- Certos alimentos ainda saem com descricao excessivamente longa e precisam de normalizacao melhor
- O parser esta mais robusto para planos estruturados, mas ainda nao cobre toda a variabilidade possivel entre nutricionistas
- A busca online de embalagens comerciais ainda nao foi implementada

## Como rodar

```bash
npm start
```

Depois acesse `http://127.0.0.1:3000`.

## Como testar

```bash
npm test
```

## Arquivos importantes

- `server.js`: servidor HTTP, APIs e integracao de ingestao
- `scripts/extract_pdf.py`: extracao de texto de PDF
- `src/domain/parser.js`: pipeline de limpeza, segmentacao e parsing
- `src/domain/packaging.js`: consolidacao semanal e resolucao de embalagens
- `public/`: interface web responsiva
- `tests/domain.test.js`: testes do dominio
- `docs/STATUS.md`: resumo da sessao, limitacoes e proximas etapas

## Estrutura

- `server.js`: servidor HTTP, APIs e servicos de persistencia
- `src/domain`: parser, normalizacao, catalogo e motor de resolucao de embalagens
- `public`: interface web responsiva
- `docs`: documentacao do produto, arquitetura e desenvolvimento
- `tests`: testes do dominio
