import json, sys
sp = sys.argv[1]
D = {k: json.load(open(f"{sp}/{k}.json")) for k in ("core", "ours_all", "ours_new")}
def g(d, k): return d.get(k, 0)
def pct(d, a, b):
    den = g(d, b); return "   n/a" if not den else f"{100*g(d,a)/den:5.1f}%"
def row(t, a, b):
    print(f"{t:66s}" + "".join(f" {pct(D[k], a, b):>7s}" for k in D) + "  " + " ".join(f"({g(D[k],a)}/{g(D[k],b)})" for k in D))
def raw(t, ks):
    print(f"{t:66s}" + "".join(f" {sum(g(D[x],k) for k in ks):7d}" for x in D))
print("== Manifest")
row("depends enthält base", "manifest_depends_has_base", "manifests")
row("installable gesetzt", "manifest_installable_True", "manifests")
raw("installable False", ["manifest_installable_False"])
row("application True", "manifest_application_true", "manifests")
row("Modul hat tests/", "manifest_has_module_dirs_tests", "manifests")
for k in sorted(k for k in D["core"] if k.startswith("manifest_key_")):
    print(f"  {k[13:]:30s}" + "".join(f" {pct(D[x],k,'manifests'):>7s}" for x in D))
for k in sorted(k for k in D["core"] if k.startswith("manifest_license_") or k.startswith("manifest_version_pattern_") or k.startswith("manifest_author_")):
    print(f"  {k[9:]:40s}" + "".join(f" {g(D[x],k):6d}" for x in D))
print("== Views / XML")
row("View-ID folgt <modell>_view_<typ>", "view_id_follows_model_view_type", "view_records")
raw("view_records", ["view_records"]); raw("<tree> Tags", ["tag_tree"]); raw("<list> Tags", ["tag_list"]); raw("attrs=", ["attr_attrs"]); raw("states=", ["attr_states"]); raw("invisible=", ["attr_invisible_expr"])
raw("t-raw (Server-XML)", ["t_raw"]); raw("t-esc (Server-XML)", ["t_esc"]); raw("t-out (Server-XML)", ["t_out"])
raw("position=replace", ["position_replace"]); raw("position=attributes", ["position_attributes"]); raw("position=inside", ["position_inside"]); raw("position=after", ["position_after"]); raw("position=before", ["position_before"])
row("replace mit Kommentar in der Nähe", "replace_with_comment_nearby", "position_replace")
row("Aktions-ID endet _action", "action_id_suffix__action", "window_action_records")
raw("Aktions-ID beginnt action_", ["action_id_prefix_action_"]); raw("Aktions-ID anders", ["action_id_other"])
raw("Regeln mit rule im Namen", ["rule_id_with__rule_"]); raw("Regeln anderer Name", ["rule_id_other"]); raw("ir.rule Records", ["xml_ir_rule_records"])
raw("<data> Tags", ["xml_data_tag"]); raw("<odoo> Wurzeln", ["xml_odoo_root"]); raw("noupdate=1", ["xml_noupdate"]); raw("menuitem", ["xml_menuitem"]); raw("ir.ui.menu Records", ["xml_record_menu"]); raw("ir.cron Records", ["xml_ir_cron_records"])
raw("Dateien Einrückung 4", ["xml_indent_4_files"]); raw("Dateien Einrückung 2", ["xml_indent_2_files"])
print("== Rechte (ir.model.access.csv)")
row("ACL-ID beginnt access_", "acl_id_starts_access_", "acl_rows")
row("ACL ohne Gruppe (jeder)", "acl_group_empty", "acl_rows")
for k in sorted(k for k in D["core"] if k.startswith("acl_perm_")):
    print(f"  {k:30s}" + "".join(f" {pct(D[x],k,'acl_rows'):>7s}" for x in D))
print("== JavaScript")
raw("js_files", ["js_files"])
row("Datei mit @odoo-module Kopf", "js_header_odoo_module", "js_files")
for k, tot in (("js_component_static_template", "js_component_classes"), ("js_component_static_props", "js_component_classes"), ("js_component_setup", "js_component_classes"), ("js_component_constructor", "js_component_classes")):
    row(k, k, tot)
raw("Komponenten", ["js_component_classes"])
raw("setTimeout bare", ["js_setTimeout_bare"]); raw("browser.setTimeout", ["js_browser_setTimeout"])
raw("fetch bare", ["js_fetch_bare"]); raw("browser.fetch", ["js_browser_fetch"])
raw("localStorage bare", ["js_localStorage_bare"]); raw("browser.localStorage", ["js_browser_localStorage"])
raw("window.open", ["js_window_open_bare"]); raw("document. direkt", ["js_document_direct"]); raw("window. direkt", ["js_window_direct"])
raw("useService(", ["js_useService"]); raw("orm.*(", ["js_orm_call"]); raw("rpc(", ["js_rpc_calls"]); raw("patch(", ["js_patch_calls"]); raw("_t(", ["js_t_func"])
raw("?. optional chaining", ["js_optional_chaining"]); raw("?? nullish", ["js_nullish"]); raw("console.log", ["js_console_log"])
raw("throw new Error", ["js_throw_new_Error"]); raw("throw other", ["js_throw_other"]); raw("var Deklarationen", ["js_var_decl"]); raw("odoo.define", ["js_odoo_define"])
raw("addEventListener bare", ["js_addEventListener_bare"]); raw("useExternalListener", ["js_useExternalListener"]); raw("useBus", ["js_useBus"]); raw("useEffect", ["js_useEffect"]); raw("onWillStart", ["js_onWillStart"])
print(f"{'JS Zeilen Median/P90':66s}" + "".join(f" {D[k].get('median_js_lines')}/{D[k].get('p90_js_lines')}" for k in D))
raw("Owl-Templates t-esc", ["owl_xml_t_esc"]); raw("Owl-Templates t-out", ["owl_xml_t_out"]); raw("Owl-Templates t-raw", ["owl_xml_t_raw"])
print("== SCSS")
raw("scss_files", ["scss_files"]); raw("ID-Selektoren", ["scss_id_selectors"]); raw(":root", ["scss_root_selector"]); raw("!important", ["scss_important"]); raw("globale $o- Variablen", ["scss_global_vars_o"]); raw("andere $-Variablen", ["scss_global_vars_other"]); raw("Klassen .o_", ["scss_class_o_prefix"]); raw("Klassen ohne o_", ["scss_class_other"])
print("== Tests")
raw("test_files", ["test_files"]); raw("test_methods", ["test_methods"])
row("Testdateien mit @tagged", "test_files_with_tagged", "test_files")
for b in ("TransactionCase", "HttpCase", "SingleTransactionCase", "BaseCase", "SavepointCase"):
    raw("Basis " + b, ["test_base_" + b])
raw("new_test_user", ["test_new_test_user"]); raw("res.users create", ["test_res_users_create"]); raw("freeze_time", ["test_freeze_time"]); raw("Form(", ["test_Form"]); raw("assertQueryCount", ["test_assertQueryCount"]); raw("subTest", ["test_subTest"]); raw("mock patch", ["test_mock_patch"]); raw("start_tour", ["test_start_tour"]); raw("setUpClass", ["test_setUpClass"]); raw("setUp", ["test_setUp"])
