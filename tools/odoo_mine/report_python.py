import json, sys
sp = sys.argv[1]
D = {k: json.load(open(f"{sp}/{k}.json")) for k in ("core", "ours_all", "ours_new")}
def g(d, k): return d.get(k, 0)
def pct(d, a, b):
    den = g(d, b)
    return "n/a" if not den else f"{100*g(d,a)/den:5.1f}%"
def row(title, a, b):
    print(f"{title:70s}" + "".join(f" {pct(D[k], a, b):>8s}" for k in D) + "   " + "".join(f"({g(D[k],a)}/{g(D[k],b)}) " for k in D))
print(f"{'':70s} {'core':>8s} {'ours_all':>8s} {'ours_new':>8s}")
for k, d in D.items():
    print(k, "modules", g(d,"modules"), "py_files", g(d,"py_files"), "models", g(d,"model_classes"), "fields", g(d,"field_total"), "methods", g(d,"method_total"), "js", g(d,"js_files"), "xml", g(d,"xml_files"), "tests", g(d,"test_files"))
print("== Modelle")
row("Datei heißt wie das Modell (Modell mit _name, in models/)", "file_named_after_model", "model_with__name")
row("Erweiterung: Datei heißt wie das erweiterte Modell", "extension_file_named_after_inherited", "model_extension")
row("Datei mit mehreren Modellen", "file_with_multiple_models", "files_with_models")
row("_description gesetzt (Modelle mit _name)", "model_has__description", "model_with__name")
row("Reihenfolge: private Attribute zuerst", "order_private_attrs_first", "order_classes")
row("Reihenfolge: Felder vor Methoden", "order_fields_before_methods", "order_classes")
row("Reihenfolge streng nach Leitfaden (monoton)", "order_monotonic", "order_classes")
row("Reihenfolge: CRUD vor action_", "order_crud_before_actions", "order_classes")
print("== Felder")
row("Many2one heißt *_id", "m2o_name_endswith__id", "m2o_total")
row("x2many heißt *_ids", "x2m_name_endswith__ids", "x2m_total")
row("string= gesetzt", "field_with_string", "field_total")
row("string= überflüssig (gleich Standard) von allen string=", "field_string_redundant", "field_with_string")
row("Many2one mit ondelete=", "m2o_has_ondelete", "m2o_total")
row("Many2one mit index=", "m2o_has_index", "m2o_total")
row("Feld mit help=", "field_kw_help", "field_total")
row("Feld mit groups=", "field_kw_groups", "field_total")
row("Feld mit copy=", "field_kw_copy", "field_total")
row("berechnet und gespeichert (von allen berechneten)", "computed_stored", "field_kw_compute")
row("berechnet, compute_sudo gesetzt (von berechneten)", "computed_with_compute_sudo", "field_kw_compute")
row("compute-Name beginnt mit _compute_", "compute_name_pattern_ok", "field_kw_compute")
row("default als lambda (von default-Feldern)", "default_lambda", "field_kw_default")
print("== Constraints")
for k in ("sql_constraints_old_style","constraint_new_style_Constraint","constraint_new_style_UniqueIndex","constraint_new_style_Index","constraint_attr_without_underscore","deco_constrains","deco_onchange","deco_depends","deco_depends_context","deco_model","deco_model_create_multi","deco_private","deco_readonly","deco_autovacuum","deco_ondelete"):
    print(f"{k:60s}" + "".join(f" {g(D[x],k):8d}" for x in D))
print("== Methoden")
row("öffentliche Methoden (von allen)", "method_public", "method_total")
row("öffentliche Methoden mit @api.private", "method_public_api_private", "method_public")
row("öffentliche Methoden mit @api.model", "method_public_api_model", "method_public")
row("Methoden mit Docstring (alle)", "method_with_docstring", "method_total")
row("öffentliche Methoden mit Docstring", "public_method_with_docstring", "method_public")
print(f"{'Docstring Zeilen: Median / Mittel / P90':70s}" + "".join(f" {D[k].get('median_docstring_lines')}/{D[k].get('mean_docstring_lines')}/{D[k].get('p90_docstring_lines')}" for k in D))
row("öffentliche Methoden mit Parameter ids/context", "method_param_ids_or_context", "method_public")
row("create-Überschreibung mit @model_create_multi", "create_override_model_create_multi", "deco_model_create_multi")
row("action_-Methoden mit ensure_one", "action_method_ensure_one", "action_method")
row("unlink-Überschreibung mit raise", "unlink_override_with_raise", "unlink_override")
print("== Aufrufe (je 1000 Methoden)")
for k in ("call_sudo","call_with_context","call_with_user","call_filtered","call_mapped","call_ensure_one","call_search","call_search_count","call_search_fetch","call__read_group","call_read_group","call_formatted_read_group","call_flush_model","call_flush_all","call_invalidate_model","call_invalidate_all","call_invalidate_recordset","call_execute_query","cr_execute_SQL","cr_execute_plain","cr_execute_formatted_string","call_cr_commit","call_cr_rollback","call_savepoint","call_check_access","call_has_access","call__commit_progress","call_try_lock_for_update","call_message_post","call_get_param","call_safe_eval","call_literal_eval","call_eval","call_exec","call_getattr","call_setattr","call_print","call_Markup","call_html_escape","search_all_no_limit","gettext__func","gettext_env_underscore","error_static_string_without_gettext","raise_UserError","raise_ValidationError","raise_AccessError","except_Exception","except_bare","except_specific","except_pass","import_Domain","import_SQL","import_from_odoo.orm","getLogger","logger_named__logger","logger_getLogger___name__"):
    vals = []
    for x in D:
        m = max(1, g(D[x], "method_total"))
        vals.append(f"{g(D[x],k):7d} ({1000*g(D[x],k)/m:6.1f})")
    print(f"{k:42s}" + " ".join(vals))
print("== Kommentare/Stil")
for x in D:
    d = D[x]; print(x, "Kommentarzeilen je 100 Zeilen:", round(100*g(d,"py_comment_lines")/max(1,g(d,"py_lines_total")),1), "Zeilen>120:", round(100*g(d,"py_lines_over_120")/max(1,g(d,"py_lines_total")),2), "%", "TODO:", g(d,"py_todo_fixme"), "auskommentierter Code (Dateien):", g(d,"files_with_commented_out_code"), "von", g(d,"py_files"), "median Dateigröße", d.get("median_py_lines"))
print("== Nicht dem Muster folgende Dateinamen (Core, Beispiele):", D["core"].get("file_not_named_examples"))
