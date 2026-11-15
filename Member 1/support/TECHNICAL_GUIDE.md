# Image Stego Lab | Member 1

A Python backend and command-line tool for a **cryptography and digital-forensics teaching lab**. Students can hide and recover a short clue, compare two embedding methods, and test what happens when an image is edited or transmitted. This package is the image component, not the team’s web UI or text-carrier algorithm.

## Start here

| Input cover | Choose this output | How it works |
|---|---|---|
| PNG, BMP, JPEG, HEIC/HEIF | **PNG** (recommended default) | Texture-adaptive spatial matrix embedding. Preserves 8-bit alpha; unchanged RGB values survive lossless PNG re-saving. |
| Same inputs, opaque only | **BMP** | Same spatial algorithm in a lossless bitmap; larger files, useful for comparison. |
| Same inputs, opaque only | **JPEG** | Edits real luminance DCT coefficients through libjpeg. Quantization index modulation (QIM), dithering and error correction give small messages a degree of recompression tolerance. |

HEIC/HEIF is **input only**: the primary still image is decoded to 8-bit RGB(A) and embedded in the selected output format. No depth data, HDR preservation or HEIC-native payload is promised. BMP/JPEG cannot preserve transparency in this implementation. Use PNG for transparent images. Any preprocessing for JPEG is performed **before** embedding. An ordinary suitable JPEG is edited directly; non-JPEG input, EXIF-rotated JPEG, and JPEG with unsuitable quantization or colorspace are normalized first. The API reports this. The new files do not copy EXIF/GPS; compatible ICC profiles can be retained in PNG/JPEG. Full color management is not part of the lab.

## Run locally in VS Code

Run the commands in the folder containing this README, ideally inside your cloned team repository. Use Python 3.10+ in a virtual environment. In VS Code, select the venv interpreter. On Windows use `py -m venv .venv` and select `.venv\Scripts\python.exe`; on macOS/Linux use `python3 -m venv .venv`, then `source .venv/bin/activate`. In the commands below, `python` means that interpreter.

```sh
python -m pip install -r requirements.txt
```

PNG/BMP require no C build. HEIC needs `pillow-heif`, or on Linux a system `libheif` with an HEVC decoder plugin. If the optional plugin has no wheel for your platform, install the first three dependencies in `requirements.txt` without `pillow-heif` and install your system's HEIF decoder, or ask the Linux backend to decode the file. The HEIC test in the delivered test run used `libheif` and its libde265 plugin with a genuine HEVC fixture.

**JPEG only:** Install CMake, a C compiler and libjpeg development files; then run:

```sh
cmake -S support -B build
cmake --build build --config Release
```

- Debian/Ubuntu: install `build-essential cmake libjpeg-dev`. For system HEIC, use the distribution’s `libheif` and HEVC (libde265) plugin packages.
- macOS/Homebrew: `brew install cmake jpeg-turbo`; if needed configure with `cmake -S support -B build -DCMAKE_PREFIX_PATH="$(brew --prefix jpeg-turbo)"`.
- Windows/Visual Studio Build Tools + vcpkg: install `libjpeg-turbo:x64-windows-static` using vcpkg; configure with `cmake -S support -B build -A x64 -DCMAKE_TOOLCHAIN_FILE=C:/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake -DVCPKG_TARGET_TRIPLET=x64-windows-static`, then use the build command above. The adapter is located automatically under `build` or `build/Release`, or set `STEGO_JPEG_TOOL` to the absolute executable path. Platform setup other than Linux was not executed here.

Try the included HEIC fixture, or use a real photo of your own:

```sh
python -m image_stego capacity support/tests/fixtures/synthetic.heic --format PNG
python -m image_stego embed support/tests/fixtures/synthetic.heic clue.png --text "Find the next clue" --demo
python -m image_stego extract clue.png recovered.txt
python -m image_stego quality support/tests/fixtures/synthetic.heic clue.png
python -m image_stego embed support/tests/fixtures/synthetic.heic clue.jpg --text "A short JPEG clue"
python -m image_stego extract clue.jpg recovered-jpeg.txt
python -m unittest discover -s support/tests -v
```

`--demo` is unencrypted. Otherwise the CLI asks for a password, and extraction prompts when required. `--file` accepts binary data. Use new output names, because the CLI deliberately does not overwrite files.

## Hand-off to your web developer

```python
from dataclasses import asdict
from image_stego import capacity, embed, extract, measure, StegoError

info = asdict(capacity(upload_bytes, 'JPEG', encrypted=True))
result = embed(upload_bytes, 'A short clue', password=user_password, output_format='JPEG')
download_bytes, content_type = result.image, result.media_type
recovered = extract(download_bytes, password=user_password)  # exact bytes
quality = asdict(measure(upload_bytes, download_bytes))
```

Use two image sources on the **Hide** screen: an uploaded file or a gallery image. Both pass bytes into the same `capacity()` and `embed()` calls. For the gallery, keep a server-side allowlist of IDs mapped to bundled images; never accept a server file path from the browser. On the **Extract** screen, accept a file chosen by the user and pass its bytes into `extract()`. A normal photo or a file from another steganography tool is not expected to contain a compatible payload. The web UI and gallery are not implemented in this package.

Treat `can_embed` separately from `max_message_bytes`; a tiny image may not fit even the header. Show the byte limit before submission (measure text in UTF-8 bytes). Return the exact generated bytes as a download; do not resize/re-encode them for the download route. Do not serve a preview as the output file. `ImageError`, `CapacityError`, `PasswordError`, `PayloadError` and `DependencyError` all derive from `StegoError`. Map user input errors to clear messages; a missing server dependency is a deployment error. `psnr_db=None` means decoded pixels are identical (infinite PSNR), not a failed metric.

For a shared web deployment, cap HTTP request size **before** buffering, run media decoding in a resource-bounded worker, rate-limit scrypt operations, keep decoder libraries patched, use TLS, and never log passwords or payloads. The backend sees data in this API; it is not end-to-end encrypted. The library also caps image input and output at 40 MiB, images at 25 MP / 12,000 pixels per side, and user payloads at 2 MiB or the smaller mode limit. Higher-resolution phone photos may need to be reduced **before** embedding.

## Why these two methods?

**Spatial method.** Rank 8×8 tiles using local differences on RGB values with the lowest bit ignored. Use the more textured half, excluding fully transparent pixels. Since embedding does not change the upper seven bits, decoding reconstructs the same tile map without the cover. In each group of seven channel values, a Hamming-style syndrome represents three payload bits; at most one channel changes by one. This is matrix embedding, not sequential LSB replacement; it still uses parity and is not a defense against a determined steganalyst. PVD is also adaptive, but this design has a simple per-group change bound and predictable decoding. The cost is lower capacity than one-bit-per-channel replacement and no compatibility with lossy pixel changes.

**JPEG method.** libjpeg reads/writes quantized luminance coefficients directly, without an RGB re-encode after embedding. For each bit, place one of four selected AC coefficients per full 8×8 block near one of two interleaved, dithered grids (QIM). Use the current quantization table to put coefficients on a comparable scale after a re-save. Space between grid points gives errors room to move. Repeated interleaved extended Hamming codewords and soft decoding handle some remaining errors. Compared with plain coefficient parity, QIM deliberately trades higher distortion and lower capacity for tolerance to coefficient movement. This project is **not** an implementation of F5, J-UNIWARD, or the compressor-specific robust lattice method of Butora et al.; those are meaningful research comparators, not methods this prototype outperforms. Do not interpret high PSNR or SSIM as low detectability.

**Shared payload.** The versioned header lets the extractor find the mode, length, salt and nonce. Password mode derives independent encryption and routing inputs with scrypt (N=32768, r=8, p=1) and uses AES-256-GCM to protect the message and authenticate its header. Demo mode uses CRC for corruption detection only. The public bootstrap can reveal this tool’s format; PCG64 only supplies reproducible placement/dither, not a cryptographic security guarantee. A strong password protects the contents, not the fact that data is hidden. A weak password can be guessed offline. Files from the prior prototype are not compatible with this v1 format.

## Evidence, not guarantees

The included `support/results.csv` records one run on seven sample images from scikit-image (photos, grayscale, text and checkerboard), with three message lengths each (24, 96, 160 bytes), unencrypted high-entropy payloads, and baseline JPEGs saved at Pillow quality 95 / 4:4:4. The JPEG re-encode tests use Pillow 4:2:0 and the stated quality settings. Unit tests separately cover encrypted JPEG recompression, encrypted PNG, password failure, corruption, capacity boundaries, odd dimensions, and actual HEIC input. See `support/test_results.txt`.

| Result in the bundled run | Outcome |
|---|---:|
| Exact output recovery, JPEG and PNG | 21/21 each |
| PNG re-saved as PNG | 21/21 |
| JPEG re-saved once, Pillow quality 95, 90, 85, 75, 60, 50, 40 or 30 | 21/21 at each setting |
| JPEG re-saved once at quality 20 | 18/21 |
| JPEG resized to 75% (both dimensions) then re-saved | 0/21 |
| PNG stego converted to JPEG | 0/21 |

JPEG PSNR was 32.01–39.90 dB and SSIM 0.803–0.944, so JPEG changes can be visible, especially on synthetic/text covers. Mean spatial PSNR was 81.68 dB against 79.11 dB for a *distortion-only* sequential LSB control with the same number of independent test bits. The control does not implement an interoperable file format and is not a detection benchmark. Measured demo capacities were 190–461 user bytes for JPEG versus 11,081–21,745 for PNG on these particular images. No tested result establishes survival through another app, repeated re-saves, resizing, cropping, screenshots, or general steganalysis resistance. Preserve the generated original file when recovery matters.

```sh
python -m pip install "scikit-image>=0.20,<1"
python -m support.benchmark --out repeat_results.csv
```

Payloads are fixed by the benchmark and salts are randomized, so counts may vary between runs. For a report-quality evaluation, test independent local/iPhone photos at equal payload sizes and include a different JPEG encoder and an explicit detector evaluation. This project addresses **practical usability** (one UI and API for several formats) and makes **capacity, visual quality, and recovery** measurable; it does not solve detector generalization or universal transformation robustness.

### Three references worth keeping

1. [Kombrink, Geradts and Worring, *Image Steganography Approaches and Their Detection Strategies: A Survey*](https://doi.org/10.1145/3694965) — taxonomy and caveats; sections 3.1 and 3.2 distinguish spatial and transform methods.
2. [Chen and Wornell, *Quantization Index Modulation*](https://doi.org/10.1109/18.923725) — the original QIM idea, not a validation of this implementation.
3. [Butora, Puteaux and Bas, *Errorless Robust JPEG Steganography using Outputs of JPEG Coders*](https://arxiv.org/abs/2211.04750) — why claims about survival must be tied to a compressor and test conditions.

The HEIC test fixture is a generated 512×384 RGB pattern encoded as a single HEVC still; it contains no user image. No production tool source was copied. Commit the source, fixture and tests to a feature branch; do not commit your local `build/`, `.venv/` or images containing real secrets.
