"""Caricamento foto, scontorno ed estrazione del colore dominante dai pixel."""

import base64
import io

import numpy as np
from PIL import Image, ImageOps

from schema import COLORI

try:  # foto HEIC da iPhone, se il pacchetto è installato
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

LATO_MAX_API = 1568  # oltre questa dimensione l'API ridimensiona comunque


def carica(percorso):
    img = Image.open(percorso)
    return ImageOps.exif_transpose(img).convert("RGB")


def jpeg_base64(img, lato_max=LATO_MAX_API, qualita=88):
    img = img.copy()
    img.thumbnail((lato_max, lato_max))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=qualita)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def png_base64(img, lato_max=480):
    img = img.copy()
    img.thumbnail((lato_max, lato_max))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def scontorna(img, metodo="auto"):
    """Restituisce (immagine RGBA, metodo usato).

    rembg: modello di segmentazione (qualità alta, scarica il modello al primo uso).
    bordo: stima lo sfondo dai bordi della foto; funziona solo con sfondo uniforme.
    """
    if metodo in ("auto", "rembg"):
        try:
            from rembg import remove

            return remove(img).convert("RGBA"), "rembg"
        except Exception:
            if metodo == "rembg":
                raise
    return _scontorna_bordo(img), "bordo"


def _scontorna_bordo(img):
    piccola = img.copy()
    piccola.thumbnail((800, 800))
    arr = np.asarray(piccola, dtype=np.float32)
    h, w, _ = arr.shape
    b = max(2, int(min(h, w) * 0.04))
    bordo = np.concatenate([
        arr[:b].reshape(-1, 3), arr[-b:].reshape(-1, 3),
        arr[:, :b].reshape(-1, 3), arr[:, -b:].reshape(-1, 3),
    ])
    sfondo_lab = _rgb_a_lab(np.median(bordo, axis=0)[None, :])[0]
    dist = np.linalg.norm(_rgb_a_lab(arr.reshape(-1, 3)) - sfondo_lab, axis=1).reshape(h, w)
    rumore = np.linalg.norm(_rgb_a_lab(bordo) - sfondo_lab, axis=1)
    soglia = max(12.0, float(np.percentile(rumore, 98)) * 1.2)
    maschera = (dist > soglia).astype(np.uint8) * 255
    rgba = np.dstack([arr.astype(np.uint8), maschera])
    out = Image.fromarray(rgba, "RGBA")
    return out.resize(img.size, Image.NEAREST) if out.size != img.size else out


def _rgb_a_lab(rgb):
    """sRGB 0-255 (N,3) -> CIELAB D65 (N,3)."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], axis=1)


def _hex(rgb):
    return "#" + "".join(f"{int(round(v)):02x}" for v in rgb)


_PALETTE_NOMI = list(COLORI)
_PALETTE_LAB = _rgb_a_lab(np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in COLORI.values()]))


def nome_colore(rgb):
    lab = _rgb_a_lab(np.asarray(rgb)[None, :])[0]
    return _PALETTE_NOMI[int(np.argmin(np.linalg.norm(_PALETTE_LAB - lab, axis=1)))]


def colori_dominanti(rgba, k=4, campioni=20000, seme=0):
    """K-means in spazio Lab sui pixel del capo. Restituisce primario/secondario."""
    arr = np.asarray(rgba)
    pixel = arr[arr[..., 3] > 128][:, :3].astype(np.float64)
    copertura = len(pixel) / (arr.shape[0] * arr.shape[1])
    if len(pixel) < 200:
        return None
    rng = np.random.default_rng(seme)
    if len(pixel) > campioni:
        pixel = pixel[rng.choice(len(pixel), campioni, replace=False)]
    lab = _rgb_a_lab(pixel)
    centri = lab[rng.choice(len(lab), k, replace=False)]
    for _ in range(15):
        etichette = np.argmin(((lab[:, None, :] - centri[None]) ** 2).sum(-1), axis=1)
        centri = np.array([lab[etichette == i].mean(0) if np.any(etichette == i) else centri[i] for i in range(k)])
    quote = np.bincount(etichette, minlength=k) / len(lab)
    gruppi = []
    for i in np.argsort(-quote):
        rgb_medio = pixel[etichette == i].mean(0)
        gruppi.append({"hex": _hex(rgb_medio), "nome": nome_colore(rgb_medio), "quota": round(float(quote[i]), 3)})
    # Cluster vicini con lo stesso nome (luci/ombre) vengono sommati.
    per_nome = {}
    for g in gruppi:
        if g["nome"] in per_nome:
            per_nome[g["nome"]]["quota"] = round(per_nome[g["nome"]]["quota"] + g["quota"], 3)
        else:
            per_nome[g["nome"]] = dict(g)
    ordinati = sorted(per_nome.values(), key=lambda g: -g["quota"])
    secondario = ordinati[1] if len(ordinati) > 1 and ordinati[1]["quota"] >= 0.15 else None
    return {
        "primario": ordinati[0]["nome"],
        "primario_hex": ordinati[0]["hex"],
        "secondario": secondario["nome"] if secondario else None,
        "cluster": ordinati,
        "copertura_capo": round(copertura, 3),
    }
