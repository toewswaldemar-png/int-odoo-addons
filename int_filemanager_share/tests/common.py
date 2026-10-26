from contextlib import contextmanager

from ..controllers.int_filemanager import key_cookie


@contextmanager
def guest_key(opener, share, key=None):
    """The browser of the test holds the key of the password of ``share`` (its own, if none is given)
    in the cookie of the share, as the page of the password leaves it."""
    name = key_cookie(share.token)
    opener.cookies.set(name, share._unlock_key() if key is None else key)
    try:
        yield
    finally:
        opener.cookies.pop(name, None)


class NoSessionMixin:
    def assertNoSession(self, response):
        """A guest gets no session and no key from a page: the only cookie that Odoo may set on a
        page of the portal is the one of its language."""
        cookies = response.headers.get("Set-Cookie", "")
        self.assertNotIn("session_id", cookies)
        self.assertNotIn("int_filemanager_share_key", cookies)
