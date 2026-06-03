Trust list per la validazione della firma QUALIFICATA.

Metti qui i certificati delle CA qualificate (file .pem o .crt) contro cui
validare la catena della firma del registro. Servono solo se vuoi attivare la
modalita' "strict qualified" (parametro di sistema
crocevia_registro_volontari.firma_strict = True).

Fonte: EU Trusted List (LOTL) / TSL italiana AgID
(https://eidas.agid.gov.it/TL/TSL-IT.xml). Da aggiornare periodicamente.

Senza certificati qui, la verifica controlla comunque integrita' della firma,
copertura del documento e marca temporale (sufficienti per la tamper-evidence
e la data certa), ma NON asserisce che la firma sia qualificata.
