# Anúncios 2.0 — simulação de descontos progressivos

Escolha do usuário recuperada no contexto: análise de descontos progressivos com rentabilidade e simulação de novas faixas. Esta etapa entrega simulação administrativa explícita; não presume que a campanha/faixa exista no marketplace e não publica ofertas.

Acesso pela rentabilidade do anúncio, com autorização administrativa, escopo loja/anúncio e CSRF global. GET não calcula valores: formulário sem premissas financeiras preenchidas. POST somente lê o título do anúncio e calcula em memória, sem escrita, chamadas externas ou migração. Não reutiliza custo histórico como projeção futura nem persiste cenários como evidência.

Até cinco quantidades crescentes (1 a 10.000) e descontos não decrescentes (0 a 99,99%). O administrador preenche preço/custo unitário, percentuais de tarifas e impostos sobre o bruto, tarifas fixas, frete, publicidade e ajustes por pedido. Todos os custos exigem valor explícito, inclusive zero; confirmação de premissas obrigatória. Máximo de R$999.999,99 por campo monetário. Ausência, números não finitos, sinal negativo, notação científica e precisão acima de centavos são rejeitados. Não aplica defaults de tarifas, imposto, custo ou margem.

Preço após desconto arredondado HALF_UP a centavos antes da multiplicação pela quantidade. Tarifas percentuais e impostos arredondados por pedido. Contribuição = bruto − produtos − tarifas − impostos − frete − Ads − ajustes. A comparação sem desconto usa a mesma quantidade e premissas, recalculando percentuais sobre seu bruto; não confunde variação de volume com desconto. Valores negativos são permitidos e exibidos. Não é lucro líquido, previsão de demanda, CAC, melhor preço ou garantia de recuperação. Despesas fixas e regras específicas de pisos tarifários, faixas logísticas, cupons e cofinanciamento não são reproduzidas.

Onze testes novos verificam identidade financeira, arredondamento, comparação de mesma quantidade, negativos, cinco faixas, ausência/inválidos, progressividade, preço zero, confirmação, escape, permissões, escopo, CSRF e ausência de escrita/rede. Navegador cobre formulário vazio, cenário e erro em 1440/390/320 px. Fixtures sintéticas identificadas como demonstração, sem dados de produção.

Mercado Pago e conciliação bancária continuam adiados expressamente na issue #201. Não pertencem ao lote de anúncios.
