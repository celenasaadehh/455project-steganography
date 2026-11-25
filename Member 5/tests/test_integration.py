"""Integration tests: the two algorithms together, and through the website.

The first part checks that the image and text modules can be combined. The
second part drives Member 3's Flask application the way the browser does
(register, send, open the inbox, reveal), using Flask's built-in test client.
The website's data folder is replaced by a temporary folder, so running the
tests never touches real accounts or messages.

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
    """End-to-end tests of Member 3's website (Stego Mail)."""

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
        cls.carol = cls.new_user("carol@example.com", "Carol")

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

    def send(self, client, **fields):
        fields.setdefault("to", "bob@example.com")
        return client.post("/api/messages", data=fields, content_type="multipart/form-data")

    def reveal(self, client, message_id, password=""):
        return client.post(f"/api/messages/{message_id}/reveal", data={"password": password})

    # ------------------------------------------------------------ text carrier

    def test_text_message_from_alice_to_bob(self):
        sent = self.send(self.alice, carrier="text", cover="See you at lunch tomorrow.", message="the code is 4551")
        self.assertEqual(sent.status_code, 200, sent.get_json())
        message = sent.get_json()["message"]
        self.assertEqual(message["carrier"], "text")
        self.assertFalse(message["locked"])
        self.assertEqual(text_stego.strip_hidden(message["text"]), "See you at lunch tomorrow.")

        inbox = self.bob.get("/api/messages?box=inbox").get_json()["items"]
        self.assertIn(message["id"], [item["id"] for item in inbox])
        revealed = self.reveal(self.bob, message["id"])
        self.assertEqual(revealed.get_json()["message"], "the code is 4551")

    def test_locked_text_message_needs_the_password(self):
        sent = self.send(self.alice, carrier="text", cover="See you at lunch tomorrow.",
                         message="locked secret", password="open sesame")
        message = sent.get_json()["message"]
        self.assertTrue(message["locked"])
        for wrong in ("", "wrong password"):
            refused = self.reveal(self.bob, message["id"], wrong)
            self.assertEqual(refused.status_code, 401)
            self.assertEqual(refused.get_json()["code"], "password")
        self.assertEqual(self.reveal(self.bob, message["id"], "open sesame").get_json()["message"], "locked secret")

    # ----------------------------------------------------------- image carrier

    def test_image_message_with_a_gallery_picture(self):
        if not common.gallery_covers():
            self.skipTest("Member 3's gallery pictures are not in the repository")
        sent = self.send(self.alice, carrier="image", gallery="1", format="PNG", message="hidden in the ocean")
        self.assertEqual(sent.status_code, 200, sent.get_json())
        message = sent.get_json()["message"]
        self.assertEqual((message["carrier"], message["format"]), ("image", "PNG"))
        self.assertEqual(self.reveal(self.bob, message["id"]).get_json()["message"], "hidden in the ocean")

        # The file Bob downloads is a real stego image that the algorithm can read on its own.
        response = self.bob.get(message["file_url"])
        downloaded = response.data
        response.close()
        self.assertEqual(image_stego.extract(downloaded), b"hidden in the ocean")

    def test_image_message_with_an_uploaded_picture_and_password(self):
        for output_format in ("PNG", "BMP"):
            with self.subTest(output_format=output_format):
                upload = (io.BytesIO(to_bytes(common.noise_image())), "cover.png")
                sent = self.send(self.alice, carrier="image", image=upload, format=output_format,
                                 message="مرحبا 🔐", password="open sesame")
                self.assertEqual(sent.status_code, 200, sent.get_json())
                message = sent.get_json()["message"]
                self.assertTrue(message["locked"])
                self.assertEqual(self.reveal(self.bob, message["id"], "wrong").status_code, 401)
                self.assertEqual(self.reveal(self.bob, message["id"], "open sesame").get_json()["message"], "مرحبا 🔐")

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
        sent = self.send(self.alice, carrier="image", image=upload, format="PNG", message="x" * 5000)
        self.assertEqual(sent.status_code, 400)
        self.assertFalse(sent.get_json()["ok"])

    def test_file_that_is_not_a_picture(self):
        upload = (io.BytesIO(b"this is not an image"), "notes.txt")
        sent = self.send(self.alice, carrier="image", image=upload, format="PNG", message="x")
        self.assertEqual(sent.status_code, 400)

    def test_missing_parts_of_the_form(self):
        cases = {
            "no secret message": dict(carrier="text", cover="A cover sentence.", message=""),
            "no cover text": dict(carrier="text", cover="", message="secret"),
            "no picture": dict(carrier="image", format="PNG", message="secret"),
            "unknown recipient": dict(carrier="text", cover="A cover sentence.", message="secret", to="nobody@example.com"),
        }
        for name, fields in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.send(self.alice, **fields).status_code, 400)

    def test_only_sender_and_recipient_can_open_a_message(self):
        sent = self.send(self.alice, carrier="text", cover="Private sentence here.", message="for bob only")
        message_id = sent.get_json()["message"]["id"]
        self.assertEqual(self.reveal(self.carol, message_id).status_code, 404)
        self.assertEqual(self.reveal(self.bob, message_id).status_code, 200)

    def test_visitors_who_are_not_signed_in_are_refused(self):
        visitor = self.website.app.test_client()
        self.assertEqual(visitor.get("/api/messages").status_code, 401)
        self.assertEqual(self.send(visitor, carrier="text", cover="A cover.", message="x").status_code, 401)

    def test_hidden_message_is_never_stored_as_plain_text(self):
        # Checks the plain bytes only. An unlocked text message is still stored inside its stego
        # text (as invisible characters), so anyone who can read the database can reveal it.
        import db
        for password in ("open sesame", ""):
            secret = f"this exact sentence must not be stored {bool(password)}"
            with self.subTest(locked=bool(password)):
                sent = self.send(self.alice, carrier="text", cover="A harmless sentence.", message=secret,
                                 password=password)
                revealed = self.reveal(self.bob, sent.get_json()["message"]["id"], password)
                self.assertEqual(revealed.status_code, 200)
                self.assertNotIn(secret.encode("utf-8"), db.DB.read_bytes())

    # ------------------------------------------- Member 4: History and Learn tabs

    def history(self, client) -> list[dict]:
        response = client.get("/api/history")
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["items"]

    def test_history_records_hide_and_reveal_without_the_secret(self):
        if not (common.MEMBER4 / "member4.py").exists():
            self.skipTest("Member 4's folder is not in the repository")
        sender = self.new_user("hist.sender@example.com", "Hana")
        recipient = self.new_user("hist.recipient@example.com", "Rami")
        secret = "history must only keep the length"
        sent = self.send(sender, to="hist.recipient@example.com", carrier="text",
                         cover="Nothing unusual here.", message=secret, password="pw-123")
        message_id = sent.get_json()["message"]["id"]
        self.assertEqual(self.reveal(recipient, message_id, "wrong").status_code, 401)
        self.assertEqual(self.reveal(recipient, message_id, "pw-123").status_code, 200)

        hides = self.history(sender)
        reveals = self.history(recipient)
        self.assertEqual([row["action"] for row in hides], ["hide"])
        self.assertEqual([row["action"] for row in reveals], ["reveal", "reveal"])
        self.assertEqual(hides[0]["message_chars"], len(secret))
        self.assertTrue(hides[0]["locked"])
        self.assertEqual(sorted(row["success"] for row in reveals), [False, True])
        self.assertNotIn(secret, str(hides + reveals))

        csv_file = recipient.get("/api/history.csv")
        self.assertEqual(csv_file.status_code, 200)
        self.assertNotIn(secret, csv_file.get_data(as_text=True))
        csv_file.close()

    def test_history_is_private_to_each_user(self):
        if not (common.MEMBER4 / "member4.py").exists():
            self.skipTest("Member 4's folder is not in the repository")
        writer = self.new_user("hist.writer@example.com", "Wafa")
        outsider = self.new_user("hist.outsider@example.com", "Omar")
        self.send(writer, to="bob@example.com", carrier="text", cover="A private note.", message="x")
        self.assertEqual(len(self.history(writer)), 1)
        self.assertEqual(self.history(outsider), [])
        self.assertEqual(self.website.app.test_client().get("/api/history").status_code, 401)

    @unittest.expectedFailure
    def test_outsider_cannot_learn_who_sent_a_message_from_history(self):
        # Issue 2 (Member 4). Someone who is neither the sender nor the recipient tries to reveal a
        # message by its number. The website correctly answers 404, but History still saves a failed
        # "reveal" row in the outsider's own History, holding the real sender's e-mail address.
        if not (common.MEMBER4 / "member4.py").exists():
            self.skipTest("Member 4's folder is not in the repository")
        sender = self.new_user("leak.sender@example.com", "Sara")
        self.new_user("leak.recipient@example.com", "Rana")
        outsider = self.new_user("leak.outsider@example.com", "Omar")
        sent = self.send(sender, to="leak.recipient@example.com", carrier="text",
                         cover="Just a short note.", message="private")
        message_id = sent.get_json()["message"]["id"]
        self.assertEqual(self.reveal(outsider, message_id).status_code, 404)
        self.assertNotIn("leak.sender@example.com", str(self.history(outsider)))

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
