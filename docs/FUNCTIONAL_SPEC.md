# Especificacao Funcional

## Ingestao do plano

- O usuario pode colar texto ou enviar arquivo
- Arquivos de texto sao lidos diretamente
- PDFs usam extracao best-effort de texto e podem exigir mais revisao

## Parsing

- O parser divide o texto em linhas
- Cada linha pode representar uma refeicao, um item ou uma observacao
- Frequencia semanal e inferida por padroes como:
  - `2x ao dia`
  - `1x ao dia`
  - `3x por semana`
  - `somente dias uteis`
  - ausencia de frequencia explicita -> 7 vezes por semana

## Revisao manual

- Cada item extraido pode ser editado
- Campos editaveis:
  - nome do alimento
  - quantidade
  - unidade
  - frequencia semanal
  - observacao
- O usuario pode remover itens invalidos antes da geracao da lista

## Geracao da lista

- O sistema consolida itens pelo alimento normalizado e unidade base
- Converte kg para g e l para ml para comparar necessidades e embalagens
- Resolve a menor combinacao de embalagens que cubra a necessidade
- Quando nao encontra embalagem conhecida:
  - marca o item como pendente
  - sugere uso de ajuste manual

## Regras de compra

- Nunca faltar alimento
- Permitir sobra estimada
- Reutilizar overrides confirmados pelo usuario em geracoes futuras

## Casos de borda

- Itens com unidade nao reconhecida continuam editaveis
- Linhas vazias ou titulos sao ignorados
- Sinonimos de alimentos sao normalizados quando conhecidos
