# Curva ABC dos anúncios

Classificação descritiva pelo valor bruto dos itens vendidos em períodos encerrados de sete ou trinta dias, com comparação das classes do período anterior. Reaproveita o ranking verificado de toda a loja, incluindo anúncios vendidos que já não estão no catálogo atual. Não adiciona consulta, chamada externa, escrita ou migração. O modo compacto de prioridades não é alterado.

A inclui o grupo que alcança ou ultrapassa 80% do valor; B continua até alcançar ou ultrapassar 95%; C contém o restante positivo. Empates permanecem juntos, sem corte arbitrário por código. Logo, os limites podem ser ultrapassados e classes podem ficar vazias. Anúncios de valor zero são separados em Sem valor bruto, que não equivale a zero pedidos. Sem total positivo, não há porcentagem. Valores inválidos ou cobertura incompleta não produzem classificação parcial.

Cards mostram contagem, valor e participação de cada classe na base completa. Filtros por classe e nome/código não recalculam essa base. Lista paginada em vinte anúncios, com links para diagnóstico e preservação de período e seleção do comparador. Cada período usa sua própria distribuição: mudança de classe não prova mudança nas vendas do anúncio. Não mede margem, lucro, estoque nem prioridade automática de reposição.

Dez testes novos cobrem limites, empates, zeros, bases independentes, fontes inválidas, imutabilidade, filtros, paginação e escaping. Navegador verifica lista completa, filtros, pendência, zeros e segunda página em 1440, 390 e 320 px, incluindo teclado e rolagem. Integração e publicação condicionadas aos checks desta revisão.
