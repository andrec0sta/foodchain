# PRD

## Visao geral

O produto ajuda uma pessoa a transformar um plano nutricional em uma lista de compras semanal, considerando como os alimentos sao vendidos no mercado brasileiro.

## Problema

Planos nutricionais costumam informar consumo em medidas de dieta, mas compras reais dependem de embalagens de mercado. O usuario acaba convertendo manualmente quantidades, calculando recorrencia e decidindo embalagens.

## Usuario inicial

- Pessoa individual que segue um plano nutricional
- Quer reduzir friccao operacional na hora de comprar
- Tolera uma etapa curta de revisao para garantir confiabilidade

## JTBD

Quando eu recebo um plano nutricional, quero transformar rapidamente esse plano em uma lista de compras semanal realista, para comprar sem faltar alimento e sem refazer contas toda semana.

## Escopo do MVP

- Entrada por texto livre e upload de arquivo
- Parser inicial para alimentos, quantidades e frequencia
- Revisao manual dos itens extraidos
- Consolidacao semanal
- Resolucao para embalagens comerciais com catalogo inicial do Brasil
- Persistencia local da ultima revisao e de ajustes manuais

## Fora de escopo

- Recomendacoes nutricionais
- Substituicao de alimentos
- Comparacao de precos
- Multiusuario profissional
- Aplicativo nativo mobile

## Metricas de sucesso

- Usuario gera uma lista semanal em menos de 5 minutos
- Pelo menos 80% dos itens sao interpretados corretamente sem edicao
- Pelo menos 90% dos itens com embalagem conhecida geram compra sem faltar quantidade

## Riscos do MVP

- Planos em texto muito livre ou pouco estruturado
- Ambiguidade em unidades caseiras
- Embalagens variando por regiao e marca
- Extracao fraca de PDF sem OCR especializado
