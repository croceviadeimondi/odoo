/**
 * Copia in sola lettura dell'inventario Odoo dentro un foglio Google.
 *
 * Ogni N minuti riscrive da zero la scheda NOME_SCHEDA con i beni presi da
 * Odoo (crocevia.foglio.elenco). Le modifiche fatte a mano in quella scheda
 * spariscono al giro dopo: l'inventario si cambia solo in Odoo.
 * Se Odoo non risponde la scheda resta com'era e in A1 compare l'errore.
 *
 * Messa in funzione (una volta per foglio):
 *  1. Estensioni > Apps Script, incolla questo file, salva.
 *  2. Impostazioni progetto > Proprieta' dello script, aggiungi:
 *       ODOO_URL    https://odoo.croceviadeimondi.org
 *       ODOO_DB     crocevia
 *       ODOO_LOGIN  foglio_inventario
 *       ODOO_CHIAVE la chiave API dell'utente "Foglio inventario"
 *       SEDE        Barletta   (o Trani; vuoto = tutte le sedi)
 *       CATEGORIA   libro      (facoltativo; "tutte" = ogni categoria)
 *  3. Esegui `installa` una volta e accetta i permessi richiesti.
 */

const NOME_SCHEDA = 'Inventario (da Odoo)';
const OGNI_MINUTI = 30;

function installa() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'aggiorna')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('aggiorna').timeBased().everyMinutes(OGNI_MINUTI).create();
  aggiorna();
}

function aggiorna() {
  const foglio = SpreadsheetApp.getActive();
  let scheda = foglio.getSheetByName(NOME_SCHEDA);
  if (!scheda) {
    scheda = foglio.insertSheet(NOME_SCHEDA, 0);
    scheda.protect()
      .setDescription('Copia da Odoo: si modifica solo in Odoo')
      .setWarningOnly(true);
  }

  let righe;
  try {
    righe = leggiDaOdoo_();
  } catch (e) {
    scheda.getRange('A1')
      .setValue('AGGIORNAMENTO NON RIUSCITO ' + adesso_() + ': ' + e.message)
      .setFontColor('#b00020');
    throw e;
  }

  const colonne = righe[0].length;
  scheda.clear();
  if (scheda.getFilter()) scheda.getFilter().remove();
  scheda.getRange('A1')
    .setValue('Copia da Odoo, aggiornata il ' + adesso_() +
              '. Non modificare qui: le modifiche si fanno in Odoo.')
    .setFontStyle('italic');
  scheda.getRange(2, 1, righe.length, colonne)
    .setNumberFormat('@')
    .setValues(righe.map(r => r.map(v => v === false || v === null ? '' : String(v))));
  scheda.getRange(2, 1, 1, colonne).setFontWeight('bold');
  scheda.setFrozenRows(2);
  scheda.getRange(2, 1, righe.length, colonne).createFilter();
  scheda.autoResizeColumns(1, colonne);
}

function leggiDaOdoo_() {
  const p = PropertiesService.getScriptProperties().getProperties();
  for (const k of ['ODOO_URL', 'ODOO_DB', 'ODOO_LOGIN', 'ODOO_CHIAVE']) {
    if (!p[k]) throw new Error('manca la proprieta\' dello script ' + k);
  }
  const uid = rpc_(p.ODOO_URL, 'common', 'authenticate',
                   [p.ODOO_DB, p.ODOO_LOGIN, p.ODOO_CHIAVE, {}]);
  if (!uid) throw new Error('login rifiutato: controlla ODOO_LOGIN e ODOO_CHIAVE');
  const categoria = (p.CATEGORIA || 'libro').trim();
  return rpc_(p.ODOO_URL, 'object', 'execute_kw', [
    p.ODOO_DB, uid, p.ODOO_CHIAVE, 'crocevia.foglio', 'elenco', [],
    {sede: (p.SEDE || '').trim() || false,
     categoria: categoria === 'tutte' ? false : categoria},
  ]);
}

function rpc_(url, servizio, metodo, args) {
  const risposta = UrlFetchApp.fetch(url.replace(/\/+$/, '') + '/jsonrpc', {
    method: 'post',
    contentType: 'application/json',
    muteHttpExceptions: true,
    payload: JSON.stringify({
      jsonrpc: '2.0', method: 'call', id: 1,
      params: {service: servizio, method: metodo, args: args},
    }),
  });
  if (risposta.getResponseCode() !== 200) {
    throw new Error('Odoo ha risposto ' + risposta.getResponseCode());
  }
  const dati = JSON.parse(risposta.getContentText());
  if (dati.error) {
    throw new Error((dati.error.data && dati.error.data.message) || dati.error.message);
  }
  return dati.result;
}

function adesso_() {
  return Utilities.formatDate(new Date(), 'Europe/Rome', 'dd/MM/yyyy HH:mm');
}
