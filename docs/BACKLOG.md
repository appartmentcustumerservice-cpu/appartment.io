# Backlog di implementazione

Le voci sono in ordine di priorità. Ogni voce indica la fattibilità separatamente per il
prototipo attuale (Artifact su claude.ai) e per la versione prodotto (app con backend proprio).

| ID | Funzione | Prototipo | Prodotto | Stato |
|---|---|---|---|---|
| B1 | Outfit del giorno in base al meteo della tua posizione | Solo con meteo inserito a mano | Sì | Da fare |
| B2 | Backend prodotto: login, database, archivio foto, API | - | Prerequisito di B1 automatico | Da fare |
| B3 | Ricerca online del capo da foto o codice articolo | No | Da valutare (Fase 3) | Rimandato |

---

## B1 - Outfit del giorno con meteo e posizione

### Obiettivo

L'utente concede l'accesso alla posizione. L'app legge le previsioni del giorno per quel luogo
e propone gli outfit adatti a temperatura, pioggia e vento, scegliendo dai capi del suo
armadio.

### Fattibilità

| Ambito | Esito | Motivo |
|---|---|---|
| Prototipo su claude.ai | **No in automatico** | La pagina gira in una cornice protetta: l'accesso alla posizione è negato e le richieste verso servizi esterni (incluso un servizio meteo) sono bloccate. |
| Prototipo, ripiego | **Sì** | Meteo inserito a mano in 2-3 tocchi (fascia di temperatura, pioggia sì/no, vento sì/no). La logica di abbinamento è la stessa che userà la versione automatica. |
| Prodotto (web app o app con backend) | **Sì** | Il browser chiede il permesso di posizione (solo su HTTPS) e il backend interroga un servizio meteo. |

### Flusso utente (prodotto)

1. Nella schermata Abbinamenti compare la scheda "Outfit di oggi".
2. Al primo uso un pulsante "Usa la mia posizione" spiega cosa viene usato e perché. Il
   permesso si chiede solo dopo il tocco, mai all'apertura dell'app.
3. Se l'utente rifiuta: ricerca della città oppure meteo inserito a mano. La funzione resta
   utilizzabile.
4. L'app mostra il meteo del giorno (minima e massima, temperatura percepita, probabilità di
   pioggia, vento) e 3 outfit coerenti, con il motivo della scelta ("12-19 °C, pioggia nel
   pomeriggio: strato intermedio e capospalla impermeabile").

### Regole di abbinamento (ipotesi da tarare con l'uso)

Le regole usano la temperatura **percepita** nelle ore in cui si sta fuori (default 8-20).

| Percepita | Capi ammessi | Capospalla |
|---|---|---|
| 26 °C o più | calore leggero | no |
| 18-25 °C | leggero o medio | facoltativo, leggero |
| 10-17 °C | medio | consigliato |
| sotto 10 °C | medio o pesante | obbligatorio, pesante |

Regole aggiuntive:

- probabilità di pioggia **≥ 50%**: capospalla impermeabile e scarpe adatte all'acqua;
  escluse le scarpe in camoscio o tela chiara;
- vento forte (soglia da definire, indicativamente oltre 30 km/h): capospalla con chiusura,
  niente gonne leggere;
- differenza tra minima e massima **≥ 8 °C**: si consiglia di vestirsi a strati (capo sopra
  più capospalla rimovibile).

Le soglie sono stime iniziali, non standard: vanno verificate con il feedback degli utenti
(pollice su/giù sull'outfit proposto).

### Modifiche allo schema dati

Lo schema del capo ha già `calore` (leggero / medio / pesante) e `stagioni`. Vanno aggiunti:

- `impermeabile` (sì/no), proposto da Claude dalla foto e dall'etichetta;
- `adatto_pioggia` per le scarpe (sì/no);
- facoltativo, `strato` (base / intermedio / esterno) per suggerire la vestizione a strati.

### Servizio meteo

| Opzione | Note |
|---|---|
| Open-Meteo | Nessuna chiave per il piano gratuito, ma **solo uso non commerciale** e limiti di 10.000 chiamate al giorno. Per un prodotto serve la licenza commerciale a pagamento; i prezzi vanno chiesti direttamente. Dati in licenza CC BY 4.0, con obbligo di attribuzione. |
| Altri fornitori (es. OpenWeather, Tomorrow.io, Meteoblue) | Da confrontare su prezzo per chiamata, copertura italiana e termini d'uso. |

Per contenere costi e chiamate: una sola richiesta per utente per fascia oraria, con cache
lato server per cella geografica (coordinate arrotondate).

### Privacy (GDPR)

- La posizione è un dato personale: base giuridica il consenso, richiesto con un'azione
  esplicita e revocabile dalle impostazioni.
- Minimizzazione: coordinate arrotondate a circa 1 km (due decimali) prima di uscire dal
  dispositivo; nessuno storico delle posizioni salvato.
- L'informativa privacy deve citare il fornitore meteo come destinatario delle coordinate.

### Criteri di accettazione

- Con il permesso concesso, la scheda "Outfit di oggi" mostra il meteo della posizione
  attuale e almeno un outfit entro 3 secondi su rete mobile.
- Con il permesso negato, la funzione resta usabile con città o meteo inserito a mano.
- Ogni outfit rispetta le regole della tabella e mostra il motivo della scelta.
- Se nell'armadio mancano capi adatti (es. nessun capospalla impermeabile con pioggia), l'app
  lo dice e indica che cosa manca, invece di proporre un outfit incoerente.
- Le coordinate esatte non vengono salvate da nessuna parte.

### Dipendenze

- B2 (backend prodotto) per la versione automatica.
- Campi `impermeabile` / `adatto_pioggia` nello schema e nel prompt di Claude.
