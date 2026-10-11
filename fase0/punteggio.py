"""Calcola l'accuratezza da output/valutazione.csv compilato a mano e applica il gate GO / NO-GO.

Le soglie sono ipotesi di lavoro da rivedere dopo il primo giro, non standard di settore.
"""

import csv
import sys
from collections import defaultdict

# (campo, fonte) -> soglia minima di accuratezza. Sono "bloccanti" solo i campi su cui
# si reggono gli abbinamenti; gli altri sono informativi.
SOGLIE_BLOCCANTI = {
    ("categoria", "foto_ai"): 0.90,
    ("colore_primario", "foto_ai"): 0.85,
    ("stagioni", "foto_ai"): 0.80,
    ("composizione", "etichetta"): 0.90,
}
SOGLIE_INFORMATIVE = {
    ("colore_primario", "calcolato"): 0.80,
    ("fantasia", "foto_ai"): 0.85,
    ("formalita", "foto_ai"): 0.75,
    ("scontorno", "rembg"): 0.85,
    ("scontorno", "bordo"): 0.85,
    ("lavaggio", "etichetta"): 0.85,
    ("stagioni", "etichetta"): 0.80,
}
CAMPIONE_MINIMO = 15  # sotto questa numerosità il risultato non è affidabile
CAMPI_ZERO_CORREZIONI = ["categoria", "colore_primario", "fantasia", "stagioni", "formalita"]


def main(percorso="output/valutazione.csv"):
    conteggi = defaultdict(lambda: [0, 0])  # (campo, fonte) -> [corretti, valutati]
    errori_per_capo = defaultdict(lambda: {"valutati": 0, "errati": 0})
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        for riga in csv.DictReader(f):
            giudizio = (riga["corretto (S/N)"] or "").strip().upper()
            if giudizio not in ("S", "N"):
                continue
            chiave = (riga["campo"], riga["fonte"])
            conteggi[chiave][1] += 1
            conteggi[chiave][0] += giudizio == "S"
            if riga["fonte"] == "foto_ai" and riga["campo"] in CAMPI_ZERO_CORREZIONI:
                errori_per_capo[riga["id"]]["valutati"] += 1
                errori_per_capo[riga["id"]]["errati"] += giudizio == "N"

    if not conteggi:
        sys.exit("Nessuna riga valutata: compila la colonna 'corretto (S/N)' con S o N.")

    print(f"{'campo':<18}{'fonte':<11}{'accuratezza':>12}{'n':>5}  soglia  esito")
    esito_gate = True
    for chiave in sorted(conteggi):
        corretti, totale = conteggi[chiave]
        acc = corretti / totale
        soglia = SOGLIE_BLOCCANTI.get(chiave) or SOGLIE_INFORMATIVE.get(chiave)
        bloccante = chiave in SOGLIE_BLOCCANTI
        if soglia is None:
            esito = ""
        elif acc >= soglia:
            esito = "ok"
        else:
            esito = "SOTTO SOGLIA" + (" (bloccante)" if bloccante else "")
            esito_gate &= not bloccante
        if totale < CAMPIONE_MINIMO and soglia is not None:
            esito += f" [campione < {CAMPIONE_MINIMO}]"
        print(f"{chiave[0]:<18}{chiave[1]:<11}{acc:>11.0%}{totale:>5}  "
              f"{(f'{soglia:.0%}' if soglia else '-'):>6}  {esito}")

    mancanti = [k for k in SOGLIE_BLOCCANTI if k not in conteggi]
    capi = [c for c in errori_per_capo.values() if c["valutati"]]
    if capi:
        perfetti = sum(c["errati"] == 0 for c in capi) / len(capi)
        print(f"\nCapi da foto senza nessuna correzione sui campi chiave: {perfetti:.0%} ({len(capi)} capi)")
    if mancanti:
        print("Campi bloccanti non valutati: " + ", ".join(f"{c}/{f}" for c, f in mancanti))
    print("\nGATE: " + ("GO" if esito_gate and not mancanti else "NO-GO / incompleto"))


if __name__ == "__main__":
    main(*sys.argv[1:])
