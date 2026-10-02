<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_account.html · abgerufen 2026-10-02 -->

# Account

## Original definition from `account`

**`model odoo.addons.account.models.account_account.AccountAccount(env: Environment, ids: tuple[IdType, ...], prefetch_ids: Reversible[IdType])`**

**`_name = account.account`**

**`name: str`**

**`Required`**

**`Name`**

Account Name

**`currency_id: int`**

**`Name`**

Account Currency

**`Comodel`**

res.currency

**`Possible_values`**

[odoo/addons/base/data/res_currency_data.xml](https://github.com/odoo/odoo/blob/19.0/odoo/addons/base/data/res_currency_data.xml)

Forces all journal items in this account to have a specific currency (i.e. bank journals). If no currency is set, entries can use any currency.

**`code: str`**

**`Name`**

Code

**`Store`**

this field is there only for technical reasons

**`account_type: str`**

**`Required`**

**`Name`**

Type

**`Selection`**

`asset_receivable`: Receivable
`asset_cash`: Bank and Cash
`asset_current`: Current Assets
`asset_non_current`: Non-current Assets
`asset_prepayments`: Prepayments
`asset_fixed`: Fixed Assets
`liability_payable`: Payable
`liability_credit_card`: Credit Card
`liability_current`: Current Liabilities
`liability_non_current`: Non-current Liabilities
`equity`: Equity
`equity_unaffected`: Current Year Earnings
`income`: Income
`income_other`: Other Income
`expense`: Expenses
`expense_other`: Other Expenses
`expense_depreciation`: Depreciation
`expense_direct_cost`: Cost of Revenue
`off_balance`: Off-Balance Sheet

Account Type is used for information purpose, to generate country-specific legal reports, and set the rules to close a fiscal year and generate opening entries.

**`reconcile: bool`**

**`Name`**

Allow Reconciliation

Check this box if this account allows invoices & payments matching of journal items.

**`note: str`**

**`Name`**

Internal Notes

**`tax_ids: Sequence[odoo.orm.commands.Command]`**

**`Name`**

Default Taxes

**`Comodel`**

[account.tax](https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_tax.html#model-account-tax)

**`tag_ids: Sequence[odoo.orm.commands.Command]`**

**`Name`**

Tags

**`Comodel`**

[account.account.tag](https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_account_tag.html#model-account-account-tag)

Optional tags you may want to assign for custom reporting
