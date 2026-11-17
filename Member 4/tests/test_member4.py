"""Member 4 tests. Run from the repository root:

    python -m unittest discover -s "Member 4/tests" -v
"""
import io
import sys
import unittest
import uuid
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
for sub in ("Member 1", "Member 2", "Member 4"):
    sys.path.insert(0, str(ROOT / sub))

import learn_trace as L  # noqa: E402

GALLERY = ROOT / "Member 2" / "static" / "gallery" / "02-sunset.png"


def noisy_png(w=200, h=150, seed=1):
    rng = np.random.default_rng(seed)
    buf = io.BytesIO()
    Image.fromarray(rng.integers(0, 256, (h, w, 3), dtype=np.uint8)).save(buf, "PNG")
    return buf.getvalue()


class ImageTrace(unittest.TestCase):
    def test_round_trip_unlocked(self):
        t = L.trace_image(GALLERY.read_bytes(), "Hi EECE 455! مرحبا 👋")
        self.assertTrue(t["ok"])
        self.assertFalse(t["encrypted"])
        self.assertEqual(t["header"]["fields"][0]["value"], "ILAB")

    def test_round_trip_locked(self):
        t = L.trace_image(noisy_png(), "top secret", password="pw123")
        self.assertTrue(t["ok"])
        self.assertTrue(t["encrypted"])
        self.assertFalse(t["body"]["readable"])

    def test_groups_follow_matrix_embedding(self):
        """Every shown group: at most one value changed, by exactly 1, and the XOR afterwards equals the hidden bits."""
        t = L.trace_image(noisy_png(seed=3), "matrix embedding check")
        self.assertTrue(t["groups"])
        for g in t["groups"]:
            diffs = [v["after"] - v["before"] for v in g["values"]]
            changed = [d for d in diffs if d]
            self.assertLessEqual(len(changed), 1)
            self.assertTrue(all(abs(d) == 1 for d in changed))
            syn = 0
            for pos, v in enumerate(g["values"], start=1):
                if v["after"] & 1:
                    syn ^= pos
            self.assertEqual(f"{syn:03b}", g["target"])

    def test_fewer_changes_than_groups(self):
        t = L.trace_image(noisy_png(seed=4), "x" * 200)
        self.assertLessEqual(t["stats"]["channels_changed"], t["stats"]["groups_used"])

    def test_too_long_is_refused(self):
        import image_stego as img
        tiny = io.BytesIO(); Image.new("RGB", (16, 16)).save(tiny, "PNG")
        with self.assertRaises(img.StegoError):
            L.trace_image(tiny.getvalue(), "this will not fit")


class TextTrace(unittest.TestCase):
    def test_round_trip(self):
        t = L.trace_text("See you tomorrow!", "gate B")
        self.assertTrue(t["ok"])
        self.assertEqual(t["stats"]["hidden_chars"], (4 + len("gate B") + 4) * 4)  # header + message + CRC, 4 chars per byte
        self.assertEqual(t["payload_rows"][0]["field"], "Tag 'ZW'")

    def test_visible_text_unchanged(self):
        import text_stego as txt
        t = L.trace_text("Hello there friend", "yo")
        self.assertEqual(txt.strip_hidden(t["stego"]), "Hello there friend")

    def test_locked_and_check(self):
        t = L.trace_text("Hello there", "secret", password="k")
        self.assertTrue(t["locked"])
        self.assertTrue(L.check_text(t["stego"], "k")["found"])
        self.assertTrue(L.check_text(t["stego"])["needs_password"])
        self.assertFalse(L.check_text("plain text")["found"])


class HistoryApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as main  # Member 2's Flask app (creates Member 2/data if needed)
        if "member4" not in main.app.blueprints:
            raise unittest.SkipTest("Member 4 is not connected to app.py yet (see README)")
        cls.app = main.app
        cls.app.testing = True

    def login(self, client, email):
        r = client.post("/api/auth/register", json={"handle": email, "first_name": "T", "password": "secret123"})
        self.assertTrue(r.get_json()["ok"], r.get_json())

    def test_send_and_reveal_are_logged_without_the_secret(self):
        a, b = self.app.test_client(), self.app.test_client()
        ea, eb = f"a{uuid.uuid4().hex[:8]}@t.com", f"b{uuid.uuid4().hex[:8]}@t.com"
        self.login(a, ea); self.login(b, eb)
        r = a.post("/api/messages", data={"to": eb, "message": "SECRET-123", "carrier": "text", "cover": "hi there"})
        self.assertTrue(r.get_json()["ok"])
        a.post("/api/messages", data={"to": "nobody@nowhere.com", "message": "x", "carrier": "text", "cover": "hi"})
        mid = b.get("/api/messages?box=inbox").get_json()["items"][0]["id"]
        self.assertTrue(b.post(f"/api/messages/{mid}/reveal").get_json()["ok"])

        ha = a.get("/api/history").get_json()["items"]
        self.assertEqual([(h["action"], h["success"]) for h in ha], [("hide", False), ("hide", True)])
        self.assertEqual(ha[1]["message_chars"], 10)
        hb = b.get("/api/history").get_json()["items"]
        self.assertEqual((hb[0]["action"], hb[0]["success"], hb[0]["other"]), ("reveal", True, ea))
        self.assertNotIn("SECRET-123", a.get("/api/history.csv").get_data(as_text=True))

        a.delete("/api/history")
        self.assertEqual(a.get("/api/history").get_json()["items"], [])

    def test_requires_login(self):
        self.assertEqual(self.app.test_client().get("/api/history").status_code, 401)
        self.assertEqual(self.app.test_client().post("/api/learn/text").status_code, 401)


if __name__ == "__main__":
    unittest.main()
