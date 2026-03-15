# Arquitetura

## Resumo

Arquitetura monolitica modular com frontend estatico e backend HTTP em Node.js, persistencia local em JSON e servicos de dominio desacoplados.

## Componentes

### Frontend

- Pagina unica responsiva
- Secoes de entrada, revisao e lista de compras
- Edicao manual de itens e embalagens

### Backend

- API `POST /api/plan/parse`
- API `POST /api/plan/review`
- API `POST /api/shopping-list`
- API `GET /api/state`
- API `GET /api/catalog`

### Dominio

- Parser de plano e frequencia
- Normalizacao de alimentos e unidades
- Catalogo inicial de embalagens
- Motor de consolidacao semanal
- Motor de resolucao de embalagens

### Persistencia

- `data/last-plan.json`
- `data/package-overrides.json`

## Fluxo principal

1. Usuario envia texto ou arquivo
2. Backend extrai texto e interpreta itens
3. Usuario revisa itens
4. Backend consolida necessidades semanais
5. Backend resolve embalagens comerciais
6. Estado revisado e ajustes sao persistidos localmente

## Decisoes arquiteturais

- Sem banco externo no MVP para manter setup simples
- Catalogo interno como fonte primaria; fallback online fica preparado como extensao futura
- Contratos de dominio puros para facilitar migracao posterior para banco e servicos separados

## Evolucao prevista

- Trocar JSON local por banco relacional
- Adicionar OCR/parse de PDF mais robusto
- Acoplar fornecedor externo para busca de embalagens
- Introduzir autenticao e historico por usuario
