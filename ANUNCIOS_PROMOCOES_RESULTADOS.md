# Anúncios 2.0 — contribuição antes e depois de preço/promoção

Acrescenta a comparação financeira documentada ao histórico de ações e alterações, quando o registro selecionado é de preço/promoção. Disponível somente para administrador no GET autenticado. Mantém a comparação de vendas e visitas existente; clientes continuam sem os novos dados financeiros.

As janelas são os sete dias anteriores e os sete seguintes ao registro, excluindo o dia da alteração. Para registro automático, a referência é o dia de detecção, não o início real da promoção. O histórico não comprova que um preço ou promoção permaneceu nas mesmas condições por toda a janela.

Consulta única de versões financeiras para loja, anúncio e os dois intervalos exatos, apenas com períodos encerrados e vendas verificadas. Sem custos preenchidos ou com base de vendas alterada, a margem fica indisponível. Usa fingerprint e validação de contribuição existentes, sem copiar custo atual para representar o passado. Seleciona a versão mais recente em cada intervalo. Links levam às datas exatas da rentabilidade para conferir componentes e fontes. Links fora da janela aceita ou para períodos futuros não são gerados.

Variação da contribuição em reais e da margem em pontos percentuais; com bruto zero, margem indisponível. Preserva contribuições e margens negativas. É comparação observacional: volume, mix e outras alterações afetam os valores, sem atribuição causal ou lucro líquido. Fontes declaradas pelo administrador, sem validação automática dos documentos. Não publica promoção, altera preço ou recomenda verba automaticamente.

O GET lê histórico, vendas e custos sob transação REPEATABLE READ, READ ONLY. Registros/ações anteriores preservados. Sem migração, chamada externa, escrita extra ou processamento em lote na página. O carregador padrão público continua sem consulta de custos. Oito testes novos cobrem datas, base, fonte/fingerprint, loja/item, versões, negativos, zeros, links, permissões e consistência de leitura. Navegador cobre pronto, negativo, ausente e aguardando em 1440/390/320 px.

Mercado Pago e conciliação bancária seguem adiados na issue #201.
