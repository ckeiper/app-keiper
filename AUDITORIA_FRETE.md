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
A tabela `frete_importacoes` guarda indicadores agregados, datas dos movimentos,
instante da importação e SHA-256. O detalhamento autorizado em 27/10/2026 acrescenta
somente os campos mínimos de pedido/envio e valores descritos na seção final.
O arquivo, nomes de produtos, pagamentos e identificadores do comprador não são persistidos.
O SHA-256 é único por loja; reenviar os mesmos bytes não duplica os indicadores.
A reanálise atualiza somente a conferência por venda, preservando os totais originais.
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
arquivos são manuais nesta etapa; não há coleta automática de relatórios.
A tarifa esperada ainda precisa de
fonte independente, com vigência e vínculo de envio verificados. A tabela
genérica de preço/peso do aplicativo não foi assumida como tarifa contratada.

## Consolidação incremental diária

O administrador informa o período exato do relatório e confirma que o arquivo
contém todos os lançamentos, sem filtros adicionais. Períodos de até 31 dias
(inclusive as duas extremidades) permitem a carga histórica e arquivos diários.
Datas futuras, datas inválidas, ausência de confirmação e movimentos fora do
período bloqueiam a consolidação antes de qualquer escrita.

Cada dia confirmado substitui sua versão anterior de forma transacional, sob
trava exclusiva da loja em namespace separado da coleta. Dias sem movimentos
dentro de um relatório completo confirmado recebem indicador zero; dias sem
relatório ficam sem cobertura. A tela mostra cobertura dos últimos 30 dias
até hoje, no fuso de São Paulo, e não converte lacunas em zero. Dias anteriores
permanecem armazenados. O mesmo arquivo só pode ser consolidado uma vez,
inclusive após importar apenas seu resumo: repetir um arquivo antigo não
reverte versões posteriores. Arquivos corrigidos diferentes substituem apenas
os dias confirmados pelo administrador. Não há deduplicação por operação nem
armazenamento de linhas de cliente; trata-se de consolidação de indicadores
diários completos, não de um livro de movimentos individuais.

## Comparação com a página de Vendas

Fonte definida pelo usuário: o frete da página de Vendas do dashboard. A auditoria
reutiliza `calcular_vendas` com a data inicial do relatório, sem o limite de 100
pedidos da tabela de detalhe. A mesma fórmula escolhe custo real de envio quando
disponível e estimativa por preço/peso caso contrário. Estimativas com peso
ausente em qualquer item ficam indisponíveis na auditoria, em vez de zero.

O vínculo usa igualdade exata entre número da operação e ID de pedido ou pagamento salvo,
ou entre número do envio e envio salvo, sempre na mesma loja. Vínculos conflitantes,
múltiplos movimentos por pedido e pedidos com múltiplos envios não são somados
nem escolhidos arbitrariamente. Ficam separados para revisão. Não se usa SKU,
valor ou proximidade de data para inferir um pedido. Apenas movimentos Venda e
Envio entram como candidatos. A falta de vínculo ou de dados de Vendas aparece
como lacuna de comparação; não se afirma que um frete é correto nesses casos.

A tela informa quantos pedidos foram comparados, referência real ou estimada,
quantos estão acima/abaixo/dentro da tolerância de R$ 0,01 e totais somente dos
pedidos comparados. A comparação retorna agregados por padrão; o fluxo detalhado
autorizado também salva evidências mínimas por pedido. Divergência entre as
duas fontes não comprova cobrança indevida nem equivale à tarifa contratada.

## Leitura única do XLSX

A rota reconhecida valida o envelope ZIP e abre o workbook uma única vez.
A mesma leitura produz a prévia, os indicadores e seis campos transitórios
por linha para a comparação. Esses campos não entram no resumo persistido.
O comparador reutiliza os campos já lidos em vez de abrir o Excel novamente.
Formatos desconhecidos continuam com prévia limitada e sem importação.
Testes da rota e do fluxo completo verificam uma única abertura do workbook.
Isso corrige o timeout observado no upload real no worker HTTP do Render.

## Página de auditoria · revisão em 27/10/2026

A apresentação prioriza diferenças por venda; envio, detalhes gerais, histórico e
cobertura diária ficam em segundo plano, sem somar arquivos sobrepostos.
Ausência de consolidação aparece como sem cobertura; um dia confirmado com valor zero
continua sendo zero. O formulário mantém CSRF, formatos/limites, ações e validação
do período no servidor. A consolidação fica em uma seção expansível e começa sem
confirmação marcada. Permissões e cálculos existentes não mudam.

Após importar, o histórico é relido na mesma transação e exibido na resposta, sem
reenviar o upload. Resultados vêm antes do histórico. O relatório e suas linhas reais
não fazem parte do código ou das capturas de testes. A validação visual cobre telas
vazias, histórico, resultado, repetição de arquivo e acesso de cliente em desktop e celular.

## Diferenças por venda · escopo solicitado em 27/10/2026

A tela prioriza valores a mais e a menos, referência real ou estimada e a lista de
diferenças por pedido. Não força vínculo para movimentos ambíguos. A lista tem 50
linhas por página, filtros de direção e referência e exportação CSV de todas as
diferenças do filtro. A conferência usa a mesma fórmula de Vendas; referência
estimada não comprova tarifa contratada ou cobrança indevida.

Sob autorização para mostrar venda por venda, a análise salva somente pedido,
envio, valores comparados, diferença, fonte, critério de vínculo e data de venda.
Esses dados mínimos ficam em `resumo.freight_review`, com instante da conferência.
Não armazena dados do comprador nem o arquivo. A listagem de históricos omite o
detalhamento; somente o relatório selecionado é carregado, com escopo de loja.
O CSV exige login administrativo e o mesmo escopo, não é armazenado publicamente
e neutraliza prefixos de fórmula em campos de texto provenientes da fonte.

Relatórios antigos conservam seus indicadores e comparação original. Reanalisar
o mesmo arquivo atualiza apenas `freight_review`, por loja e SHA-256, sem duplicar
importação, alterar consolidação diária ou substituir totais originais. Antes da
reanálise, a tela informa que a lista por pedido não está disponível. O total a
menos legado não é inferido pelo saldo líquido das diferenças.
