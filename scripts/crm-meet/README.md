# Coleta de reuniões do Google Meet no CRM Keiper

Configuração única na conta profissional. O Google Apps Script faz a coleta no Google, e o CRM recebe as reuniões por uma chave que só permite essa importação. Não depende de um navegador conectado.

1. No [CRM](https://app.keiperconsultoria.com.br/crm/integracao), gere uma chave da integração.
2. Crie um projeto privado no [Google Apps Script](https://script.google.com/) usando a conta profissional. Copie [Code.gs](Code.gs) para o editor e [appsscript.json](appsscript.json) para o manifesto (Configurações do projeto → mostrar manifesto no editor).
3. Nas propriedades do script, crie **KEIPER_CRM_TOKEN** e cole a chave diretamente lá. Não cole a chave no código nem a compartilhe. Execute **instalarColetaKeiper** e aprove a leitura do Gmail/Drive no Google. O Google programa a execução na faixa das 18h no horário de Brasília; o minuto exato pode variar.
4. Confira **Execuções** no Apps Script e **Última importação** no CRM. A primeira coleta cobre sete dias. Se houver reuniões pendentes, confira os vínculos e execute `importarReunioesKeiper` para tentar de novo sem recriar o acionador.

A coleta só envia documentos do Gemini com título iniciado por Reunião/Reuniao. Confirma e-mail do convite e primeiro nome antes de gravar, mantém o conteúdo original no histórico e não cria leads, não envia mensagens, não reabre negócios fechados nem altera valores ou follow-ups. Uma reunião sem correspondência inequívoca fica sem gravar e aparece como pendência da execução. Uma vez acertado o cadastro, a sobreposição de sete dias permite nova tentativa. O documento e o histórico são deduplicados pelo identificador de origem.

Para desligar, revogue a chave no CRM e remova o acionador no Apps Script.
