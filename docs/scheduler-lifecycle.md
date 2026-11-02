# Encerramento do agendador

Durante a substituição de instâncias no Render, o processo antigo recebia SIGTERM e o APScheduler ainda tentava submeter tarefas depois do encerramento dos executores de threads do Python (`cannot schedule new futures after shutdown`).

O hook `worker_exit` do Gunicorn encerra o agendador já carregado com `shutdown(wait=False)`, antes da finalização do interpretador. O hook `on_exit` cobre também um agendador carregado no processo mestre. Nenhum hook importa a aplicação: processos sem aplicação carregada não iniciam tarefas ao sair.

A parada impede novas submissões e preserva a execução de tarefas já iniciadas, dentro do prazo de encerramento do processo. Não altera intervalos, dados, filas ou regras comerciais. O timeout HTTP existente permanece em 120 segundos.

O marcador `keiper_scheduler_shutdown_complete` identifica uma parada concluída. Agendadores já parados são tratados de forma idempotente; falhas inesperadas geram `keiper_scheduler_shutdown_failed` e continuam visíveis no Gunicorn.

## Validação

`python -m unittest -v test_scheduler_lifecycle` verifica ausência de importação da aplicação, parada idempotente, exposição de falhas e um subprocesso real do Gunicorn recebendo SIGTERM com uma tarefa ativa. A aplicação do teste é isolada, sem banco, credenciais ou chamadas ao Mercado Livre.

Após a publicação, deve-se observar o encerramento de uma instância que já contenha a correção. O primeiro deploy ainda encerra a versão anterior; um novo deploy do mesmo commit permite validar o marcador e procurar regressões nessa instância corrigida.

Esta é uma correção operacional. Não altera a contagem das 44 frentes de Anúncios nem simula avanço na lista original de 90 melhorias.
