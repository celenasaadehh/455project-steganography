# Testing, Evaluation and Birthday Attack (Member 5)

This folder tests the team's steganography algorithms and the website, measures how well the algorithms work, tests whether hidden messages can be detected, and contains the birthday attack experiment.

Two algorithms are covered, both used by the website (Member 3):

- `Member 1/image_stego.py`: the image carrier (PNG, BMP, JPEG).
- `Member 2/text_stega.py`: the text carrier. It puts the hidden characters in one block after the first space: 2 bits per invisible character for English text, 1 bit per character when the cover has Arabic letters, with an optional password.

The website tests also cover Member 4's History and Learn tabs.

Nothing here copies the code under test. Every script imports it directly from its folder, so the tests always run against the latest version in the repository.

## What is in this folder

| File | Purpose |
|---|---|
| `tests/test_image_algorithm.py` | 58 automated tests of the image carrier: round trips, passwords, capacity limits, distortion, bad input, tampering, JPEG, black-and-white covers staying grey |
| `tests/test_text_algorithm.py` | 40 automated tests of the text carrier through the names the website calls (`hide`, `reveal`): round trips, invisibility, limits, passwords, tampering, emoji and Persian covers, and the fixed issue 1 |
| `tests/test_text_steganography_folder.py` | 29 automated tests of the text carrier through its own names (`encode_text`, `decode_text`): round trips, one block after the first space, Arabic mode, bad input, tampering |
| `tests/test_integration.py` | 22 tests of the algorithms together and through the website: register, hide and download, upload and reveal, privacy, password rules (including the lock switched off) and wrong-password limits, History and Learn tabs |
| `tests/test_birthday_attack.py` | 8 tests of the mathematics and the collision search used by the experiment |
| `tests/test_steganalysis.py` | 11 tests of the detection experiment: the three detectors on photos with a known answer, the AUC and 5% metrics, the hiding methods, the black-and-white and known-gallery-cover checks, the text scanner |
| `evaluate_images.py` | Measures image capacity, distortion (MSE, PSNR, SSIM), robustness and speed |
| `evaluate_text.py` | Measures text overhead (English and Arabic, with and without a password), robustness and whether the visible text is unchanged |
| `steganalysis.py` | The detection experiment: three classic detectors against the team's method and plain LSB, plus text detection |
| `birthday_attack.py` | The birthday attack experiment |
| `common.py`, `charts.py` | Shared helpers: test pictures, result tables, chart style |
| `results/` | Tables (CSV, open in Excel) and charts (PNG) produced by the four scripts, ready for the report |

## How to run

Python 3.10 or newer is needed. From this folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows use `py -m venv .venv` and `.venv\Scripts\activate` for the first two lines. On a Mac, do not use the Python that comes with macOS (3.9): it cannot run scrypt, which every password feature needs.

Then, still in this folder:

```sh
python -m unittest discover -s tests -v
python evaluate_images.py
python evaluate_text.py
python steganalysis.py
python birthday_attack.py
```

The tests can also be run from the repository root, like the other members' tests:

```sh
python -m unittest discover -s "Member 5/tests" -v
```

On a laptop that is not busy with other work, the tests take about 10 seconds, `evaluate_text.py` about 8 seconds, `evaluate_images.py` about 20 seconds, `birthday_attack.py` about 20 seconds and `steganalysis.py` about a minute. The experiments use fixed random seeds, so most results repeat exactly from run to run. Two things can move slightly: every embedding with the team's method uses a fresh random salt, so its distortion and detection figures change a little, and timings depend on the computer.

JPEG output needs the small C program described in `../Member 1/support/TECHNICAL_GUIDE.md`. When it is not built, the 7 JPEG tests are skipped and the JPEG rows are left out of the tables. The results below include JPEG. On macOS it was built from the `Member 1` folder with:

```sh
brew install cmake jpeg-turbo
cmake -S support -B build -DCMAKE_PREFIX_PATH="$(brew --prefix jpeg-turbo)"
cmake --build build --config Release
```

## Test results

| Test file | Tests | Result |
|---|---:|---|
| `test_image_algorithm.py` | 58 | 58 pass, including the 7 JPEG tests |
| `test_text_algorithm.py` | 40 | 40 pass |
| `test_text_steganography_folder.py` | 29 | 29 pass |
| `test_integration.py` | 22 | 22 pass |
| `test_birthday_attack.py` | 8 | 8 pass |
| `test_steganalysis.py` | 11 | 11 pass |
| **Total** | **168** | **168 pass** |

The issues found earlier were covered by "expected failure" tests (marked with `@unittest.expectedFailure`: a test that describes how the code should behave but does not yet). All of them have been fixed, so the marks were removed and the tests now pass normally.

The other members' own tests were also run on the same code: Member 1's 17 tests (including JPEG and HEIC) and Member 4's 14 tests all pass. Member 1's tests need the `Member 1` folder on Python's path, for example `PYTHONPATH="Member 1" python -m unittest discover -s "Member 1/support/tests"` from the repository root.

The most important property checked for every carrier is this: after an accidental change to the stego picture or text (any single changed character or colour value, random bit flips, cropping, recompression), the algorithm returns either the original message or an error, and never a wrong message. This held in every test, for both algorithms. A deliberate change is different: without a password it can produce a different message (see the birthday attack experiment, Part 3).

## Image carrier: capacity

Measured with `capacity()`, without a password unless stated.

| Image size | PNG or BMP | PNG with password | Bits per pixel (PNG) | JPEG |
|---|---:|---:|---:|---:|
| 256 x 256 | 5,219 bytes | 5,207 bytes | 0.637 | 59 bytes |
| 512 x 512 | 21,017 bytes | 21,005 bytes | 0.641 | 443 bytes |
| 960 x 720 (website gallery) | 55,495 bytes | 55,483 bytes | 0.642 | 1,281 bytes |
| 1920 x 1080 | 166,581 bytes | 166,569 bytes | 0.643 | 3,981 bytes |
| 4032 x 3024 (12 MP phone photo) | 979,728 bytes | 979,716 bytes | 0.643 | 23,745 bytes |

- Capacity grows in proportion to the number of pixels, at about 0.64 bits per pixel.
- This is about 21.4% of what plain LSB replacement could hold (3 bits per pixel). The method gives up capacity on purpose: it uses only the more textured half of the picture and changes at most one value in every group of seven.
- For opaque pictures whose sides are multiples of 8, like every size above, capacity depends only on the size, not on what the picture shows: all ten gallery pictures hold exactly 55,495 bytes, and four very different test pictures of 256 x 192 (gradient, noise, one solid colour, checkerboard) all hold 3,902 bytes. For other sizes the cut-off 8 x 8 tiles at the edges make it depend slightly on the content (2,153 to 2,219 bytes at 201 x 131 for the four generated pictures). Fully transparent pixels are never used, so a picture with transparent areas holds less.
- A password costs 12 bytes of capacity.
- The smallest pictures that can hold anything are 22 or 23 pixels square without a password (1 or 2 bytes) and 25 x 25 with one (5 to 23 bytes on the four generated pictures). Smaller pictures are refused with a clear error.
- JPEG holds about 2.1 to 2.4% of what PNG holds in pictures of 512 x 512 and larger, and less in small ones (1.1% at 256 x 256), because its header always takes the same 2,064 coefficients (43 bytes, error-corrected and stored three times). It uses only 4 coefficients per 8 x 8 block and stores every bit several times with error correction so it can survive recompression.

Chart: `results/image_capacity_by_size.png`. Tables: `results/image_capacity.csv`, `results/image_capacity_by_cover.csv`.

## Image carrier: distortion

Measured on 14 cover pictures (the 10 gallery pictures and 4 generated ones), with random messages from 1% to 100% of each picture's capacity. "Sequential LSB" is the classic textbook method, implemented in `evaluate_images.py` only as a comparison, hiding the same number of bits.

| Message size | Team's method PSNR | Sequential LSB PSNR | Values changed (team) | Values changed (LSB) |
|---|---:|---:|---:|---:|
| 1% of capacity | 79.09 dB | 76.59 dB | 0.08% | 0.15% |
| 10% | 70.05 dB | 67.69 dB | 0.64% | 1.11% |
| 50% | 63.17 dB | 60.82 dB | 3.13% | 5.38% |
| 100% | 60.18 dB | 57.84 dB | 6.24% | 10.71% |

- Even a completely full picture stays above 60 dB PSNR (lowest 60.15 dB), with mean SSIM 0.9998 (lowest 0.9990, the checkerboard). A change above about 40 dB is not visible to the eye.
- No colour value ever changes by more than 1 level out of 255 in PNG or BMP output.
- The team's method is about 2.3 to 2.5 dB better than sequential LSB at every message size, because it hides about 3.4 to 3.5 bits for every value it changes and sequential LSB hides 2.0.
- At full capacity distortion is almost the same on every cover (all 14 are within 0.1 dB of each other), because it depends on how many values change and not on the content. At small message sizes the four 256 x 192 covers read up to 3 dB lower (76.9 to 77.8 dB, against 79.8 dB for the gallery pictures at 1%), because the fixed 43-byte header is a larger share of their small message.
- These numbers measure how much the picture changes, not how easy the hidden data is to detect. That is measured separately in the detection experiment below.

**JPEG output** works differently: it changes DCT coefficients, and one changed coefficient shifts all 64 pixels of its block. It distorts much more, and it is measured against the same picture saved as a JPEG at quality 95.

| Message size | JPEG PSNR, all 14 covers (lowest) | JPEG PSNR, gallery pictures | SSIM, gallery pictures |
|---|---:|---:|---:|
| 10% of capacity | 38.0 dB (32.7 dB) | 39.8 dB | 0.959 |
| 50% | 33.9 dB (32.0 dB) | 34.3 dB | 0.864 |
| 100% | 31.7 dB (31.4 dB) | 31.5 dB | 0.765 |

- On the four small 256 x 192 covers the fixed JPEG header alone uses two thirds of the 3,072 coefficients the method can use (4 per 8 x 8 block), so even a small message distorts them almost as much as a full one. That is why the all-cover mean and lowest values at 10% are low; the gallery pictures show the normal case.
- Below about 40 dB a change can be visible, so a full JPEG may show faint block patterns; Member 1's technical guide also warns that JPEG changes can be visible. Pixel values change by up to 40.
- The solid-colour cover has the lowest SSIM (0.58 when full), because there is no texture to hide the change.
- JPEG trades picture quality and capacity for surviving recompression (next section). PNG is the better choice whenever the file can be sent unchanged.

Chart (PNG output only): `results/image_quality_vs_payload.png`. Tables: `results/image_distortion.csv` (every cover; the gallery-only JPEG figures above are the mean of its ten gallery rows) and `results/image_distortion_summary.csv` (averages over all 14 covers).

## Image carrier: robustness and speed

Measured on a 512 x 384 test picture.

| Edit of the stego picture | Result |
|---|---|
| PNG saved again as PNG, converted to BMP, alpha channel added | Message recovered |
| PNG saved as JPEG, cropped by one column, resized, rotated, mirrored, brightness +1, greyscale | Rejected with an error |
| JPEG saved again as JPEG at quality 95, 85, 75, 60, 40 or 20 | Message recovered |
| JPEG resized to 75%, or converted to PNG | Rejected with an error |

- A PNG survives every lossless copy, and every whole-picture edit tested destroys it. Accidental damage never produces a wrong message. Apps that recompress pictures (most messaging apps) will destroy it, so a PNG has to be sent as a file.
- A JPEG survives being saved again as a JPEG down to quality 30 on all 14 covers. Quality 20 worked on 13 of them but not on the sharp-edged checkerboard. It does not survive resizing. Converting it to PNG also loses the message, because the extractor reads JPEG coefficients from JPEG files only. Most messaging apps also resize pictures, so a JPEG is safest sent as a file too.

Hiding a 100-byte message in a 960 x 720 picture took about 105 ms without a password and 154 ms with one (median of 11 runs). Extracting took about 36 ms and 85 ms. The password adds about 50 ms, almost all of it the scrypt key derivation (about 40 to 50 ms, depending on how busy the computer is), which is slow on purpose. These times depend on the computer: an earlier run on the same laptop was about a quarter faster.

Tables: `results/image_robustness.csv`, `results/image_jpeg_resave_by_cover.csv`, `results/image_timing.csv`.

## Text carrier (`text_stega.py`): capacity and overhead

- Capacity is fixed at 65,535 bytes of secret, whatever the cover text is. A one-word cover can carry it.
- English text, and any other cover without an Arabic letter (French, Japanese, emoji...): every secret byte becomes 4 invisible characters. The fixed overhead is 32 invisible characters without a password and 184 with one (8 and 46 bytes).
- Arabic text (any cover with an Arabic letter, including Persian): only 2 invisible characters are used, 1 bit each, so every secret byte becomes 8 characters. The overhead doubles too: 64 without a password and 368 with one.
- The visible text does not change, but the stored text grows by 12 bytes for every secret byte in English (24 in Arabic), because each invisible character takes 3 bytes in UTF-8.

Measured with the English cover "Hello there, see you at lunch tomorrow." (39 characters, 39 bytes) and an Arabic sentence of 27 characters (50 bytes in UTF-8, because each Arabic letter takes 2 bytes).

| Secret | English: invisible characters | English: size vs the 39-byte cover | Arabic: invisible characters | Arabic: size vs the 50-byte cover |
|---|---:|---:|---:|---:|
| 10 bytes | 72 | 6.5 times larger | 144 | 9.6 times larger |
| 100 bytes | 432 | 34 times larger | 864 | 53 times larger |
| 1,000 bytes | 4,032 | 311 times larger | 8,064 | 485 times larger |
| 10,000 bytes | 40,032 | 3,080 times larger | 80,064 | 4,805 times larger |

So the hidden message cannot be seen, but a long secret in a short sentence is easy to notice from the size of the text. Without a password, hiding or revealing even 10,000 bytes took under 15 ms in English and under 30 ms in Arabic. With a password every operation took about 46 to 84 ms; almost all of the extra time is the scrypt key derivation (about 40 to 50 ms), which is slow on purpose, so for short secrets it is almost the whole time.

Chart: `results/text_overhead.png`. Table: `results/text_overhead.csv`.

## Text carrier (`text_stega.py`): robustness and visibility

The same edits were made to a stego text with an English cover and one with an Arabic cover. Both behaved the same.

| Edit of the stego text | Result |
|---|---|
| Text added before or after, upper case, trimming, collapsing spaces, wrapping lines at 40 columns, Unicode normalisation (NFC, NFKC), JSON, UTF-16 | Message recovered |
| A reply that contains an emoji built from joined characters | Message recovered |
| Text cut after the hidden block | Message recovered (the block sits right after the first space, near the start) |
| One invisible character deleted, text cut inside the hidden block, another stego text pasted after it | Rejected with an error |
| Sent through a system that keeps only ASCII or only printable characters | Rejected with an error (the message is gone) |

The visible text stayed exactly as typed for every cover tested, with and without a password: an English sentence, one word, French with accents, Japanese, Arabic, a family emoji joined with U+200D and a Persian word written with U+200C. Arabic and Persian covers switch to the Arabic mode automatically. This works because only a run of 8 or more invisible characters counts as the hidden message, so the single joiners that emoji and Persian words need are left alone. Spaces and line breaks inside the run are allowed, which is why wrapped lines still work. One rare cover still fails: see issue 1.

Tables: `results/text_robustness.csv`, `results/text_visibility.csv`.

## Detection experiment (steganalysis)

PSNR shows that a stego picture *looks* the same. This experiment asks the question that matters for steganography: can someone *tell* that a picture or a text hides a message, without the password and without the original?

**Detectors.** Three classic attacks from the research literature, implemented in `steganalysis.py` and checked by `tests/test_steganalysis.py` on photos with a known answer:

- **Chi-square attack** (Westfeld and Pfitzmann, 1999). Flipping last bits makes the counts of each value pair (2k, 2k+1) equal. The attack scans the picture from the top-left corner and reports the probability of hidden data.
- **RS analysis** (Fridrich, Goljan and Du, 2001). Estimates the share of colour values carrying a hidden bit from how small groups of pixels react when their last bits are flipped.
- **Sample pair analysis, SPA** (Dumitrescu, Wu and Wang, 2003). Estimates the same share from neighbouring pixel pairs. On clean photos RS and SPA read about 0.02 to 0.03 on average.

**Set-up.** 51 tiles of 256 x 256 cut from 15 real photos that come with scikit-image (portraits, a cat, coffee, textures, space and microscope images), and separately the 10 website gallery pictures. Each picture was tested clean and with random messages of 0.01 to 0.2 hidden bits per colour value (the team's method holds up to about 0.21; a black-and-white tile counts one value per pixel, because the team's code keeps it grey, and the two LSB methods follow the same rule), using three methods at the same message size: the team's method (Member 1's `embed()`, PNG), sequential LSB (last bits overwritten in reading order from the top-left corner, the same order the chi-square scan reads) and LSB at random positions. Results are given as the share of stego pictures caught when the detector's threshold wrongly flags at most 5% of clean pictures, and as AUC (0.5 means guessing, 1.0 means always caught).

**Results on the real photos.**

| Detector | Method | 0.05 bits per value | 0.1 | 0.2 |
|---|---|---:|---:|---:|
| Chi-square | **Team's method** | 6% (0.51) | 6% (0.51) | 4% (0.52) |
| Chi-square | Sequential LSB | 22% (0.77) | 28% (0.79) | 35% (0.81) |
| Chi-square | Random LSB | 6% (0.51) | 8% (0.54) | 8% (0.54) |
| RS analysis | **Team's method** | 8% (0.71) | 8% (0.78) | 16% (0.89) |
| RS analysis | Sequential LSB | 12% (0.78) | 28% (0.88) | 86% (0.97) |
| RS analysis | Random LSB | 10% (0.81) | 22% (0.91) | 96% (0.98) |
| SPA | **Team's method** | 12% (0.69) | 16% (0.80) | 33% (0.90) |
| SPA | Sequential LSB | 20% (0.79) | 39% (0.91) | 100% (0.99) |
| SPA | Random LSB | 14% (0.81) | 49% (0.94) | 100% (0.99) |

Each cell: share of the 51 stego pictures caught when at most 5% of clean pictures are wrongly flagged (here 2 of the 51 clean tiles), with the AUC in brackets. The team's rows are from one run: each embedding uses a fresh random salt, so a rerun moves them by a few points. The sequential and random LSB rows repeat exactly.

- **Sequential LSB is the easiest to catch at small sizes, but only by the chi-square scan**, which reads the picture in the order it was written and sees exactly where the message stops (`results/detect_chi_square_scan.png`). RS and SPA detect random LSB at least as well as sequential LSB (higher or equal AUC at every size) and often catch it more often (at 0.1, SPA 49% against 39%; at 0.2, RS 96% against 86%).
- **The team's method is the hardest of the three to detect, but it is not undetectable.** At the largest size, RS and SPA catch plain LSB in 86 to 100% of the photos, but the team's method in 16 to 33%. Two likely reasons, not tested separately: it changes about 41% fewer values for the same message (about 3.4 bits per change against 2), and it changes them only in textured areas, where these detectors are known to be less accurate. The chi-square scan barely sees it, because the changes are scattered.
- Small messages (0.02 bits per colour value or less, about 490 bytes in a 256 x 256 picture) are rarely caught by RS and SPA: 10% of pictures or fewer, for every method. Only the chi-square scan still catches some sequential LSB pictures (12 to 14%).
- These are classic detectors. Modern machine-learning detectors are much stronger, so the team's method is probably easier to detect than shown here.

**Black-and-white photos.** A black-and-white photo has identical red, green and blue values. The team's code used to turn a black-and-white upload into a colour picture with PNG or BMP output, so hiding even 10 bytes made the three channels differ in all 26 black-and-white tiles, which anyone can check in one line (issue 5). Member 1's code now keeps such pictures in grey mode (one value per pixel), and after the fix all 26 tiles come back as greyscale files with no colour. The cost is capacity: a grey picture holds about a third as much as a colour one of the same size.

**On the website's gallery pictures** RS fails (AUC 0.52 to 0.58) and SPA is weak (AUC at most 0.74): even the clean pictures read as 63% hidden (RS) and 33% (SPA), because the generated artwork already has random-looking last bits. Only the chi-square scan works there, against sequential LSB. But the 10 gallery pictures are public: they are in the repository and every user of the website can open them. Comparing a stego picture with the original gallery picture shows every changed value. Even a 10-byte message was found in all 10 gallery pictures (130 to 141 changed values), and a clean copy showed no changes. **For real secrecy, users should hide messages in their own photos, not in a built-in gallery picture.**

**Text.** A three-line scanner that flags a text with 8 or more zero-width characters caught every stego text, English or Arabic, with or without a password (the smallest has 36 hidden characters), and flagged none of the clean texts, including a text with three family emoji (6 zero-width characters) and a Persian sentence (2). Text steganography hides the message from people, not from software.

**What could make the team's method harder to detect.** It flips the last bit (2 becomes 3, 3 becomes 2), which leaves the pair pattern that all three detectors look for. Changing values by +1 or -1 at random instead ("LSB matching") does not create that pair pattern, so these three detectors are not designed to see it, although other detectors can still find it (for example Ker, "Steganalysis of LSB matching in grayscale images", IEEE Signal Processing Letters, 2005). This was not tested here; it is a suggestion for Member 1.

Limits: 51 tiles from 15 photos is a small set (research uses about 10,000 pictures), and only the three classic detectors were used. 26 of the 51 tiles come from black-and-white photos; since issue 5 was fixed they stay grey, so all three methods hide in one value per pixel there. JPEG output was not tested, because the team's JPEG mode changes DCT coefficients with dithered quantisation, which none of these three detectors models.

Charts: `results/detect_auc_photos.png`, `results/detect_chi_square_scan.png`, `results/detect_auc_gallery.png`. Tables: `results/detect_photos.csv`, `results/detect_gallery.csv`, `results/detect_chi_square_scan.csv`, `results/detect_greyscale_cover.csv`, `results/detect_known_gallery_cover.csv`, `results/detect_text.csv`.

## Birthday attack experiment

A check value of n bits has 2^n possible values, but two different messages with the same check value appear after about 2^(n/2) messages. This matters for the project because, without a password, both the image carrier and the text carrier protect the hidden message only with a CRC-32 checksum, which has 32 bits and no key. With a password both use AES-256-GCM, whose 128-bit tag depends on the key.

**Part 1, measured against theory.** Random messages were drawn until two had the same check value (SHA-256 cut to n bits, 300 runs per size).

| Check value | Measured mean | Theory | Measured / theory |
|---|---:|---:|---:|
| 8 bits | 20.5 | 20.7 | 0.99 |
| 16 bits | 333.9 | 321.5 | 1.04 |
| 24 bits | 5,041 | 5,134 | 0.98 |
| 32 bits | 80,566 | 82,138 | 0.98 |

**Part 2, the project's own checksum.** For CRC-32, 600 runs needed 82,972 messages on average (theory 82,138), and half of the runs had a collision within 79,043 messages (theory 77,163). A search of all 4.29 billion values was never needed.

**Part 3, what it means for the project.** The experiment prepares two different messages of the same length with the same CRC-32, which took 163,060 checksums and less than a second. It hides the first one with the team's code and no password, then exchanges it for the second one while keeping the stored checksum. Both `reveal()` and `extract()` return the second message without any error. With a password, changing even one value of the encrypted part is rejected by both carriers, because the AES-GCM check depends on the key and cannot be recomputed without it.

**Part 4, larger check values.** Work for a 50% chance of a collision:

| Check value | Tries | At one billion tries per second |
|---|---:|---|
| 32 bits (CRC-32, no password) | 77,163 | under a second |
| 64 bits | 5.06 billion | 5 seconds |
| 128 bits (the size of the AES-GCM tag) | 2.17 x 10^19 | 688 years |
| 256 bits (SHA-256) | 4.01 x 10^38 | 1.3 x 10^22 years |

These figures are the work to find two messages with the same check value when the attacker can compute the check but cannot change the stored value, for example if the checksum were sent separately. In this project the CRC-32 has no key and is stored with the message, so without a password an attacker does not even need a collision: they can compute a new checksum, or simply hide a new message, and a longer check without a key, such as SHA-256, would not help. The collision shows that even a checksum value the receiver already trusts cannot prove which message was hidden. The AES-GCM tag depends on the key and cannot be computed offline at all, so what protects a locked message is the password, not the 128 bits; the 688-years row is not the cost of attacking it.

**Conclusion.** The CRC-32 checksum detects accidental damage very well: in the tests, every single-character or single-value change was either caught or left the hidden message intact, and none produced a wrong message. It does not protect against a deliberate change, and it cannot prove which message was hidden. `Member 2/Research.md` says the same in its security section; this experiment measures it. A message that matters should always be hidden with a password, which both carriers offer. The website now shows a warning when the lock is switched off.

Charts: `results/birthday_tries_vs_bits.png`, `results/birthday_crc32_probability.png`. Tables: `results/birthday_digest_sizes.csv`, `results/birthday_crc32_probability.csv`, `results/birthday_attack_on_project.csv`, `results/birthday_time_estimates.csv`. Full output: `results/birthday_attack_log.txt`.

## Issues found

Checked and found correct: hiding and extracting with PNG, BMP and JPEG output (Member 1); the website never stores a hidden message as plain text; the History list and the History CSV export never contain the message, only its length (Member 4); and Learn runs on the real algorithms.

Issues found, with the folder whose code changed. **All of them are now fixed**; each entry keeps the original finding.

1. **Fixed.** `insert_position()` now looks past spaces on both sides of the hiding spot, falls back to the end or the start of the cover, and a cover with no safe spot gives a `TextStegoError`; the website also turns any unexpected error into a clear message instead of an error page. The test in `tests/test_text_algorithm.py` now passes normally. Original finding: *A rare cover makes the text carrier crash instead of giving an error* (`Member 2/text_stega.py`). If one of the cover's own zero-width characters sits right before the space where the hidden block goes (normally the first space), or at the end of a cover with no usable space, that character joins the hidden block, because `insert_position()` only checks the two characters touching the spot while a hidden run may contain spaces. Examples: `"Hello \u200d there"` (a zero-width joiner between two spaces) and `"abc\u200b"`. `hide()` then stops with a bare `AssertionError`. The website only catches `TextStegoError`, so the user gets a server error instead of a message. Covered by an expected-failure test in `tests/test_text_algorithm.py`. Fix: skip such spots in `insert_position()`, or raise `TextStegoError`.
2. **Resolved by the website redesign.** *History tells an outsider who sent a message* (`Member 4/member4.py`). The website no longer sends messages between users (Hide returns the file to the user, Reveal reads an upload), so there are no message numbers or senders to leak, and the test was removed. Original finding: When someone who is neither the sender nor the recipient tries to reveal a message by its number, the website correctly answers "Not found", but the History recorder still saves a failed "reveal" row in the outsider's own History, with the real sender's e-mail address. Trying message numbers one by one would collect senders' addresses. Covered by an expected-failure test in `tests/test_integration.py`. Fix: record a reveal only when the user is the sender or the recipient.
3. **Fixed.** When the lock is on (the default), Hide needs a password of at least 6 characters, and after 5 wrong passwords in 15 minutes Reveal and Sign in ask the account to wait (20 per network address, so guesses cannot be spread over many accounts). Revealing a locked message with no password typed is not counted as a wrong try. `tests/test_integration.py` checks all of this. An attacker with a copy of the picture can still guess offline, so a long password is still the real protection. Original finding: *Lock passwords can be guessed without limit* (`Member 3`). Any non-empty lock password is accepted, even one character, and the reveal page allows unlimited tries. A stored stego picture or text can also be attacked offline. scrypt makes each guess cost about 0.04 seconds on one processor core, so a million guesses take about 10 hours on one core, or about 2 hours on a 10-core laptop using every core: that slows an attacker down but does not stop one. Fix: require a longer lock password and limit wrong tries.
4. **Resolved by the website redesign.** The website now stores nothing that is hidden or revealed (no stego pictures or texts are kept), the password lock is on by default (it can be switched off, with a warning that anyone can then read the message), and the privacy text was rewritten; `test_nothing_hidden_is_stored_by_the_website` checks it. Original finding: *The website's privacy text promises more than it does* (`Member 3/templates/index.html`). It says: "Only the picture or text with the secret inside is stored. The secret itself is never saved and your lock password never leaves the moment it is used." The secret is not saved as plain text, but an unlocked message is stored inside its stego text or picture, so anyone who can read the website's data folder can reveal it: "never saved" holds in practice only for locked messages. The lock password is sent to the server with every send and reveal, where it is used and then forgotten.
5. **Fixed.** A picture whose red, green and blue values are equal everywhere is now hidden in and saved as a greyscale file (one value per pixel), so no colour appears; the reader makes the same check, and older files still open. Checked by `tests/test_image_algorithm.py` and the detection experiment. A grey picture now holds about a third as much. Original finding: *A black-and-white picture saved as PNG or BMP comes back as a colour picture with slightly different channels* (`Member 1/image_stego.py`). Any message, even 10 bytes, makes the red, green and blue values differ, which gives the message away (detection experiment). JPEG output keeps the three channels equal. Keeping greyscale pictures in grey mode would fix it.
6. **Fixed.** `HistoryApi` now points the website at a temporary folder before importing it, and the test accounts it had left in the real database were removed. Original finding: *Member 4's website tests write into the real website database* (`Member 4/tests/test_member4.py`). `HistoryApi` imports the website without pointing `db.DATA` at a temporary folder, so every run adds test accounts and a message to `Member 3/data/stego.db`. Fix: set `db.DATA` and `db.DB` to a temporary folder before `import app`, as `tests/test_integration.py` does.
7. **Fixed.** The documents below were updated. Original finding: *Some documents describe older versions.*
   - The root `README.md` still describes the website's first text format (U+200D, tag `ZW`, up to 10,000 bytes, 4 invisible characters per byte, which is 8 in Arabic covers). It also calls Member 2's method a "spread zero-width algorithm" (Member 2's first version) and says the `Member 3` folder holds the website's text carrier. Its capacity table gives JPEG "about 190–460 bytes" next to the 960 x 720 row, although a 960 x 720 gallery picture holds 1,281 bytes as JPEG. Its Member 1 test command fails unless `Member 1` is on Python's path.
   - `Member 3/README.md` calls the Learn tab "Tutorial" and has only Windows commands.
   - `Member 4/README.md` still calls the gallery "Member 2's", and its Learn page gives JPEG capacity only as "about 190–460 bytes in Member 1's tests" (smaller test pictures), although the walkthrough uses the 960 x 720 gallery pictures.
   - `Member 2/Research.md` section 2.4 lists "The method does not encrypt secret messages" as a limitation without saying that the team's version can encrypt with a password (section 9).

Fixed since the first report (22 November). At that time the website used its own text module, `text_stego.py`, which has since been replaced by `Member 2/text_stega.py`:

- The cover text changed when it already contained invisible characters (joined emoji, Persian words), and a reply containing a joined emoji made the message unreadable. Fixed: only a run of 8 or more invisible characters counts as the hidden message, so the cover's own joiners stay.
- A message that was not a string raised `AttributeError`. Fixed: a cover, message or password that is not a string now raises `TextStegoError` (a `ValueError`), like the module's other input errors. Issue 1 above is a remaining case where `hide()` raises a different error.
- An empty password meant "no password" in the text module but was an error in the image module. Fixed: both refuse an empty password when hiding a message; no password means no lock.
- The second text carrier held nothing in short or non-English covers, had no password option, was not connected to the website, and its `stego_output.txt` was not ignored by git. All fixed: any non-empty cover holds up to 65,535 bytes, Arabic covers have their own mode, there is an optional password with the same scrypt settings as the image carrier, the website calls it, messages hidden by the old module (tag `ZW`) can still be read, and `Member 2/.gitignore` lists the file.
- Two tests and one experiment check could pass or fail by chance because of the random salt. Fixed in this folder: the tamper tests allow up to two unnoticed changes to unused padding bits (the message is still correct), and the birthday attack's password check changes only an encrypted value, never the header.

For the website and the report:

- Without a password a hidden message is not protected against deliberate replacement (birthday experiment). The website now says so when the lock is switched off.
- Gallery pictures are public, so a message hidden in one can be found by comparing with the original (detection experiment). The interface could recommend uploading your own photo.
- A PNG or BMP stego picture must be shared as a file: saving it as JPEG, resizing it, or sending it through an app that recompresses pictures destroys the message. A JPEG stego picture survives being saved again as JPEG (down to quality 30 on every cover tested), but not resizing or conversion to PNG.
- A long secret in a short cover sentence makes the text hundreds of times larger than it looks, and a simple scanner finds every hidden text message.
- A secret hidden in Arabic or Persian text takes twice as many invisible characters as the same secret in English text.
