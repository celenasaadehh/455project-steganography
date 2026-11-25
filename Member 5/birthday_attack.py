"""Birthday attack experiment.

The birthday paradox: in a group of only 23 people, two of them share a birthday
with a probability above 50%, although a year has 365 days. A check value of n
bits behaves the same way. It has 2^n possible values, but two different
messages with the same check value (a collision) appear after about 2^(n/2)
messages, not 2^n.

Why this matters for our project: without a password, both carriers protect the
hidden message with a CRC-32 checksum, which has 32 bits. With a password they
use AES-256-GCM, whose authentication tag has 128 bits and depends on the key.

  Part 1  Count how many random messages are needed before two collide, for
          check values of 8 to 32 bits, and compare with the theory.
  Part 2  Repeat for CRC-32, the checksum the project really uses, and measure
          the probability of a collision against the number of messages.
  Part 3  Use the attack on the project: prepare a harmless and a harmful
          message with the same CRC-32, hide the harmless one with the team's
          code, swap in the harmful one, and check that reveal() and extract()
          accept it. Then change one encrypted value of a password-protected
          message and check that the password check rejects it.
  Part 4  Estimate the work needed for larger check values.

Run from the "Member 5" folder:
    python birthday_attack.py            (about half a minute)
    python birthday_attack.py --runs 30  (a few seconds, less precise)
Tables, charts and a log of the output are saved in the "results" folder.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import random
import statistics
import time
import zlib

import numpy as np

import charts
import common
from common import image_stego, text_stego, to_array, to_bytes

DIGEST_BITS = (8, 12, 16, 20, 24, 28, 32)
HARMLESS = "Meeting moved to 5 pm, room 204."
HARMFUL = "Send me all the exam answers now"
CODE_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


# --------------------------------------------------------------------- theory

def expected_tries(values: float) -> float:
    """Average number of random draws until the first repeat, with `values` equally likely outcomes."""
    return math.sqrt(math.pi * values / 2) + 2 / 3


def tries_for_half(values: float) -> float:
    """Number of random draws that gives a 50% chance of at least one repeat."""
    return math.sqrt(2 * math.log(2) * values)


def collision_probability(count: int, values: float) -> float:
    """Chance that `count` random draws out of `values` outcomes contain at least one repeat."""
    return 1 - math.exp(-count * (count - 1) / (2 * values))


# ------------------------------------------------------------- check functions

def truncated_sha256(bits: int):
    """SHA-256 cut down to its first `bits` bits: a well-mixed check value of any size we want."""
    def digest(message: bytes) -> int:
        return int.from_bytes(hashlib.sha256(message).digest(), "big") >> (256 - bits)
    return digest


def crc32(message: bytes) -> int:
    """The checksum both carriers use when no password is set."""
    return zlib.crc32(message)


# ------------------------------------------------------------------ the attack

def first_collision(digest, rng: random.Random):
    """Draw random 16-byte messages until two different ones have the same check value.

    Returns (number of messages drawn, first message, second message).
    """
    seen = {}
    count = 0
    while True:
        message = rng.randbytes(16)
        count += 1
        value = digest(message)
        earlier = seen.get(value)
        if earlier is not None and earlier != message:
            return count, earlier, message
        seen[value] = message


def measure(digest, runs: int, rng: random.Random) -> list[int]:
    return [first_collision(digest, rng)[0] for _ in range(runs)]


def with_code(text: str, rng: random.Random) -> str:
    """A version of the message that differs only in a meaningless reference code."""
    return f"{text} [ref {''.join(rng.choices(CODE_LETTERS, k=8))}]"


def meaningful_collision(harmless: str, harmful: str, rng: random.Random, table_size: int = 2 ** 17):
    """Find a version of each message such that both versions have the same CRC-32.

    This is the practical form of the birthday attack: store the checksums of many
    versions of the harmless message, then try versions of the harmful message
    until one of them lands on a stored checksum.
    Returns (harmless version, harmful version, number of checksums computed).
    """
    assert len(harmless.encode("utf-8")) == len(harmful.encode("utf-8")), "both messages must have the same length"
    table = {}
    for _ in range(table_size):
        version = with_code(harmless, rng)
        table[crc32(version.encode("utf-8"))] = version
    tries = table_size
    while True:
        version = with_code(harmful, rng)
        tries += 1
        match = table.get(crc32(version.encode("utf-8")))
        if match is not None:
            return match, version, tries


# ------------------------------------------------- swapping the hidden message
# The attacker is assumed to know how the algorithms work (the code is public),
# but not any password.

def _symbols_to_bytes(symbols: str) -> bytes:
    values = [text_stego.SYMBOLS.index(ch) for ch in symbols]
    return bytes((values[i] << 6) | (values[i + 1] << 4) | (values[i + 2] << 2) | values[i + 3]
                 for i in range(0, len(values), 4))


def _bytes_to_symbols(data: bytes) -> str:
    return "".join(text_stego.SYMBOLS[(byte >> shift) & 3] for byte in data for shift in (6, 4, 2, 0))


def swap_in_text(stego_text: str, old: str, new: str) -> str:
    """Replace the hidden message of an unprotected stego text and keep its checksum."""
    hidden = "".join(ch for ch in stego_text if ch in text_stego.SYMBOLS)
    payload = _symbols_to_bytes(hidden)              # format header | message | 4-byte CRC-32
    assert payload[4:-4] == old.encode("utf-8")
    forged = payload[:4] + new.encode("utf-8") + payload[-4:]
    start = stego_text.index(hidden[0])
    return stego_text[:start] + _bytes_to_symbols(forged) + stego_text[start + len(hidden):]


def swap_in_image(stego_png: bytes, old: bytes, new: bytes) -> bytes:
    """Replace the hidden message of an unprotected stego PNG and keep its checksum."""
    picture, _, _ = image_stego._load(stego_png)
    codec = image_stego._Spatial(picture)
    header = codec.read(image_stego.HEADER_BYTES, image_stego._HSEED, header=True)
    salt = image_stego._HEADER.unpack(header[:-4])[5]
    _, route = image_stego._keys(None, salt)         # without a password the positions are public
    body = codec.read(len(old) + 4, route)           # message | 4-byte CRC-32
    assert body[:-4] == old
    codec.write(new + body[-4:], route)
    return codec.render("PNG")


# --------------------------------------------------------------------- report

class Report:
    """Prints every line and keeps it, so the output can be saved next to the tables."""

    def __init__(self):
        self.lines = []

    def __call__(self, text: str = ""):
        print(text)
        self.lines.append(text)

    def table(self, title: str, rows: list[dict]):
        columns = list(rows[0])
        cells = [[str(row[column]) for column in columns] for row in rows]
        widths = [max(len(column), *(len(line[i]) for line in cells)) for i, column in enumerate(columns)]
        self("")
        self(title)
        self("  " + "  ".join(column.ljust(width) for column, width in zip(columns, widths)))
        self("  " + "  ".join("-" * width for width in widths))
        for line in cells:
            self("  " + "  ".join(cell.ljust(width) for cell, width in zip(line, widths)))

    def save(self, name: str):
        common.RESULTS.mkdir(exist_ok=True)
        (common.RESULTS / name).write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def duration(seconds: float) -> str:
    if seconds < 1:
        return "under a second"
    for unit, size in (("seconds", 60), ("minutes", 60), ("hours", 24), ("days", 365.25)):
        if seconds < size:
            return f"{seconds:.0f} {unit}"
        seconds /= size
    return f"{seconds:,.0f} years" if seconds < 1e6 else f"{seconds:.1e} years"


# ---------------------------------------------------------------------- parts

def part_1(say: Report, runs: int, rng: random.Random) -> list[dict]:
    say("PART 1  How many messages until two have the same check value?")
    say(f"        Random 16-byte messages, SHA-256 cut to n bits, {runs} runs per size.")
    rows = []
    for bits in DIGEST_BITS:
        counts = measure(truncated_sha256(bits), runs, rng)
        theory = expected_tries(2 ** bits)
        rows.append({
            "check_value_bits": bits,
            "possible_values": 2 ** bits,
            "runs": runs,
            "measured_mean_tries": round(statistics.mean(counts), 1),
            "measured_median_tries": round(statistics.median(counts), 1),
            "theory_mean_tries": round(theory, 1),
            "measured_over_theory": round(statistics.mean(counts) / theory, 3),
        })
    say.table("Tries until the first collision", rows)
    return rows


def part_2(say: Report, runs: int, rng: random.Random):
    say("")
    say("PART 2  The project's own checksum: CRC-32")
    start = time.perf_counter()
    counts = measure(crc32, runs, rng)
    rate = sum(counts) / (time.perf_counter() - start)
    values = 2 ** 32
    say(f"        {runs} runs. Mean {statistics.mean(counts):,.0f} messages until the first collision "
        f"(theory {expected_tries(values):,.0f}).")
    say(f"        Half of the runs had a collision within {statistics.median(counts):,.0f} messages "
        f"(theory {tries_for_half(values):,.0f}).")
    say(f"        A full search of all 2^32 = {values:,} values was never needed.")
    count, first, second = first_collision(crc32, rng)
    say(f"        Example: {first.hex()} and {second.hex()} both have CRC-32 {crc32(first):08x} "
        f"(found after {count:,} messages).")

    ordered = np.sort(np.array(counts))
    grid = np.linspace(0, 250_000, 26).astype(int)
    curve = [{"messages": int(k),
              "measured_probability": round(float(np.searchsorted(ordered, k, side="right")) / runs, 4),
              "theory_probability": round(collision_probability(int(k), values), 4)} for k in grid]
    summary = {
        "check_value_bits": "32 (CRC-32)", "possible_values": values, "runs": runs,
        "measured_mean_tries": round(statistics.mean(counts), 1),
        "measured_median_tries": round(statistics.median(counts), 1),
        "theory_mean_tries": round(expected_tries(values), 1),
        "measured_over_theory": round(statistics.mean(counts) / expected_tries(values), 3),
    }
    return summary, curve, ordered, rate


def part_3(say: Report, rng: random.Random) -> dict:
    say("")
    say("PART 3  Using the attack on our own steganography (no password)")
    start = time.perf_counter()
    harmless, harmful, tries = meaningful_collision(HARMLESS, HARMFUL, rng)
    elapsed = time.perf_counter() - start
    checksum = crc32(harmless.encode("utf-8"))
    say(f"        Harmless message: {harmless!r}")
    say(f"        Harmful message:  {harmful!r}")
    say(f"        Both have CRC-32 {checksum:08x}. Found with {tries:,} checksums in {elapsed:.2f} s.")
    outcome = {"harmless": harmless, "harmful": harmful, "crc32": f"{checksum:08x}", "checksums_computed": tries}

    # Text carrier (Member 2)
    cover_text = "Hello there, see you at lunch tomorrow."
    stego_text = text_stego.hide(cover_text, harmless)
    forged_text = swap_in_text(stego_text, harmless, harmful)
    revealed = text_stego.reveal(forged_text)
    outcome["text_swap_accepted"] = revealed == harmful
    say("")
    say("        Text carrier: hide the harmless message, then swap the hidden bytes and keep the checksum.")
    say(f"          reveal() before the swap: {text_stego.reveal(stego_text)!r}")
    say(f"          reveal() after the swap:  {revealed!r}")
    say(f"          visible text unchanged:   {text_stego.strip_hidden(forged_text) == cover_text}")
    say(f"          -> swap {'ACCEPTED, no error' if outcome['text_swap_accepted'] else 'rejected'}")

    # Image carrier (Member 1)
    cover_image = to_bytes(common.gradient_image())
    stego_image = image_stego.embed(cover_image, harmless).image
    forged_image = swap_in_image(stego_image, harmless.encode("utf-8"), harmful.encode("utf-8"))
    extracted = image_stego.extract(forged_image).decode("utf-8")
    outcome["image_swap_accepted"] = extracted == harmful
    say("")
    say("        Image carrier: same idea on a PNG produced by embed().")
    say(f"          extract() before the swap: {image_stego.extract(stego_image).decode('utf-8')!r}")
    say(f"          extract() after the swap:  {extracted!r}")
    say(f"          -> swap {'ACCEPTED, no error' if outcome['image_swap_accepted'] else 'rejected'}")

    # Password-protected messages: change one encrypted value (never the header)
    say("")
    # With a password the encrypted part is protected by an AES-GCM tag that depends on the key.
    # These checks change one value of the ENCRYPTED part, never the public header (protected by its
    # own CRC-32 in the image carrier, and by format checks plus the AES-GCM associated data in the
    # text carrier), so a rejection here comes from the password-based check.
    say("        With a password (AES-256-GCM: the check depends on the key and cannot be recomputed):")
    locked_text = text_stego.hide(cover_text, harmless, "course password")
    hidden = [i for i, ch in enumerate(locked_text) if ch in text_stego.SYMBOLS]
    position = hidden[4 * 30]                         # first character of the encrypted message (after TL, salt, nonce)
    other = next(ch for ch in text_stego.SYMBOLS if ch != locked_text[position])
    try:
        text_stego.reveal(locked_text[:position] + other + locked_text[position + 1:], "course password")
        outcome["locked_text_change_rejected"] = False
    except text_stego.TextPasswordError:
        outcome["locked_text_change_rejected"] = True
    say(f"          text carrier, one encrypted character changed:   "
        f"{'rejected by the password check' if outcome['locked_text_change_rejected'] else 'ACCEPTED'}")

    locked_image = image_stego.embed(cover_image, harmless, password="course password").image
    before, after = to_array(cover_image), to_array(locked_image)
    picture, _, _ = image_stego._load(locked_image)
    header = set(image_stego._Spatial(picture)._indices(image_stego.HEADER_BYTES, image_stego._HSEED,
                                                        header=True).ravel().tolist())
    changed = [int(i) for i in np.flatnonzero(before.reshape(-1) != after.reshape(-1)) if int(i) not in header]
    flat = after.reshape(-1)
    flat[changed[len(changed) // 2]] = before.reshape(-1)[changed[len(changed) // 2]]
    try:
        image_stego.extract(to_bytes(common.Image.fromarray(after.astype(np.uint8))), password="course password")
        outcome["locked_image_change_rejected"] = False
    except image_stego.PasswordError:
        outcome["locked_image_change_rejected"] = True
    say(f"          image carrier, one encrypted value changed:       "
        f"{'rejected by the password check' if outcome['locked_image_change_rejected'] else 'ACCEPTED'}")
    say("")
    say("        Note: without a password the CRC-32 has no key and is stored with the message, so an attacker")
    say("        does not even need a collision: they can compute a new checksum or simply hide a new message.")
    say("        The collision shows that even a checksum value the receiver already trusts cannot prove which")
    say("        message was hidden. With a password, what protects the message is the key, not the tag length.")
    return outcome


def part_4(say: Report, rate: float) -> list[dict]:
    say("")
    say("PART 4  What a longer check value buys")
    rows = []
    for bits, where in ((32, "CRC-32: both carriers without a password"),
                        (64, "a 64-bit check value"),
                        (128, "AES-GCM tag: both carriers with a password"),
                        (256, "SHA-256")):
        tries = tries_for_half(2 ** bits)
        rows.append({
            "check_value_bits": bits,
            "used_for": where,
            "tries_for_50_percent": f"{tries:,.0f}" if tries < 1e12 else f"{tries:.2e}",
            "time_on_this_laptop": duration(tries / rate),
            "time_at_one_billion_per_second": duration(tries / 1e9),
        })
    say.table(f"Work for a 50% chance of a collision (this laptop: {rate:,.0f} checksums per second in Python)", rows)
    say("")
    say("        Each extra bit of check value multiplies the work by 1.41; doubling the size squares it.")
    say("        The GCM tag also depends on the secret key, so an attacker cannot even compute it offline.")
    return rows


# --------------------------------------------------------------------- charts

def tries_chart(rows: list[dict]):
    figure, axes = charts.new_chart(
        "A collision needs about 2^(n/2) messages, not 2^n",
        "Random messages drawn until two share an n-bit check value (mean of the runs, logarithmic scale)")
    bits = [row["check_value_bits"] for row in rows]
    smooth = np.linspace(bits[0], bits[-1], 100)
    axes.plot(smooth, [expected_tries(2 ** b) for b in smooth], color=charts.ORANGE, linewidth=2,
              label="Theory: 1.25 x 2^(n/2)", solid_capstyle="round")
    axes.plot(bits, [row["measured_mean_tries"] for row in rows], color=charts.BLUE, linestyle="none", marker="o",
              markersize=8, markeredgecolor=charts.SURFACE, markeredgewidth=1.5, label="Measured")
    axes.set_yscale("log")
    axes.set_yticks([10, 100, 1_000, 10_000, 100_000], ["10", "100", "1,000", "10,000", "100,000"])
    axes.minorticks_off()
    axes.set_xticks(bits)
    last = rows[-1]
    axes.text(32, 5_000, f"32 bits: {last['measured_mean_tries']:,.0f} messages", ha="right", va="center",
              fontsize=9.5, color=charts.INK)
    charts.axis_labels(axes, "Size of the check value (bits)", "Messages until the first collision")
    charts.legend(axes, loc="upper left")
    return charts.save(figure, common.RESULTS / "birthday_tries_vs_bits.png")


def probability_chart(ordered: np.ndarray):
    values = 2 ** 32
    half = tries_for_half(values)
    figure, axes = charts.new_chart(
        "CRC-32: a collision is more likely than not after 77 thousand messages",
        f"Share of {len(ordered)} runs that had found two messages with the same CRC-32")
    grid = np.linspace(0, 250_000, 400)
    axes.plot(grid, [100 * collision_probability(int(k), values) for k in grid], color=charts.ORANGE, linewidth=2,
              label="Theory", solid_capstyle="round")
    axes.plot(grid, 100 * np.searchsorted(ordered, grid, side="right") / len(ordered), color=charts.BLUE,
              linewidth=2, label="Measured", solid_joinstyle="round")
    axes.plot([half], [50], linestyle="none", marker="o", markersize=8, color=charts.INK,
              markeredgecolor=charts.SURFACE, markeredgewidth=1.5)
    axes.annotate(f"50% at {half:,.0f} messages", (half, 50), xytext=(12, -6), textcoords="offset points",
                  fontsize=9.5, color=charts.INK, va="top")
    axes.set_ylim(0, 100)
    axes.set_xlim(0, 250_000)
    axes.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    axes.set_xticks([0, 50_000, 100_000, 150_000, 200_000, 250_000], ["0", "50,000", "100,000", "150,000", "200,000", "250,000"])
    charts.axis_labels(axes, "Number of random messages", "Probability of a collision")
    charts.legend(axes, loc="lower right")
    return charts.save(figure, common.RESULTS / "birthday_crc32_probability.png")


def main():
    parser = argparse.ArgumentParser(description="Birthday attack experiment")
    parser.add_argument("--runs", type=int, default=300, help="repetitions per measurement (default 300)")
    parser.add_argument("--seed", type=int, default=455, help="seed of the random generator, for repeatable results")
    args = parser.parse_args()
    rng = random.Random(args.seed)
    say = Report()

    say("Birthday attack experiment")
    say(f"Warm-up: 23 people, 365 days -> chance of a shared birthday {collision_probability(23, 365):.0%}.")
    say("")
    rows = part_1(say, args.runs, rng)
    crc_row, curve, ordered, rate = part_2(say, args.runs * 2, rng)
    demo = part_3(say, rng)
    estimates = part_4(say, rate)

    common.write_table("birthday_digest_sizes", rows + [crc_row])
    common.write_table("birthday_crc32_probability", curve)
    common.write_table("birthday_attack_on_project", [demo])
    common.write_table("birthday_time_estimates", estimates)
    say("")
    say(f"Charts: {tries_chart(rows).name} and {probability_chart(ordered).name}")
    say('All tables and charts are in the "results" folder.')
    say.save("birthday_attack_log.txt")


if __name__ == "__main__":
    main()
