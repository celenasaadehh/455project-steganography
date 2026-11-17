# Research: Similar Existing Steganography Applications

*Member 4: Educational & Convenience Features (EECE 455/632, Project 17: Stego Mail)*

## Why we looked at existing tools
Before building the educational and convenience features, we reviewed popular steganography tools. We wanted to see (1) which carriers and methods they support, (2) how easy they are to use, and (3) whether they **teach** the user what is happening. Point (3) matters because the course asks for an application that is "user friendly and suitable for educational purposes".

## Tools reviewed

| Tool | Carrier(s) | Hiding method | Interface | Extra features | Explains itself? |
|---|---|---|---|---|---|
| **OpenStego** | Images | LSB (plugins: LSB, RandomLSB) | Desktop GUI (Java) | Password encryption, watermarking | No |
| **Steghide** | JPEG, BMP, WAV, AU | Graph-theoretic method that keeps file statistics unchanged | Command line | Compression, encryption, checksum | No |
| **StegOnline** | Images (analysis focus) | LSB embed/extract, bit-plane browsing | Web | Browse bit planes, colour tricks | Partly: shows bit planes, no explanation |
| **StegCloak** | Plain text | Zero-width Unicode characters | Web, JS library, CLI | Compression + password encryption | No |
| **SNOW** | Plain ASCII text | Trailing spaces and tabs | Command line | Compression, ICE encryption | No |
| **Steganography Studio** | Images | Several algorithms + steganalysis | Desktop GUI (Java, old) | Compares methods | Yes, but old and desktop-only |

## Key findings
1. **Almost no tool explains itself.** Most are black boxes: message in, file out. You never see which pixels changed or why the picture still looks the same.
2. **Basic LSB is the common image method** (OpenStego, StegOnline). It is simple but leaves clustered, statistically detectable changes. Our app (Member 1) improves on it with texture-adaptive tile selection, matrix embedding (3 bits per 7 values, at most one change) and randomised pixel order. It also offers a separate JPEG method that survives re-saving.
3. **Text tools use invisible characters or whitespace.** StegCloak uses zero-width characters, SNOW uses trailing whitespace. Our app (Member 2) uses four zero-width characters, so each carries 2 bits.
4. **Most tools add encryption on top of hiding.** Ours does too: scrypt + AES-256-GCM, shared by the image and text methods.
5. **None of them** lets you send the result to another user, keep a history, or pick from a built-in gallery.

## What Stego Mail adds

| Gap in existing tools | Stego Mail |
|---|---|
| Black box, no explanation | **Learn tab**: explains our actual methods, with a step-by-step walkthrough that runs the real code |
| You can't see what changed | Busy-area map, the real groups of 7 values before/after, map of changed pixels, PSNR |
| No record of past operations | **History tab**: every hide and reveal (secret never stored) |
| Files must be passed around by hand | Built-in mail: send to another user's inbox |
| Choosing a cover image | **Gallery**: 10 built-in pictures + your own |
| Desktop install or command line | Runs in the browser |

## Sources
- OpenStego: https://github.com/syvaidya/openstego
- Steghide manual: https://manpages.ubuntu.com/manpages/jammy/man1/steghide.1.html
- StegOnline: https://github.com/Ge0rg3/StegOnline
- StegCloak: https://github.com/0xflotus/stegcloak
- SNOW: https://darkside.com.au/snow/manual.html
- Steganography Studio: https://stegstudio.sourceforge.net/
