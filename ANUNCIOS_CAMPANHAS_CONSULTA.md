# Catálogo — confirmação da consulta de campanhas

Nova indicação por anúncio e filtro independente para consulta válida, conferir consulta ou não aplicável. Consulta válida exige snapshot recente (até duas horas), timestamp positivo não futuro, sem erro e lista estruturada de campanhas. Lista vazia válida confirma a leitura, não uma promoção ativa ou preço vencedor. Falta, falha, formato inválido, futuro ou expiração ficam pendentes.

Não aplicável exige snapshot recente com motivo já registrado e status compatível (closed ou under_review); snapshot contraditório com anúncio ativo fica pendente. Não modifica a coleta nem recalcula snapshots passados.

O preço vencedor oficial continua independente: pode estar confirmado com erro na consulta de campanhas, como já previsto pelo contrato existente. A nova indicação explicita essa diferença sem trocar o preço vencedor por preço de campanha. Os filtros antigos de promoção registrada não passam a afirmar ausência confirmada no marketplace.

Combina busca, status, estoque, leitura do catálogo e demais filtros; paginação preserva a seleção. Sem consultas adicionais, migração, escrita ou alteração de preço. Cinco testes novos cobrem resposta vazia, datas e fronteira, não aplicável, filtro/paginação e independência do preço vencedor. Navegador confere novo seletor e indicação na tabela.
