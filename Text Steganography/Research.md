
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

Our final implementation uses four invisible Unicode characters.

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

These characters are inserted into the user's original paragraph.

The visible wording remains unchanged.

## 5. Encoding Algorithm

The encoder performs the following steps:

1. Receive the carrier paragraph and secret message.
2. Convert the secret into UTF-8 bytes.
3. Prepare a message header and CRC32 checksum.
4. Convert the complete payload into binary.
5. Divide the binary sequence into pairs of bits.
6. Map each pair to an invisible Unicode character.
7. Identify eligible English letters in the carrier paragraph.
8. Distribute the invisible characters after selected letters.
9. Return the modified paragraph.
10. Allow the result to be saved as a UTF-8 text file.

### Position Selection

The encoder automatically chooses positions throughout the paragraph.

Rather than inserting all invisible characters at the beginning, it distributes them across available English letters.

This preserves the visible paragraph and avoids concentrating the entire hidden payload in one location.

## 6. Decoding Algorithm

The decoder reverses the encoding process.

1. Receive the modified paragraph.
2. Scan it for the four invisible Unicode characters.
3. Convert each invisible character into its corresponding two-bit value.
4. Reconstruct the binary information.
5. Rebuild the original bytes.
6. Read the stored message length.
7. Extract and decode the secret message.
8. Verify the CRC32 checksum.

### Blind Decoding

Our implementation supports decoding without requiring the original carrier paragraph.

The receiver only needs the modified paragraph containing the hidden information.

---

## 7. Python Implementation

**Main Python file:** `text_stega.py`

The implementation contains both the encoder and decoder.

### Main Functions

**encode_text(carrier, secret)**

Hides a secret message inside a carrier paragraph.

**decode_text(stego)**

Extracts the secret message from the modified paragraph.

**capacity_info(carrier)**

Calculates how much secret information the carrier can hold.

### Additional Features

- UTF-8 message encoding.
- Automatic position selection.
- Capacity checking before encoding.
- Message length storage.
- CRC32 corruption detection.
- Saving and reading UTF-8 text files.
- A terminal interface for testing.

The algorithm reserves eight bytes for metadata:

- Two bytes for the `TS` identifier.
- Two bytes for the message length.
- Four bytes for the CRC32 checksum.

The maximum secret capacity is calculated as:

`max_secret_bytes = max(0, floor(English_letter_count / 4) - 8)`

The two-byte length field further limits supported secret messages to 65,535 bytes.

---

## 8. Experimental Results

We performed initial tests using different carrier paragraphs and secret messages.

### Test 1: Short Secret Message

**Secret:** `Hi`

**Carrier:** 115 English letters

**Secret size:** 2 bytes

**Maximum carrier capacity:** 20 bytes

**Results:**
- Encoding succeeded.
- The visible paragraph remained unchanged.
- The message was recovered successfully.
- The recovered secret matched the original.

### Test 2: Longer Secret Message

**Secret:** `Meet me @ 5`

**Carrier:** 240 English letters

**Secret size:** 11 bytes

**Maximum carrier capacity:** 52 bytes

**Results:**
- Encoding succeeded.
- The visible paragraph remained unchanged.
- The message was recovered successfully.
- The recovered secret matched the original.

### Initial Findings

The tests demonstrate that the implemented algorithm can successfully encode and decode the tested messages.

They also confirm that the visible carrier text remains unchanged during these tests.

Additional independent decoding and web integration tests are required for a more complete evaluation.

---

## 9. Security Considerations

Zero-width Unicode steganography provides information hiding, not encryption.

Although the secret is invisible during normal reading, software can identify the hidden Unicode characters.

An attacker who understands the encoding method may recover the message.

The implementation also uses CRC32 to detect accidental corruption.

CRC32 is not a cryptographic authentication method and does not prevent intentional tampering.

For additional confidentiality, encryption could be applied to a secret before hiding it.

This would be a separate security enhancement.

## 10. Limitations

The main limitations include:

- Hidden characters may be removed by text sanitization.
- Some editors and websites modify Unicode formatting.
- An attacker may detect zero-width characters.
- Carrier length limits the secret message size.
- The method is not designed to resist advanced steganalysis.

The modified text should therefore be preserved exactly, preferably as a UTF-8 text file.

## 11. Website Integration

The text steganography implementation is intended to be integrated into the group's web application.

The website will allow users to:

1. Enter a carrier paragraph.
2. Enter a secret message.
3. Encode and generate a stego paragraph.
4. Download the modified text.
5. Upload or paste stego text.
6. Decode and recover the hidden message.
7. Check the hiding capacity.

The web application's backend can import the Python functions from `text_stega.py`.

The terminal interface is retained for testing but is not required for website interaction.

## 12. Future Work

Further evaluation should include:

- Independent decoding from saved files.
- Unicode secret messages containing Arabic and emojis.
- Insufficient-capacity error handling.
- Corrupted-payload detection.
- Download and upload testing through the website.
- Testing whether copy-paste operations preserve hidden data.
- Comparing capacity and robustness with the BERT-based experimental approach.

## 13. Conclusion

This project investigated several text steganography techniques, including whitespace-based methods, synonym substitution, BERT-based linguistic steganography, and zero-width Unicode steganography.

We implemented and experimented with a BERT-based approach using contextual word prediction and synonym selection.

Although the experiments demonstrated the potential of linguistic steganography, limitations related to capacity, naturalness, and decoding complexity were observed.

Consequently, we implemented zero-width Unicode steganography as the final text-hiding method for the web application.

The selected algorithm preserves the visible carrier paragraph, supports independent message recovery, and provides a straightforward Python implementation.

Our initial tests successfully demonstrated message hiding and recovery.

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
