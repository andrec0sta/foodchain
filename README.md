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
- Backend HTTP em Python com parsing local e suporte opcional a LLM
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
- A integracao com LLM hoje esta preparada para Gemini e depende de `GEMINI_API_KEY`
- A estrategia com LLM agora e hibrida: parser local resolve o trivial e o Gemini entra so nos trechos mais ambiguos

## Como rodar

```bash
npm start
```

Depois acesse `http://127.0.0.1:3000`.

## Como testar

```bash
npm test
```

## LLM opcional

O backend agora suporta um modo de interpretacao com Gemini. Para habilitar:

```bash
export GEMINI_API_KEY="sua-chave"
export LLM_MODEL="gemini-2.5-flash-lite"
export LLM_PARSE_MODE="auto"
export LLM_TIMEOUT_SECONDS="60"
export LLM_THINKING_BUDGET="0"
npm start
```

Modos disponiveis na interface:

- `Automatico`: usa parser local como base e chama Gemini so para refeicoes complexas
- `Parser local`: usa apenas heuristicas locais
- `LLM (Gemini)`: usa o pipeline hibrido com Gemini; se falhar, cai para o parser local e registra aviso

## Arquivos importantes

- `server.py`: servidor HTTP, APIs e integracao de ingestao
- `backend/`: parser, normalizacao, LLM, persistencia e resolucao de embalagens em Python
- `backend/parser.py`: pipeline de limpeza, segmentacao e parsing
- `backend/packaging.py`: consolidacao semanal e resolucao de embalagens
- `scripts/extract_pdf.py`: extracao de texto de PDF
- `public/`: interface web responsiva
- `tests_py/`: testes Python do dominio e da camada LLM
- `docs/STATUS.md`: resumo da sessao, limitacoes e proximas etapas

## Estrutura

- `server.py`: servidor HTTP, APIs e servicos de persistencia
- `backend`: parser, normalizacao, catalogo, LLM e motor de resolucao de embalagens
- `public`: interface web responsiva
- `docs`: documentacao do produto, arquitetura e desenvolvimento
- `tests_py`: testes Python do dominio
