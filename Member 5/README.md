# Testing, Evaluation and Birthday Attack (Member 5)

This folder tests the team's steganography algorithms and the website, measures how well the algorithms work, and contains the birthday attack experiment.

Two algorithms are covered, both used by the website (Member 3):

- `Member 1/image_stego.py`: the image carrier (PNG, BMP, JPEG).
- `Member 2/text_stega.py`: the text carrier. It puts the hidden characters in one block after the first word: 2 bits per invisible character for English text, 1 bit per character when the cover has Arabic letters, with an optional password.

The website tests also cover Member 4's History and Learn tabs.

Nothing here copies the code under test. Every script imports it directly from its folder, so the tests always run against the latest version in the repository.

## What is in this folder

| File | Purpose |
|---|---|
| `tests/test_image_algorithm.py` | 57 automated tests of the image carrier: round trips, passwords, capacity limits, distortion, bad input, tampering, JPEG |
| `tests/test_text_algorithm.py` | 39 automated tests of the text carrier through the names the website calls (`hide`, `reveal`): round trips, invisibility, limits, passwords, tampering, emoji and Persian covers |
| `tests/test_text_steganography_folder.py` | 29 automated tests of the text carrier through its own names (`encode_text`, `decode_text`): round trips, one block after the first word, Arabic mode, bad input, tampering |
| `tests/test_integration.py` | 18 tests of the algorithms together and through the website: register, send, reveal, History and Learn tabs |
| `tests/test_birthday_attack.py` | 8 tests of the mathematics and the collision search used by the experiment |
| `evaluate_images.py` | Measures image capacity, distortion (MSE, PSNR, SSIM), robustness and speed |
| `evaluate_text.py` | Measures text overhead (English and Arabic, with and without a password), robustness and whether the visible text is unchanged |
| `birthday_attack.py` | The birthday attack experiment |
| `common.py`, `charts.py` | Shared helpers: test pictures, result tables, chart style |
| `results/` | Tables (CSV, open in Excel) and charts (PNG) produced by the three scripts, ready for the report |

## How to run

Python 3.10 or newer is needed. From this folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows use `py -m venv .venv` and `.venv\Scripts\activate` for the first two lines.

The tests can also be run from the repository root, like the other members' tests:

```sh
python -m unittest discover -s "Member 5/tests" -v
```

```sh
python -m unittest discover -s tests -v
python evaluate_images.py
python evaluate_text.py
python birthday_attack.py
```

The tests take about 7 seconds. Each evaluation script takes a few seconds, and the birthday experiment about half a minute. The experiments use fixed random seeds, so the results repeat from run to run. Two things can move slightly: the image distortion figures change in the second decimal place, because every embedding uses a fresh random salt, and the timings depend on the computer.

JPEG output needs the small C program described in `../Member 1/support/TECHNICAL_GUIDE.md`. When it is not built, the 7 JPEG tests are skipped and the JPEG rows are left out of the tables. When it is built they run automatically. The results below were produced without it, so they cover PNG and BMP output only.

## Test results

| Test file | Tests | Result |
|---|---:|---|
| `test_image_algorithm.py` | 57 | 50 pass, 7 JPEG tests skipped (helper not built) |
| `test_text_algorithm.py` | 39 | 35 pass, 4 are marked as known issues (see below) |
| `test_text_steganography_folder.py` | 28 | 28 pass |
| `test_integration.py` | 18 | 18 pass |
| `test_birthday_attack.py` | 8 | 8 pass |
| **Total** | **150** | **139 pass, 7 skipped, 4 known issues** |

The other members' own tests were also run on the same code. Member 4's 10 tests all pass. Member 1's suite passes 11 of its 17 tests; the 6 others stop with the same "JPEG helper not built" message, so they are not algorithm failures.

The most important property checked for every carrier is this: after any change to the stego picture or text, the algorithm returns either the original message or an error, and never a wrong message. This held in every test, for all three algorithms.

## Image carrier: capacity

Measured with `capacity()` for PNG and BMP output.

| Image size | Capacity | With password | Bits per pixel |
|---|---:|---:|---:|
| 256 x 256 | 5,219 bytes | 5,207 bytes | 0.637 |
| 512 x 512 | 21,017 bytes | 21,005 bytes | 0.641 |
| 960 x 720 (website gallery) | 55,495 bytes | 55,483 bytes | 0.642 |
| 1920 x 1080 | 166,581 bytes | 166,569 bytes | 0.643 |
| 4032 x 3024 (12 MP phone photo) | 979,728 bytes | 979,716 bytes | 0.643 |

- Capacity grows in proportion to the number of pixels, at about 0.64 bits per pixel.
- This is 21.4% of what plain LSB replacement could hold (3 bits per pixel). The method gives up capacity on purpose: it uses only the more textured half of the picture and changes at most one value in every group of seven.
- Capacity depends only on the size of the picture, not on what it shows. All ten gallery pictures hold exactly 55,495 bytes, and four very different test pictures of 256 x 192 (gradient, noise, one solid colour, checkerboard) all hold 3,902 bytes.
- A password costs 12 bytes of capacity.
- The smallest picture that can hold anything is about 24 x 24 pixels without a password and 32 x 32 with one. Smaller pictures are refused with a clear error.

Chart: `results/image_capacity_by_size.png`. Table: `results/image_capacity.csv`.

## Image carrier: distortion

Measured on 14 cover pictures (the 10 gallery pictures and 4 generated ones), with random messages from 1% to 100% of each picture's capacity. "Sequential LSB" is the classic textbook method, implemented in `evaluate_images.py` only as a comparison, hiding the same number of bits.

| Message size | Team's method PSNR | Sequential LSB PSNR | Values changed (team) | Values changed (LSB) |
|---|---:|---:|---:|---:|
| 1% of capacity | 79.1 dB | 76.6 dB | 0.08% | 0.15% |
| 10% | 70.1 dB | 67.7 dB | 0.64% | 1.11% |
| 50% | 63.2 dB | 60.8 dB | 3.13% | 5.38% |
| 100% | 60.2 dB | 57.8 dB | 6.25% | 10.71% |

- Even a completely full picture stays at 60 dB PSNR and SSIM 0.9998. A change above about 40 dB is not visible to the eye.
- No colour value ever changes by more than 1 level out of 255.
- The team's method is about 2.3 dB better than sequential LSB at every message size, because it hides 3.43 bits for every value it changes and sequential LSB hides 2.0.
- Distortion is almost the same on every cover (all 14 are within 0.1 dB of each other at full capacity), because it depends on how many values change and not on the content.
- These numbers measure how much the picture changes. They do not measure how hard the message is to detect with steganalysis tools.

Chart: `results/image_quality_vs_payload.png`. Tables: `results/image_distortion.csv` (every cover) and `results/image_distortion_summary.csv` (averages).

## Image carrier: robustness and speed

| Edit of the stego PNG | Result |
|---|---|
| Saved again as PNG, converted to BMP, alpha channel added | Message recovered |
| Saved as JPEG, cropped, resized, rotated, mirrored, brightness +1, greyscale | Rejected with an error |

The message survives every lossless copy and is lost after any edit that changes pixel values. Apps that recompress pictures (most messaging apps) will therefore destroy it, so the stego picture has to be sent as a file.

Hiding a 100-byte message in a 960 x 720 picture took about 82 ms without a password and 119 ms with one. Extracting took about 28 ms and 66 ms. The password adds about 37 ms because the key is derived with scrypt, which is slow on purpose.

Tables: `results/image_robustness.csv`, `results/image_timing.csv`.

## Text carrier (`text_stega.py`): capacity and overhead

- Capacity is fixed at 65,535 bytes of secret, whatever the cover text is. A one-word cover can carry it.
- English text: every secret byte becomes 4 invisible characters. The fixed overhead is 32 invisible characters without a password and 184 with one.
- Arabic text (any cover with Arabic letters, including Persian): only 2 invisible characters are used, 1 bit each, so every secret byte becomes 8 characters. The overhead doubles too: 64 without a password and 368 with one.
- The visible text does not change, but the stored text grows by 12 bytes for every secret byte in English (24 in Arabic), because each invisible character takes 3 bytes in UTF-8.

| Secret | English: invisible characters | English: size vs the 39-byte cover | Arabic: invisible characters | Arabic: size vs the 50-byte cover |
|---|---:|---:|---:|---:|
| 10 bytes | 72 | 6.5 times larger | 144 | 9.6 times larger |
| 100 bytes | 432 | 34 times larger | 864 | 53 times larger |
| 1,000 bytes | 4,032 | 311 times larger | 8,064 | 485 times larger |
| 10,000 bytes | 40,032 | 3,080 times larger | 80,064 | 4,805 times larger |

So the hidden message cannot be seen, but a long secret in a short sentence is easy to notice from the size of the text. Without a password, hiding and revealing 10,000 bytes took under 20 ms in English and under 40 ms in Arabic. With a password every operation took about 110 to 145 ms, almost all of it the scrypt key derivation, which is slow on purpose.

Chart: `results/text_overhead.png`. Table: `results/text_overhead.csv`.

## Text carrier (`text_stega.py`): robustness and visibility

The same edits were made to a stego text with an English cover and one with an Arabic cover. Both behaved the same.

| Edit of the stego text | Result |
|---|---|
| Text added before or after, upper case, trimming, collapsing spaces, wrapping lines at 40 columns, Unicode normalisation (NFC, NFKC), JSON, UTF-16 | Message recovered |
| A reply that contains an emoji built from joined characters | Message recovered |
| Text cut after the hidden block | Message recovered (the block sits after the first word) |
| One invisible character deleted, text cut inside the hidden block, two stego texts pasted together | Rejected with an error |
| Sent through a system that keeps only ASCII or only printable characters | Rejected with an error (the message is gone) |

The visible text stayed exactly as typed for every cover tested, with and without a password: an English sentence, one word, French with accents, Japanese, Arabic, a family emoji joined with U+200D and a Persian word written with U+200C. Arabic and Persian covers switch to the Arabic mode automatically. This works because only a long run of invisible characters counts as the hidden message, so the single joiners that emoji and Persian words need are left alone. Spaces and line breaks inside the run are allowed, which is why wrapped lines still work.

Tables: `results/text_robustness.csv`, `results/text_visibility.csv`.

## Birthday attack experiment

A check value of n bits has 2^n possible values, but two different messages with the same check value appear after about 2^(n/2) messages. This matters for the project because, without a password, both the image carrier and the text carrier protect the hidden message with a CRC-32 checksum, which has only 32 bits. With a password both use AES-256-GCM, whose tag has 128 bits and depends on the key.

**Part 1, measured against theory.** Random messages were drawn until two had the same check value (SHA-256 cut to n bits, 300 runs per size).

| Check value | Measured mean | Theory | Measured / theory |
|---|---:|---:|---:|
| 8 bits | 20.5 | 20.7 | 0.99 |
| 16 bits | 333.9 | 321.5 | 1.04 |
| 24 bits | 5,041 | 5,134 | 0.98 |
| 32 bits | 80,566 | 82,138 | 0.98 |

**Part 2, the project's own checksum.** For CRC-32, 600 runs needed 82,972 messages on average (theory 82,138), and half of the runs had a collision within 79,043 messages (theory 77,163). A search of all 4.29 billion values was never needed.

**Part 3, what it means for the project.** The experiment prepares two different messages of the same length with the same CRC-32, which took 163,060 checksums and 0.08 seconds. It hides the first one with the team's code and no password, then exchanges it for the second one while keeping the stored checksum. Both `reveal()` and `extract()` return the second message without any error. The same kind of change on a password-protected message is rejected by both carriers.

**Part 4, larger check values.** Work for a 50% chance of a collision:

| Check value | Tries | At one billion tries per second |
|---|---:|---|
| 32 bits (CRC-32, no password) | 77,163 | under a second |
| 64 bits | 5.06 billion | 5 seconds |
| 128 bits (AES-GCM tag, with password) | 2.17 x 10^19 | 688 years |
| 256 bits (SHA-256) | 4.01 x 10^38 | 1.3 x 10^22 years |

**Conclusion.** The CRC-32 checksum detects accidental damage very well: every single-character or single-value change was caught in the tests. It does not protect against a deliberate change, and it cannot prove which message was hidden. `Member 2/Research.md` says the same in its security section; this experiment measures it. A message that matters should always be hidden with a password, which both carriers offer. The website now shows a warning when the lock is switched off.

Charts: `results/birthday_tries_vs_bits.png`, `results/birthday_crc32_probability.png`. Full output: `results/birthday_attack_log.txt`.

## Issues found

Text carrier (`Member 2/text_stega.py`, used by the website): no open defect. The issues from the first report are fixed. At that time the website used its own text module, `text_stego.py`, which has since been merged into `text_stega.py` and removed.

1. **The cover text changed when it already contained invisible characters** (joined emoji, Persian words). Fixed: only a long run counts as the hidden message, so the cover's own joiners stay.
2. **A reply containing a joined emoji made the message unreadable.** Fixed by the same change.
3. **A message that was not a string raised `AttributeError`.** Fixed: every error is a `TextStegoError`, which is a `ValueError`.
4. **An empty password meant "no password" in the text module but was an error in the image module.** Fixed: both refuse an empty password; `None` means no lock.
5. **Short or non-English covers held nothing.** Fixed: any nonempty cover holds up to 65,535 bytes, and Arabic covers use their own 1-bit mode.
6. **There was no password option.** Fixed: optional AES-256-GCM with the same scrypt settings as the image carrier.
7. **It was not connected to the website.** Fixed: the website calls `hide()` and `reveal()` from this module. Messages hidden by the old module (tag `ZW`) can still be read.
8. **The menu's `stego_output.txt` was not in `.gitignore`.** Fixed in `Member 2/.gitignore`.

Image carrier (`Member 1/image_stego.py`): no defect was found in PNG and BMP output. JPEG output could not be tested here because the helper program was not built.

Website and Member 4's tabs: no defect was found. A hidden message, locked or not, never appears in the database file, in the History list or in the History CSV export. History is private to each user, and Learn runs on the real algorithms.

For the website and the report:

- Without a password a hidden message is not protected against deliberate replacement (birthday experiment). The interface now says so when the lock is switched off.
- A stego picture must be shared as a file. Saving it as JPEG, resizing it or sending it through an app that recompresses pictures destroys the message.
- A long secret in a short cover sentence makes the text hundreds of times larger than it looks.
- A secret hidden in Arabic or Persian text takes twice as many invisible characters as the same secret in English text.
