A leitura da Visão Geral tem orçamento conjunto de 12 segundos. Cada consulta recebe
o tempo restante via statement_timeout local à transação PostgreSQL, inclusive as
páginas de datas incomuns. O cancelamento produz aviso sem totais parciais e a
transação é revertida normalmente. Não modifica vendas, cobertura ou alertas.

Motivo: em produção houve WORKER TIMEOUT seguido de SIGKILL às 09:52 de 16/10/2026
durante abertura do painel, interrompendo também a fila de sincronização em memória.
Esse limite evita que uma consulta lenta da Visão Geral provoque esse encerramento;
não torna a fila persistente e não elimina reinícios por outras causas.

Validação: testes de orçamento compartilhado, cancelamento real por pg_sleep no
PostgreSQL, ausência de subtotal após cancelamento e recuperação na requisição
seguinte. As configurações do Render não foram modificadas.
