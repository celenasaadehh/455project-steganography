"""Member 4: two hands-on labs for the Learn tab.

1. Detection lab: "Can it be detected?"
   The same random message is hidden two ways in the same picture:
     * plain LSB: one bit in every colour value, top to bottom (the textbook method)
     * our app: Member 1's real embed() (busy areas + matrix embedding + random order)
   Then the chi-square attack (Westfeld & Pfitzmann, 2000) is run on the clean picture
   and both results, and a map shows where each method changed the picture.
   (RS analysis and the "last-bit layer" visual attack were tried too, but the gallery
   pictures are computer-generated with fine grain, which makes both unreliable here.)

2. Robustness lab: "What breaks the message?"
   A hidden message is put through everyday changes (JPEG, resizing, cropping, removing
   invisible characters, ...) and the team's real extract()/reveal() is tried after each.

Only NumPy and Pillow are needed (no SciPy).
"""
from __future__ import annotations

import base64
import io
import math
import os
import re
import unicodedata

import numpy as np
from PIL import Image, ImageEnhance

import image_stego as img   # Member 1
import text_stego as txt    # website text carrier

DISPLAY_MAX = 420
SIZES_KB = {"small": 2, "medium": 12, "large": 40}


# ------------------------------------------------------------------ helpers
def _png_data_url(im: Image.Image) -> str:
    im = im.copy()
    im.thumbnail((DISPLAY_MAX, DISPLAY_MAX), Image.NEAREST)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _rgb(data: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(data)) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8).copy()


def _png_bytes(rgb: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "PNG")
    return buf.getvalue()


def _chi2_sf(x: float, k: int) -> float:
    """P(X > x) for a chi-square distribution with k degrees of freedom (regularised upper gamma)."""
    if x <= 0 or k <= 0:
        return 1.0
    a, x2 = k / 2.0, x / 2.0
    gln = math.lgamma(a)
    if x2 < a + 1:                       # series for P, then Q = 1 - P
        ap, s, d = a, 1.0 / a, 1.0 / a
        for _ in range(1000):
            ap += 1
            d *= x2 / ap
            s += d
            if abs(d) < abs(s) * 1e-12:
                break
        return max(0.0, 1.0 - s * math.exp(-x2 + a * math.log(x2) - gln))
    b, c, d = x2 + 1 - a, 1e300, 1.0 / (x2 + 1 - a)   # continued fraction for Q
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    return min(1.0, math.exp(-x2 + a * math.log(x2) - gln) * h)


# ------------------------------------------------------------ the attacks
CHI_POINTS = sorted(set([round(float(x), 4) for x in np.linspace(0.002, 0.05, 25)] +
                        [round(float(x), 4) for x in np.linspace(0.05, 1.0, 39)]))


def chi_square_curve(rgb: np.ndarray) -> list[float]:
    """Westfeld-Pfitzmann attack. Reads the colour values top-to-bottom and, after each
    slice, gives the probability that the values read so far carry hidden data.
    LSB embedding makes each pair of values (2k, 2k+1) equally frequent; this tests for that."""
    flat = rgb.reshape(-1)
    n = flat.size
    out = []
    for frac in CHI_POINTS:
        hist = np.bincount(flat[: max(1, int(n * frac))], minlength=256).astype(np.float64)
        even, odd = hist[0::2], hist[1::2]
        expected = (even + odd) / 2
        keep = expected > 4
        if keep.sum() < 2:
            out.append(0.0)
            continue
        chi = float((((even[keep] - expected[keep]) ** 2) / expected[keep]).sum())
        out.append(round(_chi2_sf(chi, int(keep.sum()) - 1), 4))
    return out


def change_map(clean: np.ndarray, arr: np.ndarray) -> Image.Image:
    """Faded picture with every changed pixel in magenta (only possible when you have the original)."""
    gray = np.asarray(Image.fromarray(clean).convert("L"), dtype=np.float32) * 0.35 + 165
    out = np.stack([gray] * 3, axis=-1).astype(np.uint8)
    out[(arr != clean).any(axis=2)] = [255, 0, 200]
    return Image.fromarray(out)


# ----------------------------------------------------------- detection lab
def plain_lsb(rgb: np.ndarray, payload: bytes) -> np.ndarray:
    """Textbook LSB: one bit per colour value, in reading order."""
    bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))
    flat = rgb.reshape(-1).copy()
    if bits.size > flat.size:
        raise ValueError("Message too large for plain LSB.")
    flat[: bits.size] = (flat[: bits.size] & 0xFE) | bits
    return flat.reshape(rgb.shape)


def detection_lab(cover: bytes, size: str = "medium") -> dict:
    kb = SIZES_KB.get(size, SIZES_KB["medium"])
    cap = img.capacity(cover, "PNG").max_message_bytes
    n = min(kb * 1024, cap)
    if n < 64:
        raise img.CapacityError("This picture is too small for the detection lab.")
    payload = os.urandom(n)                       # random bytes look like an encrypted message

    ours_png = img.embed(cover, payload, output_format="PNG").image
    assert img.extract(ours_png) == payload       # the real extractor gets it back
    ours = _rgb(ours_png)
    codec, _, _, (w, h), _ = img._prepare(cover, "PNG")   # the cover exactly as Member 1's code reads it
    clean = codec.rgb.reshape(h, w, 3).copy()
    plain = plain_lsb(clean, payload)

    total = clean.size
    rows = []
    for key, name, arr in (("clean", "Clean picture (nothing hidden)", clean),
                           ("plain", "Plain LSB", plain),
                           ("ours", "Our app", ours)):
        changed = int((arr != clean).sum())
        rows.append({
            "key": key, "name": name,
            "chi": chi_square_curve(arr),
            "changed": changed,
            "changed_pct": round(changed / total * 100, 3),
            "map": _png_data_url(change_map(clean, arr)),
        })
    # Judge against the clean picture: smooth areas (e.g. a sky) can raise a false alarm
    # even with nothing hidden, so only alarms the clean picture does NOT have count.
    clean_flags = [p > 0.5 for p in rows[0]["chi"]]
    for r in rows:
        flags = [p > 0.5 for p in r["chi"]]
        r["false_alarm"] = any(clean_flags) if r["key"] == "clean" else False
        r["extra_alarms"] = sum(1 for f, c in zip(flags, clean_flags) if f and not c)
        alarms = r["extra_alarms"]
        r["level"] = "none" if r["key"] == "clean" or alarms == 0 else ("weak" if alarms <= 2 else "strong")
    return {
        "bytes": n,
        "width": int(clean.shape[1]), "height": int(clean.shape[0]),
        "plain_fill_pct": round(n * 8 / total * 100, 1),
        "rows": rows,
        "x": [round(f * 100, 2) for f in CHI_POINTS],
        "cover": _png_data_url(Image.fromarray(clean)),
    }


# ---------------------------------------------------------- robustness lab
def _jpeg(rgb: np.ndarray, q: int) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "JPEG", quality=q)
    return buf.getvalue()


def _resize(rgb: np.ndarray, f: float) -> bytes:
    h, w = rgb.shape[:2]
    return _png_bytes(np.asarray(Image.fromarray(rgb).resize((max(1, round(w * f)), max(1, round(h * f))), Image.LANCZOS)))


IMAGE_ATTACKS = [
    ("none", "Sent exactly as it is", lambda b, a: b),
    ("png", "Opened and saved again as PNG", lambda b, a: _png_bytes(a)),
    ("rotate", "Rotated 90° (e.g. turned on a phone)", lambda b, a: _png_bytes(np.ascontiguousarray(np.rot90(a)))),
    ("bright", "Brightness +1%", lambda b, a: _png_bytes(np.asarray(ImageEnhance.Brightness(Image.fromarray(a)).enhance(1.01)))),
    ("crop", "1 pixel cropped from the left", lambda b, a: _png_bytes(a[:, 1:])),
    ("resize99", "Resized to 99%", lambda b, a: _resize(a, 0.99)),
    ("resize50", "Resized to 50% (like many chat apps)", lambda b, a: _resize(a, 0.5)),
    ("jpeg95", "Converted to JPEG, quality 95", lambda b, a: _jpeg(a, 95)),
    ("jpeg75", "Converted to JPEG, quality 75 (like WhatsApp)", lambda b, a: _jpeg(a, 75)),
]


LOST = "Message lost: the hidden bits were changed"


def _try_extract(data: bytes, message: str, password: str | None) -> dict:
    try:
        got = img.extract(data, password=password).decode("utf-8", "replace")
        return {"ok": got == message, "result": "Message recovered" if got == message else "Wrong message"}
    except img.PasswordError:
        return {"ok": False, "result": "Message lost: the password check failed"}
    except img.StegoError:
        return {"ok": False, "result": LOST}


def robustness_image(cover: bytes, message: str, password: str | None = None) -> dict:
    out = {"modes": []}
    modes = [("PNG", "PNG (default, most capacity)")]
    try:
        img.capacity(cover, "JPEG")
        modes.append(("JPEG", "JPEG mode (built to survive JPEG)"))
        jpeg_ok = True
    except Exception:
        jpeg_ok = False
    for fmt, label in modes:
        stego = img.embed(cover, message, password=password, output_format=fmt).image
        arr = _rgb(stego)
        rows = []
        for key, name, attack in IMAGE_ATTACKS:
            r = _try_extract(attack(stego, arr), message, password)
            rows.append({"key": key, "name": name, **r})
        out["modes"].append({"format": fmt, "label": label, "rows": rows})
    out["jpeg_available"] = jpeg_ok
    return out


TEXT_ATTACKS = [
    ("none", "Copied and pasted as it is", lambda s: s),
    ("append", "Text added at the end", lambda s: s + " See you!"),
    ("edit_end", "Last word edited", lambda s: re.sub(r"(\w+)(\W*)$", r"changed\2", s, count=1)),
    ("nfc", "Unicode normalised (NFC, done by many apps)", lambda s: unicodedata.normalize("NFC", s)),
    ("nfkc", "Unicode normalised (NFKC, stricter)", lambda s: unicodedata.normalize("NFKC", s)),
    ("spaces", "Extra spaces cleaned up", lambda s: re.sub(r"[ \t]+", " ", s).strip()),
    ("emoji", "A reply with a family emoji 👨\u200d👩\u200d👧 added", lambda s: s + " 👨\u200d👩\u200d👧"),
    ("strip", "Invisible characters removed (some apps do this)", lambda s: re.sub("[\u200b\u200c\u200d\u2060]", "", s)),
    ("retype", "Retyped by hand (only visible letters)", lambda s: "".join(c for c in s if c.isprintable() and unicodedata.category(c) != "Cf")),
]


def robustness_text(cover: str, message: str, password: str | None = None) -> dict:
    stego = txt.hide(cover, message, password or None)
    rows = []
    for key, name, attack in TEXT_ATTACKS:
        changed = attack(stego)
        try:
            got = txt.reveal(changed, password or None)
            ok = got == message
            res = "Message recovered" if ok else "Wrong message"
        except txt.TextStegoError:
            ok, res = False, "Message lost: the invisible characters were changed or removed"
        rows.append({"key": key, "name": name, "ok": ok, "result": res})
    return {"rows": rows}
