# Stego Studio: Hiding Secret Messages in Images and Text

**EECE 455/632 · Fall 2026 · Project 17: Steganography (Message and Image)**

Stego Studio is a website for hiding secret messages **inside ordinary pictures or sentences**. You hide a message, download the picture (or copy the text), and later upload it to reveal the message. To anyone else it looks like a normal photo or a normal line of text, and without the password nobody can read it.

The app also **teaches how it works**: a Learn tab walks through every step of the hiding process on a real picture or sentence, using the same code as the Hide button.

---

## Table of contents
1. [What is steganography?](#1-what-is-steganography)
2. [What the app does](#2-what-the-app-does)
3. [How the hiding works](#3-how-the-hiding-works)
4. [Repository structure and team](#4-repository-structure-and-team)
5. [How to run it](#5-how-to-run-it)
6. [Testing](#6-testing)
7. [Security and privacy](#7-security-and-privacy)
8. [Limitations](#8-limitations)

---

## 1. What is steganography?
**Steganography** means hiding a message inside something that looks innocent (the *carrier*), so nobody suspects a secret exists. It is different from **cryptography**:

| | Cryptography | Steganography |
|---|---|---|
| Goal | Make the message **unreadable** | Make the message **invisible** |
| What an observer sees | Scrambled data, so they know a secret exists | A normal picture or sentence |
| Broken when | The key or algorithm is broken | Someone detects hidden data (*steganalysis*) |

Stego Studio uses **both**: it hides the message and encrypts it with the user's password.

---

## 2. What the app does

| Feature | Description |
|---|---|
| **Accounts** | Sign up with e-mail and password. E-mail verification by 6-digit code is built in (off by default). |
| **Hide** | Upload a picture (PNG, JPEG, BMP or HEIC) or pick one from the gallery, **or** write a cover sentence; type the secret and a password. The stego picture downloads straight away; stego text can be copied or saved as `.txt`. |
| **Reveal** | Upload the stego picture or paste the stego text, enter the password, and the message appears. An X-ray view shows the hidden-bit layer of a picture. |
| **Gallery** | 10 built-in cover pictures plus the user's own saved pictures. |
| **Learn** | Explains how the app hides messages, with an interactive **step-by-step walkthrough** on a real picture or sentence, plus a comparison with other methods and apps. |
| **History** | A log of every hide and reveal (including failures such as a wrong password), with filters, delete and CSV export. The secret itself is never stored. |
| **Settings** | Name, password, profile picture, dark mode, accent colour, delete account. |

---

## 3. How the hiding works

### 3.1 Hiding in pictures (PNG / BMP)
Every pixel has three colour values (red, green, blue), each from 0 to 255. Changing the **last bit** of a value moves it by only 1, which no eye can see. Basic *LSB steganography* writes one message bit into each value from top to bottom. Our method improves on that in four ways:

1. **Busy areas only.** The picture is split into 8×8 tiles, scored by texture (how much neighbouring pixels differ), and only the **busier half** is used. Small changes disappear in texture but could show in smooth areas such as a clear sky.
2. **Matrix embedding.** Usable values are grouped in sevens. The XOR of the positions (1–7) whose last bit is 1 gives a 3-bit number, and that number *is* the hidden data. To hide any 3 bits, **at most one value changes by 1**. Plain LSB changes about 1.5 values for the same 3 bits.
3. **Random order.** Groups are visited in a pseudo-random order derived from a random 16-byte *salt* (and from the password, if any), so changes are scattered over the whole image.
4. **Header.** A 43-byte header (tag `ILAB`, version, method, lock flag, length, salt, nonce, CRC) is stored first in a fixed public order, so the receiver knows where and how much to read.

The app extracts the message from the finished picture before handing it over, to verify it.

### 3.2 Hiding in JPEG pictures
JPEG compression would destroy last-bit changes, so JPEG uses a **separate method**: it slightly moves the image's compressed frequency (DCT) coefficients using *quantisation index modulation* (QIM), with repetition and error correction. It survived re-saving down to JPEG quality 30 in our tests, but holds much less data (a few hundred bytes).

### 3.3 Hiding in text
Unicode includes **invisible zero-width characters**. Member 2's `text_stega.py` uses four of them in English text, so each one carries **2 bits**:

| Bits | Character |
|---|---|
| `00` | U+200B Zero Width Space |
| `01` | U+200C Zero Width Non-Joiner |
| `10` | U+2060 Word Joiner |
| `11` | U+2063 Invisible Separator |

In Arabic text only U+200B (`0`) and U+2060 (`1`) are used, **1 bit** each, so the joined Arabic letters are never disturbed. The message plus a small packet header (tag `TS` with its length and a CRC-32 check, or tag `TL` with salt, nonce and the AES-GCM tag when locked) becomes one run of these characters, inserted at the first safe space of the cover sentence. The sentence looks exactly the same, but it becomes longer. Texts made by the website's first format (tag `ZW`, with U+200D) can still be revealed.

### 3.4 Password lock (pictures and text)
- The password and salt go through **scrypt**, a deliberately slow function, to make a 256-bit key.
- The message is encrypted with **AES-256-GCM**. Its 16-byte authentication tag makes the app **refuse** a wrong password or a tampered carrier instead of showing garbage.
- For pictures, the key also decides **which pixels** hold the message.

### 3.5 Capacity and quality (typical)
| Carrier | Holds | Picture quality |
|---|---|---|
| PNG / BMP, 960×720 picture | About 55 KB | PSNR usually well above 40 dB (invisible to the eye) |
| JPEG, 960×720 picture | About 1.3 KB (1,281 bytes) | Changes can be more visible |
| Text | Up to 65,535 bytes | Text looks identical; each byte adds 4 invisible characters (8 in Arabic text) |

---

## 4. Repository structure and team

```
455project-steganography/
├── Member 1/   Image steganography (PNG, BMP, JPEG)
├── Member 2/   Text steganography (zero-width algorithm used by the website, research)
├── Member 3/   The Stego Studio website (Flask)
├── Member 4/   Learn tab, step-by-step walkthrough, History tab, research
└── Member 5/   Automated tests, capacity and distortion evaluation, detection experiment, birthday attack experiment
```

| Member | Responsibility | Main files |
|---|---|---|
| **1: Image steganography** | Image algorithms: texture-adaptive matrix embedding (PNG/BMP), JPEG DCT method, capacity, quality measurement, tests | `Member 1/image_stego.py`, `Member 1/support/` |
| **2: Text steganography** | Zero-width text algorithm (English and Arabic, optional password) used by the website, and research | `Member 2/text_stega.py`, `Member 2/Research.md` |
| **3: Main web application & integration** | Flask website: accounts, Hide and Reveal, gallery, database; connects Member 1 and Member 2 | `Member 3/app.py`, `Member 3/templates/`, `Member 3/static/` |
| **4: Educational & convenience features** | Learn tab, step-by-step visualisation of the real algorithms, History tab, research on similar applications | `Member 4/` |
| **5: Testing, evaluation & birthday attack** | Automated tests, distortion and capacity measurements, detection experiment (steganalysis), birthday attack experiment | `Member 5/tests/`, `Member 5/evaluate_images.py`, `Member 5/evaluate_text.py`, `Member 5/steganalysis.py`, `Member 5/birthday_attack.py`, `Member 5/results/` |

Each member folder has its own README with more detail. Member 1's `support/TECHNICAL_GUIDE.md` documents the image algorithms in depth, and `Member 4/docs/research-similar-apps.md` compares Stego Studio with existing tools (OpenStego, Steghide, StegOnline, StegCloak, SNOW, Steganography Studio).

**Technologies:** Python 3.11, Flask, SQLite, NumPy, Pillow, `cryptography` (scrypt, AES-GCM), HTML/CSS/JavaScript.

---

## 5. How to run it

**Requirements:** Python 3.11+.

**Windows** (from the `Member 3` folder):
```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

**macOS / Linux** (from the `Member 3` folder):
```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Then open **http://127.0.0.1:5000**, create an account, hide a message, and open the downloaded picture in **Reveal**.

**Notes**
- **JPEG** output needs Member 1's one-time native build (see `Member 1/support/TECHNICAL_GUIDE.md`). PNG, BMP and text work without it.
- **E-mail verification** is off by default. See `Member 3/README.md` to turn it on.
- Runtime data (accounts database, own gallery pictures, profile pictures) is created in `Member 3/data/`, which is not committed.

---

## 6. Testing
From the repository root:
```sh
PYTHONPATH="Member 1" python -m unittest discover -s "Member 1/support/tests" -v   # image algorithms (JPEG/HEIC tests need the native build)
python -m unittest discover -s "Member 4/tests" -v           # Learn traces + History
python -m unittest discover -s "Member 5/tests" -v           # 166 tests: all algorithms, website, History, detection, birthday maths
```
Member 4's tests also check that every group of 7 values changes at most one value by exactly 1, and that the secret message is never written to the history. Member 5's folder also measures capacity and image distortion, measures the text carrier's overhead and robustness, tests whether hidden messages can be detected (steganalysis), and runs the birthday attack experiment on the CRC-32 checksum; results and charts are in `Member 5/results/` and summarised in `Member 5/README.md`.

---

## 7. Security and privacy
- The server stores **nothing that is hidden or revealed**: Hide builds the stego picture or text in memory and returns it, and Reveal reads the upload and forgets it.
- The History tab stores **only the length** of each message, never its content.
- Every message is locked with a password (AES-256-GCM). Share the password another way, e.g. by phone.

---

## 8. Limitations
- **No method is undetectable.** Statistical steganalysis can still find hidden data, especially across many pictures. A password protects the content, not the fact that something is hidden.
- **Don't edit received pictures.** Resizing, cropping, screenshots, filters or converting PNG to JPEG destroy the message.
- **Text carriers can be stripped.** Some apps and editors remove zero-width characters, and a character counter or Unicode scanner reveals them.
- JPEG capacity is small, and its recompression tolerance was only verified under tested conditions.
