const CRM_ENDPOINT = 'https://app.keiperconsultoria.com.br/crm/integracao/meet';
const GOOGLE_ACCOUNT = 'clinton@keiperconsultoria.com.br';
const HANDLER = 'importarReunioesKeiper';

function instalarColetaKeiper() {
  validarContaKeiper();
  for (const trigger of ScriptApp.getProjectTriggers()) {
    if (trigger.getHandlerFunction() === HANDLER) ScriptApp.deleteTrigger(trigger);
  }
  ScriptApp.newTrigger(HANDLER).timeBased().everyDays(1).atHour(18)
    .inTimezone('America/Sao_Paulo').create();
  importarReunioesKeiper();
}

function meetingDocs(part, ids) {
  if (part.body && part.body.data && /^text\/(plain|html)$/i.test(part.mimeType || '')) {
    const content = Utilities.newBlob(Utilities.base64DecodeWebSafe(part.body.data)).getDataAsString('UTF-8');
    for (const m of content.matchAll(/https:\/\/docs\.google\.com\/document\/d\/([\w-]{20,120})/g)) ids.add(m[1]);
  }
  for (const sub of (part.parts || [])) meetingDocs(sub, ids);
}

function validarContaKeiper() {
  const key = PropertiesService.getScriptProperties().getProperty('KEIPER_CRM_TOKEN');
  if (!key || !/^[A-Za-z0-9_-]{43}$/.test(key)) throw new Error('Configure KEIPER_CRM_TOKEN nas propriedades.');
  if (Gmail.Users.getProfile('me').emailAddress.toLowerCase() !== GOOGLE_ACCOUNT) {
    throw new Error('Execute pela conta Google profissional.');
  }
  return key;
}

function importarReunioesKeiper() {
  const key = validarContaKeiper();
  let pageToken, pages = 0, failures = 0;
  const docs = new Set();
  do {
    const result = Gmail.Users.Messages.list('me', {
      q: 'from:gemini-notes@google.com newer_than:7d',
      maxResults: 100,
      pageToken
    });
    for (const entry of (result.messages || [])) {
      const message = Gmail.Users.Messages.get('me', entry.id, {format:'full'});
      const part = message.payload || {};
      const subject = ((part.headers || []).find(h => h.name.toLowerCase() === 'subject') || {}).value || '';
      const normalized = subject.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
      if (!/^anotacoes:\s*["“]?reuniao\s/i.test(normalized)) continue;
      const links = new Set();
      meetingDocs(part, links);
      if (!links.size) failures++;
      for (const id of links) docs.add(id);
    }
    pageToken = result.nextPageToken;
    pages++;
  } while (pageToken && pages < 10);
  if (pageToken) failures++;
  for (const id of docs) {
    try {
      const file = Drive.Files.get(id, {fields:'name,mimeType,trashed'});
      const title = file.name || '';
      if (file.trashed || file.mimeType !== 'application/vnd.google-apps.document'
          || !/^reuni[aã]o\s+.+?\s+-\s+\d{4}\/\d{2}\/\d{2}.*anota[cç][oõ]es do gemini$/i.test(title)) continue;
      // Media export through the authenticated Drive API; the token stays inside Apps Script.
      const media = UrlFetchApp.fetch('https://www.googleapis.com/drive/v3/files/' + id + '/export?mimeType=text%2Fplain', {
        headers:{Authorization:'Bearer ' + ScriptApp.getOAuthToken()},
        followRedirects:false,
        muteHttpExceptions:true
      });
      if (media.getResponseCode() !== 200) { failures++; continue; }
      const response = UrlFetchApp.fetch(CRM_ENDPOINT, {
        method:'post', contentType:'application/json',
        headers:{Authorization:'Bearer ' + key},
        payload:JSON.stringify({document_id:id,title,text:media.getContentText('UTF-8')}),
        muteHttpExceptions:true, followRedirects:false
      });
      if (response.getResponseCode() !== 200) failures++;
    } catch (_) {
      failures++;
    }
  }
  if (failures) throw new Error('Importação do CRM: ' + failures + ' item(ns) pendente(s). Verifique vínculo, formato e chave da integração.');
}
