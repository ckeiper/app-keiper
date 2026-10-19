# Piloto da fila persistente

Ativar somente uma loja inicialmente. A candidata é 9 (Dmr Milani), que teve
uma coleta concluída antes do piloto. Não usar lista de todas as lojas.

1. Publicar a proteção de exclusão e aguardar o deploy `live` e a saída da
   instância anterior. Versões anteriores não mantêm a trava durante a coleta.
2. Conferir no banco que a loja piloto não tem execução ativa. Não alterar
   registros em execução para forçar o início.
3. Configurar no serviço Render `DURABLE_QUEUE_STORE_IDS=9` e
   `DURABLE_QUEUE_WORKER_ENABLED=true`, preservando as demais variáveis.
   Publicar essa configuração e confirmar o commit em execução.
4. O agendador de dados enfileira a loja após dois minutos do início do processo;
   o consumidor tenta uma tarefa por minuto. Nas demais lojas segue a fila legada.
   Manter requisições de observação durante o teste: o serviço usa plano free
   e pode dormir, interrompendo o scheduler e as threads.
5. Validar no banco tarefa, tentativas, lease, execução e resultados coletados.
   Exigir conclusão e avanço dos dados reais; `live` sozinho não aprova o piloto.
   Verificar ausência de sobreposição nos registros e na trava PostgreSQL.
6. Não ampliar enquanto houver falha de coleta, reinício ou resultado inconclusivo.

A reserva consulta somente lojas selecionadas e ativas. Falha na reserva do
legado impede a coleta. Toda atualização completa usa a mesma trava de sessão
PostgreSQL, mantida até a saída da coleta e liberada ao fechar a conexão. Essa
trava independe da expiração dos registros de telemetria. Perda da conexão que
mantém a trava e interrupção abrupta continuam exigindo acompanhamento: a fila
usa entrega com possíveis repetições, não promete execução exatamente uma vez.

O consumidor adquire a trava antes de registrar a execução e a mantém até a
finalização da tarefa. Sob essa trava, marca registros anteriores ainda abertos
como interrompidos: a ausência de outro dono da trava comprova que não há coleta
protegida em execução. A chamada interna da coleta reutiliza a trava na mesma
thread. Isso permite retomar após deploy sem esperar duas horas por telemetria
abandonada; uma coleta realmente ativa impede a retomada.

Para interromper o piloto, desabilitar o consumidor e impedir novas solicitações
da loja durante a drenagem. Esperar a tarefa em execução terminar antes de
remover a seleção da loja e voltar ao legado. Não apagar tarefas pendentes:
inspecionar e decidir sua retomada. Não executar rollback para versão anterior
à proteção com uma coleta ainda ativa.

Validação automatizada: testes unitários de falhas e parada do heartbeat;
PostgreSQL isolado no CI para reserva concorrente, seleção, deduplicação,
retentativa e exclusão entre sessões. Nenhum teste automatizado coleta dados de
produção ou usa credenciais reais.
