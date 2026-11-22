"""Capacity, overhead and robustness of the team's two text-carrier algorithms.

The website uses Member 2's text_stego.py. A second algorithm, text_stega.py in the
"Text Steganography" folder, spreads the hidden characters through the paragraph
instead. This script measures the first one in detail and then compares the two.

What this script measures:
  1. Overhead:   how much longer the text becomes for secrets of 1 to 10,000 bytes,
                 with and without a password, and how long hiding and revealing take.
  2. Robustness: which edits of the stego text keep the message readable.
  3. Visibility: whether the visible text is unchanged, for ordinary covers and for
                 covers that already contain invisible characters (emoji, Persian).
  4. Comparison: capacity, robustness and special covers for both algorithms.

Run from the "Member 5" folder:
    python evaluate_text.py
Tables are saved as CSV files and the chart as a PNG file in the "results" folder.
"""
from __future__ import annotations

import json
import statistics
import textwrap
import time
import unicodedata

import charts
import common
from common import text_stega as spread
from common import text_stego as stego

COVER = "Hello there, see you at lunch tomorrow."
SECRET_SIZES = (1, 10, 50, 100, 500, 1000, 5000, 10000)


def hidden_count(text: str) -> int:
    return sum(ch in stego.ALPHABET for ch in text)


def overhead_table() -> list[dict]:
    cover_bytes = len(COVER.encode("utf-8"))
    rows = []
    for size in SECRET_SIZES:
        secret = "s" * size
        for label, password in (("no password", None), ("with password", "timing password")):
            hide, show = [], []
            for _ in range(5):
                start = time.perf_counter()
                text = stego.hide(COVER, secret, password)
                middle = time.perf_counter()
                assert stego.reveal(text, password) == secret
                hide.append(middle - start)
                show.append(time.perf_counter() - middle)
            stego_bytes = len(text.encode("utf-8"))
            rows.append({
                "secret_bytes": size,
                "mode": label,
                "visible_characters": len(stego.strip_hidden(text)),
                "hidden_characters": hidden_count(text),
                "hidden_characters_per_secret_byte": round(hidden_count(text) / size, 2),
                "stego_text_bytes": stego_bytes,
                "times_larger_than_cover": round(stego_bytes / cover_bytes, 1),
                "hide_ms": round(statistics.median(hide) * 1000, 2),
                "reveal_ms": round(statistics.median(show) * 1000, 2),
            })
    return rows


def outcome(candidate: str, secret: str) -> str:
    try:
        recovered = stego.reveal(candidate)
    except stego.TextStegoError as error:
        return f"rejected ({type(error).__name__})"
    return "message recovered" if recovered == secret else "WRONG MESSAGE RETURNED"


def robustness_table() -> list[dict]:
    secret = "robustness test message"
    text = stego.hide(COVER, secret)
    first_hidden = next(i for i, ch in enumerate(text) if ch in stego.ALPHABET)
    edits = {
        "no change (copied exactly)": text,
        "text added at the end (a reply)": text + " Thanks, see you then!",
        "text added at the start": "Fwd: " + text,
        "changed to upper case": text.upper(),
        "spaces trimmed at both ends": ("  " + text + "\n").strip(),
        "repeated spaces collapsed": " ".join(text.split()),
        "wrapped to 40 columns": textwrap.fill(text, 40),
        "Unicode normalisation NFC": unicodedata.normalize("NFC", text),
        "Unicode normalisation NFKC": unicodedata.normalize("NFKC", text),
        "stored as JSON and read back": json.loads(json.dumps(text)),
        "stored as UTF-16 and read back": text.encode("utf-16").decode("utf-16"),
        "a reply that contains a joined emoji": text + " \U0001F468‍\U0001F469‍\U0001F467",
        "another stego text pasted after it": text + " " + stego.hide("Second sentence here.", "other"),
        "one hidden character deleted": text[:first_hidden] + text[first_hidden + 1:],
        "only the first half copied": text[: len(text) // 2],
        "sent through an ASCII-only system": text.encode("ascii", "ignore").decode("ascii"),
        "non-printable characters removed": "".join(ch for ch in text if ch.isprintable()),
    }
    return [{"edit": name, "result": outcome(edited, secret)} for name, edited in edits.items()]


def visibility_table() -> list[dict]:
    covers = {
        "English sentence": COVER,
        "Arabic sentence": "مرحبا كيف حالك اليوم",
        "French with accents": "Ça va très bien, merci beaucoup",
        "one word": "Hello",
        "emoji joined with U+200D (family)": "Family \U0001F468‍\U0001F469‍\U0001F467 photo attached",
        "Persian word with U+200C": "می‌خواهم بروم",
    }
    rows = []
    for name, cover in covers.items():
        text = stego.hide(cover, "secret")
        payload = 4 * (len("secret") + 8)    # hidden characters added for the secret
        own = hidden_count(cover)            # invisible characters the cover itself needs
        kept = hidden_count(text) - payload  # how many of those are still there
        rows.append({
            "cover": name,
            "message_recovered": stego.reveal(text) == "secret",
            "invisible_characters_in_cover": own,
            "kept_after_hiding": kept,
            "visible_text_unchanged": kept == own,
        })
    return rows


# ------------------------------------------------- comparison of the two methods

PARAGRAPH = ("Dear team, the weekly meeting is moved to Thursday afternoon in the main hall. " * 6).strip()
ARABIC = "مرحبا بكم جميعا في الاجتماع الأسبوعي يوم الخميس بعد الظهر في القاعة الرئيسية " * 3
WEBSITE = "text_stego.py (website)"
SPREAD = "text_stega.py (Text Steganography folder)"


def spread_capacity(cover: str) -> int:
    return spread.capacity_info(cover)["max_secret_bytes"]


def comparison_capacity_table() -> list[dict]:
    covers = {
        "one short sentence": COVER,
        "two sentences": "Hello there, see you at lunch tomorrow. Please bring the printed notes with you.",
        "short paragraph (about 50 words)": common.letter_paragraph(250),
        "long paragraph (about 200 words)": common.letter_paragraph(1000),
        "one page (about 500 words)": common.letter_paragraph(2500),
        "Arabic paragraph": ARABIC.strip(),
    }
    rows = []
    for name, cover in covers.items():
        info = spread.capacity_info(cover)
        rows.append({
            "cover": name,
            "characters": len(cover),
            "english_letters": info["carrier_letters"],
            "website_method_capacity_bytes": stego.capacity(),
            "spread_method_capacity_bytes": info["max_secret_bytes"],
        })
    return rows


def _spread_outcome(candidate: str, secret: str) -> str:
    try:
        recovered = spread.decode_text(candidate)
    except ValueError:
        return "rejected"
    return "message recovered" if recovered == secret else "WRONG MESSAGE RETURNED"


def _edits(text: str, hidden: set, other: str) -> dict:
    first = next(i for i, ch in enumerate(text) if ch in hidden)
    return {
        "text added at the end (a reply)": text + " Thanks, see you then!",
        "changed to upper case": text.upper(),
        "wrapped to 40 columns": textwrap.fill(text, 40),
        "Unicode normalisation NFKC": unicodedata.normalize("NFKC", text),
        "a reply that contains a joined emoji": text + " \U0001F468\u200d\U0001F469\u200d\U0001F467",
        "another stego text pasted after it": text + " " + other,
        "one hidden character deleted": text[:first] + text[first + 1:],
        "only the first half copied": text[: len(text) // 2],
        "sent through an ASCII-only system": text.encode("ascii", "ignore").decode("ascii"),
    }


def comparison_robustness_table() -> list[dict]:
    secret = "robustness test"
    website = _edits(stego.hide(PARAGRAPH, secret), set(stego.ALPHABET), stego.hide(PARAGRAPH, "other"))
    spreaded = _edits(spread.encode_text(PARAGRAPH, secret), set(spread.SYMBOLS), spread.encode_text(PARAGRAPH, "other"))
    rows = []
    for name in website:
        website_result = outcome(website[name], secret)
        rows.append({
            "edit": name,
            WEBSITE: "rejected" if website_result.startswith("rejected") else website_result,
            SPREAD: _spread_outcome(spreaded[name], secret),
        })
    return rows


def comparison_covers_table() -> list[dict]:
    covers = {
        "English paragraph": PARAGRAPH,
        "Arabic paragraph": ARABIC,
        "paragraph with a family emoji (U+200D)": "Family \U0001F468\u200d\U0001F469\u200d\U0001F467 " + PARAGRAPH,
        "Persian text (U+200C)": "می\u200cخواهم بروم. " + PARAGRAPH,
    }
    rows = []
    for name, cover in covers.items():
        website_text = stego.hide(cover, "hi")
        website_ok = stego.reveal(website_text) == "hi"
        website_same = sum(ch in stego.ALPHABET for ch in website_text) - 4 * (2 + 8) == hidden_count(cover)
        try:
            spread_text = spread.encode_text(cover, "hi")
            spread_result = ("works, visible text unchanged" if spread.remove_hidden_symbols(spread_text) == cover
                             and spread.decode_text(spread_text) == "hi" else "visible text changed")
        except ValueError as error:
            spread_result = "refused: " + str(error).split(":")[0].split(".")[0].lower()
        rows.append({
            "cover": name,
            WEBSITE: ("works, visible text unchanged" if website_ok and website_same
                      else "message works, visible text changed" if website_ok else "fails"),
            SPREAD: spread_result,
        })
    return rows


def capacity_chart(rows: list[dict]):
    shown = [row for row in rows if row["english_letters"] > 0]
    figure, axes = charts.new_chart(
        "The spread method needs about 4 English letters for every hidden byte",
        "Largest secret for text_stega.py; the website's method always allows 10,000 bytes", height=3.9)
    labels = [row["cover"] for row in shown]
    values = [row["spread_method_capacity_bytes"] for row in shown]
    axes.barh(labels, values, height=0.42, color=charts.BLUE)
    axes.invert_yaxis()
    axes.grid(axis="y", visible=False)
    axes.grid(axis="x", color=charts.GRID, linewidth=0.8)
    axes.spines["bottom"].set_visible(False)
    axes.tick_params(axis="y", labelsize=9.5, colors=charts.INK_SECONDARY)
    axes.set_xlim(0, max(values) * 1.18)
    for position, value in enumerate(values):
        axes.text(value + max(values) * 0.012, position, f"{value:,} bytes", va="center", fontsize=9.5, color=charts.INK)
    charts.axis_labels(axes, "Largest secret (bytes)")
    figure.subplots_adjust(left=0.36, top=0.78, bottom=0.17)
    return charts.save(figure, common.RESULTS / "text_capacity_by_paragraph.png")


def main():
    print("Evaluating the text algorithm.")
    print(f"Capacity reported by the module: {stego.capacity():,} bytes, whatever the cover text is.")

    overhead = overhead_table()
    common.write_table("text_overhead", overhead)
    common.print_table(f"Overhead for the cover {COVER!r} ({len(COVER)} characters)", overhead)

    robustness = robustness_table()
    common.write_table("text_robustness", robustness)
    common.print_table("Which edits keep the hidden message readable", robustness)

    visibility = visibility_table()
    common.write_table("text_visibility", visibility)
    common.print_table("Is the visible text unchanged?", visibility)

    if spread is None:
        print('\nThe "Text Steganography" folder is missing, so the comparison is skipped.')
    else:
        capacity = comparison_capacity_table()
        common.write_table("text_compare_capacity", capacity)
        common.print_table("Comparison: largest secret for covers of different length", capacity)
        robust = comparison_robustness_table()
        common.write_table("text_compare_robustness", robust)
        common.print_table("Comparison: which edits keep the message readable (same paragraph, same secret)", robust)
        covers = comparison_covers_table()
        common.write_table("text_compare_covers", covers)
        common.print_table("Comparison: covers that are not plain English", covers)
        print("\nChart:", capacity_chart(capacity).name)
    print(f"\nAll tables are in {common.RESULTS}")


if __name__ == "__main__":
    main()
