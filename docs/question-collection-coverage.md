# Coleta de perguntas e verificação de status

Fontes oficiais consultadas em 30/10/2026:
- https://developers.mercadolivre.com.br/pt_br/perguntas-e-respostas
- https://developers.mercadolivre.com.br/pt_br/realizacao-de-testes/gerenciamento-perguntas-respostas

A coleta usa somente GET /questions/search com seller_id, api_version=4, limit=50, offset e ordenação de criação decrescente; consulta GET /questions/{id} para revisar registros antigos. Não responde, exclui, oculta ou bloqueia perguntas/usuários. Não chama endpoints de contato. Os objetos de comprador, contatos e respostas brutas não são persistidos nem incluídos nos logs.

## Limites e cobertura

Cada atualização da loja permite no máximo duas páginas de busca e duas consultas individuais, com timeout de conexão/leitura (3,8) segundos e sem seguir redirects. HTTP 401,403,429 interrompe as demais consultas. Bloqueio transacional consultivo por loja evita execução simultânea; lojas diferentes não compartilham a chave. A base preserva registros anteriores por upsert, sem DELETE. Todo lote é validado antes de escrever. Falha de banco reverte a transação; uma segunda página indisponível preserva as páginas válidas e registra coleta parcial.

A atualização persiste quantidade de páginas, IDs distintos observados, total informado pela API, instante, vendedor e revisões de registros antigos. Só considera a paginação retornada lida quando total, offset e limite são verificáveis, os totais não mudam, não há repetição entre páginas e o total coincide com IDs observados. Não declara histórico integral: o conjunto pode mudar entre páginas, a busca é limitada a 100 perguntas por atualização e perguntas anteriormente excluídas não são reconstruídas. Não guarda cursor de scan com validade incompatível com a rotina horária e não amplia a busca além da janela sem fonte verificável.

Registros antigos são selecionados por menor instante de tentativa, com prioridade de sem resposta apenas no desempate, e nova tentativa após seis horas. IDs não verificáveis não são consultados nem podem monopolizar o rodízio. A consulta individual exige o mesmo ID, anúncio e vendedor do registro; divergência preserva o texto/status anterior e marca a verificação atual como desconhecida. HTTP 404 não vira DELETED, ANSWERED ou zero perguntas. Resposta válida com status oficial DELETED é armazenada como evidência retornada, sem inferência por ausência.

## Status e interface

Perguntas ganham campos opcionais de última tentativa, última confirmação de status, estado/erro da consulta, vendedor confirmado, visibilidade, espera e status da resposta. Registros antigos não são marcados como atuais pela migração. O painel do anúncio separa último status salvo de status confirmado nas últimas seis horas e mostra a evidência da coleta da loja (não somente do anúncio). Perguntas apagadas/retiradas/em espera não são classificadas como pendência acionável. Respostas BANNED/DISABLED são apresentadas como indisponíveis. Recorrências continuam literais, sem inferência semântica, sentimento ou avaliação de compradores.

O aviso do painel da loja usa a função pending_count: somente UNANSWERED, leitura verificada na mesma conta nos últimos seis horas, sem retirada e sem espera explicitamente confirmadas. BANNED, DELETED, CLOSED_UNANSWERED, desconhecidos, dados antigos, consulta individual com erro ou outro vendedor não geram aviso de resposta. Todas as consultas e escritas têm conexao_id. A página é administrativa, em transação somente leitura, sem consultas ao Mercado Livre na renderização. O botão Atualizar Perguntas usa a fila por seção existente (autorização, proteção CSRF e exclusão por loja), chama apenas puxar_perguntas e mantém Anúncios ativo no menu; não atualiza anúncios, promoções, vendas ou Ads. Sem alterações de dados em produção para testes.

## Validação

Testes unitários cobrem limites, paginação deslocada/incompleta, ID canônico, lote atômico, timeout, limite 429, HTTP 404, vendedor divergente, vínculo ID/anúncio, concorrência e ausência de contatos nos parâmetros persistidos. Testes PostgreSQL exercitam status antigo alterado, preservação em falha, rodízio e o predicado real do aviso. Browser checks cobrem 42 combinações de estado, tema e largura (320,390,1440), incluindo leitura antiga, recente, parcial e indisponível. A frente permanece parcial: faltam fonte/painel de avaliações, histórico integral e análise validada de objeções semânticas.
