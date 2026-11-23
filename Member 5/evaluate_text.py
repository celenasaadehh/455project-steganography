"""Overhead, robustness and visibility of the team's text carrier.

The website (Member 3) uses Member 2's text_stega.py. It puts the hidden
characters in one block after the first word: 2 bits per invisible character for
English text, 1 bit per character when the cover contains Arabic letters, with an
optional password (AES-256-GCM).

What this script measures:
  1. Overhead:   how much longer the text becomes for secrets of 1 to 10,000 bytes,
                 in English and Arabic mode, with and without a password, and how
                 long hiding and revealing take.
  2. Robustness: which edits of the stego text keep the message readable, for an
                 English and an Arabic cover.
  3. Visibility: whether the visible text is unchanged, for ordinary covers and for
                 covers that already contain invisible characters (emoji, Persian).

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
from common import text_stega as stego

COVER = "Hello there, see you at lunch tomorrow."
ARABIC_COVER = "مرحبا، نلتقي غدا عند الغداء"
SECRET_SIZES = (1, 10, 50, 100, 500, 1000, 5000, 10000)
MODES = (
    ("English", COVER, None),
    ("English + password", COVER, "timing password"),
    ("Arabic", ARABIC_COVER, None),
    ("Arabic + password", ARABIC_COVER, "timing password"),
)


def hidden_count(text: str) -> int:
    """Invisible characters of the hidden message (the cover's own joiners are not counted)."""
    return len(stego.find_hidden(text))


def overhead_table() -> list[dict]:
    rows = []
    for size in SECRET_SIZES:
        secret = "s" * size
        for label, cover, password in MODES:
            hide, show = [], []
            for _ in range(5):
                start = time.perf_counter()
                text = stego.hide(cover, secret, password)
                middle = time.perf_counter()
                assert stego.reveal(text, password) == secret
                hide.append(middle - start)
                show.append(time.perf_counter() - middle)
            cover_bytes = len(cover.encode("utf-8"))
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


def _edits(text: str, other: str) -> dict:
    run = stego.find_hidden(text)
    first = text.index(run)
    return {
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
        "another stego text pasted after it": text + " " + other,
        "one hidden character deleted": text[:first] + text[first + 1:],
        "cut in the middle of the hidden block": text[: first + len(run) // 2],
        "cut after the hidden block": text[: first + len(run) + 3],
        "sent through an ASCII-only system": text.encode("ascii", "ignore").decode("ascii"),
        "non-printable characters removed": "".join(ch for ch in text if ch.isprintable()),
    }


def robustness_table() -> list[dict]:
    secret = "robustness test message"
    english = _edits(stego.hide(COVER, secret), stego.hide("Second sentence here.", "other"))
    arabic = _edits(stego.hide(ARABIC_COVER, secret), stego.hide("جملة ثانية هنا", "other"))
    return [{"edit": name,
             "english_cover": outcome(english[name], secret),
             "arabic_cover": outcome(arabic[name], secret)} for name in english]


def visibility_table() -> list[dict]:
    covers = {
        "English sentence": COVER,
        "one word": "Hello",
        "French with accents": "Ça va très bien, merci beaucoup",
        "Japanese": "今日はいい天気ですね",
        "Arabic sentence": "مرحبا كيف حالك اليوم",
        "emoji joined with U+200D (family)": "Family \U0001F468‍\U0001F469‍\U0001F467 photo attached",
        "Persian word with U+200C": "می‌خواهم بروم",
    }
    rows = []
    for name, cover in covers.items():
        for password in (None, "pw"):
            text = stego.hide(cover, "secret", password)
            mode, _, _ = stego.read_packet(text)
            rows.append({
                "cover": name,
                "password": "yes" if password else "no",
                "mode_chosen": mode,
                "message_recovered": stego.reveal(text, password) == "secret",
                "hidden_characters": hidden_count(text),
                "visible_text_unchanged": stego.strip_hidden(text) == cover,
            })
    return rows


def overhead_chart(rows: list[dict]):
    figure, axes = charts.new_chart(
        "Arabic text needs twice as many invisible characters",
        "Invisible characters added for a secret of each size (log scale)")
    styles = {"English": (charts.BLUE, "-"), "English + password": (charts.BLUE, "--"),
              "Arabic": (charts.ORANGE, "-"), "Arabic + password": (charts.ORANGE, "--")}
    for label, (colour, dash) in styles.items():
        points = [row for row in rows if row["mode"] == label]
        lines = charts.line(axes, [row["secret_bytes"] for row in points],
                            [row["hidden_characters"] for row in points], colour, label)
        lines[0].set_linestyle(dash)
    axes.set_xscale("log")
    axes.set_yscale("log")
    charts.axis_labels(axes, "Secret size (bytes)", "Invisible characters")
    charts.legend(axes, loc="upper left")
    return charts.save(figure, common.RESULTS / "text_overhead.png")


def main():
    print("Evaluating the text carrier (Member 2's text_stega.py, used by the website).")
    print(f"Largest secret: {stego.MAX_SECRET_BYTES:,} bytes, whatever the cover text is.")

    overhead = overhead_table()
    common.write_table("text_overhead", overhead)
    common.print_table(f"Overhead for {COVER!r} and an Arabic sentence", overhead)

    robustness = robustness_table()
    common.write_table("text_robustness", robustness)
    common.print_table("Which edits keep the hidden message readable", robustness)

    visibility = visibility_table()
    common.write_table("text_visibility", visibility)
    common.print_table("Is the visible text unchanged?", visibility)

    print("\nChart:", overhead_chart(overhead).name)
    print(f"\nAll tables are in {common.RESULTS}")


if __name__ == "__main__":
    main()
