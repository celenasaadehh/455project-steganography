"""Shared helpers for the Member 5 tests and experiments.

Importing this module makes Member 1's ``image_stego``, Member 2's
``text_stego`` and the ``Text Steganography`` folder's ``text_stega``
importable, so everything in this folder runs against the real code in the
team repository and never against a copy.
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MEMBER1 = REPO / "Member 1"
MEMBER2 = REPO / "Member 2"
MEMBER4 = REPO / "Member 4"
TEXT_FOLDER = REPO / "Text Steganography"
GALLERY = MEMBER2 / "static" / "gallery"
RESULTS = HERE / "results"

for _folder in (MEMBER1, MEMBER2):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))

import image_stego  # noqa: E402  (Member 1)
import text_stego  # noqa: E402  (Member 2, used by the website)


def _load_text_stega():
    """The second text algorithm, in the "Text Steganography" folder. None if the folder is missing."""
    path = TEXT_FOLDER / "text_stega.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("text_stega", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


text_stega = _load_text_stega()


def letter_paragraph(letters: int) -> str:
    """An ordinary-looking English paragraph with exactly `letters` English letters (A-Z, a-z)."""
    words = ("the", "weekly", "meeting", "is", "moved", "to", "thursday", "afternoon", "in", "main", "hall",
             "please", "bring", "your", "notes", "and", "laptop")
    out, count, index = [], 0, 0
    while count < letters:
        word = words[index % len(words)][: letters - count]
        out.append(word)
        count += len(word)
        index += 1
    return (" ".join(out).capitalize() + ".") if out else "."


# ----------------------------------------------------------------- image files

def to_bytes(image: Image.Image, fmt: str = "PNG", **options) -> bytes:
    """Encode a Pillow image as the bytes of a PNG/BMP/JPEG file."""
    buffer = BytesIO()
    image.save(buffer, fmt, **options)
    return buffer.getvalue()


def to_image(data: bytes) -> Image.Image:
    image = Image.open(BytesIO(data))
    image.load()
    return image


def to_array(data: bytes) -> np.ndarray:
    """Decoded RGB values of an image file, as signed integers so they can be subtracted."""
    return np.asarray(to_image(data).convert("RGB")).astype(np.int16)


# ------------------------------------------------------------- synthetic covers
# The covers are generated from formulas, so every run and every machine tests
# exactly the same pixels and no personal photo has to be stored in the repository.

def gradient_image(width: int = 256, height: int = 192) -> Image.Image:
    """Smooth colour ramps: little texture, similar to sky or a wall."""
    y, x = np.indices((height, width))
    pixels = np.stack([(x + 2 * y) % 256, (2 * x + y) % 256, ((x + y) // 2) % 256], axis=-1)
    return Image.fromarray(pixels.astype(np.uint8))


def noise_image(width: int = 256, height: int = 192, seed: int = 455) -> Image.Image:
    """Random pixels: the most textured cover possible."""
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0, 256, (height, width, 3), dtype=np.uint8))


def flat_image(width: int = 256, height: int = 192, colour=(120, 130, 140)) -> Image.Image:
    """One solid colour: no texture at all, the hardest case for a texture-adaptive method."""
    return Image.new("RGB", (width, height), colour)


def checker_image(width: int = 256, height: int = 192, square: int = 16) -> Image.Image:
    """Black and white squares: only two colours and very sharp edges."""
    y, x = np.indices((height, width))
    board = (((x // square) + (y // square)) % 2 * 255).astype(np.uint8)
    return Image.fromarray(np.stack([board, board, board], axis=-1))


def synthetic_covers() -> dict[str, bytes]:
    return {
        "gradient": to_bytes(gradient_image()),
        "noise": to_bytes(noise_image()),
        "flat": to_bytes(flat_image()),
        "checkerboard": to_bytes(checker_image()),
    }


def gallery_covers() -> dict[str, bytes]:
    """The ten pictures of the website's built-in gallery (Member 2), if they are present."""
    return {path.stem.split("-", 1)[1]: path.read_bytes() for path in sorted(GALLERY.glob("[0-9][0-9]-*.png"))}


# ------------------------------------------------------------------ JPEG helper

def jpeg_ready() -> bool:
    """True when Member 1's JPEG helper program has been built on this machine.

    PNG and BMP need nothing extra. JPEG needs the small C program described in
    Member 1's technical guide; without it the JPEG tests are skipped.
    """
    try:
        image_stego.capacity(to_bytes(gradient_image(64, 64)), "JPEG")
    except image_stego.DependencyError:
        return False
    return True


# ---------------------------------------------------------------- result tables

def write_table(name: str, rows: list[dict]) -> Path:
    """Save rows as results/<name>.csv (opens in Excel) and return the path."""
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def print_table(title: str, rows: list[dict], columns: list[str] | None = None) -> None:
    """Print rows as an aligned text table."""
    columns = columns or list(rows[0])
    cells = [[str(row[column]) for column in columns] for row in rows]
    widths = [max(len(column), *(len(line[i]) for line in cells)) for i, column in enumerate(columns)]
    print(f"\n{title}")
    print("  " + "  ".join(column.ljust(width) for column, width in zip(columns, widths)))
    print("  " + "  ".join("-" * width for width in widths))
    for line in cells:
        print("  " + "  ".join(cell.ljust(width) for cell, width in zip(line, widths)))
