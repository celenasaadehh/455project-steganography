# Stego Mail (Member 2)

An e-mail style website where people send each other secret messages hidden inside pictures or ordinary text.

- **Accounts.** Sign up with an e-mail address and a password. Users sign in on every visit. First and last name are saved with the account. Optional profile picture (circle, top left). E-mail verification (a 6-digit code sent to the address; 10-minute expiry, 5 tries, resend after 45 s) is built in but **switched off for now**; start the server with `STEGO_VERIFY_EMAIL=1` to turn it on.
- **Inbox / Sent / Gallery / Tutorial / Settings** in the left column.
- **+ button** opens a new message: recipient e-mail, subject, a picture from the built-in gallery of 10 or an upload (PNG, JPEG, BMP, iPhone HEIC), or *Text* mode which hides the secret in invisible characters inside a visible sentence. Optional password lock.
- **Inbox** shows the picture as received. The hidden message is revealed on open (unlocked) or after the password is entered (locked). Unread badge, search, delete, download, dark mode.

Only the stego picture or stego text is stored on the server. The hidden message itself is never stored; it is extracted on demand, so a locked message cannot be read without its password, not even from the database.

## Run it (Windows)

From this `Member 2` folder:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000. Create two accounts (use a private window for the second) to send messages between them.

### Sending real verification e-mails

Only needed when verification is switched on. Copy `mail.env.example` to `data/mail.env` and fill in the Gmail address that will send the codes and its **App Password** (Google Account → Security → 2-Step Verification → App passwords). Start with `$env:STEGO_VERIFY_EMAIL = "1"; .venv\Scripts\python.exe app.py`. Without `mail.env` the code is printed in the server window instead, so the flow can still be tried locally.

JPEG needs Member 1's compiled helper at `Member 1\build\jpegtool.exe` (see Member 1's technical guide). PNG, BMP and text work without it.

## Files

| File | Purpose |
|---|---|
| `app.py` | Flask server: pages, auth, profile, gallery, messages API |
| `db.py` | SQLite schema and helpers (`data/stego.db`) |
| `mailer.py`, `mail.env.example` | SMTP sending of verification codes; settings template |
| `text_stego.py` | Text carrier: zero-width character steganography with optional AES-256-GCM |
| `templates/index.html` | The single page: sign-in, app shell, compose sheet |
| `static/app.css`, `static/app.js` | Design (blue and white, dark mode) and page behaviour |
| `static/gallery/` | The 10 built-in pictures (`tools/make_gallery.py` regenerates them) |
| `data/` | Created at run time: database, sent files, avatars, session key. Not committed. |

Image steganography is imported from `../Member 1/image_stego.py`; nothing is copied.

## API (for the report)

| Method and path | Purpose |
|---|---|
| `POST /api/auth/register`, `/verify`, `/resend`, `/login`, `/logout` · `GET /api/me` | Accounts, e-mail code, session |
| `POST /api/me`, `POST/DELETE /api/me/avatar` | Name, password, profile picture |
| `GET /api/users/lookup?q=` | Check a recipient exists |
| `GET /api/gallery` · `POST /api/image/capacity` | Built-in pictures and how much a picture can hold |
| `POST /api/messages` · `GET /api/messages?box=inbox\|sent` | Send and list |
| `POST /api/messages/<id>/reveal` · `DELETE /api/messages/<id>` | Extract the hidden message; delete |
| `GET /files/<id>`, `/files/<id>/thumb`, `/avatars/<uid>` | Files, only for sender and recipient |

Accounts are identified by a verified e-mail address. This is not Google OAuth (that needs a Google Cloud client ID); ownership is proven by the e-mailed code instead.
