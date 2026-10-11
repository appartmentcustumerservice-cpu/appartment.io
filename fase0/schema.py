"""Schema dati unico del capo e vocabolari controllati.

Le tre modalità di inserimento (foto, etichetta, manuale) producono valori per
gli stessi campi; `unisci()` li combina con una priorità esplicita e registra la
fonte di ogni campo, così la valutazione può misurare l'accuratezza per fonte.
"""

CATEGORIE = [
    "t-shirt/top", "camicia", "maglieria", "felpa", "pantaloni", "jeans",
    "gonna", "shorts", "abito", "tuta/jumpsuit", "giacca", "cappotto/giubbotto",
    "scarpe", "borsa", "accessorio", "altro",
]

# Ruolo del capo nella composizione di un outfit (derivato, non chiesto al modello).
MACRO_CATEGORIA = {
    "t-shirt/top": "sopra", "camicia": "sopra", "maglieria": "sopra", "felpa": "sopra",
    "pantaloni": "sotto", "jeans": "sotto", "gonna": "sotto", "shorts": "sotto",
    "abito": "intero", "tuta/jumpsuit": "intero",
    "giacca": "capospalla", "cappotto/giubbotto": "capospalla",
    "scarpe": "scarpe", "borsa": "accessori", "accessorio": "accessori", "altro": "altro",
}

# Palette nominale: il colore calcolato dai pixel viene ricondotto al nome più vicino.
COLORI = {
    "nero": "#1a1a1a", "bianco": "#f5f5f5", "panna": "#efe6d2",
    "grigio chiaro": "#b8b8b8", "grigio scuro": "#555555", "beige": "#d6c3a0",
    "cammello": "#b5895a", "marrone": "#6b4423", "blu navy": "#1f2a44",
    "blu": "#2f5bb7", "azzurro": "#8fbbe0", "verde oliva": "#6b6b2f",
    "verde": "#2e7d4f", "verde salvia": "#9cae8f", "rosso": "#c0282d",
    "bordeaux": "#6d1a2a", "rosa": "#e8a3b5", "arancione": "#e07b2a",
    "giallo": "#e8c547", "viola": "#6a3d8f", "oro": "#c9a443", "argento": "#c0c0c8",
}

FANTASIE = [
    "tinta unita", "righe", "quadri", "pois", "floreale", "animalier",
    "geometrica", "camouflage", "stampa/grafica", "altro",
]

MATERIALI = [
    "cotone", "lino", "lana", "cachemire", "seta", "denim", "pelle", "ecopelle",
    "sintetico", "velluto", "maglia", "misto", "non determinabile",
]

STAGIONI = ["primavera", "estate", "autunno", "inverno"]
CALORE = ["leggero", "medio", "pesante"]
FORMALITA = [1, 2, 3, 4, 5]  # 1 = sportivo/casa, 5 = cerimonia

FIBRE = [
    "cotone", "lino", "lana", "cachemire", "alpaca", "mohair", "seta", "viscosa",
    "modal", "lyocell", "poliestere", "poliammide", "elastan", "acrilico",
    "pelle", "piuma", "altro",
]


def _nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


# Output strutturato richiesto al modello per la foto del capo.
SCHEMA_FOTO = {
    "type": "object",
    "properties": {
        "capo_singolo": {"type": "boolean"},
        "categoria": {"type": "string", "enum": CATEGORIE},
        "sottocategoria": {"type": "string"},
        "colore_primario": {"type": "string", "enum": list(COLORI)},
        "colore_secondario": _nullable({"type": "string", "enum": list(COLORI)}),
        "fantasia": {"type": "string", "enum": FANTASIE},
        "materiale_stimato": {"type": "string", "enum": MATERIALI},
        "stagioni": {"type": "array", "items": {"type": "string", "enum": STAGIONI}},
        "calore": {"type": "string", "enum": CALORE},
        "formalita": {"type": "integer", "enum": FORMALITA},
        "brand_visibile": _nullable({"type": "string"}),
        "campi_incerti": {"type": "array", "items": {"type": "string"}},
        "descrizione": {"type": "string"},
    },
    "required": [
        "capo_singolo", "categoria", "sottocategoria", "colore_primario",
        "colore_secondario", "fantasia", "materiale_stimato", "stagioni", "calore",
        "formalita", "brand_visibile", "campi_incerti", "descrizione",
    ],
    "additionalProperties": False,
}

# Output strutturato richiesto al modello per la foto dell'etichetta.
SCHEMA_ETICHETTA = {
    "type": "object",
    "properties": {
        "leggibile": {"type": "boolean"},
        "testo_letto": {"type": "string"},
        "brand": _nullable({"type": "string"}),
        "taglia": _nullable({"type": "string"}),
        "codice_articolo": _nullable({"type": "string"}),
        "paese_produzione": _nullable({"type": "string"}),
        "composizione": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fibra": {"type": "string", "enum": FIBRE},
                    "percentuale": {"type": "number"},
                    "parte": {"type": "string"},
                },
                "required": ["fibra", "percentuale", "parte"],
                "additionalProperties": False,
            },
        },
        "lavaggio": {
            "type": "string",
            "enum": ["lavatrice", "a mano", "non lavare", "non determinabile"],
        },
        "temperatura_max_c": _nullable({"type": "integer"}),
        "asciugatrice": _nullable({"type": "boolean"}),
        "lavaggio_a_secco": _nullable({"type": "boolean"}),
        "campi_incerti": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "leggibile", "testo_letto", "brand", "taglia", "codice_articolo",
        "paese_produzione", "composizione", "lavaggio", "temperatura_max_c",
        "asciugatrice", "lavaggio_a_secco", "campi_incerti",
    ],
    "additionalProperties": False,
}

# Indice di calore per fibra (euristica dichiarata, da tarare): 0 = fresco, 3 = caldo.
CALORE_FIBRA = {
    "lino": 0.0, "seta": 1.0, "viscosa": 1.0, "modal": 1.0, "lyocell": 1.0,
    "cotone": 1.5, "poliestere": 1.5, "poliammide": 1.5, "elastan": None,
    "acrilico": 2.0, "pelle": 2.5, "lana": 3.0, "cachemire": 3.0, "alpaca": 3.0,
    "mohair": 3.0, "piuma": 3.0, "altro": None,
}

# Campi del record finale e priorità delle fonti (la prima disponibile vince).
PRIORITA = ["manuale", "etichetta", "calcolato", "foto_ai"]
# Stagione e calore dipendono da tipologia e peso del capo, che la foto vede e la
# composizione no (t-shirt e felpa possono essere entrambe 100% cotone): la stima
# dall'etichetta resta come alternativa e viene valutata separatamente.
PRIORITA_PER_CAMPO = {
    "stagioni": ["manuale", "foto_ai", "etichetta"],
    "calore": ["manuale", "foto_ai", "etichetta"],
}

CAMPI_VALUTATI = [
    "categoria", "colore_primario", "colore_secondario", "fantasia", "materiale",
    "stagioni", "calore", "formalita", "brand", "taglia", "composizione",
    "lavaggio",
]


def senza_fodera(composizione):
    """La fodera non determina materiale né calore; imbottiture e tessuto esterno sì."""
    return [c for c in composizione if "fodera" not in c["parte"].lower()] or composizione


def stagioni_da_composizione(composizione):
    """Deduce calore e stagioni dalla composizione dell'etichetta (parte principale)."""
    righe = senza_fodera(composizione)
    pesi = [(CALORE_FIBRA.get(c["fibra"]), c["percentuale"]) for c in righe]
    pesi = [(v, p) for v, p in pesi if v is not None and p > 0]
    if not pesi:
        return None, None
    indice = sum(v * p for v, p in pesi) / sum(p for _, p in pesi)
    if indice < 0.8:
        return "leggero", ["primavera", "estate"]
    if indice <= 1.6:
        return "medio", ["primavera", "estate", "autunno"]
    if indice < 2.4:
        return "medio", ["primavera", "autunno", "inverno"]
    return "pesante", ["autunno", "inverno"]


def unisci(id_capo, foto=None, colore_calcolato=None, etichette=(), manuale=None):
    """Combina i contributi delle tre modalità in un unico record con fonte per campo."""
    candidati = {}  # campo -> {fonte: valore}

    def proponi(campo, fonte, valore):
        if valore in (None, "", []):
            return
        candidati.setdefault(campo, {})[fonte] = valore

    if foto:
        proponi("categoria", "foto_ai", foto["categoria"])
        proponi("sottocategoria", "foto_ai", foto["sottocategoria"])
        proponi("colore_primario", "foto_ai", foto["colore_primario"])
        proponi("colore_secondario", "foto_ai", foto["colore_secondario"])
        proponi("fantasia", "foto_ai", foto["fantasia"])
        if foto["materiale_stimato"] != "non determinabile":
            proponi("materiale", "foto_ai", foto["materiale_stimato"])
        proponi("stagioni", "foto_ai", foto["stagioni"])
        proponi("calore", "foto_ai", foto["calore"])
        proponi("formalita", "foto_ai", foto["formalita"])
        proponi("brand", "foto_ai", foto["brand_visibile"])

    if colore_calcolato:
        proponi("colore_hex", "calcolato", colore_calcolato["primario_hex"])

    for et in etichette:
        if not et.get("leggibile"):
            continue
        proponi("brand", "etichetta", et["brand"])
        proponi("taglia", "etichetta", et["taglia"])
        proponi("codice_articolo", "etichetta", et["codice_articolo"])
        proponi("lavaggio", "etichetta", None if et["lavaggio"] == "non determinabile" else et["lavaggio"])
        proponi("temperatura_max_c", "etichetta", et["temperatura_max_c"])
        if et["composizione"]:
            proponi("composizione", "etichetta", et["composizione"])
            dominante = max(senza_fodera(et["composizione"]), key=lambda c: c["percentuale"])
            proponi("materiale", "etichetta", dominante["fibra"])
            calore, stagioni = stagioni_da_composizione(et["composizione"])
            proponi("calore", "etichetta", calore)
            proponi("stagioni", "etichetta", stagioni)

    for campo, valore in (manuale or {}).items():
        proponi(campo, "manuale", valore)

    record = {"id": id_capo, "fonti": {}, "alternative": {}}
    for campo, per_fonte in candidati.items():
        fonte = next(f for f in PRIORITA_PER_CAMPO.get(campo, PRIORITA) if f in per_fonte)
        record[campo] = per_fonte[fonte]
        record["fonti"][campo] = fonte
        altre = {f: v for f, v in per_fonte.items() if f != fonte}
        if altre:
            record["alternative"][campo] = altre
    if "categoria" in record:
        record["macro_categoria"] = MACRO_CATEGORIA.get(record["categoria"], "altro")
    return record
