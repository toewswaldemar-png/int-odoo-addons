import hmac
import json

from odoo import http
from odoo.http import request


class IntKeepassAida(http.Controller):
    @http.route("/int_keepass/aida_users", type="http", auth="public", methods=["GET"], cors="*", readonly=True)
    def aida_users(self, token=None, **_kwargs):
        """The user names for the list on the login page of AIDA, behind a token.

        Names only. The token is the system parameter ``int_keepass.aida_token``; without it
        (or with a wrong one) the answer is the same 404 as for a page that does not exist.
        """
        expected = request.env["ir.config_parameter"].sudo().get_param("int_keepass.aida_token")
        if not expected or not token or not hmac.compare_digest(expected.encode(), token.encode()):
            raise request.not_found()
        names = request.env["int.keepass.aida.user"].sudo().search([]).mapped("name")
        return request.make_response(
            json.dumps({"users": sorted(names)}),
            headers=[("Content-Type", "application/json"), ("Cache-Control", "no-store")],
        )
