
# Text Steganography — Research and Implementation

**Course:** EECE 455/632 — Cryptography and Network Security  
**Project:** 17 — Steganography (Message and Image)  
**Contribution:** Member 2 — Text Steganography

---

## 1. Introduction

Steganography is the technique of hiding secret information inside ordinary data so that the presence of the hidden message is not immediately noticeable.

Unlike cryptography, which makes a message unreadable, steganography attempts to conceal the existence of the message itself.

Text steganography hides secret information inside written text using techniques such as whitespace manipulation, synonym substitution, language models, and invisible Unicode characters.

The objective of our implementation is to allow users to enter a carrier paragraph and a secret message, generate a modified paragraph containing the hidden information, and recover the secret without requiring the original paragraph.

## 2. Text Steganography Methods Researched

### 2.1 Whitespace-Based Steganography

Whitespace-based steganography hides information by modifying spaces, tabs, or other formatting characters.

For example, different spacing patterns can represent binary values.

**Advantages:**
- Simple to understand and implement.
- Does not require complex algorithms.

**Limitations:**
- Formatting changes may destroy the hidden message.
- Some methods have low hiding capacity.
- Additional spaces may be detectable.

### 2.2 Synonym Substitution

Synonym substitution hides information by replacing selected words with alternatives that have similar meanings.

For example, choosing between "big" and "large" can represent different binary values.

**Advantages:**
- Can preserve natural-looking text.
- Does not require invisible Unicode characters.
- Hides information through linguistic choices.

**Limitations:**
- Synonyms are not always interchangeable.
- Word replacements may change the meaning of a sentence.
- Reliable decoding requires consistent word choices.
- Hiding capacity depends on the available synonyms.

### 2.3 BERT-Based Linguistic Steganography

BERT (Bidirectional Encoder Representations from Transformers) is a pretrained language model that uses the surrounding context to understand words in sentences.

Research by Ueoka et al. (2021) explores edit-based linguistic steganography using a masked language model.

#### Our BERT Implementation

During the research and experimentation phase, we implemented a BERT-based text steganography approach using Python.

Our implementation used:

- A pretrained BERT language model.
- The Hugging Face Transformers library.
- PyTorch.
- WordNet for synonym selection.
- Python functions for encoding and decoding secret information.

The objective was to hide binary information by replacing selected words with contextually suitable alternatives.

#### How Our Approach Worked

1. The user provided a carrier paragraph and a secret message.
2. The secret message was converted into binary.
3. BERT analyzed words in their sentence context.
4. WordNet helped identify alternative words.
5. Candidate replacements were evaluated for suitability.
6. Selected replacements represented secret bits.
7. The decoder attempted to reconstruct the hidden information from the modified text.

#### Experiments Performed

We experimented with several variations:

**Experiment 1: Basic Synonym Encoding**

We investigated whether selecting between alternative words could represent binary values.

**Experiment 2: Adaptive Bit Encoding**

We experimented with different numbers of available word choices, allowing some positions to represent more than one bit.

**Experiment 3: Block Coding**

We explored combining several word-selection positions to encode groups of secret bits.

#### Observations

Our experiments demonstrated that BERT-assisted synonym substitution could hide and recover short messages under controlled conditions.

However, several limitations were observed:

- Some proposed synonyms did not preserve the exact meaning.
- Some replacements sounded unnatural in context.
- The number of usable word positions was limited.
- Longer messages required significantly more carrier text.
- Reliable encoding and decoding were more complicated.
- Additional machine learning dependencies were required.

For example, one adaptive experiment provided approximately 34 bits of hiding capacity in a carrier containing 230 words.

This corresponds to approximately 0.148 bits per word for that experimental carrier. It is not a general performance guarantee.

#### Conclusion of BERT Experiments

Although we successfully implemented and experimented with BERT-based linguistic steganography, its capacity and meaning-preservation limitations made it less suitable for our final educational web application.

Therefore, we selected zero-width Unicode steganography as our main implementation.

The BERT-based approach remains an important part of our research and experimental work.

### 2.4 Zero-Width Unicode Steganography

Zero-width Unicode steganography hides information by inserting invisible Unicode characters into ordinary text.

These characters can be stored and processed by software without being visible during normal reading.

**Advantages:**
- Preserves the visible carrier paragraph.
- Supports simple encoding and decoding.
- Does not require machine learning libraries.
- Provides relatively high hiding capacity.
- Suitable for web application integration.
- Can support UTF-8 secret messages.

**Limitations:**
- Invisible characters can be detected programmatically.
- Some applications remove or normalize them.
- The method does not encrypt secret messages.
- Copying text through certain applications may destroy hidden data.

---

## 3. Comparison of Researched Techniques

| Technique | Main Advantage | Main Limitation |
|---|---|---|
| Whitespace-based | Simple implementation | Formatting can destroy data |
| Synonym substitution | Uses linguistic changes | May alter meaning |
| BERT-based | Context-aware word selection | Complex and capacity-limited |
| Zero-width Unicode | Preserves visible text | Invisible characters are detectable |

After researching and experimenting with these techniques, we selected **zero-width Unicode steganography** for our final implementation.

Our decision prioritized reliability, ease of integration, and preservation of the visible text.

---

## 4. Selected Algorithm: Zero-Width Unicode Steganography

Our final implementation uses four invisible Unicode characters for English text.

| Binary Value | Unicode | Character Name |
|---|---|---|
| 00 | U+200B | Zero Width Space |
| 01 | U+200C | Zero Width Non-Joiner |
| 10 | U+2060 | Word Joiner |
| 11 | U+2063 | Invisible Separator |

Each invisible character represents **two bits** of information.

For example, the letter `H` is represented in UTF-8 by the byte:

`01001000`

The algorithm divides it into pairs:

`01 00 10 00`

Each pair is converted into its corresponding invisible Unicode character.

### Arabic Mode

Arabic letters join to their neighbours, and U+200C would break a join if it landed inside a word.

When the carrier contains Arabic letters, the algorithm therefore uses only two characters, each holding **one bit**:

| Binary Value | Unicode | Character Name |
|---|---|---|
| 0 | U+200B | Zero Width Space |
| 1 | U+2060 | Word Joiner |

The mode is chosen automatically from the carrier.

The visible wording remains unchanged in both modes.

## 5. Encoding Algorithm

The encoder performs the following steps:

1. Receive the carrier paragraph, the secret message and an optional password.
2. Convert the secret into UTF-8 bytes.
3. Without a password, build the packet `TS` + message length + secret + CRC32 checksum.
4. With a password, build the packet `TL` + salt + nonce + the secret encrypted with AES-256-GCM.
5. Convert the complete packet into binary.
6. Choose the mode: two bits per character for English, one bit for Arabic.
7. Map the bits to invisible Unicode characters.
8. Insert the whole invisible run in one place, right after the first space of the carrier.
9. Return the modified paragraph.
10. Allow the result to be saved as a UTF-8 text file.

### Position Selection

Our first version distributed the invisible characters after English letters across the whole paragraph.

That design limited the capacity to about one byte for every four English letters, so short sentences and Arabic text could not carry any message.

The final version places the hidden run in a single block after the first space.

This means any nonempty carrier, even a single word, can hold the maximum message size.

The insertion point is never placed next to an invisible character that already belongs to the carrier.

## 6. Decoding Algorithm

The decoder reverses the encoding process.

1. Receive the modified paragraph.
2. Find the hidden run: eight or more invisible characters in a row.
3. Ignore single invisible characters elsewhere, because joined emoji and Persian words use them.
4. Allow spaces and line breaks inside the run, because some applications wrap long lines.
5. Detect the mode: the English header always contains U+200C, and the Arabic mapping never does.
6. Convert the characters back into bits and rebuild the packet bytes.
7. Read the tag: `TS` means no password, `TL` means the message is locked.
8. Without a password, check the stored length and the CRC32 checksum.
9. With a password, derive the key and decrypt; the GCM tag rejects a wrong password or any edit.
10. Decode the secret message as UTF-8.

### Blind Decoding

Our implementation supports decoding without requiring the original carrier paragraph.

The receiver only needs the modified paragraph containing the hidden information, and the password if one was used.

---

## 7. Python Implementation

**Main Python file:** `text_stega.py`

The implementation contains both the encoder and decoder.

### Main Functions

**encode_text(carrier, secret, password=None)**

Hides a secret message inside a carrier paragraph, optionally locked with a password.

**decode_text(stego, password=None)**

Extracts the secret message from the modified paragraph.

**remove_hidden_symbols(stego)**

Returns the original carrier, keeping the carrier's own invisible characters.

**capacity_info(carrier)**

Reports the chosen mode, the maximum secret size and the overhead.

The website calls the same functions as `hide()`, `reveal()` and `strip_hidden()`.

### Additional Features

- UTF-8 message encoding.
- Automatic English or Arabic mode.
- Optional password: AES-256-GCM with a key derived by scrypt, using the same settings as the image module.
- Message length storage.
- CRC32 corruption detection without a password.
- Carriers containing joined emoji or Persian words are kept exactly.
- Clear errors (`TextStegoError`, and `TextPasswordError` for password problems).
- Reading the website's first text format (tag `ZW`), so older messages still open.
- Saving and reading UTF-8 text files.
- A terminal interface for testing.

Without a password, the algorithm reserves eight bytes for metadata:

- Two bytes for the `TS` identifier.
- Two bytes for the message length.
- Four bytes for the CRC32 checksum.

With a password, it reserves 46 bytes:

- Two bytes for the `TL` identifier.
- Sixteen bytes of random salt.
- Twelve bytes of random nonce.
- Sixteen bytes for the GCM authentication tag.

The capacity does not depend on the carrier.

The two-byte length field limits secret messages to 65,535 bytes.

The number of invisible characters added is:

`English: 4 × (secret bytes + overhead bytes)`

`Arabic: 8 × (secret bytes + overhead bytes)`

---

## 8. Experimental Results

We tested the final implementation with short carriers, Arabic and Persian carriers, and a password.

| Test | Carrier | Secret | Mode | Invisible characters | Visible text unchanged | Recovered |
|---|---|---|---|---:|---|---|
| 1 | `See you at five.` (16 characters) | `Hi` (2 bytes) | English | 40 | Yes | Yes |
| 2 | English sentence (63 characters) | `Meet me @ 5` (11 bytes) | English | 76 | Yes | Yes |
| 3 | Arabic sentence (27 characters) | `Hi` (2 bytes) | Arabic | 80 | Yes | Yes |
| 4 | `See you at five.` with a password | `Hi` (2 bytes) | English | 192 | Yes | Yes |
| 5 | Persian sentence containing U+200C | `Meet me @ 5` (11 bytes) | Arabic | 152 | Yes | Yes |

### Findings

The tests show that even a 16-character sentence can carry a message.

Arabic and Persian carriers work, at twice the number of invisible characters.

A password adds 38 bytes of overhead, or 152 invisible characters in English.

Member 5's automated tests and evaluation cover the module further: round trips, tampering, copy and paste edits, joined emoji, line wrapping and timing. The results are in `Member 5/README.md` and `Member 5/results/`.

---

## 9. Security Considerations

Without a password, zero-width Unicode steganography provides information hiding, not encryption.

Although the secret is invisible during normal reading, software can identify the hidden Unicode characters.

An attacker who understands the encoding method may recover an unlocked message.

Unlocked messages use CRC32 to detect accidental corruption.

CRC32 is not a cryptographic authentication method and does not prevent intentional tampering.

Member 5's birthday attack experiment demonstrated this: two meaningful messages with the same CRC32 were found in under a second, and one was swapped for the other without any error.

With a password, the secret is encrypted with AES-256-GCM.

The key is derived from the password with scrypt, which is deliberately slow and makes guessing passwords expensive.

The 16-byte GCM tag detects a wrong password and any change to the hidden data.

The website warns users when they send a message without a password.

## 10. Limitations

The main limitations include:

- Hidden characters may be removed by text sanitization.
- Some editors and websites modify Unicode formatting.
- An attacker may detect zero-width characters.
- A long secret makes the stored text much larger than it looks; each invisible character takes three bytes in UTF-8.
- Arabic text needs twice as many invisible characters as English text.
- The method is not designed to resist advanced steganalysis.

The modified text should therefore be preserved exactly, preferably as a UTF-8 text file.

## 11. Website Integration

The text steganography implementation is integrated into the group's web application, Stego Mail.

The website's backend imports `text_stega.py` directly from this folder.

The website allows users to:

1. Choose **Text** when writing a message.
2. Enter a visible carrier sentence and a secret message.
3. Optionally lock the message with a password.
4. Send the stego text to another user.
5. Reveal the hidden message in the inbox, entering the password if needed.
6. View the hidden characters as a coloured barcode with **Show hidden**.

Member 4's Learn tab walks through the same functions step by step.

The terminal interface is retained for testing but is not required for website interaction.

## 12. Future Work

Further work could include:

- Testing which messaging and e-mail applications preserve the hidden characters.
- Spreading the hidden run while keeping the current capacity, to make it harder to spot.
- Comparing capacity and robustness with the BERT-based experimental approach.

## 13. Conclusion

This project investigated several text steganography techniques, including whitespace-based methods, synonym substitution, BERT-based linguistic steganography, and zero-width Unicode steganography.

We implemented and experimented with a BERT-based approach using contextual word prediction and synonym selection.

Although the experiments demonstrated the potential of linguistic steganography, limitations related to capacity, naturalness, and decoding complexity were observed.

Consequently, we implemented zero-width Unicode steganography as the final text-hiding method for the web application.

The final algorithm preserves the visible carrier paragraph, works with English, Arabic and Persian text, supports an optional password, and recovers messages without the original paragraph.

Our tests and Member 5's evaluation confirmed reliable message hiding and recovery.

## 14. References

[1] M. T. Ahvanooey et al., "Modern Text Hiding, Text Steganalysis, and Applications: A Comparative Analysis," Entropy, 2019.

https://pmc.ncbi.nlm.nih.gov/articles/PMC7514839/

[2] M. A. Majeed et al., "A Review on Text Steganography Techniques," Mathematics, 2021.

https://doi.org/10.3390/math9212829

[3] H. Ueoka, Y. Murawaki, and S. Kurohashi, "Frustratingly Easy Edit-based Linguistic Steganography with a Masked Language Model," NAACL, 2021.

https://aclanthology.org/2021.naacl-main.433/

[4] Official BERT-Based Steganography Research Implementation.

https://github.com/ku-nlp/steganography-with-masked-lm

[5] Unicode Consortium, Unicode Character Charts.

https://www.unicode.org/charts/
