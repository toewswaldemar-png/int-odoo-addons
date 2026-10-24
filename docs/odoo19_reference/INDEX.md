# Index – Odoo 19.0 Developer Reference (lokale Kopie)

Abgerufen 2026-10-02. Pro Zeile: Datei · Zeilenzahl · Titel · Abschnitte (H2). Zuerst hier die passende Datei suchen, dann nur diese Datei lesen.

**Hinweis:** Das ist der Volltext zum Nachschlagen. Maßgeblich ist die offizielle Dokumentation; Hinweise zur Prüfung stehen in `CLAUDE.md`.


## backend

- `backend/actions.md` (652) – **Actions** – Bindings; Window Actions (`ir.actions.act_window`); URL Actions (`ir.actions.act_url`); Server Actions (`ir.actions.server`); Report Actions (`ir.actions.report`); Client Actions (`ir.actions.client`); Scheduled Actions (`ir.cron`)
- `backend/data.md` (402) – **Data Files** – Structure; Core operations; Shortcuts; CSV data files
- `backend/http.md` (361) – **Web Controllers** – Controllers; API
- `backend/mixins.md` (1156) – **Mixins and Useful Classes** – Messaging features; Website features; Others
- `backend/module.md` (186) – **Module Manifests** – Manifest
- `backend/orm/01_models.md` (280) – **ORM API – Teil 1/6: Models** – Models
- `backend/orm/02_fields.md` (1175) – **ORM API – Teil 2/6: Fields** – Fields
- `backend/orm/03_constraints_and_indexes__method_decorators.md` (387) – **ORM API – Teil 3/6: Constraints and indexes / Recordsets / Method decorators** – Constraints and indexes; Recordsets; Method decorators
- `backend/orm/04_environment.md` (445) – **ORM API – Teil 4/6: Environment** – Environment
- `backend/orm/05_common_orm_methods.md` (787) – **ORM API – Teil 5/6: Common ORM methods** – Common ORM methods
- `backend/orm/06_inheritance_and_extension__error_management.md` (293) – **ORM API – Teil 6/6: Inheritance and extension / Error management** – Inheritance and extension; Error management
- `backend/orm_changelog.md` (145) – **Changelog** – Odoo version 19.0; Odoo Online version 18.4; Odoo Online version 18.3; Odoo Online version 18.2; Odoo Online version 18.1; Odoo version 18.0; Odoo Online version 17.4; Odoo Online version 17.3; Odoo Online version 17.2; Odoo Online version 17.1; Odoo version 17.0; Odoo Online version 16.4; Odoo Online version 16.3; Odoo Online version 16.2; Odoo version 16.0; Odoo Online version 15.4; Odoo Online version 15.3; Odoo Online version 15.2
- `backend/performance.md` (405) – **Performance** – Profiling; Good practices
- `backend/reports.md` (347) – **QWeb Reports** – Report template; Paper Format; Custom Reports; Custom fonts; Reports are web pages
- `backend/security.md` (597) – **Security in Odoo** – Access Rights; Record Rules; Field Access; Security Pitfalls
- `backend/testing.md` (1074) – **Testing Odoo** – Testing Python code; Testing JS code; Integration Testing; Performance Testing

## frontend

- `frontend/assets.md` (360) – **Assets** – Asset types; Bundles; Lazy loading; The asset model (`ir.asset`)
- `frontend/error_handling.md` (565) – **Error handling** – Errors in JavaScript; Lifecycle of errors within the Odoo JS framework; Avoid throwing errors as much as possible; Catching errors; Error free control flow; When to throw errors
- `frontend/framework_overview.md` (657) – **Framework Overview** – Introduction; Code structure; WebClient Architecture; Environment; Building Blocks; Context; Python Interpreter; Domains; Bus; Browser Object; Debug mode; Tooltips
- `frontend/hooks.md` (286) – **Hooks** – useAssets; useAutofocus; useBus; usePager; usePosition; useSpellCheck
- `frontend/javascript_modules.md` (345) – **Javascript Modules** – Plain Javascript files; Native Javascript Modules; Odoo Module System
- `frontend/javascript_reference.md` (1416) – **Javascript Reference** – Overview; Web client; Loading Javascript Code; Registries; Services; Notifications; Systray; Translation management; Session; Views; Fields; Client actions
- `frontend/mobile.md` (214) – **Mobile JavaScript** – Introduction; How does it work?; How to use it?
- `frontend/odoo_editor.md` (167) – **Odoo Editor** – Powerbox
- `frontend/owl_components.md` (875) – **Owl components** – Using Owl components; Best practices; Reference List
- `frontend/patching_code.md` (256) – **Patching code** – Description; Patching a simple object; Patching a javascript class; Patching a component; Removing a patch; Applying the same patch to multiple objects
- `frontend/qweb.md` (858) – **QWeb Templates** – Data output; Conditionals; Loops; attributes; setting variables; calling sub-templates; Advanced Output; Python; Javascript
- `frontend/registries.md` (298) – **Registries** – Registry API; Reference List
- `frontend/services.md` (770) – **Services** – Defining a service; Using a service; Reference List
- `frontend/unit_testing.md` (76) – **JavaScript Unit Testing** – Testing Framework; Setup; Writing tests
- `frontend/unit_testing/hoot/01_overview__writing_tests.md` (183) – **HOOT – Teil 1/5: Overview / Running tests / Writing tests** – Overview; Running tests; Writing tests
- `frontend/unit_testing/hoot/02_expect.md` (664) – **HOOT – Teil 2/5: Expect** – Expect
- `frontend/unit_testing/hoot/03_dom_queries.md` (212) – **HOOT – Teil 3/5: DOM: queries** – DOM: queries
- `frontend/unit_testing/hoot/04_dom_interaction_helpers.md` (407) – **HOOT – Teil 4/5: DOM: interaction helpers** – DOM: interaction helpers
- `frontend/unit_testing/hoot/05_mocks.md` (262) – **HOOT – Teil 5/5: Mocks** – Mocks
- `frontend/unit_testing/mock_server.md` (361) – **Mock server** – Rationale; Overview; Configuration; Spawning a mock server; Interacting with the server
- `frontend/unit_testing/web_helpers.md` (168) – **Web test helpers** – Overview; Mock environment; Mounting components; Mounting views; Interacting with components

## user_interface

- `user_interface/icons.md` (398) – **UI icons** – Odoo UI icons; Odoo Spreadsheet icons
- `user_interface/scss_inheritance.md` (106) – **SCSS inheritance** – Overview; SCSS’s `!default` directive; Odoo’s SCSS inheritance system
- `user_interface/view_architectures/01_generic_architecture__form.md` (1558) – **View architectures – Teil 1/10: Generic architecture / Python expression / Form** – Generic architecture; Python expression; Form
- `user_interface/view_architectures/02_settings.md` (463) – **View architectures – Teil 2/10: Settings** – Settings
- `user_interface/view_architectures/03_list.md` (1149) – **View architectures – Teil 3/10: List** – List
- `user_interface/view_architectures/04_search.md` (947) – **View architectures – Teil 4/10: Search** – Search
- `user_interface/view_architectures/05_kanban.md` (799) – **View architectures – Teil 5/10: Kanban** – Kanban
- `user_interface/view_architectures/06_qweb__graph.md` (157) – **View architectures – Teil 6/10: QWeb / Graph** – QWeb; Graph
- `user_interface/view_architectures/07_pivot__calendar.md` (675) – **View architectures – Teil 7/10: Pivot / Calendar** – Pivot; Calendar
- `user_interface/view_architectures/08_activity__cohort.md` (178) – **View architectures – Teil 8/10: Activity / Cohort** – Activity; Cohort
- `user_interface/view_architectures/09_grid.md` (315) – **View architectures – Teil 9/10: Grid** – Grid
- `user_interface/view_architectures/10_gantt__map.md` (357) – **View architectures – Teil 10/10: Gantt / Map** – Gantt; Map
- `user_interface/view_records.md` (460) – **View records** – Generic structure; View types; Fields; Inheritance; Model commons

## standard_modules

- `standard_modules/account/account_account.md` (112) – **Account** – Original definition from `account`
- `standard_modules/account/account_account_tag.md` (70) – **Account Tag** – Original definition from `account`
- `standard_modules/account/account_fiscal_position.md` (118) – **Fiscal Position** – Original definition from `account`
- `standard_modules/account/account_group.md` (44) – **Account Group** – Original definition from `account`
- `standard_modules/account/account_report.md` (208) – **Report** – Original definition from `account`
- `standard_modules/account/account_report_line.md` (104) – **Report Line** – Original definition from `account`
- `standard_modules/account/account_tax.md` (248) – **Taxes** – Original definition from `account`
- `standard_modules/account/account_tax_repartition.md` (94) – **Tax Repartitions** – Original definition from `account`
- `standard_modules/payment/payment_method.md` (57) – **Payment Method** – –
- `standard_modules/payment/payment_provider.md` (363) – **Payment Provider** – –
- `standard_modules/payment/payment_token.md` (114) – **Payment Token** – –
- `standard_modules/payment/payment_transaction.md` (429) – **Payment Transaction** – –

## upgrades

- `upgrades/upgrade_scripts.md` (105) – **Upgrade scripts** – Writing upgrade scripts; Phases of upgrade scripts
- `upgrades/upgrade_utils/01_installation__util_functions.md` (1977) – **Upgrade utils – Teil 1/2: Installation / Using upgrade utils / Util functions** – Installation; Using upgrade utils; Util functions
- `upgrades/upgrade_utils/02_testing_upgrade_scripts.md` (205) – **Upgrade utils – Teil 2/2: Testing upgrade scripts** – Testing upgrade scripts

## (Wurzel: cli, APIs)

- `cli.md` (1386) – **Command-line interface (CLI)** – Version; `help` - Show available commands; `server` - Run the Server; Configuration file; `shell` - Open a Shell; `db` - Manage a Database; `i18n` - Internationalization; `module` - Manage modules; `neutralize` - Neutralize a Database; `scaffold` - Scaffold a Module; `populate` - Populate a Database; `cloc` - Count Lines of Code; `obfuscate` - Obfuscate database; `deploy` - Deploy module remotely; `upgrade_code` - Rewrite source code
- `external_api.md` (754) – **External JSON-2 API** – API; Configuration; Transaction; Code Example; Dynamic Documentation; Migrating from XML-RPC / JSON-RPC
- `external_rpc_api.md` (1446) – **External RPC API** – Connection; Calling methods
- `extract_api.md` (506) – **Extract API** – Overview; Parse; Get results; Integration Testing

## contributing

- `contributing/coding_guidelines.md` (1338) – **Coding guidelines** – Module structure; XML files; Python; Javascript; CSS and SCSS (Quelle: Contributing → Development, nicht Reference)
