"""Capacity and distortion of the image-carrier algorithm (Member 1).

What this script measures:
  1. Capacity:   how many bytes fit in pictures of different sizes.
  2. Distortion: how much the picture changes (MSE, PSNR, SSIM, share of values changed)
                 for messages from 1% to 100% of the capacity, on 14 cover pictures,
                 compared with the classic "sequential LSB" method at the same message size.
  3. Robustness: which edits of the stego picture keep the message readable, and
                 (JPEG) low-quality re-saving on every cover.
  4. Speed:      time to hide and to extract, with and without a password.

Run from the "Member 5" folder:
    python evaluate_images.py
Tables are saved as CSV files and charts as PNG files in the "results" folder.
"""
from __future__ import annotations

import math
import statistics
import time

import numpy as np
from PIL import Image

import charts
import common
from common import image_stego as stego
from common import to_bytes, to_image

TEAM = "texture-adaptive matrix embedding (Member 1)"
BASELINE = "sequential LSB replacement (baseline)"
JPEG = "JPEG DCT coefficients (Member 1)"
PAYLOAD_SHARES = (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 1.00)
SIZES = (
    ("256 x 256", 256, 256),
    ("512 x 512", 512, 512),
    ("960 x 720 (website gallery)", 960, 720),
    ("1920 x 1080 (Full HD)", 1920, 1080),
    ("4032 x 3024 (12 MP phone photo)", 4032, 3024),
)


# -------------------------------------------------------------------- metrics

def ssim(cover: np.ndarray, stego_pixels: np.ndarray, block: int = 8) -> float:
    """Structural similarity of the brightness, averaged over 8x8 blocks. 1.0 means identical."""
    def blocks(rgb):
        grey = rgb[:, :, 0] * 0.299 + rgb[:, :, 1] * 0.587 + rgb[:, :, 2] * 0.114
        rows, columns = grey.shape[0] // block * block, grey.shape[1] // block * block
        tiles = grey[:rows, :columns].reshape(rows // block, block, columns // block, block)
        return tiles.transpose(0, 2, 1, 3).reshape(-1, block * block)

    a, b = blocks(cover.astype(np.float64)), blocks(stego_pixels.astype(np.float64))
    mean_a, mean_b = a.mean(axis=1), b.mean(axis=1)
    covariance = ((a - mean_a[:, None]) * (b - mean_b[:, None])).mean(axis=1)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    score = ((2 * mean_a * mean_b + c1) * (2 * covariance + c2)) / (
        (mean_a ** 2 + mean_b ** 2 + c1) * (a.var(axis=1) + b.var(axis=1) + c2))
    return float(score.mean())


def distortion(cover: np.ndarray, stego_pixels: np.ndarray, hidden_bits: int) -> dict:
    """Compare two pictures given as arrays of RGB values."""
    difference = cover.astype(np.int16) - stego_pixels.astype(np.int16)
    mse = float(np.mean(difference.astype(np.float64) ** 2))
    changed = int(np.count_nonzero(difference))
    return {
        "mse": round(mse, 6),
        "psnr_db": round(10 * math.log10(255 ** 2 / mse), 2) if mse else float("inf"),
        "ssim": round(ssim(cover, stego_pixels), 6),
        "changed_values": changed,
        "changed_percent": round(100 * changed / difference.size, 4),
        "largest_change": int(np.abs(difference).max()),
        "bits_per_change": round(hidden_bits / changed, 2) if changed else float("inf"),
    }


def sequential_lsb(cover: np.ndarray, bit_count: int, rng: np.random.Generator) -> np.ndarray:
    """The textbook method, used only as a comparison: overwrite the last bit of each
    colour value with a message bit, in reading order from the top-left pixel."""
    values = cover.copy().reshape(-1)
    bits = rng.integers(0, 2, bit_count, dtype=np.uint8)
    values[:bit_count] = (values[:bit_count] & 0xFE) | bits
    return values.reshape(cover.shape)


def pixels(data: bytes) -> np.ndarray:
    return np.asarray(to_image(data).convert("RGB"))


# ------------------------------------------------------------------- capacity

def capacity_table() -> list[dict]:
    jpeg = common.jpeg_ready()
    rows = []
    for label, width, height in SIZES:
        image = common.gradient_image(width, height)
        cover = to_bytes(image)
        plain = stego.capacity(cover, "PNG", encrypted=False).max_message_bytes
        locked = stego.capacity(cover, "PNG", encrypted=True).max_message_bytes
        plain_lsb = width * height * 3 // 8
        row = {
            "image_size": label,
            "megapixels": round(width * height / 1e6, 2),
            "capacity_bytes": plain,
            "capacity_bytes_with_password": locked,
            "bits_per_pixel": round(plain * 8 / (width * height), 3),
            "plain_lsb_capacity_bytes": plain_lsb,
            "percent_of_plain_lsb": round(100 * plain / plain_lsb, 1),
        }
        if jpeg:
            jpeg_cover = to_bytes(image, "JPEG", quality=95, subsampling=0)
            row["jpeg_capacity_bytes"] = stego.capacity(jpeg_cover, "JPEG", encrypted=False).max_message_bytes
        rows.append(row)
    return rows


def capacity_by_cover(covers: dict[str, bytes]) -> list[dict]:
    """Does the content of the picture change the capacity? (It should not for PNG.)"""
    jpeg = common.jpeg_ready()
    rows = []
    for name, cover in covers.items():
        report = stego.capacity(cover, "PNG", encrypted=False)
        row = {"cover": name, "width": report.width, "height": report.height, "png_capacity_bytes": report.max_message_bytes}
        if jpeg:
            jpeg_cover = to_bytes(to_image(cover).convert("RGB"), "JPEG", quality=95, subsampling=0)
            row["jpeg_capacity_bytes"] = stego.capacity(jpeg_cover, "JPEG", encrypted=False).max_message_bytes
        rows.append(row)
    return rows


# ----------------------------------------------------------------- distortion

def distortion_table(covers: dict[str, bytes]) -> list[dict]:
    rng = np.random.default_rng(455)
    rows = []
    for name, cover in covers.items():
        original = pixels(cover)
        limit = stego.capacity(cover, "PNG", encrypted=False).max_message_bytes
        for share in PAYLOAD_SHARES:
            size = max(1, int(limit * share))
            message = rng.integers(0, 256, size, dtype=np.uint8).tobytes()
            # Header, message and 4-byte check are all written into the picture.
            hidden_bits = (stego.HEADER_BYTES + size + 4) * 8
            common_columns = {"cover": name, "payload_percent_of_capacity": round(share * 100), "payload_bytes": size}

            result = stego.embed(cover, message)
            assert stego.extract(result.image) == message
            rows.append({**common_columns, "method": TEAM, **distortion(original, pixels(result.image), hidden_bits)})

            baseline = sequential_lsb(original, hidden_bits, rng)
            rows.append({**common_columns, "method": BASELINE, **distortion(original, baseline, hidden_bits)})
    return rows


def jpeg_distortion_table(covers: dict[str, bytes]) -> list[dict]:
    """Same measurement for JPEG output. Only runs when Member 1's JPEG helper is built."""
    rng = np.random.default_rng(455)
    rows = []
    for name, cover in covers.items():
        jpeg_cover = to_bytes(to_image(cover).convert("RGB"), "JPEG", quality=95, subsampling=0)
        original = pixels(jpeg_cover)
        limit = stego.capacity(jpeg_cover, "JPEG", encrypted=False).max_message_bytes
        if limit < 1:
            continue
        for share in (0.10, 0.50, 1.00):
            size = max(1, int(limit * share))
            message = rng.integers(0, 256, size, dtype=np.uint8).tobytes()
            hidden_bits = (stego.HEADER_BYTES + size + 4) * 8
            result = stego.embed(jpeg_cover, message, output_format="JPEG")
            measured = distortion(original, pixels(result.image), hidden_bits)
            # One changed DCT coefficient alters all 64 pixels of its block, so "bits per changed
            # pixel value" does not describe this method and is left empty.
            measured["bits_per_change"] = ""
            rows.append({"cover": name, "payload_percent_of_capacity": round(share * 100), "payload_bytes": size,
                         "method": JPEG, **measured})
    return rows


def summarise(rows: list[dict]) -> list[dict]:
    """Average over the cover pictures, one row per message size and method."""
    summary = []
    for share in sorted({row["payload_percent_of_capacity"] for row in rows}):
        for method in dict.fromkeys(row["method"] for row in rows):
            group = [r for r in rows if r["payload_percent_of_capacity"] == share and r["method"] == method]
            if not group:
                continue
            summary.append({
                "payload_percent_of_capacity": share,
                "method": method,
                "covers": len(group),
                "mean_psnr_db": round(statistics.mean(r["psnr_db"] for r in group), 2),
                "lowest_psnr_db": min(r["psnr_db"] for r in group),
                "mean_ssim": round(statistics.mean(r["ssim"] for r in group), 6),
                "mean_changed_percent": round(statistics.mean(r["changed_percent"] for r in group), 4),
                "largest_change": max(r["largest_change"] for r in group),
                "mean_bits_per_change": (round(statistics.mean(r["bits_per_change"] for r in group), 2)
                                         if all(r["bits_per_change"] != "" for r in group) else ""),
            })
    return summary


# ----------------------------------------------------------------- robustness

def outcome(candidate: bytes, message: bytes) -> str:
    try:
        recovered = stego.extract(candidate)
    except stego.StegoError as error:
        return f"rejected ({type(error).__name__})"
    return "message recovered" if recovered == message else "WRONG MESSAGE RETURNED"


def robustness_table() -> list[dict]:
    message = b"robustness test message"
    cover = to_bytes(common.gradient_image(512, 384))
    image = to_image(stego.embed(cover, message).image)
    brighter = Image.fromarray(np.clip(np.asarray(image).astype(np.int16) + 1, 0, 255).astype(np.uint8))
    edits = {
        "no change (the downloaded file)": to_bytes(image),
        "saved again as PNG": to_bytes(image, optimize=True, compress_level=9),
        "converted to BMP": to_bytes(image, "BMP"),
        "alpha channel added": to_bytes(image.convert("RGBA")),
        "saved as JPEG (quality 95)": to_bytes(image, "JPEG", quality=95),
        "cropped by one column": to_bytes(image.crop((1, 0, image.width, image.height))),
        "resized to 50%": to_bytes(image.resize((image.width // 2, image.height // 2))),
        "rotated 90 degrees": to_bytes(image.rotate(90, expand=True)),
        "mirrored": to_bytes(image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)),
        "brightness +1": to_bytes(brighter),
        "converted to greyscale": to_bytes(image.convert("L")),
    }
    rows = [{"stego_format": "PNG", "edit": name, "result": outcome(data, message)} for name, data in edits.items()]

    if common.jpeg_ready():
        jpeg_cover = to_bytes(common.gradient_image(512, 384), "JPEG", quality=95, subsampling=0)
        downloaded = stego.embed(jpeg_cover, message, output_format="JPEG").image
        jpeg = to_image(downloaded)
        jpeg_edits = {"no change (the downloaded file)": downloaded}
        for quality in (95, 85, 75, 60, 40, 20):
            jpeg_edits[f"saved again as JPEG (quality {quality})"] = to_bytes(jpeg, "JPEG", quality=quality, subsampling=2)
        jpeg_edits["resized to 75%"] = to_bytes(jpeg.resize((jpeg.width * 3 // 4, jpeg.height * 3 // 4)), "JPEG", quality=90)
        jpeg_edits["converted to PNG"] = to_bytes(jpeg)
        rows += [{"stego_format": "JPEG", "edit": name, "result": outcome(data, message)} for name, data in jpeg_edits.items()]
    return rows


def jpeg_resave_by_cover(covers: dict[str, bytes]) -> list[dict]:
    """Low-quality JPEG re-saving on every cover. Only runs when Member 1's JPEG helper is built."""
    message = b"robustness test message"
    rows = []
    for name, cover in covers.items():
        jpeg_cover = to_bytes(to_image(cover).convert("RGB"), "JPEG", quality=95, subsampling=0)
        if stego.capacity(jpeg_cover, "JPEG", encrypted=False).max_message_bytes < len(message):
            continue
        jpeg = to_image(stego.embed(jpeg_cover, message, output_format="JPEG").image)
        row = {"cover": name}
        for quality in (40, 30, 20):
            row[f"saved_again_at_quality_{quality}"] = outcome(
                to_bytes(jpeg, "JPEG", quality=quality, subsampling=2), message)
        rows.append(row)
    return rows


# ---------------------------------------------------------------------- speed

def timing_table(cover: bytes) -> list[dict]:
    message = b"m" * 100
    rows = []
    for label, password in (("no password", None), ("with password", "timing password")):
        hide, show = [], []
        for _ in range(11):
            start = time.perf_counter()
            result = stego.embed(cover, message, password=password)
            middle = time.perf_counter()
            stego.extract(result.image, password=password)
            hide.append(middle - start)
            show.append(time.perf_counter() - middle)
        rows.append({"mode": label, "hide_ms": round(statistics.median(hide) * 1000, 1),
                     "extract_ms": round(statistics.median(show) * 1000, 1)})
    return rows


# --------------------------------------------------------------------- charts

def quality_chart(summary: list[dict]):
    figure, axes = charts.new_chart(
        "Image quality stays high, and beats plain LSB at every message size",
        "Mean PSNR over the cover pictures (higher is better; above about 40 dB a change is not visible)")
    ends = []
    for method, colour, label in ((TEAM, charts.BLUE, "Team's method"), (BASELINE, charts.ORANGE, "Sequential LSB")):
        points = [row for row in summary if row["method"] == method]
        x = [row["payload_percent_of_capacity"] for row in points]
        y = [row["mean_psnr_db"] for row in points]
        charts.line(axes, x, y, colour, label)
        ends.append((x[-1], y[-1]))
    axes.set_xscale("log")
    axes.set_xticks([1, 5, 10, 25, 50, 100], ["1%", "5%", "10%", "25%", "50%", "100%"])
    axes.minorticks_off()
    axes.set_xlim(0.8, 185)
    for (x, y), offset in zip(ends, (5, -5)):
        axes.annotate(f"{y:.1f} dB", (x, y), xytext=(9, offset), textcoords="offset points",
                      fontsize=9.5, color=charts.INK, va="center")
    charts.axis_labels(axes, "Message size (share of the picture's capacity)", "PSNR (dB)")
    charts.legend(axes, loc="lower left")
    return charts.save(figure, common.RESULTS / "image_quality_vs_payload.png")


def capacity_chart(rows: list[dict]):
    figure, axes = charts.new_chart(
        "Capacity grows in proportion to the number of pixels",
        "Largest message without a password, PNG or BMP output", height=3.9)
    labels = [row["image_size"] for row in rows]
    values = [row["capacity_bytes"] / 1000 for row in rows]
    axes.barh(labels, values, height=0.42, color=charts.BLUE)
    axes.invert_yaxis()
    axes.grid(axis="y", visible=False)
    axes.grid(axis="x", color=charts.GRID, linewidth=0.8)
    axes.spines["bottom"].set_visible(False)
    axes.tick_params(axis="y", labelsize=9.5, colors=charts.INK_SECONDARY)
    axes.set_xlim(0, max(values) * 1.16)
    for position, value in enumerate(values):
        axes.text(value + max(values) * 0.012, position, f"{value:,.1f} KB", va="center", fontsize=9.5, color=charts.INK)
    charts.axis_labels(axes, "Capacity (thousand bytes)")
    figure.subplots_adjust(left=0.36, top=0.78, bottom=0.17)
    return charts.save(figure, common.RESULTS / "image_capacity_by_size.png")


def main():
    covers = {**common.synthetic_covers(), **common.gallery_covers()}
    print(f"Evaluating the image algorithm on {len(covers)} cover pictures "
          f"(JPEG output {'included' if common.jpeg_ready() else 'skipped: helper not built'}).")

    sizes = capacity_table()
    common.write_table("image_capacity", sizes)
    common.print_table("Capacity by image size", sizes)
    by_cover = capacity_by_cover(covers)
    common.write_table("image_capacity_by_cover", by_cover)

    rows = distortion_table(covers)
    if common.jpeg_ready():
        rows += jpeg_distortion_table(covers)
    common.write_table("image_distortion", rows)
    summary = summarise(rows)
    common.write_table("image_distortion_summary", summary)
    common.print_table("Distortion, averaged over the cover pictures", summary)

    robustness = robustness_table()
    common.write_table("image_robustness", robustness)
    common.print_table("Which edits keep the hidden message readable", robustness)
    if common.jpeg_ready():
        resave = jpeg_resave_by_cover(covers)
        common.write_table("image_jpeg_resave_by_cover", resave)
        common.print_table("Stego JPEG saved again at low quality, on every cover", resave)

    gallery = common.gallery_covers()
    speed = timing_table(next(iter(gallery.values())) if gallery else to_bytes(common.gradient_image(960, 720)))
    common.write_table("image_timing", speed)
    common.print_table("Speed for a 100-byte message in a 960 x 720 picture (median of 11 runs)", speed)

    print("\nCharts:", quality_chart(summary).name, "and", capacity_chart(sizes).name)
    print('All tables and charts are in the "results" folder.')


if __name__ == "__main__":
    main()
