from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request

from ..models.int_liedanzeige_state import CONDUCTOR_GROUP, OPERATOR_GROUP


class IntLiedanzeige(http.Controller):
    @http.route("/lied", type="http", auth="public", methods=["GET"])
    def display_hymn(self):
        return self._render_display("hymn", request.env._("Hymn display"))

    @http.route("/chor", type="http", auth="public", methods=["GET"])
    def display_choir(self):
        return self._render_display("choir", request.env._("Choir display"))

    @http.route("/int_liedanzeige/state", type="jsonrpc", auth="public", methods=["POST"], readonly=True)
    def display_state(self):
        """Return what a display shows, for the page load and after a lost connection."""
        # sudo: the public user has no access to the state model, and the values below contain
        # nothing a display may not show.
        return request.env.ref("int_liedanzeige.state_main").sudo()._public_values()

    @http.route(["/steuerung", "/steuerung/lied"], type="http", auth="user", methods=["GET"])
    def control_hymn(self):
        return self._render_control("hymn", request.env._("Control - hymn"))

    @http.route("/steuerung/chor", type="http", auth="user", methods=["GET"])
    def control_choir(self):
        return self._render_control("choir", request.env._("Control - choir"))

    @http.route("/dirigent", type="http", auth="user", methods=["GET"])
    def conductor(self):
        if not request.env.user.has_group(CONDUCTOR_GROUP):
            raise Forbidden()
        state = request.env["int_liedanzeige.state"].get_conductor_state()
        return self._render_page(
            request.env._("Conductor view"), {"page": "conductor", "target": "conductor", "state": state}
        )

    def _render_display(self, target, title):
        state = request.env.ref("int_liedanzeige.state_main").sudo()
        return self._render_page(title, {"page": "display", "target": target, "state": state._public_values()})

    def _render_control(self, target, title):
        if not request.env.user.has_group(OPERATOR_GROUP):
            raise Forbidden()
        state = request.env["int_liedanzeige.state"].get_state()
        return self._render_page(title, {"page": "control", "target": target, "state": state})

    def _render_page(self, title, config):
        return request.render(
            "int_liedanzeige.page",
            {
                "title": title,
                "session_info": request.env["ir.http"].session_info(),
                "config": config,
            },
        )
