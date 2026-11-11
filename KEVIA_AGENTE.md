# KEVIA — primeira missão do agente

O administrador escolhe três prioridades da loja, revisão de Ads ou investigação de vendas na própria tela `/ia-keiper/<loja>`. O planejador reúne os diagnósticos existentes de loja e campanhas, seleciona até três sinais com evidências e prepara passos para conferência na origem.

A primeira versão tem planejamento determinístico, sem modelo escolhendo ferramentas ou conversa livre. Não gera chamadas pagas, não dispara coletas, não altera anúncios ou campanhas, não cria novas tabelas e não usa evidências financeiras privadas. Os sinais disponíveis já são limitados pelas análises de origem (até três por fonte); o resultado não representa auditoria integral dos anúncios.

Autorização e isolamento continuam na rota existente. A missão é exibida apenas para administradores. Um diagnóstico só participa se estiver concluído na data de Brasília e terminar ontem; campanhas com leitura limitada ficam bloqueadas. Fontes indisponíveis e ressalvas permanecem visíveis. Os links usam somente a loja autorizada.

Próximas etapas: ferramentas de consulta de anúncios individuais com cobertura explícita; planejamento por modelo dentro do orçamento existente; histórico de missões e decisões; alterações preparadas com revisão. Execução automática exige implementação específica das regras e permissões de cada ferramenta.

Validação: `python -m unittest test_kevia_agent test_keiper_ai test_keiper_ai_view test_kyra_campaigns test_kevia_identity`; verificação de integridade do registro de Anúncios. Não altera as 44 frentes auditadas, pois esta entrega é da KEVIA e ainda não implementa diagnóstico individual de anúncios.
