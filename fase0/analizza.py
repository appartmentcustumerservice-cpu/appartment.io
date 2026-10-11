"""Fase 0 - test di fattibilità dell'armadio digitale.

Per ogni capo combina fino a tre modalità di inserimento:
  - foto del capo     -> scontorno + colore calcolato dai pixel + attributi via Claude
  - foto etichetta/e  -> composizione, lavaggio, brand, taglia via Claude (+ stagione dedotta)
  - inserimento manuale (manuale.csv) -> sovrascrive gli altri valori

Produce in output/: capi.json, valutazione.csv (da compilare a mano), report.html.

Uso:
  python analizza.py                 # analisi completa (richiede ANTHROPIC_API_KEY)
  python analizza.py --solo-locale   # solo scontorno e colore, senza chiamate API
"""

import argparse
import csv
import html
import json
import re
import sys
import time
from pathlib import Path

import anthropic

import immagini
from schema import (
    CAMPI_VALUTATI, COLORI, SCHEMA_ETICHETTA, SCHEMA_FOTO, unisci,
)

ESTENSIONI = {".jpg", ".jpeg", ".png", ".webp", ".heic"}

# Prezzi per milione di token (input, output) usati solo per la stima dei costi.
PREZZI_MTOK = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

SYSTEM_FOTO = """Sei il catalogatore di un'app di armadio digitale. Ricevi la foto di un capo di \
abbigliamento e compili la sua scheda. I valori servono a creare abbinamenti per colore, \
tipologia e stagione, quindi conta la correttezza più della completezza.

Regole:
- Descrivi solo il capo principale. Se nella foto ci sono più capi o una persona che ne indossa \
più di uno, imposta capo_singolo a false e descrivi quello più in evidenza.
- colore_primario è il colore che copre la superficie maggiore del capo, mai lo sfondo. Tieni \
conto che luce artificiale e ombre alterano i colori. colore_secondario solo se occupa una parte \
rilevante del capo (fantasie, inserti), altrimenti null.
- materiale_stimato: indicalo solo se riconoscibile con ragionevole sicurezza dalla trama, \
altrimenti "non determinabile". Il denim è un materiale, non una fantasia.
- stagioni: tutte quelle in cui il capo si indossa normalmente in un clima temperato.
- formalita: 1 sport/casa, 2 casual, 3 smart casual, 4 business/elegante, 5 cerimonia.
- brand_visibile: solo se un logo o una scritta del brand è leggibile nella foto, altrimenti null.
- campi_incerti: i nomi dei campi su cui la foto non ti permette una scelta sicura.
- descrizione: una frase breve e concreta (es. "camicia oxford azzurra a maniche lunghe")."""

SYSTEM_ETICHETTA = """Sei il catalogatore di un'app di armadio digitale. Ricevi la foto di \
un'etichetta interna di un capo (etichetta del brand, di composizione o di manutenzione) e ne \
estrai i dati.

Regole:
- testo_letto: trascrivi il testo leggibile, anche se in più lingue.
- composizione: una voce per fibra con la percentuale; in "parte" indica a cosa si riferisce \
("principale" se non specificato, oppure "fodera", "imbottitura", "inserti", ...). Riconduci i \
nomi in qualunque lingua o sigla alla voce dell'elenco (wool/laine/WO = lana, CO = cotone, \
PES/polyester = poliestere, PA/nylon = poliammide, EA/EL/elastane/spandex = elastan, \
CV/viscose = viscosa, LI/linen = lino, WS/cashmere = cachemire, down/duvet/feather/\
piumino = piuma).
- Simboli di manutenzione (ISO 3758): vasca con numero = temperatura massima; mano nella vasca = \
lavaggio a mano; vasca barrata = non lavare; quadrato con cerchio = asciugatrice (barrato = no); \
cerchio semplice = lavaggio a secco (barrato = no).
- Ogni dato assente o illeggibile va a null (o lista vuota). Non dedurre il brand o la taglia \
da elementi che non sono scritti sull'etichetta.
- leggibile = false se l'etichetta è troppo sfocata, tagliata o sbiadita per leggerne i dati.
- campi_incerti: i nomi dei campi letti con incertezza."""


def trova_file(cartella):
    if not cartella.exists():
        return []
    return sorted(p for p in cartella.iterdir() if p.suffix.lower() in ESTENSIONI)


def id_etichetta(percorso):
    # "05.jpg" e "05__2.jpg" appartengono entrambi al capo "05".
    return re.sub(r"__\d+$", "", percorso.stem)


def leggi_manuale(percorso):
    if not percorso.exists():
        return {}
    dati = {}
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        for riga in csv.DictReader(f):
            id_capo = (riga.pop("id", "") or "").strip()
            if not id_capo:
                continue
            valori = {}
            for campo, valore in riga.items():
                valore = (valore or "").strip()
                if not valore:
                    continue
                if campo == "stagioni":
                    valori[campo] = [s.strip() for s in valore.split(";") if s.strip()]
                elif campo == "formalita":
                    valori[campo] = int(valore)
                else:
                    valori[campo] = valore
            dati[id_capo] = valori
    return dati


class Estrattore:
    def __init__(self, modello, effort, fallback):
        self.client = anthropic.Anthropic()
        self.modello = modello
        self.effort = effort
        self.fallback = fallback
        self.token_in = 0
        self.token_out = 0

    def chiedi(self, system, img_b64, istruzione, schema):
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if self.fallback else {}
        inizio = time.monotonic()
        risposta = self.client.beta.messages.create(
            model=self.modello,
            max_tokens=16000,
            system=system,
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                    {"type": "text", "text": istruzione},
                ],
            }],
            **extra,
        )
        secondi = time.monotonic() - inizio
        self.token_in += risposta.usage.input_tokens
        self.token_out += risposta.usage.output_tokens
        if risposta.stop_reason == "refusal":
            raise RuntimeError(f"richiesta rifiutata dal modello ({risposta.stop_details})")
        if risposta.stop_reason == "max_tokens":
            raise RuntimeError("risposta troncata (max_tokens)")
        testo = next(b.text for b in risposta.content if b.type == "text")
        return json.loads(testo), round(secondi, 1), risposta.model

    def costo_stimato(self):
        prezzo_in, prezzo_out = PREZZI_MTOK.get(self.modello, (0, 0))
        return (self.token_in * prezzo_in + self.token_out * prezzo_out) / 1_000_000


def analizza(args):
    cartella = Path(args.input)
    uscita = Path(args.output)
    uscita.mkdir(parents=True, exist_ok=True)

    foto_capi = {p.stem: p for p in trova_file(cartella / "capi")}
    foto_etichette = {}
    for p in trova_file(cartella / "etichette"):
        foto_etichette.setdefault(id_etichetta(p), []).append(p)
    manuale = leggi_manuale(cartella / "manuale.csv")

    ids = sorted(set(foto_capi) | set(foto_etichette) | set(manuale))
    if args.limite:
        ids = ids[: args.limite]
    if not ids:
        sys.exit(f"Nessun capo trovato in {cartella}/capi, {cartella}/etichette o {cartella}/manuale.csv")

    estrattore = None if args.solo_locale else Estrattore(args.modello, args.effort, not args.senza_fallback)
    capi, schede_report = [], []

    for n, id_capo in enumerate(ids, 1):
        print(f"[{n}/{len(ids)}] {id_capo}", flush=True)
        voce = {"id": id_capo, "errori": [], "tempi_s": {}}
        foto_ai = colore = None
        etichette_ai = []

        if id_capo in foto_capi:
            img = immagini.carica(foto_capi[id_capo])
            ritaglio, metodo = immagini.scontorna(img, args.scontorno)
            colore = immagini.colori_dominanti(ritaglio)
            voce["scontorno"] = metodo
            voce["colore_calcolato"] = colore
            voce["img"] = immagini.png_base64(img.convert("RGBA"))
            voce["img_scontornata"] = immagini.png_base64(ritaglio)
            if estrattore:
                try:
                    foto_ai, voce["tempi_s"]["foto"], voce["modello"] = estrattore.chiedi(
                        SYSTEM_FOTO, immagini.jpeg_base64(img), "Compila la scheda di questo capo.", SCHEMA_FOTO)
                except (anthropic.APIError, RuntimeError, json.JSONDecodeError) as e:
                    voce["errori"].append(f"foto: {e}")
            voce["foto_ai"] = foto_ai

        for i, percorso in enumerate(foto_etichette.get(id_capo, [])):
            voce.setdefault("img_etichette", []).append(immagini.png_base64(immagini.carica(percorso).convert("RGBA")))
            if not estrattore:
                continue
            try:
                dati, voce["tempi_s"][f"etichetta_{i + 1}"], _ = estrattore.chiedi(
                    SYSTEM_ETICHETTA, immagini.jpeg_base64(immagini.carica(percorso)),
                    "Estrai i dati da questa etichetta.", SCHEMA_ETICHETTA)
                etichette_ai.append(dati)
            except (anthropic.APIError, RuntimeError, json.JSONDecodeError) as e:
                voce["errori"].append(f"etichetta {percorso.name}: {e}")
        voce["etichette_ai"] = etichette_ai

        record = unisci(id_capo, foto=foto_ai, colore_calcolato=colore,
                        etichette=etichette_ai, manuale=manuale.get(id_capo))
        voce["record"] = record
        for errore in voce["errori"]:
            print(f"    ! {errore}", flush=True)
        capi.append({k: v for k, v in voce.items() if not k.startswith("img")})
        schede_report.append(voce)

    (uscita / "capi.json").write_text(json.dumps(capi, ensure_ascii=False, indent=2), encoding="utf-8")
    scrivi_valutazione(capi, uscita / "valutazione.csv")
    (uscita / "report.html").write_text(genera_report(schede_report), encoding="utf-8")

    print(f"\nCapi elaborati: {len(capi)}  -> {uscita}/report.html, {uscita}/valutazione.csv")
    if estrattore:
        chiamate = [t for c in capi for t in c["tempi_s"].values()]
        if chiamate:
            print(f"Tempo medio per chiamata: {sum(chiamate) / len(chiamate):.1f}s (max {max(chiamate):.1f}s)")
        print(f"Token: {estrattore.token_in} in / {estrattore.token_out} out  "
              f"- costo stimato {estrattore.costo_stimato():.3f} USD "
              f"({estrattore.costo_stimato() / max(1, len(capi)):.4f} USD/capo)")


def _testo(valore):
    if valore is None:
        return ""
    if isinstance(valore, list):
        if valore and isinstance(valore[0], dict):
            return "; ".join(f"{c['percentuale']:g}% {c['fibra']}" + (f" ({c['parte']})" if c["parte"] else "") for c in valore)
        return ";".join(str(v) for v in valore)
    return str(valore)


def scrivi_valutazione(capi, percorso):
    """Una riga per (capo, campo, fonte): l'accuratezza si misura separatamente per fonte."""
    with open(percorso, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "campo", "fonte", "valore", "corretto (S/N)", "valore_corretto", "note"])
        for c in capi:
            r = c["record"]
            if "scontorno" in c:
                w.writerow([c["id"], "scontorno", c["scontorno"], "ritaglio del capo", "", "", ""])
            if c.get("colore_calcolato"):
                w.writerow([c["id"], "colore_primario", "calcolato", c["colore_calcolato"]["primario"], "", "", ""])
            for campo in CAMPI_VALUTATI:
                if campo not in r:
                    continue
                fonte = r["fonti"][campo]
                if fonte != "manuale":
                    w.writerow([c["id"], campo, fonte, _testo(r[campo]), "", "", ""])
                for altra_fonte, valore in r["alternative"].get(campo, {}).items():
                    if altra_fonte != "manuale":
                        w.writerow([c["id"], campo, altra_fonte, _testo(valore), "", "", ""])


def genera_report(schede):
    def badge(fonte):
        return f'<span class="b b-{fonte}">{fonte}</span>'

    def swatch(nome):
        return f'<i class="sw" style="background:{COLORI.get(nome, "#fff")}"></i>' if nome in COLORI else ""

    carte = []
    for s in schede:
        r = s["record"]
        righe = []
        for campo in ["categoria", "sottocategoria", "macro_categoria", "colore_primario", "colore_secondario",
                      "fantasia", "materiale", "composizione", "stagioni", "calore", "formalita", "brand",
                      "taglia", "codice_articolo", "lavaggio", "temperatura_max_c"]:
            if campo not in r:
                continue
            valore = r[campo]
            extra = swatch(valore) if campo.startswith("colore") else ""
            alternative = "".join(
                f'<div class="alt">{badge(f)} {html.escape(_testo(v))}</div>'
                for f, v in r["alternative"].get(campo, {}).items())
            righe.append(f"<tr><th>{campo}</th><td>{extra}{html.escape(_testo(valore))} "
                         f"{badge(r['fonti'].get(campo, 'derivato'))}{alternative}</td></tr>")
        col = s.get("colore_calcolato")
        if col:
            cluster = "".join(f'<i class="sw" title="{c["nome"]} {c["quota"]:.0%}" style="background:{c["hex"]}"></i>'
                              for c in col["cluster"])
            righe.append(f"<tr><th>colore dai pixel</th><td>{cluster} {col['primario']} "
                         f"<small>({col['primario_hex']}, capo = {col['copertura_capo']:.0%} della foto)</small></td></tr>")
        foto_ai = s.get("foto_ai") or {}
        if foto_ai.get("campi_incerti"):
            righe.append(f"<tr><th>incerti (AI)</th><td>{html.escape(', '.join(foto_ai['campi_incerti']))}</td></tr>")
        if foto_ai and not foto_ai.get("capo_singolo", True):
            righe.append('<tr><th>attenzione</th><td>più capi nella foto</td></tr>')
        for e in s["errori"]:
            righe.append(f'<tr class="err"><th>errore</th><td>{html.escape(e)}</td></tr>')
        immagini_html = ""
        if s.get("img"):
            immagini_html += f'<img src="data:image/png;base64,{s["img"]}" alt="foto">'
            immagini_html += f'<img class="cut" src="data:image/png;base64,{s["img_scontornata"]}" alt="scontorno {s["scontorno"]}">'
        for e in s.get("img_etichette", []):
            immagini_html += f'<img src="data:image/png;base64,{e}" alt="etichetta">'
        titolo = html.escape(foto_ai.get("descrizione") or r.get("sottocategoria") or r.get("categoria") or "")
        tempi = ", ".join(f"{k} {v}s" for k, v in s["tempi_s"].items())
        carte.append(f"""<section><h2>{html.escape(s['id'])} <small>{titolo}</small></h2>
<div class="imgs">{immagini_html}</div><table>{''.join(righe)}</table>
<p class="meta">{html.escape(tempi)}{' · scontorno: ' + s['scontorno'] if s.get('scontorno') else ''}</p></section>""")

    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Fase 0 - report</title>
<style>
body{{font:14px/1.45 system-ui,sans-serif;margin:0;padding:16px;background:#f6f5f2;color:#1d1d1f}}
h1{{font-size:20px}} section{{background:#fff;border-radius:10px;padding:14px;margin:0 0 14px;box-shadow:0 1px 3px #0001}}
h2{{font-size:16px;margin:0 0 8px}} h2 small{{font-weight:400;color:#666}}
.imgs{{display:flex;gap:8px;overflow-x:auto}} .imgs img{{height:180px;border-radius:6px;background:#eee}}
.imgs img.cut{{background:repeating-conic-gradient(#ddd 0 25%,#fff 0 50%) 0/16px 16px}}
table{{border-collapse:collapse;margin-top:8px;width:100%}} th{{text-align:left;color:#666;font-weight:500;width:150px;vertical-align:top;padding:3px 8px 3px 0}}
td{{padding:3px 0}} .sw{{display:inline-block;width:14px;height:14px;border-radius:3px;border:1px solid #0002;margin-right:4px;vertical-align:-2px}}
.b{{font-size:11px;padding:1px 6px;border-radius:8px;margin-left:4px;background:#eee}}
.b-foto_ai{{background:#e3ecff}} .b-etichetta{{background:#e6f5e6}} .b-manuale{{background:#fff1d6}} .b-calcolato{{background:#f1e6ff}}
.alt{{color:#666;font-size:12px}} .err td{{color:#b00020}} .meta{{color:#888;font-size:12px;margin:6px 0 0}}
</style></head><body><h1>Fase 0 - armadio digitale: {len(schede)} capi</h1>
<p>Confronta ogni valore con il capo reale e compila <code>output/valutazione.csv</code>
(colonna <i>corretto</i> = S/N), poi esegui <code>python punteggio.py</code>.</p>
{''.join(carte)}</body></html>"""


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="input")
    p.add_argument("--output", default="output")
    p.add_argument("--modello", default="claude-opus-5-5")
    p.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--scontorno", default="auto", choices=["auto", "rembg", "bordo"])
    p.add_argument("--senza-fallback", action="store_true", help="non usare il fallback lato server sui rifiuti")
    p.add_argument("--solo-locale", action="store_true", help="niente chiamate API: solo scontorno e colore")
    p.add_argument("--limite", type=int, default=0, help="elabora solo i primi N capi")
    analizza(p.parse_args())


if __name__ == "__main__":
    main()
