# Ordenação e confirmação de preço no catálogo

Corrige divergência entre a coluna exibida e o filtro Maior preço: a ordenação usava `anuncios.preco`, enquanto a tela podia mostrar o preço promocional oficial confirmado. Agora ambos usam o mesmo resolvedor: promoção efetiva com dados válidos ou, sem essa confirmação, preço cadastrado da última coleta. O nome do filtro explicita Maior preço exibido. Não escolhe o menor preço de campanhas nem soma descontos.

Valores ausentes ficam no fim e empates usam item_id. Promoção expirada, futura, com erro ou timestamp inválido não permanece confirmada; não substitui por outra campanha. A data deve ser numérica positiva, não futura e dentro de duas horas. Estruturas inválidas na resposta de preço efetivo não confirmam oferta. Mantém o limite de duas horas inclusive na fronteira.

Não altera preços, promoções, snapshots ou dados, e não acrescenta consultas. Os rótulos existentes de promoção registrada não passam a afirmar ausência confirmada no marketplace. O fallback continua explicitamente identificado como preço do anúncio na última coleta.

Quatro testes novos cobrem preço exibido versus cadastrado, expiração/futuro/inválidos, fronteira, empates, ausentes e estrutura inválida. Preview sintético e navegador conferem a ordem R$100 antes da promoção de R$80 apesar do preço cadastrado de R$200.
