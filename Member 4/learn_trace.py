"""Member 4: step-by-step traces of OUR app's real algorithms, for the Learn tab.

Nothing here re-implements hiding. Every trace runs the team's real code:
  * images -> Member 1's image_stego.embed() / extract()
  * text   -> Member 2's text_stega.hide() / reveal()
and then looks inside the result to explain what happened, step by step.

Image traces read a few internal helpers of image_stego (_prepare, _Spatial, _HSEED,
_HEADER, _keys) to show which pixels were used. If Member 1 renames those, update
the names in _image_internals() below.
"""
from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image

import image_stego as img   # Member 1
import text_stega as txt    # Member 2

DISPLAY_MAX = 480     # pictures shown in the browser are scaled to this size
GROUP_EXAMPLES = 4    # how many groups of 7 values we show in detail
BITS_SHOWN = 512      # cap on bits sent to the page

CHANNELS = "RGB"
TEXT_SYMBOLS = {      # Member 2's English alphabet: 4 invisible characters, 2 bits each
    "\u200b": ("00", "U+200B", "Zero Width Space"),
    "\u200c": ("01", "U+200C", "Zero Width Non-Joiner"),
    "\u2060": ("10", "U+2060", "Word Joiner"),
    "\u2063": ("11", "U+2063", "Invisible Separator"),
}
ARABIC_SYMBOLS = {    # Member 2's Arabic alphabet: 2 characters, 1 bit each (safe between joined letters)
    "\u200b": ("0", "U+200B", "Zero Width Space"),
    "\u2060": ("1", "U+2060", "Word Joiner"),
}


# ----------------------------------------------------------------- helpers
def bits_of(data: bytes) -> str:
    return "".join(f"{b:08b}" for b in data)


def char_table(message: str, limit: int = 40) -> list[dict]:
    rows = []
    for ch in list(message)[:limit]:
        b = ch.encode("utf-8")
        rows.append({"char": ch, "code": f"U+{ord(ch):04X}", "bytes": list(b), "bits": [f"{x:08b}" for x in b]})
    return rows


def _png_data_url(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _scaled(im: Image.Image, nearest: bool = False) -> Image.Image:
    im = im.copy()
    im.thumbnail((DISPLAY_MAX, DISPLAY_MAX), Image.NEAREST if nearest else Image.LANCZOS)
    return im


def _image_internals():
    return img._prepare, img._Spatial, img._HSEED, img._HEADER, img._keys, img.HEADER_BYTES


# ------------------------------------------------------------------ images
def trace_image(cover: bytes, message: str, password: str | None = None) -> dict:
    """Hide `message` in `cover` with Member 1's real embed() (PNG output) and explain every step."""
    prepare, Spatial, HSEED, HEADER, keys, HEADER_BYTES = _image_internals()

    # 1. The cover exactly as Member 1's code sees it (decoded, rotated, RGB/RGBA).
    cover_codec, _, _, (w, h), _ = prepare(cover, "PNG")
    cover_rgb = cover_codec.rgb.copy()
    cap = img.capacity(cover, "PNG", encrypted=bool(password))

    # 2. REAL hiding, exactly like the Send button does.
    result = img.embed(cover, message, password=password or None, output_format="PNG")
    recovered = img.extract(result.image, password=password or None).decode("utf-8", errors="replace")

    stego_im = Image.open(io.BytesIO(result.image))
    stego_im.load()
    stego_codec = Spatial(stego_im)
    stego_rgb = stego_codec.rgb

    # 3. Read the header back out of the stego picture (public, no password needed).
    header_raw = stego_codec.read(HEADER_BYTES, HSEED, header=True)
    magic, version, ident, flag, length, salt, nonce = HEADER.unpack(header_raw[:-4])
    encrypted = bool(flag)
    body_len = length + (16 if encrypted else 4)
    _, route = keys(img._password(password) if encrypted else None, salt)
    body_raw = stego_codec.read(body_len, route)

    # 4. Where did the bits go?
    hdr_idx = stego_codec._indices(HEADER_BYTES, HSEED, header=True)
    body_idx = stego_codec._indices(body_len, route, header=False)

    def group_rows(idx, data: bytes, part: str):
        rows = []
        bits = bits_of(data)
        for g in range(min(GROUP_EXAMPLES, len(idx))):
            ids = idx[g]
            before = [int(cover_rgb[i]) for i in ids]
            after = [int(stego_rgb[i]) for i in ids]
            syn_before = 0
            for pos, v in enumerate(before, start=1):
                if v & 1:
                    syn_before ^= pos
            target = bits[g * 3:g * 3 + 3].ljust(3, "0")
            changed = [p + 1 for p in range(7) if before[p] != after[p]]
            rows.append({
                "part": part,
                "bits": target,
                "values": [{
                    "x": int(i // 3 % w), "y": int(i // 3 // w), "channel": CHANNELS[int(i % 3)],
                    "before": b, "after": a,
                } for i, b, a in zip(ids, before, after)],
                "syndrome_before": f"{syn_before:03b}",
                "target": target,
                "flip": changed[0] if changed else 0,
            })
        return rows

    # 5. Pictures for the page.
    tiles_x, tiles_y = (w + 7) // 8, (h + 7) // 8
    used = np.zeros(h * w, dtype=bool)
    used[np.unique(stego_codec.indices // 3)] = True                    # textured pixels Member 1 may use
    changed_ch = np.flatnonzero(cover_rgb != stego_rgb)
    changed_px = np.zeros(h * w, dtype=bool)
    changed_px[np.unique(changed_ch // 3)] = True

    cover_img = Image.fromarray(cover_rgb.reshape(h, w, 3))
    stego_img = Image.fromarray(stego_rgb.reshape(h, w, 3))
    gray = np.asarray(cover_img.convert("L"), dtype=np.float32)
    faded = (gray * 0.35 + 165).astype(np.uint8)

    tex = np.stack([faded] * 3, axis=-1).copy()
    tex[used.reshape(h, w)] = [70, 140, 255]                             # blue = busy areas that can hold data
    diff = np.stack([faded] * 3, axis=-1).copy()
    mask = changed_px.reshape(h, w)
    if mask.any():                                                       # grow each dot so it is visible when scaled
        grow = mask.copy()
        r = max(1, max(w, h) // DISPLAY_MAX)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                grow |= np.roll(np.roll(mask, dy, 0), dx, 1)
        diff[grow] = [255, 0, 200]                                       # magenta = a value changed here

    quality = img.measure(cover, result.image)
    used_channels = (len(hdr_idx) + len(body_idx)) * 7
    return {
        "width": w, "height": h,
        "message": message, "table": char_table(message),
        "message_bits": bits_of(message.encode())[:BITS_SHOWN],
        "message_bytes": len(message.encode()),
        "encrypted": encrypted,
        "header": {
            "bytes": HEADER_BYTES,
            "fields": [
                {"name": "Tag", "value": magic.decode("ascii", "replace"), "size": 4, "why": "Marks the picture as one of ours"},
                {"name": "Version", "value": version, "size": 1, "why": "Format version"},
                {"name": "Method", "value": "1 = spatial (PNG/BMP)" if ident == 1 else "2 = JPEG", "size": 1, "why": "Which hiding method was used"},
                {"name": "Locked", "value": "yes" if encrypted else "no", "size": 1, "why": "Is there a password?"},
                {"name": "Length", "value": f"{length} bytes", "size": 4, "why": "Where the message ends"},
                {"name": "Salt", "value": salt.hex()[:16] + "…", "size": 16, "why": "Random; makes every picture use different pixels"},
                {"name": "Nonce", "value": nonce.hex()[:12] + "…" if encrypted else "unused", "size": 12, "why": "Needed by the encryption"},
                {"name": "Check (CRC)", "value": header_raw[-4:].hex(), "size": 4, "why": "Detects a damaged header"},
            ],
            "bits": bits_of(header_raw)[:BITS_SHOWN],
        },
        "body": {
            "bytes": body_len,
            "hex": body_raw[:48].hex(" "),
            "bits": bits_of(body_raw)[:BITS_SHOWN],
            "readable": not encrypted,
        },
        "groups": group_rows(hdr_idx, header_raw, "header") + group_rows(body_idx, body_raw, "message"),
        "images": {
            "cover": _png_data_url(_scaled(cover_img)),
            "stego": _png_data_url(_scaled(stego_img)),
            "texture": _png_data_url(_scaled(Image.fromarray(tex), nearest=True)),
            "diff": _png_data_url(_scaled(Image.fromarray(diff), nearest=True)),
        },
        "stats": {
            "tiles_total": tiles_x * tiles_y,
            "tiles_used": (tiles_x * tiles_y + 1) // 2,   # Member 1 keeps the busier half of the 8x8 tiles
            "capacity_bytes": cap.max_message_bytes,
            "groups_used": len(hdr_idx) + len(body_idx),
            "groups_total": int(stego_codec.groups),
            "channels_used": used_channels,
            "channels_changed": int(len(changed_ch)),
            "channels_total": int(h * w * 3),
            "pixels_changed": int(changed_px.sum()),
            "pixels_total": int(h * w),
            "psnr": quality.psnr_db,
            "plain_lsb_changes": int(round((len(hdr_idx) + len(body_idx)) * 3 / 2)),
        },
        "recovered": recovered,
        "ok": recovered == message,
        "png_base64": base64.b64encode(result.image).decode(),
    }


# -------------------------------------------------------------------- text
def trace_text(cover: str, message: str, password: str | None = None) -> dict:
    """Hide `message` in `cover` with Member 2's real hide() and explain every step."""
    stego = txt.hide(cover, message, password or None)
    clean_cover = txt.strip_hidden(cover)
    pos = txt.insert_position(clean_cover)
    mode, symbols, payload = txt.read_packet(stego)
    locked = payload[:2] == txt.LOCKED_MAGIC
    width = 2 if mode == "English" else 1          # bits per invisible character
    table = TEXT_SYMBOLS if width == 2 else ARABIC_SYMBOLS

    def label(i: int) -> str:
        if i < 2: return "Tag 'TL'" if locked else "Tag 'TS'"
        if locked:
            if i < 18: return "Salt"
            if i < 30: return "Nonce"
            if i >= len(payload) - 16: return "Auth tag"
            return "Encrypted message"
        if i < 4: return "Length"
        if i >= len(payload) - 4: return "Check (CRC)"
        return "Message"

    rows = []
    for i, b in enumerate(payload[:64]):
        bits = f"{b:08b}"
        rows.append({"index": i, "field": label(i), "value": b, "bits": bits,
                     "pairs": [bits[k:k + width] for k in range(0, 8, width)]})

    recovered = txt.reveal(stego, password or None)
    return {
        "message": message, "table": char_table(message),
        "message_bits": bits_of(message.encode())[:BITS_SHOWN],
        "cover": clean_cover, "stego": stego, "insert_at": pos,
        "locked": locked,
        "mode": mode, "bits_per_symbol": width,
        "payload_bytes": len(payload),
        "payload_rows": rows,
        "symbols": len(symbols),
        "symbol_table": [{"bits": v[0], "code": v[1], "name": v[2]} for v in table.values()],
        "stats": {"cover_chars": len(clean_cover), "stego_chars": len(stego), "hidden_chars": len(symbols)},
        "recovered": recovered,
        "ok": recovered == message,
    }


def check_text(text: str, password: str | None = None) -> dict:
    """'Try it yourself': look for a hidden message in pasted text with Member 2's reveal()."""
    try:
        hidden = len(txt.find_hidden(text))
    except txt.TextStegoError:
        hidden = 0
    try:
        return {"found": True, "message": txt.reveal(text, password or None), "hidden_chars": hidden}
    except txt.TextPasswordError as exc:
        return {"found": False, "needs_password": True, "reason": str(exc), "hidden_chars": hidden}
    except txt.TextStegoError as exc:
        return {"found": False, "reason": str(exc), "hidden_chars": hidden}
