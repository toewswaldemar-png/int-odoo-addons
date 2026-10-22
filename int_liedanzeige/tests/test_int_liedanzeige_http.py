import re

from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestIntLiedanzeigeHttp(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = new_test_user(
            cls.env,
            login="lied_http_operator",
            groups="base.group_user,int_liedanzeige.group_liedanzeige_operator",
        )
        cls.outsider = new_test_user(cls.env, login="lied_http_outsider", groups="base.group_user")
        cls.conductor = new_test_user(
            cls.env,
            login="lied_http_conductor",
            groups="base.group_user,int_liedanzeige.group_liedanzeige_conductor",
        )
        cls.env["int_liedanzeige.song"].create({"number": "77", "name": "Hidden title", "text": "Hidden words"})
        cls.env.ref("int_liedanzeige.state_main").choir_state = "77"

    def test_displays_are_public_and_load_the_page_assets(self):
        for url in ("/lied", "/chor"):
            response = self.url_open(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertIn("int_liedanzeige", response.text)
            self.assertNotIn("control_state", response.text)
            # The bundles are compiled on first request: a broken stylesheet fails here.
            assets = re.findall(r'(?:src|href)="(/web/assets/[^"]+)"', response.text)
            self.assertTrue(assets, "the page links its asset bundle")
            for asset in assets:
                bundle = self.url_open(asset)
                self.assertEqual(bundle.status_code, 200, asset)
                # With x_sendfile the body is empty and the web server delivers the file.
                self.assertTrue(
                    bundle.content or bundle.headers.get("X-Sendfile") or bundle.headers.get("X-Accel-Redirect"),
                    asset,
                )

    def test_display_page_carries_its_target_and_no_control_number(self):
        hymn = self.url_open("/lied").text
        choir = self.url_open("/chor").text
        self.assertIn('"target": "hymn"', hymn)
        self.assertIn('"target": "choir"', choir)

    def test_display_state_route_answers_the_public_without_the_control_number(self):
        response = self.url_open(
            "/int_liedanzeige/state",
            data='{"jsonrpc": "2.0", "method": "call", "params": {}}',
            headers={"Content-Type": "application/json"},
        )
        result = response.json()["result"]
        self.assertEqual(set(result), {"hymn_state", "choir_state", "settings"})

    def test_control_page_asks_anonymous_visitors_to_log_in(self):
        response = self.url_open("/steuerung/lied", allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertIn("/web/login", response.headers["Location"])

    def test_control_page_is_refused_without_the_operator_group(self):
        self.authenticate("lied_http_outsider", "lied_http_outsider")
        self.assertEqual(self.url_open("/steuerung/lied").status_code, 403)
        self.assertEqual(self.url_open("/steuerung/chor").status_code, 403)

    def test_operator_opens_both_control_pages(self):
        self.authenticate("lied_http_operator", "lied_http_operator")
        for url, target in (("/steuerung", "hymn"), ("/steuerung/lied", "hymn"), ("/steuerung/chor", "choir")):
            response = self.url_open(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertIn(f'"target": "{target}"', response.text)
            self.assertIn("control_state", response.text)

    def test_conductor_page_needs_a_login(self):
        response = self.url_open("/dirigent", allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertIn("/web/login", response.headers["Location"])

    def test_conductor_page_is_refused_without_the_conductor_group(self):
        for login in ("lied_http_outsider", "lied_http_operator"):
            self.authenticate(login, login)
            response = self.url_open("/dirigent")
            self.assertEqual(response.status_code, 403, login)
            self.assertNotIn("Hidden words", response.text)

    def test_conductor_opens_the_page_with_the_song(self):
        self.authenticate("lied_http_conductor", "lied_http_conductor")
        response = self.url_open("/dirigent")
        self.assertEqual(response.status_code, 200)
        self.assertIn('"target": "conductor"', response.text)
        self.assertIn("Hidden words", response.text)

    def test_the_song_text_is_not_on_the_public_pages_or_the_public_route(self):
        for url in ("/lied", "/chor"):
            self.assertNotIn("Hidden words", self.url_open(url).text)
        response = self.url_open(
            "/int_liedanzeige/state",
            data='{"jsonrpc": "2.0", "method": "call", "params": {}}',
            headers={"Content-Type": "application/json"},
        )
        self.assertNotIn("Hidden words", response.text)
