# Leitura limitada no acompanhamento de ações

A comparação de uma ação usa 7 dias anteriores e 14 posteriores, excluindo o dia da ação nos resultados. As duas leituras de pedidos/itens passam a carregar apenas candidatos desse intervalo, em vez do histórico integral da loja. Conservam buffer de um dia nos timestamps textuais para conversão de fuso e fallback pela data da coleta para timestamps inválidos. A classificação final continua em horário de Brasília.

Todos os itens dos pedidos candidatos continuam carregados: filtrar apenas pelo MLB esconderia vínculos incompletos. Pedidos não verificados continuam bloqueando globalmente a loja, mesmo antigos. Cobertura, visitas, sobreposição de ações e regras de ausência de causalidade permanecem iguais. Não há limite arbitrário de pedidos, cache, alteração de dados, chamada externa ou migração.

Seis leituras por comparação, independentes do número de ações na página. A redução é do volume retornado/materializado; não se afirma eliminação de varredura no PostgreSQL nem latência garantida. Os predicados textuais podem exigir varredura; não foi criado índice adicional sem evidência de plano e necessidade.

Testes verificam escopo SQL, buffer, fallback, preservação dos itens e bloqueio global. Integração PostgreSQL inclui pedido antigo excluído, fronteiras UTC que pertencem ao dia de Brasília, timestamp inválido dentro do período e pedido antigo não verificado que ainda bloqueia a análise. Sem dados de produção na fixture.
