<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_report.html · abgerufen 2026-10-02 -->

# Report

## Original definition from `account`

**`model odoo.addons.account.models.account_report.AccountReport(env: Environment, ids: tuple[IdType, ...], prefetch_ids: Reversible[IdType])`**

**`_name = account.report`**

**`name: str`**

**`Required`**

**`Name`**

Name

**`line_ids: Sequence[odoo.orm.commands.Command]`**

**`Name`**

Lines

**`Comodel`**

[account.report.line](https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_report_line.html#model-account-report-line)

**`column_ids: Sequence[odoo.orm.commands.Command]`**

**`Name`**

Columns

**`Comodel`**

account.report.column

**`root_report_id: int`**

**`Name`**

Root Report

**`Comodel`**

account.report

The report this report is a variant of.

**`country_id: int`**

**`Name`**

Country

**`Comodel`**

res.country

**`Possible_values`**

[odoo/addons/base/data/res_country_data.xml](https://github.com/odoo/odoo/blob/19.0/odoo/addons/base/data/res_country_data.xml)

**`only_tax_exigible: bool`**

**`Name`**

Only Tax Exigible Lines

**`availability_condition: str`**

**`Name`**

Availability

**`Selection`**

`country`: Country Matches
`coa`: Chart of Accounts Matches
`always`: Always

**`load_more_limit: int`**

**`Name`**

Load More Limit

**`search_bar: bool`**

**`Name`**

Search Bar

**`default_opening_date_filter: str`**

**`Name`**

Default Opening

**`Selection`**

`this_year`: This Year
`this_quarter`: This Quarter
`this_month`: This Month
`today`: Today
`previous_month`: Last Month
`previous_quarter`: Last Quarter
`previous_year`: Last Year
`this_return_period`: This Return Period
`previous_return_period`: Last Return Period

**`filter_multi_company: str`**

**`Name`**

Multi-Company

**`Selection`**

`selector`: Use Company Selector
`tax_units`: Use Tax Units

**`filter_date_range: bool`**

**`Name`**

Date Range

**`filter_show_draft: bool`**

**`Name`**

Draft Entries

**`filter_unreconciled: bool`**

**`Name`**

Unreconciled Entries

**`filter_unfold_all: bool`**

**`Name`**

Unfold All

**`filter_period_comparison: bool`**

**`Name`**

Period Comparison

**`filter_growth_comparison: bool`**

**`Name`**

Growth Comparison

**`filter_journals: bool`**

**`Name`**

Journals

**`filter_analytic: bool`**

**`Name`**

Analytic Filter

**`filter_hierarchy: str`**

**`Name`**

Account Groups

**`Selection`**

`by_default`: Enabled by Default
`optional`: Optional
`never`: Never

**`filter_account_type: str`**

**`Name`**

Account Types

**`Selection`**

`both`: Payable and receivable
`payable`: Payable
`receivable`: Receivable
`disabled`: Disabled

**`filter_partner: bool`**

**`Name`**

Partners

**`allow_foreign_vat: bool`**

**`Name`**

Allow Foreign VAT
