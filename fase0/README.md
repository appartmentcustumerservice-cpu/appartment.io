# Fase 0 - Test di fattibilità dell'armadio digitale

Prima di sviluppare l'app, questo kit risponde a tre domande con dati reali:

1. **Foto:** l'AI riconosce categoria, colore e stagione di un capo abbastanza bene da
   precompilare la scheda? Quante schede escono senza correzioni?
2. **Etichetta:** la lettura dell'etichetta (composizione, lavaggio, brand, taglia) è affidabile
   e aggiunge informazioni che la foto non dà?
3. **Inserimento:** quanto tempo costa inserire un capo con ciascuna modalità (foto, etichetta,
   manuale)?

Le tre modalità producono **lo stesso schema dati** (`schema.py`). Ogni campo registra da quale
fonte proviene (`foto_ai`, `etichetta`, `calcolato`, `manuale`). In questo modo si misura
l'accuratezza di ogni fonte separatamente.

## Prerequisiti

- Python 3.10 o superiore
- Una chiave API Anthropic (da console.anthropic.com), esportata come `ANTHROPIC_API_KEY`
- `pip install -r requirements.txt`
- Opzionale, consigliato: `pip install "rembg[cpu]"` per uno scontorno di qualità. Senza
  rembg lo script usa un metodo semplice che stima lo sfondo dai bordi della foto e funziona
  solo con uno sfondo uniforme.

## 1. Preparare il campione (circa 25 capi)

Il campione deve contenere i casi difficili, altrimenti il test risulta ottimista:

| Gruppo | Quanti | Perché |
|---|---|---|
| Capi scuri (nero, navy, grigio scuro) | 5 | È dove i colori si confondono di più |
| Capi con fantasia (righe, quadri, fiori) | 5 | Colore secondario e fantasia |
| Bianchi / panna / beige | 3 | Bilanciamento del bianco |
| Capispalla (giacche, cappotti) | 4 | Stagione e calore |
| Scarpe, borse, accessori | 3 | Categorie fuori dal tessile |
| Altri capi a scelta | 5 | Varietà |

Per **almeno 15 capi** fotografa anche l'etichetta. Includi 3 etichette sbiadite o lavate
molte volte, 3 in lingua straniera e 2 con sole sigle (es. "CO 95% EA 5%"). Inserisci
inoltre **5 capi solo a mano**, senza foto, per cronometrare la modalità manuale.

## 2. Scattare le foto

Esegui il test **due volte**, con due cartelle separate, per misurare quanto conta la qualità
dello scatto:

- **Protocollo A (ideale):** capo steso su sfondo neutro e uniforme, luce naturale diffusa,
  inquadratura intera.
- **Protocollo B (realistico):** capo appeso alla gruccia o sul letto, luce di casa,
  come lo farebbe un utente qualunque.

Se B è molto peggio di A, l'app dovrà guidare lo scatto, e questo costa frizione all'utente.

### Nomi dei file

```
input/
  capi/01.jpg            foto del capo 01
  etichette/01.jpg       etichetta del capo 01
  etichette/01__2.jpg    seconda etichetta dello stesso capo (es. brand + composizione)
  etichette/07.jpg       capo 07 inserito SOLO dall'etichetta (nessuna foto in capi/)
  manuale.csv            inserimento manuale (vedi manuale_esempio.csv)
```

Lo stesso `id` collega foto, etichette e riga manuale. In `manuale.csv` le stagioni si separano
con `;`. I valori inseriti a mano prevalgono sempre sugli altri. Sono accettati JPG, PNG e WEBP;
per le foto HEIC dell'iPhone installa `pillow-heif` oppure esporta in JPG.

## 3. Eseguire l'analisi

```bash
export ANTHROPIC_API_KEY=...
python analizza.py --input input_A --output output_A
python analizza.py --input input_B --output output_B
```

Opzioni utili:

- `--solo-locale` esegue solo scontorno e colore dai pixel, senza chiamate API e senza costi;
- `--limite 3` è una prova veloce sui primi 3 capi;
- `--modello` / `--effort` servono a confrontare i modelli (vedi "Costi").

Lo script stampa il tempo medio per chiamata, cioè l'attesa che l'utente avrà nell'app, e il
costo stimato per capo.

## 4. Valutare

1. Apri `output_A/report.html`: per ogni capo trovi foto, scontorno, etichette e i valori con la
   relativa fonte.
2. Compila `output_A/valutazione.csv`: nella colonna `corretto (S/N)` metti **S** o **N**; se è
   sbagliato, scrivi il valore giusto in `valore_corretto`. Per le righe `scontorno` valuta se il
   ritaglio è usabile nell'armadio virtuale.
3. Esegui `python punteggio.py output_A/valutazione.csv`.

### Gate di decisione

Le soglie sono **ipotesi di lavoro**, non standard di settore. Vanno riviste dopo il primo
giro.

| Campo (fonte) | Soglia | Bloccante |
|---|---|---|
| categoria (foto) | 90% | sì |
| colore primario (foto) | 85% | sì |
| stagioni (foto) | 80% | sì |
| composizione (etichetta leggibile) | 90% | sì |
| colore dai pixel, fantasia, formalità, lavaggio, scontorno | 75-85% | no |

Oltre alle soglie, conta questa metrica: **% di capi da foto che non richiedono nessuna
correzione** sui campi chiave. È il valore che determina la fatica dell'onboarding.

| Esito | Decisione |
|---|---|
| GO su A e su B | Fase 1 (MVP) con il flusso foto → conferma |
| GO su A, NO-GO su B | Fase 1, ma con guida allo scatto obbligatoria |
| Colore sotto soglia | Colore calcolato dai pixel come default, scelta rapida da palette |
| Etichetta sotto soglia | Etichetta solo per la composizione, il resto a mano |
| Categoria sotto soglia | Rivedere vocabolario e prompt prima di procedere |

## 5. Cronometrare l'inserimento

Per 5 capi per modalità, misura il tempo dall'inizio alla scheda confermata:

| Modalità | Cosa include | Tempo medio (s) |
|---|---|---|
| Foto | scatto + attesa AI + verifica/correzione | |
| Foto + etichetta | due scatti + attesa + verifica | |
| Manuale | compilazione di tutti i campi | |

Riferimento di prodotto (ipotesi): oltre 20-30 secondi a capo, un armadio da 100-150 capi
richiede circa un'ora e la maggior parte degli utenti abbandona prima di finire.

## Costi

Lo script usa `claude-opus-5-5` con effort `medium`. Un capo con foto ed etichetta richiede 2
chiamate; il costo reale viene stampato a fine esecuzione. Per un prodotto il costo per capo
moltiplicato per milioni di capi è una decisione economica: rilancia lo stesso campione con
`--modello claude-sonnet-5-5` o `--modello claude-haiku-5-5` e confronta accuratezza e costo
prima di scegliere.

Sulle richieste è attivo il fallback lato server (`fallbacks: "default"`): se il modello
rifiuta una richiesta, l'API la ripete su un modello alternativo. Si disattiva con
`--senza-fallback`.

## Privacy

Le foto vengono inviate all'API Anthropic per l'analisi. Le cartelle `input/` e `output/` sono
escluse da git. Evita foto con volti o dati personali visibili. Per la versione prodotto
servono informativa privacy e una base giuridica GDPR per il trattamento delle immagini.

## Limiti noti del kit

- La stagione dedotta dall'etichetta è un'euristica sulla composizione (`schema.py`,
  `CALORE_FIBRA`) e non vede peso e tipologia del capo: una t-shirt e una felpa possono essere
  entrambe 100% cotone. Per questo stagione e calore danno priorità alla foto; il valore da
  etichetta resta come alternativa e viene valutato a parte.
- Lo scontorno senza rembg funziona solo con sfondo uniforme.
- Il kit non verifica la ricerca online del capo: è rimandata alla Fase 3.
