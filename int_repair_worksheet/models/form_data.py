"""Small, framework-independent parser for the explicit worksheet fields."""
from datetime import date


class FormError(ValueError):
    pass


def text(form, key, limit=250):
    value = form.get(key, "")
    if not isinstance(value, str):
        raise FormError("Ungültiger Feldwert: " + key)
    value = value.strip()
    if len(value) > limit:
        raise FormError("Eingabe zu lang: " + key)
    return value


def parse_form(form, plan):
    variant = text(form, "variant")
    if variant not in ("br185", "atc"):
        raise FormError("Bitte ATC oder BR185.2 auswählen.")
    inspection_date = text(form, "inspection_date")
    if inspection_date:
        try:
            inspection_date = date.fromisoformat(inspection_date)
        except ValueError as exc:
            raise FormError("Bitte ein gültiges Prüfdatum eingeben.") from exc
    entries = {}
    for item in plan:
        code = item["code"]
        result = text(form, "result_" + code)
        if result not in ("", "pass", "fail", "na"):
            raise FormError("Ungültiges Prüfergebnis: " + item["name"])
        performed = form.get("performed_" + code, "") == "1"
        if item["br_only"] and variant == "atc":
            result, performed = "na", False
        if result == "na":
            performed = False
        entries[code] = {
            "result": result, "performed": performed,
            "operator": text(form, "operator_" + code, 80),
            "hm": text(form, "hm_" + code, 80),
        }
    try:
        count = int(text(form, "material_count") or "0")
    except ValueError as exc:
        raise FormError("Ungültige Anzahl Materialzeilen.") from exc
    if not 0 <= count <= 200:
        raise FormError("Maximal 200 Materialzeilen sind möglich.")
    materials = []
    for index in range(count):
        material = {key: text(form, f"material_{key}_{index}", 500 if key == "description" else 150)
                    for key in ("description", "old", "new")}
        if any(material.values()):
            if not material["description"]:
                raise FormError(f"Materialzeile {index + 1}: Bitte eine Beschreibung ergänzen.")
            materials.append(material)
    return {
        "variant": variant, "serial_number": text(form, "serial_number"),
        "rb_reference": text(form, "rb_reference"),
        "inspection_date": inspection_date or False, "inspector": text(form, "inspector", 80),
        "notes": text(form, "notes", 10000), "entry_data": entries, "material_data": materials,
    }
