"""Integration tests: the two algorithms together, and through the website.

The first part checks that the image and text modules can be combined. The
second part drives Member 3's Flask application the way the browser does
(register, hide and download, upload and reveal), using Flask's built-in test
client. The website's data folder is replaced by a temporary folder, so running
the tests never touches real accounts.

Run from the "Member 5" folder:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common  # noqa: E402
from common import image_stego, text_stego, to_bytes  # noqa: E402


class AlgorithmsTogetherTests(unittest.TestCase):
    def setUp(self):
        self.cover = to_bytes(common.gradient_image())

    def test_stego_text_can_be_hidden_inside_an_image(self):
        # Two layers: a secret inside a sentence, and that sentence inside a picture.
        inner = text_stego.hide("Nothing special in this sentence.", "inner secret", "text pass")
        picture = image_stego.embed(self.cover, inner, password="image pass")
        recovered = image_stego.extract(picture.image, password="image pass").decode("utf-8")
        self.assertEqual(recovered, inner)
        self.assertEqual(text_stego.reveal(recovered, "text pass"), "inner secret")

    def test_same_secret_survives_both_carriers(self):
        for secret in ("plain ascii", "مرحبا 🔐 émoji", "x" * 1000):
            with self.subTest(secret=secret[:12]):
                from_image = image_stego.extract(image_stego.embed(self.cover, secret).image).decode("utf-8")
                from_text = text_stego.reveal(text_stego.hide("A normal sentence.", secret))
                self.assertEqual(from_image, secret)
                self.assertEqual(from_text, secret)

    def test_a_message_from_one_carrier_is_not_accepted_by_the_other(self):
        text = text_stego.hide("A normal sentence.", "secret")
        with self.assertRaises(image_stego.StegoError):
            image_stego.extract(text.encode("utf-8"))
        with self.assertRaises(text_stego.TextStegoError):
            text_stego.reveal(self.cover.decode("latin-1"))

    def test_both_modules_report_errors_the_same_way(self):
        # The website turns ValueError subclasses into messages for the user.
        self.assertTrue(issubclass(image_stego.StegoError, ValueError))
        self.assertTrue(issubclass(text_stego.TextStegoError, ValueError))
        self.assertTrue(issubclass(image_stego.PasswordError, image_stego.StegoError))
        self.assertTrue(issubclass(text_stego.TextPasswordError, text_stego.TextStegoError))


class WebsiteTests(unittest.TestCase):
    """End-to-end tests of Member 3's website (Stego Studio): hide, download, upload, reveal."""

    @classmethod
    def setUpClass(cls):
        try:
            import flask  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("Flask is not installed")
        if not (common.MEMBER3 / "app.py").exists():
            raise unittest.SkipTest("Member 3's website is not in the repository")

        # Point the website at an empty temporary data folder before it starts.
        cls.folder = tempfile.TemporaryDirectory()
        os.environ["STEGO_VERIFY_EMAIL"] = "0"
        import db
        db.DATA = Path(cls.folder.name) / "data"
        db.DB = db.DATA / "stego.db"
        import app as website
        website.app.config["TESTING"] = True
        cls.website = website

        cls.alice = cls.new_user("alice@example.com", "Alice")
        cls.bob = cls.new_user("bob@example.com", "Bob")

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    @classmethod
    def new_user(cls, email: str, name: str):
        client = cls.website.app.test_client()
        response = client.post("/api/auth/register", json={
            "handle": email, "first_name": name, "last_name": "Tester", "password": "test-password"})
        assert response.status_code == 200, response.get_json()
        return client

    def setUp(self):
        self.website.attempts.clear()      # every test starts with no wrong-password count

    def hide(self, client, **fields):
        fields.setdefault("password", "pw-test-1")      # the website always asks for one (6+ characters)
        return client.post("/api/hide", data=fields, content_type="multipart/form-data")

    def reveal(self, client, **fields):
        fields.setdefault("password", "pw-test-1")
        return client.post("/api/reveal", data=fields, content_type="multipart/form-data")

    def hide_picture(self, client, **fields) -> bytes:
        """Hide in a picture and return the downloaded file."""
        response = self.hide(client, carrier="image", **fields)
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.data
        response.close()
        return data

    def reveal_picture(self, client, picture: bytes, password="pw-test-1"):
        return self.reveal(client, carrier="image", image=(io.BytesIO(picture), "stego.png"), password=password)

    # ------------------------------------------------------------ text carrier

    def test_text_hidden_by_alice_is_revealed_by_bob(self):
        hidden = self.hide(self.alice, carrier="text", cover="See you at lunch tomorrow.", message="the code is 4551")
        self.assertEqual(hidden.status_code, 200, hidden.get_json())
        stego = hidden.get_json()["text"]
        self.assertEqual(text_stego.strip_hidden(stego), "See you at lunch tomorrow.")
        revealed = self.reveal(self.bob, carrier="text", text=stego)
        self.assertEqual(revealed.get_json()["message"], "the code is 4551")

    def test_locked_text_needs_the_password(self):
        stego = self.hide(self.alice, carrier="text", cover="See you at lunch tomorrow.",
                          message="locked secret", password="open sesame").get_json()["text"]
        for wrong in ("", "wrong password"):
            refused = self.reveal(self.bob, carrier="text", text=stego, password=wrong)
            self.assertEqual(refused.status_code, 401)
            self.assertEqual(refused.get_json()["code"], "password")
        opened = self.reveal(self.bob, carrier="text", text=stego, password="open sesame")
        self.assertEqual(opened.get_json()["message"], "locked secret")

    # ----------------------------------------------------------- image carrier

    def test_picture_from_the_gallery_downloads_and_reveals(self):
        if not common.gallery_covers():
            self.skipTest("Member 3's gallery pictures are not in the repository")
        response = self.hide(self.alice, carrier="image", gallery="1", format="PNG", message="hidden in the ocean")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.mimetype, "image/png")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        picture = response.data
        response.close()
        # The downloaded file is a real stego image that the algorithm can read on its own...
        self.assertEqual(image_stego.extract(picture, password="pw-test-1"), b"hidden in the ocean")
        # ...and uploading it to Reveal gives the message back.
        revealed = self.reveal_picture(self.bob, picture)
        self.assertEqual(revealed.get_json()["message"], "hidden in the ocean")

    def test_uploaded_picture_with_password(self):
        for output_format in ("PNG", "BMP"):
            with self.subTest(output_format=output_format):
                upload = (io.BytesIO(to_bytes(common.noise_image())), "cover.png")
                picture = self.hide_picture(self.alice, image=upload, format=output_format,
                                            message="مرحبا 🔐", password="open sesame")
                self.assertEqual(self.reveal_picture(self.bob, picture, "wrong").status_code, 401)
                opened = self.reveal_picture(self.bob, picture, "open sesame").get_json()
                self.assertEqual((opened["message"], opened["format"]), ("مرحبا 🔐", output_format))

    def test_capacity_shown_by_the_website_matches_the_algorithm(self):
        cover = to_bytes(common.noise_image())
        for encrypted in ("0", "1"):
            with self.subTest(encrypted=encrypted):
                answer = self.alice.post("/api/image/capacity", content_type="multipart/form-data", data={
                    "image": (io.BytesIO(cover), "cover.png"), "format": "PNG", "encrypted": encrypted}).get_json()
                expected = image_stego.capacity(cover, "PNG", encrypted=encrypted == "1")
                self.assertEqual(answer["max_message_bytes"], expected.max_message_bytes)
                self.assertTrue(answer["can_embed"])

    # ------------------------------------------------------------------ errors

    def test_message_too_long_for_the_picture(self):
        upload = (io.BytesIO(to_bytes(common.noise_image(48, 48))), "small.png")
        response = self.hide(self.alice, carrier="image", image=upload, format="PNG", message="x" * 5000)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_file_that_is_not_a_picture(self):
        upload = (io.BytesIO(b"this is not an image"), "notes.txt")
        self.assertEqual(self.hide(self.alice, carrier="image", image=upload, format="PNG", message="x").status_code, 400)
        notes = (io.BytesIO(b"this is not an image"), "notes.txt")
        self.assertEqual(self.reveal(self.alice, carrier="image", image=notes).status_code, 400)

    def test_missing_parts_of_the_form(self):
        cases = {
            "hide: no password": ("hide", dict(carrier="text", cover="A cover sentence.", message="secret", password="")),
            "hide: password under 6 characters": ("hide", dict(carrier="text", cover="A cover sentence.", message="secret", password="abc")),
            "hide: no secret message": ("hide", dict(carrier="text", cover="A cover sentence.", message="")),
            "hide: no cover text": ("hide", dict(carrier="text", cover="", message="secret")),
            "hide: no picture": ("hide", dict(carrier="image", format="PNG", message="secret")),
            "reveal: no picture": ("reveal", dict(carrier="image")),
            "reveal: no text": ("reveal", dict(carrier="text", text="")),
        }
        for name, (action, fields) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(getattr(self, action)(self.alice, **fields).status_code, 400)

    def test_ordinary_picture_has_no_message(self):
        response = self.reveal_picture(self.bob, to_bytes(common.noise_image()))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_wrong_passwords_are_limited(self):
        # After 5 wrong passwords the account must wait, even for the right one; a wrong sign-in is limited the same way.
        stego = self.hide(self.alice, carrier="text", cover="Guess the password.", message="x",
                          password="right-pass").get_json()["text"]
        for attempt in range(5):
            self.assertEqual(self.reveal(self.bob, carrier="text", text=stego, password=f"guess-{attempt}").status_code, 401)
        blocked = self.reveal(self.bob, carrier="text", text=stego, password="right-pass")
        self.assertEqual((blocked.status_code, blocked.get_json()["code"]), (429, "slow_down"))
        self.assertEqual(self.reveal(self.alice, carrier="text", text=stego, password="right-pass").status_code, 200)

        visitor = self.website.app.test_client()
        for attempt in range(5):
            wrong = visitor.post("/api/auth/login", json={"handle": "alice@example.com", "password": f"guess-{attempt}"})
            self.assertEqual(wrong.status_code, 401)
        self.assertEqual(visitor.post("/api/auth/login", json={"handle": "alice@example.com",
                                                               "password": "test-password"}).status_code, 429)

    def test_unexpected_server_error_is_a_clear_message(self):
        # A text that cannot be hidden used to crash with an HTML error page (issue 1); now it is a JSON error.
        response = self.hide(self.alice, carrier="text", cover="​ ​", message="x")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_visitors_who_are_not_signed_in_are_refused(self):
        visitor = self.website.app.test_client()
        self.assertEqual(self.hide(visitor, carrier="text", cover="A cover.", message="x").status_code, 401)
        self.assertEqual(self.reveal(visitor, carrier="text", text="A cover.").status_code, 401)

    def test_nothing_hidden_is_stored_by_the_website(self):
        secret = "this exact sentence must not be stored"
        stego = self.hide(self.alice, carrier="text", cover="A harmless sentence.",
                          message=secret, password="open sesame").get_json()["text"]
        self.reveal(self.bob, carrier="text", text=stego, password="open sesame")
        import db
        stored = db.DB.read_bytes()
        self.assertNotIn(secret.encode("utf-8"), stored)
        self.assertNotIn(stego.encode("utf-8"), stored)

    # ------------------------------------------- Member 4: History and Learn tabs

    def history(self, client) -> list[dict]:
        response = client.get("/api/history")
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["items"]

    def test_history_records_hide_and_reveal_without_the_secret(self):
        if not (common.MEMBER4 / "member4.py").exists():
            self.skipTest("Member 4's folder is not in the repository")
        hider = self.new_user("hist.hider@example.com", "Hana")
        revealer = self.new_user("hist.revealer@example.com", "Rami")
        secret = "history must only keep the length"
        stego = self.hide(hider, carrier="text", cover="Nothing unusual here.",
                          message=secret, password="pw-123").get_json()["text"]
        self.assertEqual(self.reveal(revealer, carrier="text", text=stego, password="wrong").status_code, 401)
        self.assertEqual(self.reveal(revealer, carrier="text", text=stego, password="pw-123").status_code, 200)
        upload = (io.BytesIO(to_bytes(common.noise_image())), "cover.png")
        self.hide_picture(hider, image=upload, format="PNG", message="in a picture")

        hides = self.history(hider)
        reveals = self.history(revealer)
        self.assertEqual([row["action"] for row in hides], ["hide", "hide"])
        self.assertEqual([row["carrier"] for row in hides], ["image", "text"])
        self.assertTrue(all(row["success"] for row in hides))
        self.assertEqual([row["action"] for row in reveals], ["reveal", "reveal"])
        self.assertEqual(hides[1]["message_chars"], len(secret))
        self.assertTrue(hides[1]["locked"])
        self.assertEqual(sorted(row["success"] for row in reveals), [False, True])
        self.assertNotIn(secret, str(hides + reveals))

        csv_file = revealer.get("/api/history.csv")
        self.assertEqual(csv_file.status_code, 200)
        self.assertNotIn(secret, csv_file.get_data(as_text=True))
        csv_file.close()

    def test_history_is_private_to_each_user(self):
        if not (common.MEMBER4 / "member4.py").exists():
            self.skipTest("Member 4's folder is not in the repository")
        writer = self.new_user("hist.writer@example.com", "Wafa")
        outsider = self.new_user("hist.outsider@example.com", "Omar")
        self.hide(writer, carrier="text", cover="A private note.", message="x")
        self.assertEqual(len(self.history(writer)), 1)
        self.assertEqual(self.history(outsider), [])
        self.assertEqual(self.website.app.test_client().get("/api/history").status_code, 401)

    def test_learn_walkthrough_uses_the_real_algorithms(self):
        if not (common.MEMBER4 / "member4.py").exists():
            self.skipTest("Member 4's folder is not in the repository")
        text = self.alice.post("/api/learn/text", data={"cover": "See you at lunch tomorrow.", "message": "learn"})
        self.assertEqual(text.status_code, 200, text.get_json())
        self.assertTrue(text.get_json()["ok"])
        upload = (io.BytesIO(to_bytes(common.gradient_image(96, 96))), "cover.png")
        image = self.alice.post("/api/learn/image", content_type="multipart/form-data",
                                data={"image": upload, "message": "learn"})
        self.assertEqual(image.status_code, 200, image.get_json())
        self.assertTrue(image.get_json()["ok"])
        self.assertEqual(self.alice.post("/api/learn/text", data={"cover": "", "message": "x"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
