# Campanhas incompletas sem interrupção do catálogo

O catálogo e os detalhes de promoções tratam datas ausentes, futuras ou inválidas e estruturas incompletas como pendências de leitura. Campanhas com campos incompatíveis com o contrato normalizado não são apresentadas como confirmadas nem geram detalhes parciais.

O preço vencedor segue independente: uma resposta válida e recente de sale_price pode continuar sendo exibida mesmo quando a consulta das campanhas está pendente. Campanhas antigas não são reexibidas como confirmadas apenas porque sale_price está recente. Nenhum preço, campanha ou dado persistido é alterado; não há novas chamadas ao Mercado Livre.

Validação: testes de regressão exercitam a renderização do catálogo completo com datas e estruturas inválidas, a preservação do preço vencedor e o comportamento de campanhas válidas. A suíte existente e a verificação de interface devem passar antes da integração.
