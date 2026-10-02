import functools
import json
import logging
import os
import re

from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

from .. import blobstore, params, value_suggest, value_types
from .. import derivative_plan as plan
from . import int_filemanager_derivative as derivative

_logger = logging.getLogger(__name__)

# Company names are looked for in the letterhead, the start of the first page.
NAME_SEARCH_CHARS = 20000
MAX_SUGGESTED_TAGS = 10
# Boxes one request may carry, and the longest text a marking may cover.
MAX_AREAS = 50
MAX_SELECTION_CHARS = 200
# Words of one page sent to the properties form to click on.
MAX_PAGE_WORDS = 5000
# Values one confirmation may carry, and tags it may add.
MAX_CONFIRMED_VALUES = 200
MAX_CONFIRMED_TAGS = 100


def _website_host(website):
    """Return the host of a web address, e.g. "example.com" for "https://www.example.com/x"."""
    host = re.sub(r"^[a-z]+://", "", (website or "").strip().lower())
    return host.split("/")[0].removeprefix("www.")


def _area(field):
    """Return the page area a field is looked for in, None for anywhere."""
    return None if field.page_area == "anywhere" else field.page_area


def _whole_words(text, start, end):
    """Widen ``[start:end]`` where it cuts a word, up to a blank, tab or line break.

    Looks no further than a marking may be long, so a text without blanks costs no more.
    """
    if 0 < start < len(text) and not text[start - 1].isspace():
        if not text[start].isspace():
            head = text[max(0, start - MAX_SELECTION_CHARS) : start]
            start -= len(re.search(r"\S*$", head)[0])
    if 0 < end < len(text) and not text[end - 1].isspace():
        if not text[end].isspace():
            end += len(re.match(r"\S*", text[end : end + MAX_SELECTION_CHARS])[0])
    return start, end


def _log_slow_rule(node_id, rule_id, seconds):
    _logger.warning(
        "extraction rule %s took %.1f s on node %s", rule_id, seconds, node_id
    )


class IntFilemanagerValueRecognition(models.AbstractModel):
    """Reading values out of a file's text, for the nodes that inherit it."""

    _name = "int_filemanager.value_recognition"
    _description = "Value recognition of a file"

    @api.model
    def _recognition_shared(self, with_own=True):
        """Return what the recognition of any file needs, to be read once per request.

        ``options`` and ``codes`` are for reading values (currencies as printed,
        defaults of the company, currency ids); ``own`` is what to leave out because
        it belongs to the own companies.
        """
        # sudo(): currencies and the company settings are no data of the caller.
        company = self.env.company.sudo()
        currencies = (
            self.env["res.currency"].sudo().search([("active", "=", True)])
            + company.currency_id
        )
        names = {}
        for currency in currencies:
            names[currency.symbol] = currency.name
            names[currency.name] = currency.name
        if "EUR" in names:
            names["Euro"] = "EUR"
        return {
            "options": {
                "currencies": names,
                "default_currency": company.currency_id.name,
                "default_country": (company.country_id.code or "DE").upper(),
            },
            "codes": {currency.name: currency.id for currency in currencies},
            "own": self._own_company_values() if with_own else None,
        }

    @api.model
    @api.readonly
    def suggest_field_values(self, node_id, areas=None):
        """Suggest values for the extraction fields from the file's current text.

        Nothing is stored. ``areas`` are boxes the user drew, ``[{"page", "x0", "top",
        "x1", "bottom"}]`` as shares (0 to 1) of the page: a value in a box goes before
        the same kind outside. ``state`` is "ready", "pending" or "none";
        ``revision_id`` is the revision to send back when the values are confirmed.
        """
        node = self.browse(params.require_id(self.env, node_id, "node_id"))
        node.check_access("read")
        return self._suggest_values(
            node, self._parse_areas(areas), self._recognition_shared()
        )

    def _suggest_values(self, node, boxes, shared):
        """Return the answer of ``suggest_field_values`` for a readable node."""
        revision = node.current_revision_id
        if node.is_dir or not revision:
            return {"state": "none", "revision_id": False}
        state, page = self._recognition_page(node, revision)
        if state != "ready":
            return {
                "state": state,
                "revision_id": revision.id,
                # A picture has no text until it is asked for (``request_text``).
                "can_read_text": state == "none" and plan.can_read_text(node.name),
            }
        own, options, codes = shared["own"], shared["options"], shared["codes"]
        partner = self._suggest_partner(page.text, own, options)
        suggestions, unassigned = value_suggest.suggest(
            page,
            self._extraction_specs(self._sender(node, partner)),
            skip=lambda value_type, value: self._is_own_value(own, value_type, value),
            slow=functools.partial(_log_slow_rule, node.id),
            areas=boxes,
            **options,
        )
        return {
            "state": "ready",
            "revision_id": revision.id,
            "review_state": node.review_state,
            # Width and height of the pages in the unit of the value boxes; a page
            # not listed is taken as A4.
            "page_sizes": {str(n): list(size) for n, size in page.sizes.items()},
            "fields": self._fields_answer(node, page, suggestions, codes),
            "unassigned": [
                self._json_value(u, codes) for u in unassigned if u["area"] is None
            ],
            "areas": self._areas_answer(page, boxes, suggestions, unassigned, codes),
            "partner": partner,
            "tags": self._suggest_tags(page.text),
            "warnings": self._suggest_warnings(partner, suggestions),
        }

    def _fields_answer(self, node, page, suggestions, codes):
        """Return one entry per extraction field, with suggestions and stored value."""
        confirmed = {v.field_id.id: v for v in node.field_value_ids}
        return [
            {
                "field_id": field.id,
                "name": field.name,
                "value_type": field.value_type,
                "suggestions": [
                    self._json_suggestion(s.as_dict(), codes)
                    for s in suggestions.get(field.id, [])
                ],
                "confirmed": confirmed[field.id].value_text
                if field.id in confirmed
                else False,
                # Where the stored value was read from, shaped like a suggestion,
                # with the boxes of the words as they are now.
                "confirmed_place": self._place_of(confirmed[field.id], page)
                if field.id in confirmed
                else False,
            }
            for field in self.env["int_filemanager.extraction_field"].search(
                [("active", "=", True)]
            )
        ]

    def _areas_answer(self, page, boxes, suggestions, unassigned, codes):
        """Return one entry per drawn box: its number of values and loose pairs."""
        return [
            {
                "index": index,
                "values": sum(
                    1
                    for found in suggestions.values()
                    if page.in_box(found[0].start, found[0].end, box)
                )
                + sum(1 for u in unassigned if u["area"] == index),
                "unassigned": [
                    self._json_value(u, codes) for u in unassigned if u["area"] == index
                ],
            }
            for index, box in enumerate(boxes)
        ]

    @staticmethod
    def _place_of(value, page):
        """Return where a stored value is printed, as a suggestion would, or False."""
        if not value.page:
            return False
        place = {
            "page": value.page,
            "x0": value.x0,
            "top": value.top,
            "x1": value.x1,
            "bottom": value.bottom,
        }
        return page.refit(place)

    def _suggest_warnings(self, partner, suggestions):
        """Return hints about values that look wrong; nothing is stored.

        An IBAN that none of the bank accounts of the sender has: the protection
        against a forged invoice with a new account. Without a known sender or
        accounts there is nothing to compare with.
        """
        if not partner:
            return []
        # sudo(): the sender was found among the contacts the caller may read; their
        # accounts are only compared with, never shown.
        accounts = (
            self.env["res.partner.bank"]
            .sudo()
            .search([("partner_id", "child_of", partner["id"])])
        )
        known = {a.sanitized_acc_number for a in accounts if a.sanitized_acc_number}
        if not known:
            return []
        warnings = []
        for field in self.env["int_filemanager.extraction_field"].search(
            [("active", "=", True), ("value_type", "=", "iban")]
        ):
            best = (suggestions.get(field.id) or [None])[0]
            if best and best.value["value_text"] not in known:
                warnings.append(
                    {
                        "type": "iban_differs",
                        "field_id": field.id,
                        "message": self.env._(
                            "%(field)s: this IBAN is not one of the bank accounts "
                            "of %(partner)s.",
                            field=field.name,
                            partner=partner["name"],
                        ),
                    }
                )
        return warnings

    @api.model
    def request_text(self, node_id):
        """Have the text of a picture read, to find values in it and click on its words.

        Does not wait for the converter: ``suggest_field_values`` answers "pending"
        until the text is there. Return the state of the text.
        """
        node = self.browse(params.require_id(self.env, node_id, "node_id"))
        node.check_access("write")
        revision = node.current_revision_id
        if node.is_dir or not revision or not plan.can_read_text(node.name):
            raise UserError(self.env._("The text of this file cannot be read."))
        # sudo(): the converter queue has no user rights; the write right was checked.
        self.env["int_filemanager.derivative"].sudo()._request_words(
            revision.blob_id.id, node.name
        )
        return {"state": self._recognition_page(node, revision)[0]}

    @api.model
    @api.readonly
    def page_words(self, node_id, revision_id, page_number):
        """Return the words of one page of a file with their places, to click on.

        Each word is ``[x0, top, x1, bottom, start, end]`` in the unit of the value
        boxes, ``start`` and ``end`` the offsets in the text of the file. ``state`` is
        "changed" when the file has a newer revision than ``revision_id``.
        """
        node = self.browse(params.require_id(self.env, node_id, "node_id"))
        node.check_access("read")
        if not isinstance(page_number, int) or isinstance(page_number, bool):
            raise UserError(self.env._("The page is not valid."))
        revision = node.current_revision_id
        if node.is_dir or not revision:
            return {"state": "none", "revision_id": False, "words": []}
        if revision.id != revision_id:
            return {"state": "changed", "revision_id": revision.id, "words": []}
        state, page = self._recognition_page(node, revision)
        if state != "ready":
            return {"state": state, "revision_id": revision.id, "words": []}
        words = [
            [w[1], w[2], w[3], w[4], w[5], w[6]]
            for w in page.words
            if w[0] == page_number
        ]
        return {
            "state": "ready",
            "revision_id": revision.id,
            "words": words[:MAX_PAGE_WORDS],
        }

    def _parse_areas(self, areas):
        """Return the boxes of a request as tuples ``(page, x0, top, x1, bottom)``."""
        areas = areas or []
        if not isinstance(areas, list | tuple) or len(areas) > MAX_AREAS:
            raise UserError(self.env._("There are too many boxes."))
        boxes = []
        for area in areas:
            try:
                page = area["page"]
                x0, top, x1, bottom = (
                    float(area[k]) for k in ("x0", "top", "x1", "bottom")
                )
                valid = (
                    isinstance(page, int)
                    and not isinstance(page, bool)
                    and page >= 1
                    and 0.0 <= x0 < x1 <= 1.0
                    and 0.0 <= top < bottom <= 1.0
                )
            except (KeyError, TypeError, ValueError):
                valid = False
            if not valid:
                raise UserError(self.env._("A box is not valid."))
            boxes.append((page, x0, top, x1, bottom))
        return boxes

    def _recognition_page(self, node, revision):
        """Return ``("ready", Page)`` of the revision's text, or ``(state, None)``."""
        # sudo(): the converter results have no user rights; the caller read the node.
        jobs = (
            self.env["int_filemanager.derivative"]
            .sudo()
            .search(
                [
                    ("source_blob_id", "=", revision.blob_id.id),
                    "|",
                    "&",
                    ("kind", "=", "words"),
                    ("spec", "=", plan.WORDS_SPEC),
                    "&",
                    ("kind", "=", "text"),
                    ("spec", "=", plan.TEXT_SPEC),
                ]
            )
        )
        done = jobs.filtered(lambda j: j.state == "done")
        words_job = done.filtered(lambda j: j.kind == "words" and j.derived_blob_id)[:1]
        if words_job:
            words = self._read_word_list(words_job.derived_blob_id)
            if words is not None:
                return "ready", value_suggest.Page(
                    words["text"], words["words"], words.get("pages")
                )
        text_job = done.filtered(lambda j: j.kind == "text" and j.text)[:1]
        if text_job:
            return "ready", value_suggest.Page(text_job.text)
        if jobs.filtered(lambda j: j.state in ("pending", "running")):
            return "pending", None
        # Not queued yet (the queue runs by cron), but planned for this kind of file.
        planned = {item.kind for item in plan.job_plan(node.name)}
        if not jobs and planned & {"words", "text"}:
            return "pending", None
        return "none", None

    def _read_word_list(self, blob):
        """Return the word list the converter wrote, or None if it cannot be used."""
        path = blobstore.blob_path(self.env, blob.sha256)
        try:
            if os.path.getsize(path) > derivative.MAX_WORDS_BYTES:
                return None
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            _logger.warning(
                "word list %s could not be read", blob.sha256, exc_info=True
            )
            return None
        if not isinstance(data, dict) or data.get("version") != 2:
            return None
        text, words = data.get("text"), data.get("words")
        if not isinstance(text, str) or not isinstance(words, list):
            return None
        # Only well-formed words that point into the text; a broken entry is left
        # out rather than breaking the whole suggestion.
        data["words"] = [
            w
            for w in words
            if isinstance(w, list)
            and len(w) == 7
            and all(isinstance(x, int | float) for x in w)
            and 0 <= w[5] <= w[6] <= len(text)
        ]
        return data

    def _sender(self, node, suggested):
        """Return the contact whose learned labels apply, if the caller may read it.

        The file's contact, else the one suggested.
        """
        partner = node.partner_id.commercial_partner_id
        if not partner and suggested:
            partner = self.env["res.partner"].browse(suggested["id"])
        return partner._filtered_access("read")

    def _extraction_specs(self, sender=None):
        """Return the active fields and rules as the recognition needs them.

        With the labels learned for ``sender``.
        """
        specs = []
        # sudo(): users have no access to the learned labels themselves, the list
        # would show which senders there are documents from, also in scopes they
        # cannot read.
        hints = (
            self.env["int_filemanager.extraction_hint"]
            .sudo()
            .search(
                [("partner_id", "=", sender.id), ("field_id.active", "=", True)]
                if sender
                else [("id", "=", False)]
            )
        )
        for field in hints.field_id:
            specs.append(
                value_suggest.FieldSpec(
                    field.id,
                    field.value_type,
                    unit=field.unit or None,
                    hints={h.label: h.id for h in hints if h.field_id == field},
                    area=_area(field),
                )
            )
        rules = self.env["int_filemanager.extraction_rule"].search(
            [("field_id.active", "=", True)]
        )
        for rule in rules:
            f = rule.field_id
            spec = value_suggest.FieldSpec(
                f.id, f.value_type, unit=f.unit or None, rule_id=rule.id, area=_area(f)
            )
            if rule.mode == "keyword":
                spec.keywords = rule._keyword_list()
            else:
                flags = re.IGNORECASE if rule.ignore_case else 0
                pattern = re.compile(rule.pattern, flags)
                spec.patterns = [(rule.id, pattern, rule.group_index)]
            specs.append(spec)
        return specs

    def _own_company_values(self):
        """Return VAT numbers, bank accounts and mail domains of the own companies."""
        # sudo(): the own companies and their accounts are only compared with, to
        # leave them out of the suggestions; they are never shown.
        partners = (
            self.env["res.company"]
            .sudo()
            .search([("partner_id", "!=", False)])
            .partner_id
        )
        accounts = (
            self.env["res.partner.bank"]
            .sudo()
            .search([("partner_id", "in", partners.ids)])
        )
        domains = set()
        for partner in partners:
            if partner.email and "@" in partner.email:
                domains.add(partner.email.rsplit("@", 1)[1].strip().lower())
            if partner.website:
                domains.add(_website_host(partner.website))
        return {
            "partner_ids": set(partners.commercial_partner_id.ids),
            "vat": {re.sub(r"[^A-Z0-9]", "", p.vat.upper()) for p in partners if p.vat},
            "iban": {
                a.sanitized_acc_number for a in accounts if a.sanitized_acc_number
            },
            "domains": domains - {""},
        }

    @api.model
    def _is_own_value(self, own, value_type, value):
        """Return whether a found value belongs to one of the own companies."""
        text = value.get("value_text") or ""
        if value_type in ("iban", "vat"):
            return text in own[value_type]
        if value_type == "email":
            return text.rsplit("@", 1)[-1] in own["domains"]
        return False

    def _suggest_partner(self, text, own, options):
        """Return the sender as ``{id, name, via}``, or False if none is found.

        Found like account's ``_import_retrieve_customer`` does: VAT number, bank
        account, mail address or its domain, then the name; never an own company, and
        only a contact the caller may read.
        """
        printed = {}

        def values(value_type):
            if value_type not in printed:
                printed[value_type] = sorted(
                    {
                        c.value["value_text"]
                        for c in value_types.find(value_type, text, **options)
                        if not self._is_own_value(own, value_type, c.value)
                    }
                )
            return printed[value_type]

        for find in (
            lambda: self._partner_by_vat(values("vat"), own),
            lambda: self._partner_by_iban(values("iban"), own),
            lambda: self._partner_by_email(values("email"), own),
            lambda: self._partner_by_website(values("email"), own),
            lambda: self._partner_by_name(text, own),
        ):
            if hit := find():
                return hit
        return False

    def _readable_company(self, records, via, own):
        """Return the readable company behind ``records``, or None.

        The answer is ``{id, name, via}``. Access is checked on the company that is
        returned, not on the contact that led to it.
        """
        commercial = records.commercial_partner_id.filtered(
            lambda p: p.id not in own["partner_ids"]
        )
        readable = commercial.with_env(self.env)._filtered_access("read")
        if not readable:
            return None
        partner = readable[0]
        return {"id": partner.id, "name": partner.display_name, "via": via}

    def _partner_by_vat(self, vats, own):
        """Return the sender with one of the VAT numbers."""
        # sudo(): contacts are searched freely; _readable_company() narrows to the
        # ones the caller may read.
        partners = self.env["res.partner"].sudo()
        for vat in vats:
            # Stored with or without the country prefix.
            domain = ["|", ("vat", "=ilike", vat), ("vat", "=ilike", vat[2:])]
            if hit := self._readable_company(
                partners.search(domain, limit=5), "vat", own
            ):
                return hit
        return None

    def _partner_by_iban(self, ibans, own):
        """Return the sender who has one of the bank accounts."""
        if not ibans:
            return None
        # sudo(): see _partner_by_vat.
        accounts = (
            self.env["res.partner.bank"]
            .sudo()
            .search([("sanitized_acc_number", "in", ibans)], limit=5)
        )
        return self._readable_company(accounts.partner_id, "iban", own)

    def _partner_by_email(self, addresses, own):
        """Return the sender with one of the mail addresses."""
        # sudo(): see _partner_by_vat.
        partners = self.env["res.partner"].sudo()
        for address in addresses:
            records = partners.search([("email", "=ilike", address)], limit=5)
            if hit := self._readable_company(records, "email", own):
                return hit
        return None

    def _partner_by_website(self, addresses, own):
        """Return the sender whose website is the domain of one of the addresses.

        A mail provider's domain is nobody's website, so it never matches.
        """
        # sudo(): see _partner_by_vat.
        partners = self.env["res.partner"].sudo()
        for domain in sorted({a.rsplit("@", 1)[1] for a in addresses}):
            records = partners.search([("website", "ilike", domain)], limit=20)
            records = records.filtered(
                lambda p, d=domain: _website_host(p.website) == d
            )
            if hit := self._readable_company(records, "email", own):
                return hit
        return None

    def _partner_by_name(self, text, own):
        """Return the company whose whole name stands in the letterhead.

        The letterhead is the first page; the names are compared in the database
        rather than one by one.
        """
        first_page = text.split("\f", 1)[0][:NAME_SEARCH_CHARS]
        tokens = [t.strip(",;:()").lower() for t in first_page.split()]
        phrases = {
            " ".join(tokens[i : i + n])
            for n in range(1, 7)
            for i in range(len(tokens) - n + 1)
        }
        phrases = [p for p in phrases if len(p) >= 5]
        if not phrases:
            return None
        partner = self.env["res.partner"]
        rows = self.env.execute_query(
            SQL(
                """
                SELECT id FROM res_partner
                WHERE active AND is_company AND length(name) >= 5
                  AND lower(regexp_replace(name, '[[:space:]]+', ' ', 'g')) IN (
                      SELECT unnest(%s::text[])
                  )
                ORDER BY length(name) DESC
                LIMIT 20
                """,
                phrases,
                to_flush=[partner._fields[n] for n in ("active", "is_company", "name")],
            )
        )
        # sudo(): see _partner_by_vat.
        found = partner.sudo().browse([row[0] for row in rows])
        return self._readable_company(found, "name", own)

    def _suggest_tags(self, text):
        """Return the tags whose name stands in the text as a whole word or phrase."""
        words = re.findall(r"\w+", text.lower())
        single, joined = set(words), f" {' '.join(words)} "
        result = []
        for tag in self.env["int_filemanager.tag"].search_fetch(
            [("name", "!=", False)], ["name"]
        ):
            parts = re.findall(r"\w+", tag.name.lower())
            if not parts:
                continue
            if (
                parts[0] in single
                if len(parts) == 1
                else f" {' '.join(parts)} " in joined
            ):
                result.append({"id": tag.id, "name": tag.name})
                if len(result) == MAX_SUGGESTED_TAGS:
                    break
        return result

    @api.model
    def _json_value(self, value, codes):
        """Return a value of ``value_types`` as JSON, the currency as a record id."""
        result = {}
        for key, item in value.items():
            if key == "currency_code":
                result["currency_id"] = codes.get(item, False)
            elif hasattr(item, "isoformat"):
                result[key] = item.isoformat()
            else:
                result[key] = item
        return result

    @api.model
    def _json_suggestion(self, suggestion, codes):
        """Return a suggestion as JSON."""
        return {**suggestion, "value": self._json_value(suggestion["value"], codes)}

    @api.model
    @api.readonly
    def read_selection(self, node_id, revision_id, field_id, start, end):
        """Read the marked text of a file as a value of a field; store nothing.

        ``start`` and ``end`` are offsets in the text of the file, widened to whole
        words. ``state`` is "changed" if there is a newer revision than ``revision_id``;
        ``suggestion`` is False, with a ``message``, if the text is no value of it.
        """
        node = self.browse(params.require_id(self.env, node_id, "node_id"))
        node.check_access("read")
        field = self.env["int_filemanager.extraction_field"].browse(
            params.require_id(self.env, field_id, "field_id")
        )
        if not field.exists():
            raise UserError(self.env._("This field does not exist any more."))
        revision = node.current_revision_id
        if node.is_dir or not revision:
            return {"state": "none", "revision_id": False}
        if revision.id != revision_id:
            return {"state": "changed", "revision_id": revision.id}
        state, page = self._recognition_page(node, revision)
        if state != "ready":
            return {"state": state, "revision_id": revision.id}
        start, end, text = self._marked_text(page, start, end)
        result = {"state": "ready", "revision_id": revision.id}
        shared = self._recognition_shared(with_own=False)
        try:
            parsed = self._parse_confirmed(field, text, shared["options"])
        except UserError:
            labels = dict(field._fields["value_type"]._description_selection(self.env))
            message = self.env._(
                "%(text)s cannot be read as: %(type)s.",
                text=text,
                type=labels[field.value_type],
            )
            return {**result, "suggestion": False, "message": message}
        suggestion = self._selection_suggestion(page, start, end, text, parsed)
        return {
            **result,
            "suggestion": self._json_suggestion(suggestion, shared["codes"]),
        }

    def _selection_suggestion(self, page, start, end, text, parsed):
        """Return the marked text as a suggestion of the direction "selection"."""
        box = dict(
            zip(
                ("page", "x0", "top", "x1", "bottom"),
                page.box(start, end) or (0, 0.0, 0.0, 0.0, 0.0),
                strict=True,
            )
        )
        return {
            "value": parsed,
            "source_text": text,
            "start": start,
            "end": end,
            **box,
            "label": "",
            "direction": "selection",
            "tier": None,
            "rule_id": None,
            "hint_id": None,
            "in_area": False,
        }

    def _marked_text(self, page, start, end):
        """Return ``(start, end, text)`` of a marking, widened to whole words."""
        if not (
            isinstance(start, int)
            and isinstance(end, int)
            and 0 <= start < end <= len(page.text)
            # Blanks are squeezed below, so the range may be longer than the text.
            and end - start <= 4 * MAX_SELECTION_CHARS
        ):
            raise UserError(self.env._("The marking is not valid."))
        start, end = _whole_words(page.text, start, end)
        marked = page.text[start:end]
        text = " ".join(marked.split())
        # Not over a page break: the place of the value would belong to no page.
        if not text or len(text) > MAX_SELECTION_CHARS or "\f" in marked:
            raise UserError(self.env._("The marking is not valid."))
        return start, end, text

    @api.model
    def apply_field_values(
        self, node_id, revision_id, values, partner_id=False, tag_ids=None
    ):
        """Store the confirmed values of the extraction fields on a file.

        Nothing is stored if the file has a newer revision than ``revision_id``.
        ``values`` is ``[{"field_id", "text", "source", "rule_id", "start"}]``; an empty
        ``text`` removes the value, ``source`` is "rule" or "manual". Every text is read
        again with the field's type. Return ``{field_id: value_text}`` as stored.
        """
        node = self.browse(params.require_id(self.env, node_id, "node_id"))
        node.check_access("write")
        revision_id = params.optional_id(self.env, revision_id, "revision_id")
        items = self._clean_values(values)
        partner_id = params.optional_id(self.env, partner_id, "partner_id")
        tags = self.env["int_filemanager.tag"].browse(
            params.require_ids(self.env, tag_ids or [], "tag_ids", MAX_CONFIRMED_TAGS)
        )
        # Under the node's lock, like a new revision: a revision stored meanwhile by
        # another request makes these values stale.
        self._lock_and_check_base_revision(node, revision_id)
        if partner_id:
            self.env["res.partner"].browse(partner_id).check_access("read")
        tags.check_access("read")

        existing, stored, removed, learn = self._store_values(node, revision_id, items)

        if partner_id and node.partner_id.id != partner_id:
            node.partner_id = partner_id
        if tags:
            node.tag_ids = [Command.link(tag.id) for tag in tags]
        self._learn_labels(node.partner_id, learn)
        # sudo(): the review state is server-only; the write right was checked.
        node.sudo().review_state = "reviewed"
        if stored or removed:
            self._post_confirmed_values(node, stored, removed)
        return {v.field_id.id: v.value_text for v in existing.values()}

    def _store_values(self, node, revision_id, items):
        """Write the checked ``items`` as the values of ``node``.

        Return ``(existing, stored, removed, learn)``: the values of the node by field
        id, the ``(field, text)`` stored, the fields cleared, and the labels to learn.
        """
        options = self._recognition_shared(with_own=False)["options"]
        _state, page = self._recognition_page(node, node.current_revision_id)
        # sudo(): users have no right on the stored values; the write right on the
        # node was checked by the caller.
        existing = {v.field_id.id: v for v in node.sudo().field_value_ids}
        stored, removed, learn = [], [], []
        for item in items:
            field = item["field"]
            if not item["text"]:
                if field.id in existing:
                    existing.pop(field.id).unlink()
                    removed.append(field)
                continue
            parsed = self._parse_confirmed(field, item["text"], options)
            vals, label, label_box = self._value_vals(
                node, revision_id, field, item, parsed, page, options
            )
            if field.id in existing:
                existing[field.id].write(vals)
            else:
                existing[field.id] = (
                    self.env["int_filemanager.field_value"].sudo().create(vals)
                )
            stored.append((field, parsed["value_text"]))
            if label:
                learn.append((field, label, label_box))
        return existing, stored, removed, learn

    def _clean_values(self, values):
        """Return the confirmed values of a request, checked, as a list of dicts."""
        if not isinstance(values, list | tuple) or len(values) > MAX_CONFIRMED_VALUES:
            raise UserError(self.env._("%(argument)s is not valid.", argument="values"))
        Field = self.env["int_filemanager.extraction_field"]
        Rule = self.env["int_filemanager.extraction_rule"]
        items = []
        for item in values:
            if not isinstance(item, dict):
                raise UserError(
                    self.env._("%(argument)s is not valid.", argument="values")
                )
            field = Field.browse(
                params.require_id(self.env, item.get("field_id"), "field_id")
            )
            if not field.exists():
                raise UserError(self.env._("This field does not exist any more."))
            text = params.require_text(self.env, item.get("text") or "", "text")
            from_rule = item.get("source") == "rule"
            rule_id = params.optional_id(self.env, item.get("rule_id"), "rule_id")
            # A rule that was deleted since the suggestion is just no longer named.
            rule = Rule.browse(rule_id).exists() if from_rule and rule_id else Rule
            items.append(
                {
                    "field": field,
                    "text": text.strip(),
                    "from_rule": from_rule,
                    "rule_id": rule.id,
                    "start": item.get("start"),
                }
            )
        return items

    def _value_vals(self, node, revision_id, field, item, parsed, page, options):
        """Return ``(vals, label, label_box)`` for storing one confirmed value.

        ``label`` is the printed label that named the value, to be learned.
        """
        vals = {
            "node_id": node.id,
            "field_id": field.id,
            "revision_id": revision_id,
            "source": "rule" if item["from_rule"] else "manual",
            "rule_id": (item["from_rule"] and item["rule_id"]) or False,
            "source_text": item["text"],
            "value_text": parsed["value_text"],
            "value_date": parsed.get("value_date") or False,
            "value_date_to": parsed.get("value_date_to") or False,
            "value_number": parsed.get("value_number") or 0.0,
            "currency_id": self._currency_id(parsed.get("currency_code")),
            "unit": parsed.get("unit") or False,
            "page": 0,
            "x0": 0.0,
            "top": 0.0,
            "x1": 0.0,
            "bottom": 0.0,
        }
        if not page:
            return vals, None, None
        label, printed = value_suggest.label_of_value(
            page,
            field.value_type,
            parsed["value_text"],
            near=item["start"],
            unit=field.unit or None,
            **options,
        )
        box = printed and page.box(printed.start, printed.end)
        if box:
            vals.update(zip(("page", "x0", "top", "x1", "bottom"), box, strict=False))
        return vals, label, label and page.box(label.start, label.end)

    def _parse_confirmed(self, field, text, options):
        """Return the value of a confirmed text, read with the field's type.

        A number typed without its unit or currency is read with the field's.
        Raise a ``UserError`` if the text is no value of the field.
        """
        unit = field.unit or None
        if field.value_type == "amount" and field.currency_id:
            options = {**options, "default_currency": field.currency_id.name}
        attempts = [text]
        if field.value_type == "quantity":
            attempts.append(f"{text} {field.unit}")
        elif field.value_type == "amount":
            code = field.currency_id.name or options["default_currency"]
            attempts.append(f"{text} {code}")
        for attempt in attempts:
            parsed = value_types.parse(field.value_type, attempt, unit=unit, **options)
            if parsed:
                return parsed
        raise UserError(
            self.env._(
                "%(field)s: %(text)s cannot be read as a value of this field.",
                field=field.name,
                text=text,
            )
        )

    def _currency_id(self, code):
        """Return the id of the currency with this ISO code, or False."""
        if not code:
            return False
        # sudo(): currencies are no data of the caller.
        return (
            self.env["res.currency"]
            .sudo()
            .with_context(active_test=False)
            .search([("name", "=", code)], limit=1)
            .id
        )

    def _learn_labels(self, partner, learned):
        """Remember for the sender which label named which field; the last one wins."""
        own = self._own_company_values()["partner_ids"]
        partner = partner.commercial_partner_id
        if not partner or partner.id in own:
            return
        # sudo(): users have no right on the learned labels (see _extraction_specs).
        Hint = self.env["int_filemanager.extraction_hint"].sudo()
        for field, label, box in learned:
            norm = value_suggest.normalize(label.text)
            if not norm:
                continue
            vals = {
                "field_id": field.id,
                "direction": label.direction,
                "page": box[0] if box else 0,
                "x0": box[1] if box else 0.0,
                "top": box[2] if box else 0.0,
                "last_date": fields.Datetime.now(),
            }
            hint = Hint.search(
                [("partner_id", "=", partner.id), ("label", "=", norm)], limit=1
            )
            if hint:
                vals["hit_count"] = hint.hit_count + 1 if hint.field_id == field else 1
                hint.write(vals)
            else:
                Hint.create({**vals, "partner_id": partner.id, "label": norm})

    def _post_confirmed_values(self, node, stored, removed):
        """Leave a note on the file: who confirmed which values, for later questions."""
        lines = [Markup("<li>%s: %s</li>") % (f.name, text) for f, text in stored]
        lines += [
            Markup("<li>%s: %s</li>") % (f.name, self.env._("removed")) for f in removed
        ]
        node.message_post(
            body=Markup("<p>%s</p><ul>%s</ul>")
            % (self.env._("Values confirmed"), Markup("").join(lines)),
            subtype_xmlid="mail.mt_note",
        )
