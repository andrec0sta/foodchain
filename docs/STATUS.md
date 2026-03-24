# Status da Sessao

## Resumo

O projeto segue funcional com backend Python, parser heuristico, integracao opcional com Gemini e pipeline hibrido de parse. Nesta sessao, o foco foi transformar a comparacao entre `gemini-2.5-flash-lite` e `gemini-2.5-flash` em um processo confiavel, separado dos testes unitarios e sem mascarar falhas por fallback local.

## O que foi entregue

- Benchmark dedicado para comparacao ao vivo entre modelos Gemini em `scripts/benchmark_llm.py`
- Benchmark em round-robin entre modelos para reduzir vies temporal
- Suporte a casos builtin, texto puro e PDF no benchmark
- Relatorio JSON com:
  - latencia total
  - latencia de LLM
  - erros
  - contagem de itens
  - consistencia de saida
- Documentacao de uso do benchmark no `README.md`
- Ajuste no backend para respeitar `LLM_TIMEOUT_SECONDS` de forma deterministica no caminho real da chamada LLM
- Teste automatizado cobrindo a propagacao do timeout configurado

## Estado validado

- `npm test` esta passando
- O benchmark dedicado executa localmente e aceita parametros esperados
- A comparacao inicial com `runs=3`, `warmups=1` mostrou que o protocolo antigo estava sujeito a `429` por quota no `gemini-2.5-flash`
- A comparacao com protocolo mais seguro:
  - `runs=2`
  - `warmups=0`
  - `pause_ms=13000`
  - `timeout_seconds=120`
  estabilizou os resultados e eliminou erros de quota nos testes executados

## Ultimas descobertas

- O problema principal observado na primeira rodada de comparacao nao foi timeout; foi `429 RESOURCE_EXHAUSTED` por quota do `gemini-2.5-flash`
- Com pausas maiores entre chamadas, os benchmarks ficaram repetiveis e sem falha de quota
- Nos casos builtin validados, `flash-lite` foi consistentemente mais rapido:
  - `small_complex`: cerca de `1284 ms` vs `2108 ms`
  - `medium_complex`: cerca de `1510 ms` vs `2554 ms`
- No PDF real `samples/Plano Nutricional André Costa - Junho.pdf`, `flash-lite` tambem foi mais rapido:
  - cerca de `4384 ms` vs `5205 ms`
- Nos casos builtin do protocolo seguro, ambos os modelos ficaram estaveis e semanticamente equivalentes
- No PDF real, houve diferenca material de qualidade:
  - `flash-lite` retornou `23` itens
  - `flash` retornou `21` itens
  - os 2 itens extras do `flash-lite` vieram da `Opcao 2` do cafe da manha
- Como a regra do produto e priorizar apenas `Opcao 1`, o `flash` ficou mais fiel ao comportamento esperado no PDF real, apesar de ser mais lento
- Ainda existe uma limitacao de normalizacao/medidas caseiras exposta pelos benchmarks:
  - em um caso medio, ambos os modelos mantiveram `feijao` com unidade `concha`

## Limitacoes conhecidas

- O benchmark ainda considera diferencas literais de assinatura; pequenas variacoes de acento ou rotulo podem aparecer como mudanca de saida
- O pipeline ainda permite que o LLM veja contexto suficiente para, em alguns casos, puxar itens de `Opcao 2+`
- Medidas caseiras como `concha`, `colher`, `pegador` ainda nao sao convertidas de forma confiavel
- Nem todo alimento esta suficientemente normalizado para virar item de compra ideal
- O parser esta mais robusto, mas ainda nao cobre toda a variabilidade de formatos reais
- A camada LLM atual esta focada em Gemini; ainda nao existe abstracao multi-provider
- O sample PDF real ainda depende demais do LLM para ficar rapido e preciso ao mesmo tempo

## Proximas etapas recomendadas

1. Endurecer o pre-processamento antes do LLM para filtrar `Opcao 2+` com mais confianca
2. Revisar a segmentacao dos blocos enviados ao Gemini para reduzir vazamento entre opcoes exclusivas
3. Melhorar a normalizacao de alimentos e sinonimos
4. Criar uma camada de equivalencias para medidas caseiras
5. Refinar a comparacao do benchmark para ignorar variacoes superficiais de rotulo quando o item semantico for o mesmo
6. Reavaliar o criterio de fallback entre `flash-lite` e `flash` depois que o filtro de opcoes estiver mais forte
7. Repetir a medicao no PDF real apos o ajuste de segmentacao para verificar se o `flash-lite` continua mais rapido sem perder fidelidade

## Observacao de arquitetura

O parser continua sendo conduzido para preservar as camadas que devem permanecer mesmo com mais uso de LLM:

- extracao
- limpeza
- segmentacao
- normalizacao
- validacao
- revisao manual

O papel ideal do LLM continua sendo interpretar os trechos semanticamente mais dificeis, e nao substituir essas etapas estruturais.

## Sugestao para retomar na proxima sessao

Comecar pelo pre-processamento dos blocos enviados ao Gemini, focando em garantir que apenas `Opcao 1` siga para o LLM nos trechos com exclusividade. Depois, repetir o benchmark do PDF real para comparar qualidade e latencia entre `flash-lite` e `flash`.
