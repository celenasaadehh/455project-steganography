"""Member 4: Educational & convenience features for Stego Studio.

Plugs into Member 3's Flask app with two lines in app.py:

    import member4
    member4.init_app(app)

It adds:
  * Learn tab API  -> /api/learn/image, /api/learn/text, /api/learn/check-text
                      /api/learn/detect, /api/learn/robust-image, /api/learn/robust-text (labs.py)
                      (step-by-step traces of the team's REAL algorithms, see learn_trace.py)
  * History tab    -> /api/history (list, delete one, clear, CSV export)
                      Every Hide and Reveal is recorded automatically. The secret message
                      itself is never stored, only its length.
  * Static files   -> /member4/static/... and templates under templates/member4/
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

from flask import Blueprint, Response, g, jsonify, request, session

import db                 # Member 3's SQLite helpers (same database file)
import labs
import learn_trace

HERE = Path(__file__).resolve().parent
bp = Blueprint("member4", __name__, template_folder="templates",
               static_folder="static", static_url_path="/member4/static")

MAX_HISTORY = 500         # per user; oldest entries are dropped after this

SCHEMA = """
CREATE TABLE IF NOT EXISTS member4_history (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  created TEXT NOT NULL DEFAULT (datetime('now')),
  action TEXT NOT NULL,          -- 'hide' | 'reveal'
  carrier TEXT NOT NULL,         -- 'image' | 'text'
  method TEXT NOT NULL,          -- e.g. 'Spatial matrix embedding (PNG)'
  locked INTEGER NOT NULL DEFAULT 0,
  message_chars INTEGER,         -- length only, never the message
  other TEXT NOT NULL DEFAULT '',-- file name of the picture (or empty for text)
  success INTEGER NOT NULL,
  error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_m4_hist ON member4_history(user_id, created);
"""

IMAGE_METHODS = {
    "PNG": "Spatial matrix embedding (PNG)",
    "BMP": "Spatial matrix embedding (BMP)",
    "JPEG": "JPEG DCT embedding (QIM)",
}
TEXT_METHOD = "Zero-width characters"


def _fail(message: str, status: int = 400):
    return jsonify(ok=False, error=message, code="error"), status


def _uid():
    return session.get("uid")


@bp.before_request
def _need_login():
    if request.endpoint and request.endpoint.startswith("member4.") and request.endpoint != "member4.static" and not _uid():
        return jsonify(ok=False, error="Please sign in.", code="auth"), 401


# ------------------------------------------------------------------ Learn
def _main_app_module():
    """Member 3's app.py module (named '__main__' when started with `python app.py`)."""
    import sys
    for name in ("app", "__main__"):
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "_cover_bytes"):
            return mod
    raise RuntimeError("Member 3's app.py is not loaded")


def _cover_for_learn() -> bytes | None:
    """Same picture choice as the Hide form: gallery picture (built-in or own) or an upload."""
    cover, _ = _main_app_module()._cover_bytes()
    return cover


@bp.post("/api/learn/image")
def learn_image():
    import image_stego as img
    message = request.form.get("message", "")
    if not message.strip():
        return _fail("Type a secret message first.")
    if len(message.encode()) > 2000:
        return _fail("For the walkthrough, keep the message under 2,000 bytes.")
    cover = _cover_for_learn()
    if cover is None:
        return _fail("Choose a picture from the gallery or upload one.")
    try:
        trace = learn_trace.trace_image(cover, message, request.form.get("password") or None)
    except img.StegoError as exc:
        return _fail(str(exc))
    return jsonify(ok=True, trace=trace)


@bp.post("/api/learn/text")
def learn_text():
    import text_stega as txt
    try:
        trace = learn_trace.trace_text(request.form.get("cover", ""), request.form.get("message", ""),
                                       request.form.get("password") or None)
    except txt.TextStegoError as exc:
        return _fail(str(exc))
    return jsonify(ok=True, trace=trace)


@bp.post("/api/learn/detect")
def learn_detect():
    import image_stego as img
    cover = _cover_for_learn()
    if cover is None:
        return _fail("Choose a picture from the gallery or upload one.")
    try:
        return jsonify(ok=True, lab=labs.detection_lab(cover, request.form.get("size", "medium")))
    except img.StegoError as exc:
        return _fail(str(exc))


@bp.post("/api/learn/robust-image")
def learn_robust_image():
    import image_stego as img
    message = request.form.get("message", "").strip()
    if not message:
        return _fail("Type a secret message first.")
    cover = _cover_for_learn()
    if cover is None:
        return _fail("Choose a picture from the gallery or upload one.")
    try:
        return jsonify(ok=True, lab=labs.robustness_image(cover, message, request.form.get("password") or None))
    except img.StegoError as exc:
        return _fail(str(exc))


@bp.post("/api/learn/robust-text")
def learn_robust_text():
    import text_stega as txt
    try:
        return jsonify(ok=True, lab=labs.robustness_text(request.form.get("cover", ""), request.form.get("message", ""),
                                                          request.form.get("password") or None))
    except txt.TextStegoError as exc:
        return _fail(str(exc))


@bp.post("/api/learn/check-text")
def learn_check_text():
    return jsonify(ok=True, result=learn_trace.check_text(request.form.get("text", ""),
                                                          request.form.get("password") or None))


# ---------------------------------------------------------------- History
def _row(r: dict) -> dict:
    return {k: r[k] for k in ("id", "created", "action", "carrier", "method", "message_chars", "other", "error")} | {
        "locked": bool(r["locked"]), "success": bool(r["success"])}


@bp.get("/api/history")
def history_list():
    rows = db.all_("SELECT * FROM member4_history WHERE user_id=? ORDER BY created DESC, id DESC", _uid())
    return jsonify(ok=True, items=[_row(r) for r in rows])


@bp.delete("/api/history/<int:hid>")
def history_delete(hid):
    db.run("DELETE FROM member4_history WHERE id=? AND user_id=?", hid, _uid())
    return jsonify(ok=True)


@bp.delete("/api/history")
def history_clear():
    db.run("DELETE FROM member4_history WHERE user_id=?", _uid())
    return jsonify(ok=True)


@bp.get("/api/history.csv")
def history_csv():
    rows = db.all_("SELECT * FROM member4_history WHERE user_id=? ORDER BY created DESC, id DESC", _uid())
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["time (UTC)", "action", "carrier", "method", "locked", "message length", "with", "result", "error"])
    for r in rows:
        w.writerow([r["created"], r["action"], r["carrier"], r["method"], "yes" if r["locked"] else "no",
                    r["message_chars"] if r["message_chars"] is not None else "", r["other"],
                    "success" if r["success"] else "failed", r["error"]])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=stego-history.csv"})


def log(uid: int, action: str, carrier: str, method: str, *, locked: bool, message_chars: int | None,
        other: str, success: bool, error: str = "") -> None:
    db.run("INSERT INTO member4_history(user_id,action,carrier,method,locked,message_chars,other,success,error) "
           "VALUES (?,?,?,?,?,?,?,?,?)", uid, action, carrier, method, int(locked), message_chars, other[:120],
           int(success), error[:200])
    db.run("DELETE FROM member4_history WHERE user_id=? AND id NOT IN "
           "(SELECT id FROM member4_history WHERE user_id=? ORDER BY id DESC LIMIT ?)", uid, uid, MAX_HISTORY)


def _record(response):
    """Runs after every request. Records Member 3's Hide and Reveal calls; changes nothing else."""
    try:
        ep, uid = request.endpoint, g.get("m4_uid")
        if ep not in ("hide_secret", "reveal_secret", "delete_me") or not uid or request.method not in ("POST", "DELETE"):
            return response
        data = response.get_json(silent=True) or {}
        ok = response.status_code == 200 and data.get("ok") is True
        if ep == "delete_me":
            if ok:
                db.run("DELETE FROM member4_history WHERE user_id=?", uid)
            return response
        carrier = "text" if request.form.get("carrier") == "text" else "image"
        upload = request.files.get("image")
        other = (upload.filename or "") if (carrier == "image" and upload) else ""
        locked = bool(request.form.get("password"))
        if ep == "hide_secret":
            # A hidden picture comes back as the file itself (not JSON): status 200 means it worked.
            ok = response.status_code == 200 and (response.mimetype != "application/json" or data.get("ok") is True)
            error = "" if ok else str(data.get("error", "Failed"))
            fmt = (request.form.get("format") or "PNG").upper()
            method = TEXT_METHOD if carrier == "text" else IMAGE_METHODS.get(fmt, fmt)
            if carrier == "image" and request.form.get("gallery"):
                other = "Gallery picture"
            log(uid, "hide", carrier, method, locked=locked,
                message_chars=len(request.form.get("message", "")), other=other, success=ok, error=error)
        else:
            error = "" if ok else str(data.get("error", "Failed"))
            fmt = (data.get("format") or "PNG").upper()
            method = TEXT_METHOD if carrier == "text" else IMAGE_METHODS.get(fmt, "Spatial matrix embedding")
            log(uid, "reveal", carrier, method, locked=locked,
                message_chars=len(data["message"]) if ok else None, other=other, success=ok, error=error)
    except Exception as exc:  # history must never break the main app
        print("[member4] history not recorded:", exc)
    return response


def init_app(app) -> None:
    with db.connect() as con:
        con.executescript(SCHEMA)
    app.register_blueprint(bp)
    app.before_request(lambda: g.__setattr__("m4_uid", session.get("uid")))
    app.after_request(_record)
