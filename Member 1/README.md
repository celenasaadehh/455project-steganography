# Image Stego Lab — Member 1

**Start here.** Open this folder in VS Code. `image_stego.py` is the only application source file you normally open. `requirements.txt` installs the Python dependencies. `support/` holds the JPEG build files, HEIC fallback decoder, tests, and research evidence. Keep that folder in the repository; you do not need to edit it for normal use.

## Test with your own photo

From the project folder in macOS Terminal, replace `My Photo.HEIC` with the exact name of a photo on your Desktop. You do not need to copy it into the project.

```sh
.venv/bin/python -m image_stego embed "$HOME/Desktop/My Photo.HEIC" "$HOME/Desktop/stego-test.png" --text "My test message" --demo
.venv/bin/python -m image_stego extract "$HOME/Desktop/stego-test.png" "$HOME/Desktop/recovered-test.txt"
cat "$HOME/Desktop/recovered-test.txt"
```

Use new output names if those files already exist. Extract from the **generated** image, not your original photo. `--demo` does not encrypt; omit it to set a password. Included test fixtures are only for repeatable tests; they are not required for your own photos.

**Output choices:** PNG is the lossless default. BMP uses the same embedding method without alpha support. JPEG uses the separate DCT method and needs a one-time native build. HEIC is supported as input, not output. Recompression tolerance is limited to tested conditions, not a guarantee.

**Next:** For the JPEG build or Member 3’s integration calls (`capacity`, `embed`, `extract`, `measure`), see the [technical guide](support/TECHNICAL_GUIDE.md). It also contains the algorithm rationale, test instructions, and references. Keep the entire folder together when you copy it to your team repo.
