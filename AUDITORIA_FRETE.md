# Auditoria de frete: relatório por vendas

Formato verificado: XLSX, aba `DAILY_CONCILIATION`, linha 1 informativa,
linha 2 com grupos, linha 3 com 32 cabeçalhos, lançamentos a partir da linha 4.
O parser exige os cabeçalhos exatos (normalizando acentos, caixa e espaços),
sem depender da posição e rejeitando campos duplicados ou ausentes.

| Coluna original | Campo | Uso |
| --- | --- | --- |
| A–E | Datas, número, tipo e status da operação | Contexto do lançamento; número da operação não garante pedido único |
| P | Envio pago pelo comprador (+) | Separado do custo do vendedor |
| T–W | Tarifas totais, pós-pagas, líquido e detalhes | Não equivalem ao custo de frete |
| X–Z | Número do envio, número do pacote, método | Identificadores distintos; não inferir pedido pelo pacote |
| AA | Valor bruto do envio | Valor bruto do lançamento |
| AB | Desconto sobre o envio | Desconto do lançamento |
| AC | Envio pago pelo vendedor | Valor cobrado do vendedor no lançamento |

A conferência testa AA − AB = AC, com tolerância de R$ 0,01. Isso é uma
verificação aritmética, não uma estimativa de tarifa contratada. O arquivo
não fornece o frete esperado. Não somar tarifas totais ao frete: elas podem
conter a própria tarifa de envio. Não deduplicar por número da operação:
há movimentos distintos associados à mesma operação e tipos além de vendas.

Na prévia, o processamento é temporário, sem gravação do upload. Valores ausentes,
negativos, fórmulas e representações monetárias não numéricas são sinalizados,
sem conversão para zero. Arquivos desconhecidos continuam apenas na prévia.
Limites de upload/ZIP existentes e limite de 25 mil lançamentos são aplicados.
Comparação por pedido depende de fonte independente de tarifa esperada e de
regras verificadas para movimentos, estornos e agrupamento por envio.

Testes usam exclusivamente planilhas sintéticas geradas em memória. Não anexar
relatórios de clientes, identificadores reais ou detalhes de pagamento ao Git.

## Importação de indicadores por loja

O administrador pode importar o resumo de um relatório XLSX na loja selecionada.
A tabela `frete_importacoes` guarda somente indicadores agregados, datas dos
movimentos, instante da importação e SHA-256. O arquivo, nomes de produtos,
pedidos, pagamentos e identificadores do cliente não são persistidos.
O SHA-256 é único por loja; reenviar os mesmos bytes é uma operação sem efeito.
Relatórios diferentes permanecem separados, inclusive se seus períodos se
sobrepõem: não somar históricos como se fossem movimentos novos.

Campos de frete simultaneamente vazios são contados como informação ausente,
separadamente de valores parciais ou inválidos. Não equivalem a frete zero.
Totais abrangem somente lançamentos com os três campos monetários válidos;
não representam pedidos únicos. Datas inválidas impedem a importação do resumo.
Os limites do período são as datas efetivas de operação, não o nome do arquivo;
datas com movimentos não garantem cobertura completa.

A coleta de pedidos mantém o histórico inicial dos últimos 30 dias e sua
atualização incremental existente com reconsulta recente. Uploads de conciliação
não alteram a cobertura nem o agendamento dessa coleta. Importações diárias de
arquivos são manuais nesta etapa; não há coleta automática de relatórios nem
consolidação de movimentos entre arquivos. A tarifa esperada ainda precisa de
fonte independente, com vigência e vínculo de envio verificados. A tabela
genérica de preço/peso do aplicativo não foi assumida como tarifa contratada.
