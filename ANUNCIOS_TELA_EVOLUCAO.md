# Tela de evolução de Anúncios 2.0

Tela administrativa `/evolucao-anuncios`, acessível no menu lateral da página inicial e nas ferramentas da loja. Por pedido explícito, o conteúdo mostra somente o gráfico de evolução, sem lista, controles de filtro ou links externos. Clientes não recebem acesso.

A lista de trabalho fica no arquivo versionado `anuncios_progresso.json`, com frentes conhecidas, estados, escopo entregue, lacunas, código/testes e correspondência original quando confirmada. A primeira medição registra 44 frentes auditadas: 20 concluídas no escopo descrito, 13 parciais e 11 pendentes. Esses números não equivalem a 20 de 90. A lista literal original continua incompleta, com contagem original nula; a tela explicita a base usada sem inventar correspondências.

O gráfico inicia com uma medição real; não cria crescimento retroativo nem pontos fictícios. As medições seguintes são acrescentadas no mesmo PR das entregas. Mudança na base de medição preserva o histórico anterior e não mistura séries de frentes agrupadas com requisitos originais. O registro só aparece em produção ao publicar a versão que o contém. Não há inferência automática de conclusão a partir do número de PRs.

A validação em CI confere IDs, estados, conclusão sem lacuna, referências de código/testes existentes, associação original, ordem/contagens do histórico e consistência da última medição. Instruções de manutenção em `AGENTS.md` tornam a atualização parte das próximas entregas. O gráfico aberto consulta uma rota interna autenticada a cada minuto, ou quando a aba volta a ficar visível; altera o desenho somente quando a revisão muda. Não há edição de estados pela interface, consulta ao GitHub/Render durante a navegação, migração, gravação em dados de lojas ou chamada de IA.

Oito testes novos cobrem integridade, contagem, associação original incompleta, evolução da série, bases separadas, escaping, tela somente com gráfico, permissões e ausência de rede. Navegador cobre primeira medição e uma série sintética claramente identificada em 1440, 390 e 320 px. Publicação condicionada aos checks.
