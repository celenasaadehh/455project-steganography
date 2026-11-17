"""Stego Mail: send secret messages hidden in images or text to other users.

Run from this folder:  python app.py   then open http://127.0.0.1:5000
Image steganography comes from Member 1 (../Member 1/image_stego.py).
Only the stego image/text is stored on the server, never the hidden message.
"""
from __future__ import annotations

import io
import json
import os
import re
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file, session
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "Member 1"))
sys.path.insert(0, str(ROOT.parent / "Member 4"))

import image_stego as img  # noqa: E402  (Member 1's module)
import text_stego as txt  # noqa: E402
import db  # noqa: E402
import mailer  # noqa: E402
import member4  # noqa: E402  (Member 4: Learn tab + History tab)

VERIFY_EMAIL = os.environ.get("STEGO_VERIFY_EMAIL", "0") == "1"  # off for now: accounts work without the e-mailed code
ACCENTS = ("navy", "sky", "red", "green", "purple")  # app colour choices in Settings
CODE_TTL_MIN = 10        # a verification code is valid this long
CODE_RESEND_SEC = 45     # minimum gap between two codes for the same address
CODE_MAX_TRIES = 5

GALLERY_DIR = ROOT / "static" / "gallery"       # the 10 built-in pictures
USER_GALLERY = db.DATA / "gallery"               # pictures users add to their own gallery
USER_GALLERY_MAX = 30
FILES = db.DATA / "files"
AVATARS = db.DATA / "avatars"
FORMATS = {"PNG": "png", "JPEG": "jpg", "BMP": "bmp"}
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
    """What the browser sees of a user. For other people (me=False) the Privacy
    setting "show full name" may reduce the name to the first name only."""
    if not u:
        return None
    last = u["last_name"] if (me or u.get("show_name", 1)) else ""
    out = {
        "id": u["id"], "handle": u["handle"], "is_email": bool(u["is_email"]),
        "first_name": u["first_name"], "last_name": last,
        "name": f"{u['first_name']} {last}".strip(),
        "initials": (u["first_name"][:1] + last[:1]).upper() or u["handle"][:2].upper(),
        "avatar": f"/avatars/{u['id']}?v={u['avatar']}" if u["avatar"] else None,
        "accent": u.get("accent") or "navy",
    }
    if me:
        out["created"] = u["created"]
        out["prefs"] = {"inbox_mode": u.get("inbox_mode") or "everyone", "show_name": bool(u.get("show_name", 1)),
                        "auto_delete_days": int(u.get("auto_delete_days") or 0), "default_lock": bool(u.get("default_lock", 1))}
    return out


def me_user():
    return public_user(current_user(), me=True)


INBOX_MODES = ("everyone", "contacts", "nobody")
AUTO_DELETE_CHOICES = (0, 7, 30, 90)


def _purge_old(uid: int):
    """Privacy setting: drop received messages older than N days (lazy, on inbox load)."""
    u = db.one("SELECT auto_delete_days FROM users WHERE id=?", uid)
    days = int(u["auto_delete_days"] or 0) if u else 0
    if not days:
        return
    old = db.all_("SELECT id FROM messages WHERE recipient_id=? AND recipient_deleted=0 AND created < datetime('now', ?)", uid, f"-{days} days")
    for m in old:
        _delete_for(m["id"], uid)


def _delete_for(mid: int, uid: int):
    """Hide a message from one side; remove it entirely once both sides have deleted it."""
    m = db.one("SELECT * FROM messages WHERE id=?", mid)
    if not m:
        return
    if m["sender_id"] == m["recipient_id"]:
        db.run("UPDATE messages SET sender_deleted=1, recipient_deleted=1 WHERE id=?", mid)
    else:
        col = "sender_deleted" if m["sender_id"] == uid else "recipient_deleted"
        db.run(f"UPDATE messages SET {col}=1 WHERE id=?", mid)
    m = db.one("SELECT * FROM messages WHERE id=?", mid)
    if m["sender_deleted"] and m["recipient_deleted"]:
        if m["file"]:
            _unlink_quiet(FILES / m["file"])
            _unlink_quiet(FILES / f"{m['file']}.thumb.jpg")
        db.run("DELETE FROM messages WHERE id=?", mid)


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


def message_view(m: dict, me: int, box: str | None = None) -> dict:
    other = db.one("SELECT * FROM users WHERE id=?", m["recipient_id"] if m["sender_id"] == me else m["sender_id"])
    direction = box or ("sent" if m["sender_id"] == me else "inbox")  # a self-sent message is in both boxes
    return {
        "id": m["id"], "carrier": m["carrier"], "format": m["format"], "subject": m["subject"],
        "locked": bool(m["locked"]), "created": m["created"], "read": m["read_at"] is not None,
        "direction": direction,
        "to_me": m["recipient_id"] == me,
        "with": public_user(other),
        "file_url": f"/files/{m['id']}" if m["file"] else None,
        "thumb_url": f"/files/{m['id']}/thumb" if m["file"] else None,
        "text": m["text"],
        "gallery_id": m["gallery_id"],
    }


def _load_message(mid: int, me: int) -> dict:
    m = db.one("SELECT * FROM messages WHERE id=?", mid)
    if not m or me not in (m["sender_id"], m["recipient_id"]):
        abort(404)
    if (m["sender_id"] == me and m["sender_deleted"]) or (m["recipient_id"] == me and m["recipient_deleted"]):
        abort(404)
    return m


# ---------------------------------------------------------------- errors

@app.errorhandler(413)
def too_large(_):
    return fail("That file is too large. Please use an image under 40 MB.", "too_large", 413)


@app.errorhandler(404)
def not_found(_):
    if request.path.startswith(("/api/", "/files/", "/avatars/")):
        return fail("Not found.", "not_found", 404)
    return render_template("index.html"), 404


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
    body = (f"Hi {u['first_name']},\n\nYour Stego Mail verification code is:\n\n    {code}\n\n"
            f"It expires in {CODE_TTL_MIN} minutes. If you did not create an account, ignore this e-mail.\n")
    if mailer.configured():
        try:
            mailer.send(u["handle"], f"{code} is your Stego Mail code", body)
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
    if len(pw) < 6:
        return fail("Use a password of at least 6 characters.")
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
    u = db.one("SELECT * FROM users WHERE handle=?", handle)
    if not u or not check_password_hash(u["password_hash"], d.get("password") or ""):
        return fail("Wrong e-mail or password.", "auth", 401)
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
    unread = db.one("SELECT COUNT(*) n FROM messages WHERE recipient_id=? AND read_at IS NULL AND recipient_deleted=0", u["id"])["n"]
    received = db.one("SELECT COUNT(*) n FROM messages WHERE recipient_id=? AND recipient_deleted=0", u["id"])["n"]
    sent = db.one("SELECT COUNT(*) n FROM messages WHERE sender_id=? AND sender_deleted=0", u["id"])["n"]
    pictures = db.one("SELECT COUNT(*) n FROM user_gallery WHERE user_id=?", u["id"])["n"]
    return jsonify(ok=True, user=public_user(u, me=True), unread=unread, received=received, sent=sent, pictures=pictures)


@app.post("/api/me")
@login_required
def update_me():
    d = request.get_json(silent=True) or request.form
    u = current_user()
    if "accent" in d:
        if d["accent"] not in ACCENTS:
            return fail("Unknown colour.")
        db.run("UPDATE users SET accent=? WHERE id=?", d["accent"], u["id"])
    # Privacy / security preferences (each optional)
    truthy = lambda v: v in (True, 1, "1", "true", "on")
    if "inbox_mode" in d:
        if d["inbox_mode"] not in INBOX_MODES:
            return fail("Unknown option.")
        db.run("UPDATE users SET inbox_mode=? WHERE id=?", d["inbox_mode"], u["id"])
    if "show_name" in d:
        db.run("UPDATE users SET show_name=? WHERE id=?", int(truthy(d["show_name"])), u["id"])
    if "default_lock" in d:
        db.run("UPDATE users SET default_lock=? WHERE id=?", int(truthy(d["default_lock"])), u["id"])
    if "auto_delete_days" in d:
        try:
            days = int(d["auto_delete_days"])
        except (TypeError, ValueError):
            return fail("Unknown option.")
        if days not in AUTO_DELETE_CHOICES:
            return fail("Unknown option.")
        db.run("UPDATE users SET auto_delete_days=? WHERE id=?", days, u["id"])
    first = (d.get("first_name") or u["first_name"]).strip()[:40]
    last = (d.get("last_name") or "").strip()[:40] if "last_name" in d else u["last_name"]
    if not first:
        return fail("First name cannot be empty.")
    if d.get("new_password"):
        if not check_password_hash(u["password_hash"], d.get("current_password") or ""):
            return fail("Your current password is wrong.", "password", 401)
        if len(d["new_password"]) < 6:
            return fail("Use a new password of at least 6 characters.")
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
    rows = db.all_("SELECT * FROM messages WHERE (sender_id=? AND sender_deleted=0) OR (recipient_id=? AND recipient_deleted=0) ORDER BY created, id", uid, uid)
    data = {
        "exported": _now().isoformat(timespec="seconds") + "Z",
        "account": me_user(),
        "messages": [message_view(m, uid) for m in rows],
        "gallery": [g for g in _gallery_items(uid) if g["own"]],
        "note": "Hidden messages are not included: they exist only inside the image/text files and need their passwords.",
    }
    resp = jsonify(data)
    resp.headers["Content-Disposition"] = 'attachment; filename="stego-mail-export.json"'
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
    for m in db.all_("SELECT * FROM messages WHERE sender_id=? OR recipient_id=?", uid, uid):
        if m["file"]:
            _unlink_quiet(FILES / m["file"])
            _unlink_quiet(FILES / f"{m['file']}.thumb.jpg")
        db.run("DELETE FROM messages WHERE id=?", m["id"])
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


@app.get("/api/users/lookup")
@login_required
def lookup():
    try:
        q, _ = normalize_handle(request.args.get("q", ""))
    except ValueError:
        return jsonify(ok=True, user=None)
    u = db.one("SELECT * FROM users WHERE handle=? AND verified=1", q)
    return jsonify(ok=True, user=public_user(u))


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


def _cover_bytes():
    """Cover image for the compose form: a built-in picture, one of the user's own, or an upload."""
    gid = request.form.get("gallery")
    if gid:
        own = _own_gallery_row(gid, session["uid"])
        if own:
            return (USER_GALLERY / f"{own['file']}.png").read_bytes(), None
        g = gallery_item(gid)
        if not g:
            return None, None
        return (GALLERY_DIR / g["file"]).read_bytes(), int(gid)
    return _upload("image"), None


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


# ---------------------------------------------------------------- messages

@app.post("/api/messages")
@login_required
def send_message():
    me_id = session["uid"]
    try:
        to_handle, _ = normalize_handle(request.form.get("to", ""))
    except ValueError:
        return fail("Enter the e-mail of the person you are sending to.")
    to = db.one("SELECT * FROM users WHERE handle=? AND verified=1", to_handle)
    if not to:
        return fail("No one with that e-mail has an account yet.", "no_user")
    mode = to.get("inbox_mode") or "everyone"
    if to["id"] != me_id and mode == "nobody":
        return fail("This person is not accepting messages right now.", "blocked")
    if to["id"] != me_id and mode == "contacts" and not db.one(
            "SELECT id FROM messages WHERE sender_id=? AND recipient_id=? LIMIT 1", to["id"], me_id):
        return fail("This person only accepts messages from people they have written to first.", "blocked")
    message = request.form.get("message", "")
    if not message.strip():
        return fail("Write the secret message.")
    subject = (request.form.get("subject") or "").strip()[:80]
    password = _password()
    carrier = request.form.get("carrier", "image")

    if carrier == "text":
        stego_text = txt.hide(request.form.get("cover", ""), message, password)
        mid = db.run("INSERT INTO messages(sender_id,recipient_id,carrier,text,subject,locked) VALUES (?,?,?,?,?,?)",
                     me_id, to["id"], "text", stego_text, subject, int(password is not None))
    else:
        fmt = request.form.get("format", "PNG").upper()
        if fmt not in FORMATS:
            return fail("Unknown image type.")
        cover, gid = _cover_bytes()
        if cover is None:
            return fail("Choose a picture from the gallery or upload one.")
        result = img.embed(cover, message, password=password, output_format=fmt)
        name = f"{uuid.uuid4().hex}.{FORMATS[fmt]}"
        (FILES / name).write_bytes(result.image)
        thumb = Image.open(io.BytesIO(result.image)).convert("RGB")
        thumb.thumbnail((320, 320))
        thumb.save(FILES / f"{name}.thumb.jpg", quality=80)
        mid = db.run("INSERT INTO messages(sender_id,recipient_id,carrier,format,file,subject,locked,gallery_id) VALUES (?,?,?,?,?,?,?,?)",
                     me_id, to["id"], "image", fmt, name, subject, int(password is not None), gid)
    return jsonify(ok=True, message=message_view(db.one("SELECT * FROM messages WHERE id=?", mid), me_id))


@app.get("/api/messages")
@login_required
def list_messages():
    me_id = session["uid"]
    box = "sent" if request.args.get("box") == "sent" else "inbox"
    if box == "inbox":
        _purge_old(me_id)
    if box == "sent":
        rows = db.all_("SELECT * FROM messages WHERE sender_id=? AND sender_deleted=0 ORDER BY created DESC, id DESC", me_id)
    else:
        rows = db.all_("SELECT * FROM messages WHERE recipient_id=? AND recipient_deleted=0 ORDER BY created DESC, id DESC", me_id)
    return jsonify(ok=True, items=[message_view(m, me_id, box) for m in rows])


@app.get("/api/messages/<int:mid>")
@login_required
def get_message(mid):
    return jsonify(ok=True, message=message_view(_load_message(mid, session["uid"]), session["uid"]))


@app.post("/api/messages/<int:mid>/reveal")
@login_required
def reveal_message(mid):
    me_id = session["uid"]
    m = _load_message(mid, me_id)
    password = _password()
    if m["carrier"] == "text":
        text = txt.reveal(m["text"], password)
    else:
        text = img.extract((FILES / m["file"]).read_bytes(), password=password).decode("utf-8", errors="replace")
    if m["recipient_id"] == me_id and m["read_at"] is None:
        db.run("UPDATE messages SET read_at=datetime('now') WHERE id=?", mid)
    return jsonify(ok=True, message=text)


@app.delete("/api/messages/<int:mid>")
@login_required
def delete_message(mid):
    me_id = session["uid"]
    _load_message(mid, me_id)
    _delete_for(mid, me_id)
    return jsonify(ok=True)


@app.get("/files/<int:mid>")
@login_required
def download(mid):
    m = _load_message(mid, session["uid"])
    if not m["file"]:
        abort(404)
    ext = FORMATS[m["format"]]
    return send_file(FILES / m["file"], mimetype={"png": "image/png", "jpg": "image/jpeg", "bmp": "image/bmp"}[ext],
                     as_attachment=request.args.get("dl") == "1", download_name=f"stego-mail-{mid}.{ext}")


@app.get("/files/<int:mid>/thumb")
@login_required
def thumb(mid):
    m = _load_message(mid, session["uid"])
    if not m["file"]:
        abort(404)
    return send_file(FILES / f"{m['file']}.thumb.jpg", mimetype="image/jpeg", max_age=3600)


if __name__ == "__main__":
    app.run(debug=False, port=int(os.environ.get("PORT", 5000)))
