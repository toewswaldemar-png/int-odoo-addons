from odoo import http
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class IntUiShowcasePortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "showcase_count" in counters:
            Showcase = request.env["int.ui.showcase"]
            values["showcase_count"] = (
                Showcase.search_count([]) if Showcase.has_access("read") else 0
            )
        return values

    @http.route(["/my/ui-showcase", "/my/ui-showcase/page/<int:page>"], type="http", auth="user", website=True)
    def portal_my_ui_showcase(self, page=1, **kw):
        """Render the portal page with a record table, a pager and Bootstrap elements."""
        Showcase = request.env["int.ui.showcase"]
        step = 5
        total = Showcase.search_count([])
        pager = portal_pager(
            url="/my/ui-showcase", total=total, page=page, step=step
        )
        records = Showcase.search([], limit=step, offset=pager["offset"])
        values = {
            "page_name": "ui_showcase",
            "records": records,
            "pager": pager,
            "default_url": "/my/ui-showcase",
        }
        return request.render("int_ui_showcase.portal_my_ui_showcase", values)
