import json

CONFIG_KEY = "int_legacy_erp_import.artikel_rename_snapshot"
RENAMES = {"Produkt": "Artikel", "Produkte": "Artikel"}

# Field-label/menu/action renames: exact-value matches only, no substring
# replacement, so compounds like "Produktion" stay untouched.
RENAME_MODELS = [
    ("ir.model.fields", "field_description"),
    ("ir.ui.menu", "name"),
    ("ir.actions.act_window", "name"),
]

# A handful of static view labels (e.g. the small "Produkt" caption above the
# product name field) are baked into the view's arch instead of a field/menu
# record, so they need a scoped, exact substring replacement per view.
ARCH_LABEL_VIEWS = [
    ("product.product_template_form_view", 'string="Produkt"', 'string="Artikel"'),
]


def post_init_hook(env):
    """Rename 'Produkt(e)' to 'Artikel' throughout the German UI (field
    labels, menu names, window-action/breadcrumb names, and a few static
    view labels). Snapshots the originals so uninstall can restore them."""
    env_de = env(context=dict(env.context, lang="de_DE"))
    existing_raw = env["ir.config_parameter"].sudo().get_param(CONFIG_KEY)
    snapshot = json.loads(existing_raw) if existing_raw else []

    for model, field in RENAME_MODELS:
        records = env_de[model].search([(field, "in", list(RENAMES))])
        for rec in records:
            old_value = rec[field]
            snapshot.append({"type": "value", "model": model, "id": rec.id, "field": field, "old": old_value})
            rec.write({field: RENAMES[old_value]})

    for xml_id, old_snippet, new_snippet in ARCH_LABEL_VIEWS:
        view = env.ref(xml_id, raise_if_not_found=False)
        if not view:
            continue
        view_de = view.with_context(lang="de_DE")
        old_arch = view_de.arch_db
        if old_snippet in old_arch:
            snapshot.append({"type": "arch", "model": "ir.ui.view", "id": view.id, "old": old_arch})
            view_de.write({"arch_db": old_arch.replace(old_snippet, new_snippet)})

    env["ir.config_parameter"].sudo().set_param(CONFIG_KEY, json.dumps(snapshot))


def uninstall_hook(env):
    """Restore the original 'Produkt(e)' labels saved by post_init_hook."""
    raw = env["ir.config_parameter"].sudo().get_param(CONFIG_KEY)
    if not raw:
        return
    snapshot = json.loads(raw)
    env_de = env(context=dict(env.context, lang="de_DE"))

    for entry in snapshot:
        rec = env_de[entry["model"]].browse(entry["id"])
        if not rec.exists():
            continue
        if entry["type"] == "arch":
            rec.write({"arch_db": entry["old"]})
        else:
            rec.write({entry["field"]: entry["old"]})

    env["ir.config_parameter"].sudo().search([("key", "=", CONFIG_KEY)]).unlink()
