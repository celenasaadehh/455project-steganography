"""Detection experiment (steganalysis): can someone tell that a picture or a text hides a message?

The earlier experiments measured how much a picture CHANGES (PSNR). That is not the
same as how easy the hidden data is to DETECT. This script attacks the stego pictures
with three classic detectors from the research literature and measures how often each
one catches them.

Detectors (all look only at the picture, without the password or the original):
  Chi-square attack  Westfeld and Pfitzmann (1999). Flipping last bits makes the counts
                     of each value pair (2k, 2k+1) become equal. Strong against
                     sequential LSB, weak when changes are scattered.
  RS analysis        Fridrich, Goljan and Du (2001). Estimates the share of colour values
                     that carry hidden bits from how "smooth" small groups of pixels stay
                     when their last bits are flipped.
  Sample pair        Dumitrescu, Wu and Wang (2003). Estimates the same share from
  analysis (SPA)     statistics of neighbouring pixel pairs. Usually the most accurate.

Hiding methods compared, at the same message sizes (bits per colour value):
  Team's method      Member 1's image_stego.embed() (texture-adaptive matrix embedding, PNG).
  Sequential LSB     The textbook method: last bits overwritten from the top-left corner.
  Random LSB         Last bits overwritten at random positions spread over the picture.

Pictures: 51 tiles of 256 x 256 cut from 15 real photos that come with scikit-image,
and, separately, the 10 pictures of the website's gallery.

Result for each detector, method and size: AUC (0.5 = guessing, 1.0 = always caught),
the share of stego pictures caught when at most 5% of clean pictures are wrongly flagged,
and the average hidden-data share the detector estimates.

The text part checks whether a simple scanner for invisible characters finds
messages hidden by the website's text carrier (Member 2's text_stega.py), in English
and Arabic mode, with and without a password.

Run from the "Member 5" folder:
    python steganalysis.py
Tables, charts and a log are saved in the "results" folder.
"""
from __future__ import annotations

import statistics
import warnings

import numpy as np
from scipy.stats import chi2

import charts
import common
from common import image_stego, text_stega, to_bytes, to_image

TILE = 256
MAX_TILES_PER_PHOTO = 6
RATES = (0.01, 0.02, 0.05, 0.10, 0.20)   # hidden bits per colour value; the team's method holds up to ~0.21
TEAM = "Team's method"
SEQUENTIAL = "Sequential LSB"
RANDOM = "Random LSB"
METHODS = (TEAM, SEQUENTIAL, RANDOM)
DETECTORS = ("Chi-square", "RS analysis", "SPA")
PHOTOS = ("astronaut", "coffee", "chelsea", "rocket", "camera", "coins", "moon", "brick", "grass",
          "gravel", "immunohistochemistry", "hubble_deep_field", "cell", "retina", "clock")


# ==================================================================== detectors

def chi_square_p(values: np.ndarray) -> float:
    """Westfeld-Pfitzmann chi-square attack. Returns the probability of embedding (near 1 = detected)."""
    histogram = np.bincount(np.asarray(values, dtype=np.int64).ravel(), minlength=256)[:256].astype(np.float64)
    even, odd = histogram[0::2], histogram[1::2]
    expected = (even + odd) / 2
    keep = expected > 4                      # categories with enough data, as in the original attack
    if keep.sum() < 2:
        return 0.0
    statistic = float(np.sum((even[keep] - expected[keep]) ** 2 / expected[keep]))
    return float(chi2.sf(statistic, int(keep.sum()) - 1))


def _flip_positive(x):  # F1: 0<->1, 2<->3, ... (what LSB replacement does)
    return x ^ 1


def _flip_negative(x):  # F-1: -1<->0, 1<->2, 3<->4, ...
    return ((x + 1) ^ 1) - 1


def _rs_counts(groups: np.ndarray) -> tuple[float, float, float, float]:
    """Share of regular and singular groups for the mask [0, 1, 1, 0] and its negative."""
    mask = np.array([0, 1, 1, 0], dtype=bool)

    def smoothness(g):
        return np.abs(np.diff(g, axis=-1)).sum(axis=-1)

    base = smoothness(groups)
    positive = groups.copy()
    positive[..., mask] = _flip_positive(positive[..., mask])
    negative = groups.copy()
    negative[..., mask] = _flip_negative(negative[..., mask])
    fp, fn = smoothness(positive), smoothness(negative)
    return (float(np.mean(fp > base)), float(np.mean(fp < base)),
            float(np.mean(fn > base)), float(np.mean(fn < base)))


def _rs_channel(channel: np.ndarray) -> float:
    estimates = []
    for plane in (channel, channel.T):                     # horizontal and vertical groups of 4
        height, width = plane.shape
        groups = plane[:, : width // 4 * 4].reshape(height, width // 4, 4).astype(np.int32)
        r_m, s_m, r_n, s_n = _rs_counts(groups)
        r_m1, s_m1, r_n1, s_n1 = _rs_counts(groups ^ 1)   # the same picture with every last bit flipped
        d0, d1 = r_m - s_m, r_m1 - s_m1
        dn0, dn1 = r_n - s_n, r_n1 - s_n1
        a, b, c = 2 * (d1 + d0), dn0 - dn1 - d1 - 3 * d0, d0 - dn0
        if abs(a) < 1e-12:
            x = -c / b if abs(b) > 1e-12 else 0.0
        else:
            disc = b * b - 4 * a * c
            if disc < 0:
                x = -b / (2 * a)
            else:
                roots = ((-b + disc ** 0.5) / (2 * a), (-b - disc ** 0.5) / (2 * a))
                x = min(roots, key=abs)
        estimates.append(x / (x - 0.5) if abs(x - 0.5) > 1e-12 else 1.0)
    return float(np.mean(estimates))


def rs_estimate(pixels: np.ndarray) -> float:
    """RS analysis. Estimated share of colour values carrying a hidden bit (0 = clean)."""
    return float(np.mean([_rs_channel(pixels[:, :, c]) for c in range(pixels.shape[2])]))


def _spa_channel(channel: np.ndarray) -> float:
    estimates = []
    for plane in (channel, channel.T):                     # horizontal and vertical neighbours
        u = plane[:, :-1].astype(np.int32).ravel()
        v = plane[:, 1:].astype(np.int32).ravel()
        v_even = (v & 1) == 0
        x = np.count_nonzero((v_even & (u < v)) | (~v_even & (u > v)))
        y = np.count_nonzero((v_even & (u > v)) | (~v_even & (u < v)))
        z = np.count_nonzero(u == v)
        w = np.count_nonzero(((u >> 1) == (v >> 1)) & (u != v))
        total = u.size
        a, b, c = (w + z) / 2, 2 * x - total, y - x
        if a == 0:
            p = -c / b if b else 0.0
        else:
            disc = b * b - 4 * a * c
            roots = ((-b - max(disc, 0) ** 0.5) / (2 * a), (-b + max(disc, 0) ** 0.5) / (2 * a))
            p = min(roots)
        estimates.append(p)
    return float(np.mean(estimates))


def spa_estimate(pixels: np.ndarray) -> float:
    """Sample pair analysis. Estimated share of colour values carrying a hidden bit (0 = clean)."""
    return float(np.mean([_spa_channel(pixels[:, :, c]) for c in range(pixels.shape[2])]))


def chi_square_scan_score(pixels: np.ndarray) -> float:
    """The attack as Westfeld and Pfitzmann use it: test the first 1%, 2%, ... 100% of the picture
    in reading order and keep the highest probability of embedding."""
    values = pixels.reshape(-1)
    return max(chi_square_p(values[: values.size * percent // 100]) for percent in range(1, 101))


def scores(pixels: np.ndarray) -> dict[str, float]:
    return {"Chi-square": chi_square_scan_score(pixels), "RS analysis": rs_estimate(pixels), "SPA": spa_estimate(pixels)}


# ================================================================ hiding methods

def message_bytes(pixels: np.ndarray, rate: float) -> int:
    return int(rate * pixels.size / 8)


def sequential_lsb(pixels: np.ndarray, bits: int, rng: np.random.Generator) -> np.ndarray:
    out = pixels.copy().reshape(-1)
    out[:bits] = (out[:bits] & 0xFE) | rng.integers(0, 2, bits, dtype=np.uint8)
    return out.reshape(pixels.shape)


def random_lsb(pixels: np.ndarray, bits: int, rng: np.random.Generator) -> np.ndarray:
    out = pixels.copy().reshape(-1)
    where = rng.choice(out.size, size=bits, replace=False)
    out[where] = (out[where] & 0xFE) | rng.integers(0, 2, bits, dtype=np.uint8)
    return out.reshape(pixels.shape)


def team_method(pixels: np.ndarray, size: int, rng: np.random.Generator) -> np.ndarray:
    message = rng.integers(0, 256, size, dtype=np.uint8).tobytes()
    result = image_stego.embed(to_bytes(common.Image.fromarray(pixels)), message)
    return np.asarray(to_image(result.image).convert("RGB"))


def hide(method: str, pixels: np.ndarray, rate: float, rng: np.random.Generator) -> np.ndarray:
    size = message_bytes(pixels, rate)
    if method == TEAM:
        return team_method(pixels, size, rng)
    bits = size * 8
    return sequential_lsb(pixels, bits, rng) if method == SEQUENTIAL else random_lsb(pixels, bits, rng)


# ======================================================================= covers

def photo_tiles() -> dict[str, np.ndarray]:
    """Tiles of 256 x 256 from the real photos bundled with scikit-image (no download)."""
    import skimage.data

    tiles = {}
    for name in PHOTOS:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            image = np.asarray(getattr(skimage.data, name)())
        if image.ndim == 2:
            image = np.stack([image] * 3, axis=-1)
        image = image[:, :, :3].astype(np.uint8)
        rows, columns = image.shape[0] // TILE, image.shape[1] // TILE
        positions = [(r, c) for r in range(rows) for c in range(columns)][:MAX_TILES_PER_PHOTO]
        for r, c in positions:
            tiles[f"{name}-{r}{c}"] = np.ascontiguousarray(image[r * TILE:(r + 1) * TILE, c * TILE:(c + 1) * TILE])
    return tiles


def gallery_pictures() -> dict[str, np.ndarray]:
    return {name: np.asarray(to_image(data).convert("RGB")) for name, data in common.gallery_covers().items()}


# ====================================================================== metrics

def auc(clean: list[float], stego: list[float]) -> float:
    """Chance that a random stego picture scores higher than a random clean one (ties count half)."""
    clean_values, stego_values = np.asarray(clean), np.asarray(stego)
    higher = (stego_values[:, None] > clean_values[None, :]).sum()
    ties = (stego_values[:, None] == clean_values[None, :]).sum()
    return float((higher + 0.5 * ties) / (clean_values.size * stego_values.size))


def caught_at_5_percent(clean: list[float], stego: list[float]) -> float:
    """Share of stego pictures above the threshold that flags at most 5% of clean pictures."""
    threshold = np.quantile(np.asarray(clean), 0.95, method="higher")
    return float(np.mean(np.asarray(stego) > threshold))


# =================================================================== experiment

def run(covers: dict[str, np.ndarray], label: str, rng: np.random.Generator) -> list[dict]:
    clean = {name: scores(pixels) for name, pixels in covers.items()}
    rows = []
    for rate in RATES:
        for method in METHODS:
            stego_scores = [scores(hide(method, pixels, rate, rng)) for pixels in covers.values()]
            for detector in DETECTORS:
                clean_values = [clean[name][detector] for name in covers]
                stego_values = [s[detector] for s in stego_scores]
                row = {
                    "pictures": label,
                    "bits_per_colour_value": rate,
                    "method": method,
                    "detector": detector,
                    "auc": round(auc(clean_values, stego_values), 3),
                    "caught_at_5_percent_false_alarms": round(caught_at_5_percent(clean_values, stego_values), 3),
                }
                if detector != "Chi-square":
                    row["mean_estimate_clean"] = round(statistics.mean(clean_values), 4)
                    row["mean_estimate_stego"] = round(statistics.mean(stego_values), 4)
                else:
                    row["mean_estimate_clean"] = row["mean_estimate_stego"] = ""
                rows.append(row)
    return rows


def chi_square_scan(pixels: np.ndarray, rng: np.random.Generator) -> list[dict]:
    """Westfeld's classic picture: probability of embedding over the first x% of the picture."""
    rate = 0.20
    pictures = {method: hide(method, pixels, rate, rng).reshape(-1) for method in METHODS}
    pictures["Clean picture"] = pixels.reshape(-1)
    rows = []
    for percent in range(2, 101, 2):
        end = pixels.size * percent // 100
        rows.append({"percent_scanned": percent,
                     **{name: round(chi_square_p(values[:end]), 4) for name, values in pictures.items()}})
    return rows


# ================================================================== known cover

def known_cover_check(rng: np.random.Generator) -> list[dict]:
    """The website's 10 gallery pictures are public. Compare a stego picture made from one of them
    with the public original: any changed value gives the hidden data away."""
    rows = []
    for name, original in common.gallery_covers().items():
        clean_copy = to_bytes(to_image(original))                       # the same picture, just saved again
        stego_file = image_stego.embed(original, rng.integers(0, 256, 10, dtype=np.uint8).tobytes()).image
        reference = np.asarray(to_image(original).convert("RGB")).astype(np.int16)
        rows.append({
            "gallery_picture": name,
            "values_changed_in_clean_copy": int(np.count_nonzero(np.asarray(to_image(clean_copy).convert("RGB")) != reference)),
            "values_changed_with_10_byte_message": int(np.count_nonzero(np.asarray(to_image(stego_file).convert("RGB")) != reference)),
        })
    for row in rows:
        row["detected"] = row["values_changed_with_10_byte_message"] > 0
        row["false_alarm"] = row["values_changed_in_clean_copy"] > 0
    return rows


# ============================================================ black-and-white covers

def grey_cover_check(tiles: dict[str, np.ndarray], rng: np.random.Generator) -> list[dict]:
    """A black-and-white photo has identical red, green and blue values. The team's code turns a
    greyscale upload into a colour picture, so hiding anything makes the three channels differ."""
    rows = []
    for name, pixels in tiles.items():
        if not (np.array_equal(pixels[:, :, 0], pixels[:, :, 1]) and np.array_equal(pixels[:, :, 1], pixels[:, :, 2])):
            continue
        upload = to_bytes(common.Image.fromarray(pixels[:, :, 0]))      # a real greyscale ("L") file
        result = np.asarray(to_image(image_stego.embed(upload, rng.integers(0, 256, 10, dtype=np.uint8).tobytes()).image))
        same = result.ndim == 2 or (np.array_equal(result[:, :, 0], result[:, :, 1])
                                     and np.array_equal(result[:, :, 1], result[:, :, 2]))
        rows.append({"greyscale_tile": name, "stego_mode": "L" if result.ndim == 2 else "RGB",
                     "channels_differ_after_10_byte_message": not same})
    return rows


# ========================================================================= text

ZERO_WIDTH = {"​", "‌", "‍", "⁠", "⁣", "﻿"}


def invisible_count(text: str) -> int:
    return sum(ch in ZERO_WIDTH for ch in text)


def text_detection() -> list[dict]:
    """A three-line scanner: flag a text that contains 8 or more zero-width characters."""
    paragraph = common.letter_paragraph(400)
    clean = {
        "English paragraph": paragraph,
        "Arabic paragraph": "مرحبا بكم جميعا في الاجتماع الأسبوعي يوم الخميس بعد الظهر " * 3,
        "French with accents": "Ça va très bien, merci beaucoup. À bientôt à la réunion! " * 3,
        "text with three family emoji": "Photos: \U0001F468‍\U0001F469‍\U0001F467 "
                                        "\U0001F468‍\U0001F469‍\U0001F466 "
                                        "\U0001F469‍\U0001F469‍\U0001F467 " + paragraph,
        "Persian sentence": "می‌خواهم فردا به جلسه بروم و می‌توانم کمک کنم.",
    }
    stego = {}
    covers = {"English": paragraph, "Arabic": clean["Arabic paragraph"]}
    for secret in ("a", "hello", "x" * 50):
        for language, cover in covers.items():
            stego[f"{language} cover, {len(secret)}-byte secret"] = text_stega.hide(cover, secret)
            stego[f"{language} cover, {len(secret)}-byte secret, password"] = text_stega.hide(cover, secret, "pw")
    rows = []
    for kind, texts in (("clean", clean), ("stego", stego)):
        for name, text in texts.items():
            count = invisible_count(text)
            rows.append({"text": name, "kind": kind, "zero_width_characters": count, "flagged": count >= 8})
    return rows


# ======================================================================== charts

COLOURS = {TEAM: charts.BLUE, SEQUENTIAL: charts.ORANGE, RANDOM: "#1baf7a"}


def auc_chart(rows: list[dict], label: str, filename: str, title: str):
    import matplotlib.pyplot as plt

    figure, panels = plt.subplots(1, 3, figsize=(11, 4.6), dpi=160, sharey=True)
    figure.patch.set_facecolor(charts.SURFACE)
    figure.suptitle(title,
                    x=0.015, y=0.98, ha="left", va="top", fontsize=12.5, fontweight="bold", color=charts.INK)
    figure.text(0.015, 0.905, f"Detection AUC on {label} (0.5 = guessing, 1.0 = always caught), "
                "by message size in hidden bits per colour value", ha="left", va="top", fontsize=9.5,
                color=charts.INK_SECONDARY)
    for axes, detector in zip(panels, DETECTORS):
        axes.set_facecolor(charts.SURFACE)
        for side in ("top", "right"):
            axes.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            axes.spines[side].set_color(charts.AXIS)
        axes.grid(axis="y", color=charts.GRID, linewidth=0.8)
        axes.set_axisbelow(True)
        axes.tick_params(colors=charts.INK_MUTED, labelsize=9, length=0)
        for method in METHODS:
            points = [r for r in rows if r["detector"] == detector and r["method"] == method]
            charts.line(axes, [r["bits_per_colour_value"] for r in points], [r["auc"] for r in points],
                        COLOURS[method], method)
        axes.set_xscale("log")
        axes.set_xticks(RATES, [f"{r:g}" for r in RATES])
        axes.minorticks_off()
        axes.set_ylim(0.4, 1.03)
        axes.axhline(0.5, color=charts.AXIS, linewidth=0.8)
        axes.set_title(detector, fontsize=10.5, color=charts.INK, loc="left")
        axes.set_xlabel("Hidden bits per colour value", fontsize=9, color=charts.INK_SECONDARY)
    panels[0].set_ylabel("Detection AUC", fontsize=9.5, color=charts.INK_SECONDARY)
    handles, labels = panels[0].get_legend_handles_labels()
    box = figure.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=3, frameon=False,
                        fontsize=9.5, handlelength=1.6)
    for text in box.get_texts():
        text.set_color(charts.INK_SECONDARY)
    figure.subplots_adjust(top=0.78, left=0.06, right=0.99, bottom=0.24, wspace=0.08)
    return charts.save(figure, common.RESULTS / filename)


def scan_chart(rows: list[dict], photo: str):
    figure, axes = charts.new_chart(
        "The chi-square attack sees exactly where sequential LSB stops",
        f"Probability of hidden data over the first part of one photo ({photo}), message of 0.2 bits per colour value")
    x = [r["percent_scanned"] for r in rows]
    axes.plot(x, [r["Clean picture"] for r in rows], color=charts.INK_MUTED, linewidth=1.5, label="Clean picture")
    for name, colour in ((SEQUENTIAL, charts.ORANGE), (RANDOM, "#1baf7a"), (TEAM, charts.BLUE)):
        charts.line(axes, x, [r[name] for r in rows], colour, name, markers=False)
    axes.set_ylim(-0.03, 1.05)
    axes.set_xlim(0, 100)
    axes.set_yticks([0, 0.25, 0.5, 0.75, 1.0], ["0", "0.25", "0.5", "0.75", "1"])
    charts.axis_labels(axes, "Share of the picture scanned, from the top-left (%)", "Probability of embedding")
    charts.legend(axes, loc="center right")
    return charts.save(figure, common.RESULTS / "detect_chi_square_scan.png")


# ========================================================================== main

def main():
    rng = np.random.default_rng(455)
    tiles = photo_tiles()
    gallery = gallery_pictures()
    print(f"Detection experiment: {len(tiles)} photo tiles, {len(gallery)} gallery pictures.")

    rows = run(tiles, "photos", rng)
    common.write_table("detect_photos", rows)
    common.print_table("Detection on real photos (256 x 256 tiles)", rows)
    print("\nChart:", auc_chart(rows, f"{len(tiles)} real photo tiles", "detect_auc_photos.png",
                                      "The team's method is the hardest of the three to detect, but not undetectable").name)

    if gallery:
        gallery_rows = run(gallery, "website gallery", rng)
        common.write_table("detect_gallery", gallery_rows)
        common.print_table("Detection on the website's gallery pictures", gallery_rows)
        print("\nChart:", auc_chart(gallery_rows, "the 10 website gallery pictures", "detect_auc_gallery.png",
                                          "On the gallery pictures RS and SPA barely work; the chi-square scan catches only sequential LSB").name)

    # A photo whose clean version passes the scan everywhere, so any rise comes from the hidden data.
    # (Some clean photos already look "embedded" to this attack; those are its false alarms.)
    photo = "rocket-00"
    scan = chi_square_scan(tiles[photo], rng)
    common.write_table("detect_chi_square_scan", scan)
    print("Chart:", scan_chart(scan, photo).name)

    grey = grey_cover_check(tiles, rng)
    common.write_table("detect_greyscale_cover", grey)
    print(f"\nBlack-and-white uploads: channels differ after hiding 10 bytes in "
          f"{sum(r['channels_differ_after_10_byte_message'] for r in grey)} of {len(grey)}.")

    known = known_cover_check(rng)
    if known:
        common.write_table("detect_known_gallery_cover", known)
        common.print_table("Known cover: stego picture compared with the public gallery original", known)

    text_rows = text_detection()
    common.write_table("detect_text", text_rows)
    common.print_table("Text: a scanner that flags 8 or more zero-width characters", text_rows)
    print('\nAll tables and charts are in the "results" folder.')


if __name__ == "__main__":
    main()
