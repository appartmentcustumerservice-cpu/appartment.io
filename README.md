# Armadio Digitale

Armadio virtuale da telefono. Ogni capo entra con una foto (scontorno e scheda proposta da
Claude), con la foto dell'etichetta (composizione, lavaggio, brand, taglia) oppure a mano.
L'app propone abbinamenti per colore, fantasia, formalità e stagione.

## Struttura

| Cartella | Contenuto |
|---|---|
| `app/armadio-digitale.html` | La web app (prototipo Fase 0), pubblicata come Artifact su claude.ai |
| `fase0/` | Kit Python per analizzare in blocco un campione di foto da computer (opzionale) |
| `docs/BACKLOG.md` | Funzioni in coda di implementazione, con fattibilità e requisiti |

## Web app

- **Dove si apre:** https://claude.ai/artifact/HUDH2yseXVcHUDhocaYJsd. È privata: la apre solo
  il proprietario, salvo condivisione dal menu Condividi.
- **Riconoscimento:** usa Claude tramite l'account di chi usa l'app; non serve una chiave API.
  Alla prima analisi l'app chiede il permesso di inviare foto a Claude.
- **Archivio:** l'archivio di claude.ai, in una sezione privata per ogni utente. Le foto
  vengono salvate come miniature dentro la scheda del capo.
- **Fase 0 integrata:** la sezione "Qualità AI" misura quante proposte di Claude accetti
  senza correggerle, per campo e per fonte, e applica le soglie GO / NO-GO del piano.

### Limiti del prototipo

- Lo scontorno avviene nel browser. Funziona bene con capo steso su sfondo uniforme; con
  sfondi complessi l'app ripiega su un ritaglio rettangolare.
- Dipende da claude.ai (accesso, archivio, chiamate a Claude). Un prodotto pubblico richiederà
  un backend proprio (autenticazione, database, archivio immagini, API) e una base giuridica
  GDPR per il trattamento delle foto.

### Aggiornare l'app

Il file sorgente è `app/armadio-digitale.html`. Chiedi a Claude di modificarlo e ripubblicarlo
sullo stesso indirizzo (passando l'URL qui sopra); poi fai il commit del file aggiornato.
