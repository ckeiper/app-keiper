# Validação da conciliação de fretes — Keiper

## Regra de ativação

A auditoria **não** consulta divergências em segundo plano e **não** classifica
cobranças automaticamente antes de o administrador importar uma planilha real
de Conciliação Bancária do Mercado Livre, específica da loja selecionada.

A tela inicial de importação é somente uma pré-visualização limitada. Não grava
o arquivo nem lançamentos, não presume cabeçalhos e não calcula diferenças.

## Conferência com planilha real (pendente)

- [ ] Identificar qual aba e linha contêm o cabeçalho de lançamentos.
- [ ] Confirmar o campo que representa o identificador da venda/pedido.
- [ ] Confirmar quais lançamentos são custo de envio **do vendedor**, não tarifa
      de anúncio, comissão, desconto do comprador ou valor bruto de repasse.
- [ ] Verificar se ajustes, reembolsos e estornos aparecem em linhas distintas.
- [ ] Confirmar formato de moeda, data, timezone e separador decimal.
- [ ] Confirmar se há múltiplos lançamentos por pedido e qual a chave estável
      para evitar duplicações em reimportações.
- [ ] Confirmar se os valores são assinados (débito negativo ou positivo).
- [ ] Validar pedidos sem envio, envio compartilhado, pacotes com vários itens
      e pedidos com mais de um envio.
- [ ] Confirmar associação à loja sem aceitar ID de outra conexão.
- [ ] Comparar amostras reais do Excel com tela de vendas e extrato de repasse.

## Estados previstos para resultados

- **Sem correspondência**: lançamento da planilha sem pedido/envio local seguro.
- **Pendente de conferência**: dados insuficientes, estorno não conciliado,
  múltiplos envios ou valores não comparáveis.
- **Valores conciliados**: valores e contexto confirmados, sem diferença.
- **Diferença a investigar**: valores comparáveis, mas diferentes; **não**
  significa cobrança indevida comprovada.
- **Contestação aberta**: divergência revisada, vinculada a chamado e protocolo.
- **Resolvida**: resposta e valor efetivamente recuperado registrados.

Nenhum estado de recuperação deve ser preenchido automaticamente com base no
valor inicialmente contestado.

## Critérios para liberar a primeira auditoria

1. Upload validado com arquivo real e formatos esperados, com limites de
   tamanho e quantidade de linhas.
2. Importação idempotente por loja; mesma planilha não gera cobrança duplicada.
3. Cada lançamento preserva origem, data e identificador para rastreabilidade.
4. A comparação usa Decimal, não float, e contabiliza ajustes/estornos.
5. Não há cruzamento entre lojas.
6. Diferenças são exibidas com motivo e dados de origem, sem acusações
   automáticas de cobrança indevida.
7. Testes para divergência real, valor igual, estorno, pedido ausente, múltiplos
   lançamentos, reimportação, arquivo inválido e loja diferente.
8. Conferência manual com pedidos fornecidos pelo administrador.

**Não fazer merge/deploy da PR de auditoria sem validação operacional.**
