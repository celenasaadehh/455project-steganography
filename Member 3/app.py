"""Stego Studio: hide a secret message in a picture or a sentence, download it, reveal it later.

Run from this folder:  python app.py   then open http://127.0.0.1:5000
Image steganography comes from Member 1 (../Member 1/image_stego.py), text from
Member 2 (../Member 2/text_stega.py). Nothing is sent to anyone: Hide returns the
finished picture or text straight to the browser and Reveal reads an uploaded one.
Neither the stego files nor the hidden messages are stored on the server.
"""
from __future__ import annotations

import io
import json
import os
import re
import secrets
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file, session
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "Member 1"))
sys.path.insert(0, str(ROOT.parent / "Member 2"))
sys.path.insert(0, str(ROOT.parent / "Member 4"))

import image_stego as img  # noqa: E402  (Member 1's module)
import text_stega as txt  # noqa: E402  (Member 2's text carrier)
import db  # noqa: E402
import mailer  # noqa: E402
import member4  # noqa: E402  (Member 4: Learn tab + History tab)
import extras  # noqa: E402  (self-destruct date, split secret, QR code)

VERIFY_EMAIL = os.environ.get("STEGO_VERIFY_EMAIL", "0") == "1"  # off for now: accounts work without the e-mailed code
ACCENTS = ("navy", "sky", "red", "green", "purple")  # app colour choices in Settings
CODE_TTL_MIN = 10        # a verification code is valid this long
CODE_RESEND_SEC = 45     # minimum gap between two codes for the same address
CODE_MAX_TRIES = 5
MIN_PASSWORD = 6         # shortest password Hide accepts (and accounts use)
TRY_WINDOW = 15 * 60     # wrong passwords are counted over this many seconds
TRY_LIMIT = 5            # wrong passwords allowed per account in that window...
TRY_LIMIT_IP = 20        # ...and per network address (stops spreading guesses over many accounts)

GALLERY_DIR = ROOT / "static" / "gallery"       # the 10 built-in pictures
USER_GALLERY = db.DATA / "gallery"               # pictures users add to their own gallery
USER_GALLERY_MAX = 30
AVATARS = db.DATA / "avatars"
FORMATS = {"PNG": "png", "JPEG": "jpg", "BMP": "bmp"}
MIMES = {"png": "image/png", "jpg": "image/jpeg", "bmp": "image/bmp"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _secret_key() -> bytes:
    db.DATA.mkdir(exist_ok=True)
    f = db.DATA / "secret.key"
    if not f.exists():
        f.write_bytes(secrets.token_bytes(32))
    return f.read_bytes()


db.init()
if not VERIFY_EMAIL:
    # Verification is off: no account may sit in the "unverified" state, because that
    # state would let someone else re-register the same e-mail.
    db.run("UPDATE users SET verified=1, code_hash=NULL WHERE verified=0")
app = Flask(__name__)
app.secret_key = _secret_key()
app.config.update(
    MAX_CONTENT_LENGTH=img.MAX_FILE + 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
member4.init_app(app)  # Member 4: Learn + History (see ../Member 4/README.md)
# Sessions are not permanent: the cookie ends when the browser closes, and the
# page itself signs out on every load, so users sign in each time they enter.


# ---------------------------------------------------------------- helpers

def fail(message: str, code: str = "error", status: int = 400):
    return jsonify(ok=False, error=message, code=code), status


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("uid"):
            return fail("Please sign in.", "auth", 401)
        return fn(*a, **kw)
    return wrapper


def current_user():
    return db.one("SELECT * FROM users WHERE id=?", session["uid"])


def public_user(u: dict | None, me: bool = False):
    """What the browser sees of a user."""
    if not u:
        return None
    out = {
        "id": u["id"], "handle": u["handle"], "is_email": bool(u["is_email"]),
        "first_name": u["first_name"], "last_name": u["last_name"],
        "name": f"{u['first_name']} {u['last_name']}".strip(),
        "initials": (u["first_name"][:1] + u["last_name"][:1]).upper() or u["handle"][:2].upper(),
        "avatar": f"/avatars/{u['id']}?v={u['avatar']}" if u["avatar"] else None,
        "accent": u.get("accent") or "navy",
    }
    if me:
        out["created"] = u["created"]
    return out


def me_user():
    return public_user(current_user(), me=True)


def normalize_handle(raw: str):
    """Accounts are identified by e-mail address only; one account per address.

    Lower-cased and trimmed. For Gmail, dots and "+tags" in the name part are ignored
    (Gmail delivers them to the same inbox), so they cannot be used to make a second account.
    """
    h = (raw or "").strip().lower()
    if not EMAIL_RE.match(h):
        raise ValueError("Enter a valid e-mail address.")
    local, domain = h.rsplit("@", 1)
    if domain in ("gmail.com", "googlemail.com"):
        local = local.split("+", 1)[0].replace(".", "")
        h = f"{local}@gmail.com"
    return h, True


def _user_by_handle(raw) -> dict | None:
    try:
        handle, _ = normalize_handle(raw or "")
    except ValueError:
        return None
    return db.one("SELECT * FROM users WHERE handle=?", handle)


def _upload(field: str) -> bytes | None:
    f = request.files.get(field)
    if f is None or not f.filename:
        return None
    return f.read()


def _unlink_quiet(path: Path):
    """Delete a file; on Windows a file still being served can be briefly locked, so never fail on it."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


class Attempts:
    """Counts wrong passwords in memory and blocks a key after too many in TRY_WINDOW seconds."""

    def __init__(self):
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        times = [t for t in self._fails.get(key, []) if now - t < TRY_WINDOW]
        if times:
            self._fails[key] = times
        else:
            self._fails.pop(key, None)
        return times

    def wait(self, limits: dict[str, int]) -> int:
        """Seconds until the blocked key with the longest wait is free again (0 = not blocked)."""
        now = time.time()
        with self._lock:
            waits = [int(times[-limit] + TRY_WINDOW - now) + 1
                     for key, limit in limits.items() if len(times := self._recent(key, now)) >= limit]
        return max(waits, default=0)

    def fail(self, *keys: str):
        with self._lock:
            for key in keys:
                self._fails.setdefault(key, []).append(time.time())

    def clear(self, *keys: str):
        with self._lock:
            for key in keys or list(self._fails):
                self._fails.pop(key, None)


attempts = Attempts()


def _too_many(limits: dict[str, int]):
    """A 429 response if any of the keys is blocked, else None."""
    wait = attempts.wait(limits)
    if not wait:
        return None
    minutes = max(1, round(wait / 60))
    return fail(f"Too many wrong passwords. Try again in {minutes} minute{'s' if minutes > 1 else ''}.", "slow_down", 429)


def _ip() -> str:
    return request.remote_addr or "?"


def _password() -> str | None:
    pw = request.form.get("password", "")
    return pw or None


def gallery_index() -> list[dict]:
    try:
        return json.loads((GALLERY_DIR / "index.json").read_text())
    except FileNotFoundError:
        return []


def gallery_item(gid) -> dict | None:
    return next((g for g in gallery_index() if str(g["id"]) == str(gid)), None)


# ---------------------------------------------------------------- errors

@app.errorhandler(413)
def too_large(_):
    return fail("That file is too large. Please use an image under 40 MB.", "too_large", 413)


@app.errorhandler(404)
def not_found(_):
    if request.path.startswith(("/api/", "/avatars/", "/gallery/")):
        return fail("Not found.", "not_found", 404)
    return render_template("index.html"), 404


@app.errorhandler(500)
def server_error(_):
    if request.path.startswith("/api/"):
        return fail("Something went wrong on the server. Please try again.", "server", 500)
    return "Something went wrong on the server.", 500


@app.errorhandler(img.DependencyError)
def missing_dependency(_):
    return fail("JPEG is not available on this server yet. Please choose PNG.", "server", 500)


@app.errorhandler(img.PasswordError)
@app.errorhandler(txt.TextPasswordError)
def password_error(exc):
    return fail(str(exc), "password", 401)


@app.errorhandler(img.StegoError)
@app.errorhandler(txt.TextStegoError)
def stego_error(exc):
    return fail(str(exc))


# ---------------------------------------------------------------- pages

@app.get("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------- auth

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _send_code(u: dict):
    """Create a fresh 6-digit code for an unverified account and e-mail it.

    Returns a JSON response: ok with verify=True, or a failure. The code itself is
    never returned to the browser. Without mail settings it is printed to the server
    console so the flow can be tried locally.
    """
    if u["code_sent"]:
        age = (_now() - datetime.fromisoformat(u["code_sent"])).total_seconds()
        if age < CODE_RESEND_SEC:
            return fail(f"A code was just sent. Wait {int(CODE_RESEND_SEC - age) + 1} seconds before asking for another.", "slow_down", 429)
    code = f"{secrets.randbelow(10**6):06d}"
    db.run("UPDATE users SET code_hash=?, code_expires=?, code_sent=?, code_attempts=0 WHERE id=?",
           generate_password_hash(code), (_now() + timedelta(minutes=CODE_TTL_MIN)).isoformat(), _now().isoformat(), u["id"])
    body = (f"Hi {u['first_name']},\n\nYour Stego Studio verification code is:\n\n    {code}\n\n"
            f"It expires in {CODE_TTL_MIN} minutes. If you did not create an account, ignore this e-mail.\n")
    if mailer.configured():
        try:
            mailer.send(u["handle"], f"{code} is your Stego Studio code", body)
        except mailer.MailError as exc:
            return fail(str(exc), "mail", 502)
        return jsonify(ok=True, verify=True, email=u["handle"], mail_sent=True)
    print(f"\n*** E-mail is not configured (see mail.env.example). Verification code for {u['handle']}: {code} ***\n", flush=True)
    return jsonify(ok=True, verify=True, email=u["handle"], mail_sent=False)


@app.post("/api/auth/register")
def register():
    d = request.get_json(silent=True) or request.form
    try:
        handle, is_email = normalize_handle(d.get("handle", ""))
    except ValueError as exc:
        return fail(str(exc))
    first, last = (d.get("first_name") or "").strip()[:40], (d.get("last_name") or "").strip()[:40]
    pw = d.get("password") or ""
    if not first:
        return fail("Please enter your first name.")
    if len(pw) < MIN_PASSWORD:
        return fail(f"Use a password of at least {MIN_PASSWORD} characters.")
    existing = db.one("SELECT * FROM users WHERE handle=?", handle)
    if existing and (existing["verified"] or not VERIFY_EMAIL):
        return fail("That e-mail is already registered. Sign in instead.", "exists")
    if existing:  # verification on, started before but never verified: take the new details and send a new code
        db.run("UPDATE users SET first_name=?, last_name=?, password_hash=? WHERE id=?", first, last, generate_password_hash(pw), existing["id"])
        uid = existing["id"]
    else:
        uid = db.run("INSERT INTO users(handle,is_email,first_name,last_name,password_hash,verified) VALUES (?,?,?,?,?,0)",
                     handle, int(is_email), first, last, generate_password_hash(pw))
    if not VERIFY_EMAIL:
        db.run("UPDATE users SET verified=1 WHERE id=?", uid)
        session["uid"] = uid
        return jsonify(ok=True, user=me_user())
    return _send_code(db.one("SELECT * FROM users WHERE id=?", uid))


@app.post("/api/auth/verify")
def verify():
    d = request.get_json(silent=True) or request.form
    code = re.sub(r"\D", "", d.get("code") or "")
    u = _user_by_handle(d.get("handle"))
    if not u:
        return fail("Start by creating an account.", "no_user")
    if u["verified"]:
        return fail("This e-mail is already verified. Sign in.", "verified")
    if len(code) != 6:
        return fail("Enter the 6-digit code from the e-mail.")
    if not u["code_hash"] or _now() > datetime.fromisoformat(u["code_expires"]):
        return fail("That code has expired. Request a new one.", "expired")
    if u["code_attempts"] >= CODE_MAX_TRIES:
        return fail("Too many wrong tries. Request a new code.", "expired")
    if not check_password_hash(u["code_hash"], code):
        db.run("UPDATE users SET code_attempts=code_attempts+1 WHERE id=?", u["id"])
        left = CODE_MAX_TRIES - u["code_attempts"] - 1
        return fail("Wrong code." + (f" {left} tries left." if left else " Request a new code."), "wrong")
    db.run("UPDATE users SET verified=1, code_hash=NULL, code_expires=NULL, code_attempts=0 WHERE id=?", u["id"])
    session["uid"] = u["id"]
    return jsonify(ok=True, user=me_user())


@app.post("/api/auth/resend")
def resend():
    d = request.get_json(silent=True) or request.form
    u = _user_by_handle(d.get("handle"))
    if not u:
        return fail("Start by creating an account.", "no_user")
    if u["verified"]:
        return fail("This e-mail is already verified. Sign in.", "verified")
    return _send_code(u)


@app.post("/api/auth/login")
def login():
    d = request.get_json(silent=True) or request.form
    try:
        handle, _ = normalize_handle(d.get("handle", ""))
    except ValueError:
        return fail("Wrong e-mail or password.", "auth", 401)
    keys = {f"login:{handle}": TRY_LIMIT, f"login-ip:{_ip()}": TRY_LIMIT_IP}
    if (blocked := _too_many(keys)):
        return blocked
    u = db.one("SELECT * FROM users WHERE handle=?", handle)
    if not u or not check_password_hash(u["password_hash"], d.get("password") or ""):
        attempts.fail(*keys)
        return fail("Wrong e-mail or password.", "auth", 401)
    attempts.clear(f"login:{handle}")
    if not u["verified"] and not VERIFY_EMAIL:
        db.run("UPDATE users SET verified=1 WHERE id=?", u["id"])
    elif not u["verified"]:
        res = _send_code(u)
        data = (res[0] if isinstance(res, tuple) else res).get_json() or {}
        sent = bool(data.get("ok") and data.get("mail_sent"))
        note = " We sent you a new code." if sent else (" " + data["error"] if not data.get("ok") else "")
        return jsonify(ok=False, code="unverified", email=handle, mail_sent=sent, error="Verify your e-mail first." + note), 403
    session["uid"] = u["id"]
    return jsonify(ok=True, user=public_user(u, me=True))


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    if not session.get("uid"):
        return jsonify(ok=True, user=None)
    u = current_user()
    if not u or not u["verified"]:
        session.clear()
        return jsonify(ok=True, user=None)
    pictures = db.one("SELECT COUNT(*) n FROM user_gallery WHERE user_id=?", u["id"])["n"]
    return jsonify(ok=True, user=public_user(u, me=True), pictures=pictures)


@app.post("/api/me")
@login_required
def update_me():
    d = request.get_json(silent=True) or request.form
    u = current_user()
    if "accent" in d:
        if d["accent"] not in ACCENTS:
            return fail("Unknown colour.")
        db.run("UPDATE users SET accent=? WHERE id=?", d["accent"], u["id"])
    first = (d.get("first_name") or u["first_name"]).strip()[:40]
    last = (d.get("last_name") or "").strip()[:40] if "last_name" in d else u["last_name"]
    if not first:
        return fail("First name cannot be empty.")
    if d.get("new_password"):
        if not check_password_hash(u["password_hash"], d.get("current_password") or ""):
            return fail("Your current password is wrong.", "password", 401)
        if len(d["new_password"]) < MIN_PASSWORD:
            return fail(f"Use a new password of at least {MIN_PASSWORD} characters.")
        db.run("UPDATE users SET password_hash=? WHERE id=?", generate_password_hash(d["new_password"]), u["id"])
    db.run("UPDATE users SET first_name=?, last_name=? WHERE id=?", first, last, u["id"])
    return jsonify(ok=True, user=me_user())


@app.post("/api/me/avatar")
@login_required
def set_avatar():
    data = _upload("avatar")
    if data is None:
        return fail("Choose a picture.")
    try:
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im).convert("RGB")
    except (UnidentifiedImageError, OSError):
        return fail("That file is not an image we can read.")
    im = ImageOps.fit(im, (256, 256), Image.LANCZOS)
    name = f"{session['uid']}-{uuid.uuid4().hex[:8]}.png"
    old = current_user()["avatar"]
    im.save(AVATARS / name, optimize=True)
    db.run("UPDATE users SET avatar=? WHERE id=?", name, session["uid"])
    if old:
        _unlink_quiet(AVATARS / old)
    return jsonify(ok=True, user=me_user())


@app.delete("/api/me/avatar")
@login_required
def clear_avatar():
    old = current_user()["avatar"]
    db.run("UPDATE users SET avatar=NULL WHERE id=?", session["uid"])
    if old:
        _unlink_quiet(AVATARS / old)
    return jsonify(ok=True, user=me_user())


@app.get("/api/me/export")
@login_required
def export_me():
    """Download everything the server knows about the account, as JSON."""
    uid = session["uid"]
    data = {
        "exported": _now().isoformat(timespec="seconds") + "Z",
        "account": me_user(),
        "gallery": [g for g in _gallery_items(uid) if g["own"]],
        "note": "Nothing you hide is stored on the server, so no pictures, texts or messages are included.",
    }
    resp = jsonify(data)
    resp.headers["Content-Disposition"] = 'attachment; filename="stego-studio-export.json"'
    return resp


@app.delete("/api/me")
@login_required
def delete_me():
    """Delete the account and everything stored for it. Needs the password."""
    d = request.get_json(silent=True) or request.form
    u = current_user()
    if not check_password_hash(u["password_hash"], d.get("password") or ""):
        return fail("Wrong password.", "password", 401)
    uid = u["id"]
    for g in db.all_("SELECT * FROM user_gallery WHERE user_id=?", uid):
        _unlink_quiet(USER_GALLERY / f"{g['file']}.png")
        _unlink_quiet(USER_GALLERY / f"{g['file']}.thumb.jpg")
    db.run("DELETE FROM user_gallery WHERE user_id=?", uid)
    if u["avatar"]:
        _unlink_quiet(AVATARS / u["avatar"])
    db.run("DELETE FROM users WHERE id=?", uid)
    session.clear()
    return jsonify(ok=True)


@app.get("/avatars/<int:uid>")
@login_required
def avatar(uid):
    u = db.one("SELECT avatar FROM users WHERE id=?", uid)
    if not u or not u["avatar"]:
        abort(404)
    return send_file(AVATARS / u["avatar"], mimetype="image/png", max_age=3600)


# ---------------------------------------------------------------- gallery

def _own_gallery_row(gid: str, uid: int) -> dict | None:
    """User-added pictures have ids like 'u12'; built-in ones are plain numbers."""
    if not (isinstance(gid, str) and gid.startswith("u") and gid[1:].isdigit()):
        return None
    return db.one("SELECT * FROM user_gallery WHERE id=? AND user_id=?", int(gid[1:]), uid)


def _gallery_items(uid: int) -> list[dict]:
    items = [{"id": str(g["id"]), "name": g["name"], "width": g["width"], "height": g["height"], "own": False,
              "url": f"/static/gallery/{g['file']}", "thumb_url": f"/static/gallery/{g['thumb']}"} for g in gallery_index()]
    for r in db.all_("SELECT * FROM user_gallery WHERE user_id=? ORDER BY created, id", uid):
        items.append({"id": f"u{r['id']}", "name": r["name"], "width": r["width"], "height": r["height"], "own": True,
                      "url": f"/gallery/u{r['id']}", "thumb_url": f"/gallery/u{r['id']}/thumb"})
    return items


@app.get("/api/gallery")
@login_required
def gallery():
    return jsonify(ok=True, items=_gallery_items(session["uid"]), limit=USER_GALLERY_MAX)


@app.post("/api/gallery")
@login_required
def gallery_add():
    """Add a picture to the user's own gallery, kept until they remove it."""
    uid = session["uid"]
    if db.one("SELECT COUNT(*) n FROM user_gallery WHERE user_id=?", uid)["n"] >= USER_GALLERY_MAX:
        return fail(f"Your gallery is full ({USER_GALLERY_MAX} pictures). Remove one first.")
    data = _upload("image")
    if data is None:
        return fail("Choose a picture.")
    try:
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im)
        im.load()
    except (UnidentifiedImageError, OSError):
        return fail("That file is not an image we can read.")
    if im.width * im.height > img.MAX_PIXELS or max(im.size) > 12000:
        return fail("That picture is too large. Use one under 25 megapixels.")
    im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
    base = uuid.uuid4().hex
    im.save(USER_GALLERY / f"{base}.png", optimize=True)
    thumb = Image.new("RGB", im.size, "white")
    thumb.paste(im, mask=im.getchannel("A") if im.mode == "RGBA" else None)
    thumb.thumbnail((320, 320))
    thumb.save(USER_GALLERY / f"{base}.thumb.jpg", quality=82)
    name = re.sub(r"[_\-]+", " ", Path(request.files["image"].filename).stem).strip()[:40] or "My picture"
    gid = db.run("INSERT INTO user_gallery(user_id,name,file,width,height) VALUES (?,?,?,?,?)", uid, name, base, im.width, im.height)
    item = next(i for i in _gallery_items(uid) if i["id"] == f"u{gid}")
    return jsonify(ok=True, item=item)


@app.delete("/api/gallery/<gid>")
@login_required
def gallery_remove(gid):
    r = _own_gallery_row(gid, session["uid"])
    if not r:
        return fail("Only pictures you added can be removed.", "not_found", 404)
    db.run("DELETE FROM user_gallery WHERE id=?", r["id"])
    _unlink_quiet(USER_GALLERY / f"{r['file']}.png")
    _unlink_quiet(USER_GALLERY / f"{r['file']}.thumb.jpg")
    return jsonify(ok=True)


@app.get("/gallery/<gid>")
@login_required
def gallery_file(gid):
    r = _own_gallery_row(gid, session["uid"])
    if not r:
        abort(404)
    return send_file(USER_GALLERY / f"{r['file']}.png", mimetype="image/png", max_age=3600)


@app.get("/gallery/<gid>/thumb")
@login_required
def gallery_thumb(gid):
    r = _own_gallery_row(gid, session["uid"])
    if not r:
        abort(404)
    return send_file(USER_GALLERY / f"{r['file']}.thumb.jpg", mimetype="image/jpeg", max_age=3600)


def _cover_bytes(n: str = ""):
    """Cover image for Hide (and the Learn labs): a built-in picture, one of the user's own, or an upload.

    n="2" reads the second picture of a split hide (fields gallery2 / image2).
    """
    gid = request.form.get("gallery" + n)
    if gid:
        own = _own_gallery_row(gid, session["uid"])
        if own:
            return (USER_GALLERY / f"{own['file']}.png").read_bytes(), None
        g = gallery_item(gid)
        if not g:
            return None, None
        return (GALLERY_DIR / g["file"]).read_bytes(), int(gid)
    return _upload("image" + n), None


def _extra_covers():
    """Pictures added after the first to spread a long message: fields gallery_m<i> / image_m<i>, i < more_count.

    Returns [(bytes, stem)], or None when one of them is missing.
    """
    try:
        n = max(0, min(int(request.form.get("more_count", 0)), extras.MAX_PICTURES - 1))
    except ValueError:
        n = 0
    out = []
    for i in range(n):
        cover, _ = _cover_bytes(f"_m{i}")
        if cover is None:
            return None
        out.append((cover, _cover_stem(f"_m{i}")))
    return out


def _part(name: str, cover: bytes, result, ext: str, cover_index: int) -> dict:
    """One output picture of a split or spread hide, with its own "did it change?" numbers."""
    part = {"name": name, "data": extras.png_data_uri(result.image, MIMES[ext]), "cover": cover_index,
            "used": result.message_bytes, "capacity": result.capacity_bytes, "psnr": None, "changed": None}
    try:
        q = img.measure(cover, result.image)
        part.update(psnr=None if q.psnr_db is None else round(q.psnr_db, 1), changed=q.changed_rgb_fraction)
    except img.StegoError:
        pass
    return part


def _cover_stem(n: str = "") -> str:
    """A safe file-name stem for the result: the gallery picture's name or the uploaded file's name."""
    gid = request.form.get("gallery" + n)
    if gid:
        own = _own_gallery_row(gid, session["uid"])
        stem = own["name"] if own else (gallery_item(gid) or {}).get("name", "picture")
    else:
        stem = Path(request.files["image" + n].filename).stem
    return re.sub(r"[^\w\-]+", "-", stem).strip("-")[:40] or "picture"


@app.post("/api/image/capacity")
@login_required
def image_capacity():
    cover, _ = _cover_bytes()
    if cover is None:
        return fail("Choose a picture first.")
    fmt = request.form.get("format", "PNG").upper()
    if fmt not in FORMATS:
        return fail("Unknown image type.")
    cap = img.capacity(cover, fmt, encrypted=request.form.get("encrypted") == "1")
    return jsonify(ok=True, max_message_bytes=cap.max_message_bytes, can_embed=cap.can_embed,
                   width=cap.width, height=cap.height)


# ---------------------------------------------------------------- hide / reveal

EXPIRY_CHOICES = {60, 24 * 60, 7 * 24 * 60, 30 * 24 * 60}   # minutes: 1 hour, 1 day, 1 week, 30 days


@app.post("/api/hide")
@login_required
def hide_secret():
    """Hide a message and hand the result straight back. Nothing is saved.

    Image: returns the stego picture as a download. Text: returns {ok, text}.
    Split (image only, split=1): returns {ok, split, parts:[{name, data}], ...}: two pictures that each hold half.
    Optional: expires=<minutes> sets a self-destruct date (needs the password lock).
    """
    message = request.form.get("message", "")
    if not message.strip():
        return fail("Write the secret message.")
    # lock=0 means "no password": the message is hidden but not encrypted.
    # Anything else (or no field, as older clients send) keeps the password required.
    password = None
    if request.form.get("lock", "1") != "0":
        password = _password()
        if password is None:
            return fail("Enter a password.")
        if len(password) < MIN_PASSWORD:
            return fail(f"Use a password of at least {MIN_PASSWORD} characters.")
    expires = None
    if request.form.get("expires"):
        try:
            minutes = int(request.form["expires"])
        except ValueError:
            minutes = -1
        if minutes not in EXPIRY_CHOICES:
            return fail("Unknown self-destruct time.")
        if password is None:
            return fail("A self-destruct date needs the password lock, so nobody can change it.")
        expires = (_now() + timedelta(minutes=minutes)).replace(tzinfo=timezone.utc, second=0, microsecond=0)
    message = extras.wrap_expiry(message, expires)
    expires_iso = expires.strftime("%Y-%m-%dT%H:%M:%SZ") if expires else None

    if request.form.get("carrier") == "text":
        cover = request.form.get("cover", "")
        if not cover.strip():
            return fail("Write the visible text.")
        return jsonify(ok=True, text=txt.hide(cover, message, password), expires=expires_iso)

    fmt = request.form.get("format", "PNG").upper()
    if fmt not in FORMATS:
        return fail("Unknown image type.")
    cover, _ = _cover_bytes()
    if cover is None:
        return fail("Choose a picture from the gallery or upload one.")
    stem = _cover_stem()
    ext = FORMATS[fmt]

    if request.form.get("split") == "1":
        # Two pictures, each holding one random-looking half; only both together give the message.
        cover2, _ = _cover_bytes("2")
        if cover2 is None:
            return fail("Choose the second picture.")
        stem2 = _cover_stem("2")
        if stem2 == stem:
            stem, stem2 = f"{stem}-part1", f"{stem2}-part2"
        shares = extras.split_secret(message.encode("utf-8"))
        results = [img.embed(c, share, password=password, output_format=fmt) for c, share in zip((cover, cover2), shares)]
        return jsonify(ok=True, split=True, expires=expires_iso,
                       parts=[_part(f"{name}-stego.{ext}", c, r, ext, i)
                              for i, (name, c, r) in enumerate(zip((stem, stem2), (cover, cover2), results))])

    more = _extra_covers()
    if more is None:
        return fail("One of the added pictures is missing. Choose it again.")
    if more:
        data = message.encode("utf-8")
        covers = [(cover, stem)] + more
        room = [img.capacity(c, fmt, encrypted=password is not None).max_message_bytes for c, _ in covers]
        if len(data) > room[0]:          # one picture is not enough: cut the message into pieces
            pieces = extras.chain_pieces(data, room)
            if pieces is None:
                return fail("Still too long. Add another picture.")
            total = len(pieces)
            made = [(covers[i], img.embed(covers[i][0], piece, password=password, output_format=fmt)) for i, piece in pieces]
            return jsonify(ok=True, chain=True, expires=expires_iso,
                           parts=[_part(f"{covers[i][1]}-{k}-of-{total}-stego.{ext}", covers[i][0], r, ext, i)
                                  for k, ((i, _), (_, r)) in enumerate(zip(pieces, made), 1)])

    result = img.embed(cover, message, password=password, output_format=fmt)
    resp = send_file(io.BytesIO(result.image), mimetype=MIMES[ext], as_attachment=True,
                     download_name=f"{stem}-stego.{ext}")
    # "Did it change?" proof for the result panel: how different the picture is from the original.
    try:
        q = img.measure(cover, result.image)
        resp.headers["X-Stego-Psnr"] = "inf" if q.psnr_db is None else f"{q.psnr_db:.1f}"
        resp.headers["X-Stego-Changed"] = f"{q.changed_rgb_fraction:.6f}"
    except img.StegoError:
        pass   # e.g. the picture was turned by its camera tag, so sizes differ: the result is still fine
    resp.headers["X-Stego-Used"] = f"{result.message_bytes}/{result.capacity_bytes}"
    if expires_iso:
        resp.headers["X-Stego-Expires"] = expires_iso
    return resp


def _image_format(data: bytes) -> str | None:
    try:
        fmt = (Image.open(io.BytesIO(data)).format or "PNG").upper()
    except (UnidentifiedImageError, OSError):
        return None
    return "JPEG" if fmt in ("JPEG", "MPO") else fmt


@app.post("/api/reveal")
@login_required
def reveal_secret():
    """Read the hidden message from an uploaded picture (or two halves) or pasted text.

    The password is optional: a message hidden without one opens without one,
    and a locked message without a password just answers "needs its password".
    Wrong passwords are counted: after TRY_LIMIT in TRY_WINDOW the account is asked to wait.
    A message past its self-destruct date is refused.
    """
    password = _password()
    mine = f"reveal:{session['uid']}"
    keys = {mine: TRY_LIMIT, f"reveal-ip:{_ip()}": TRY_LIMIT_IP}
    if (blocked := _too_many(keys)):
        return blocked
    fmt = None
    try:
        if request.form.get("carrier") == "text":
            text = request.form.get("text", "")
            if not text.strip():
                return fail("Paste the text first.")
            secret = txt.reveal(text, password)
        else:
            data = _upload("image")
            if data is None:
                return fail("Choose a picture first.")
            fmt = _image_format(data)
            if fmt is None:
                return fail("That file is not an image we can read.")
            # Every picture is read; which is a half or which piece comes first is worked out
            # from what is inside them, so the pictures can be given in any order.
            others = [b for b in [_upload("image2")] + [f.read() for f in request.files.getlist("more") if f.filename] if b]
            others = others[:extras.MAX_PICTURES - 1]
            if any(_image_format(o) is None for o in others):
                return fail("One of the added files is not an image we can read.")
            raws = []
            for n, picture in enumerate([data] + others, 1):
                try:
                    raws.append(img.extract(picture, password=password))
                except img.PasswordError:
                    raise
                except img.StegoError:
                    if not others:
                        raise
                    return fail(f"Picture {n} has no hidden message from this site.", "need_part")
            try:
                raw = extras.combine(raws)
            except extras.ShareMismatch as exc:
                return fail(str(exc), "need_part")
            secret = raw.decode("utf-8", errors="replace")
    except (img.PasswordError, txt.TextPasswordError):
        if password is not None:   # only a wrong guess counts, not a missing password
            attempts.fail(*keys)
        raise
    attempts.clear(mine)
    secret, expires = extras.unwrap_expiry(secret)
    if expires and _now().replace(tzinfo=timezone.utc) >= expires:
        return fail(f"This message self-destructed on {expires.strftime('%d %b %Y, %H:%M')} UTC.", "expired", 410)
    out = dict(ok=True, message=secret, expires=expires.strftime("%Y-%m-%dT%H:%M:%SZ") if expires else None)
    if fmt:
        out["format"] = fmt
    return jsonify(out)


@app.post("/api/qr")
@login_required
def qr_code():
    """A QR code (PNG data URI) of a stego text, for scanning on a phone."""
    text = (request.get_json(silent=True) or {}).get("text", "")
    if not text:
        return fail("Nothing to put in the QR code.")
    try:
        return jsonify(ok=True, png=extras.qr_png_data_uri(text))
    except extras.QrTooLong as exc:
        return fail(str(exc))


if __name__ == "__main__":
    app.run(debug=False, port=int(os.environ.get("PORT", 5000)))
