# Stego Studio (Member 3)

A website for hiding a secret message inside a picture or an ordinary sentence, downloading the result, and revealing it again later. Nothing is sent to anyone: you keep or share the file yourself.

- **Accounts.** Sign up with an e-mail address and a password. Users sign in on every visit. Optional profile picture. E-mail verification (a 6-digit code) is built in but **switched off for now**; start the server with `STEGO_VERIFY_EMAIL=1` to turn it on.
- **Hide.** Pick a picture from the built-in gallery of 10, one of your own, or an upload (PNG, JPEG, BMP, iPhone HEIC). Write the secret and a password (at least 6 characters), choose PNG, JPEG or BMP, and the stego picture downloads straight away. A black-and-white picture stays black-and-white. *Text* mode hides the secret in invisible characters inside a visible sentence; copy it or save it as `.txt`. A meter shows how much the picture can hold, and **X-ray** / **Show hidden** let you see where the message went.
- **Reveal.** Upload (or drop) a stego picture, or paste stego text, enter the password, and the message appears. After 5 wrong passwords in 15 minutes the account has to wait; Sign in is limited the same way.
- **Gallery / Learn / History / Settings** in the left column. Learn and History come from Member 4.

The server stores **nothing you hide or reveal**: Hide builds the picture or text in memory and returns it to the browser; Reveal reads the upload and forgets it.

## Run it

From this `Member 3` folder, on **Windows**:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

On **macOS / Linux**:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Open http://127.0.0.1:5000, create an account, hide a message, then open the downloaded picture in **Reveal**.

### Sending real verification e-mails

Only needed when verification is switched on. Copy `mail.env.example` to `data/mail.env` and fill in the Gmail address that will send the codes and its **App Password** (Google Account → Security → 2-Step Verification → App passwords). Start with `$env:STEGO_VERIFY_EMAIL = "1"; .venv\Scripts\python.exe app.py` (Windows) or `STEGO_VERIFY_EMAIL=1 .venv/bin/python app.py` (macOS / Linux). Without `mail.env` the code is printed in the server window instead.

JPEG needs Member 1's compiled helper at `Member 1\build\jpegtool.exe` (see Member 1's technical guide). PNG, BMP and text work without it.

## Files

| File | Purpose |
|---|---|
| `app.py` | Flask server: pages, auth, profile, gallery, hide and reveal API |
| `db.py` | SQLite schema and helpers (`data/stego.db`): accounts and own gallery pictures |
| `mailer.py`, `mail.env.example` | SMTP sending of verification codes; settings template |
| `templates/index.html` | The single page: sign-in, app shell, Hide and Reveal |
| `static/app.css`, `static/app.js` | Design (blue and white, dark mode) and page behaviour |
| `static/gallery/` | The 10 built-in pictures (`tools/make_gallery.py` regenerates them) |
| `data/` | Created at run time: database, own gallery pictures, avatars, session key. Not committed. |

Image steganography is imported from `../Member 1/image_stego.py` and text steganography from `../Member 2/text_stega.py`; nothing is copied.

## API (for the report)

| Method and path | Purpose |
|---|---|
| `POST /api/auth/register`, `/verify`, `/resend`, `/login`, `/logout` · `GET /api/me` | Accounts, e-mail code, session |
| `POST /api/me`, `POST/DELETE /api/me/avatar`, `DELETE /api/me` | Name, password, preferences, profile picture, delete account |
| `GET/POST /api/gallery`, `DELETE /api/gallery/<id>` | Built-in and own pictures |
| `POST /api/image/capacity` | How much a picture can hold |
| `POST /api/hide` | `carrier=image`: returns the stego picture as a download. `carrier=text`: returns `{ok, text}` |
| `POST /api/reveal` | Picture upload or pasted text (+ password) → `{ok, message}` |
