<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_tax_repartition.html · abgerufen 2026-10-02 -->

# Tax Repartitions

## Original definition from `account`

**`model odoo.addons.account.models.account_tax.AccountTaxRepartitionLine(env: Environment, ids: tuple[IdType, ...], prefetch_ids: Reversible[IdType])`**

**`_name = account.tax.repartition.line`**

**`factor_percent: float`**

**`Required`**

**`Name`**

%

**`Default`**

100

Factor to apply on the account move lines generated from this distribution line, in percents

**`repartition_type: str`**

**`Required`**

**`Name`**

Based On

**`Selection`**

`base`: Base
`tax`: of tax

**`Default`**

tax

Base on which the factor will be applied.

**`document_type: str`**

**`Required`**

**`Name`**

Related to

**`Selection`**

`invoice`: Invoice
`refund`: Refund

**`account_id: int`**

**`Name`**

Account

**`Comodel`**

[account.account](https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_account.html#model-account-account)

Account on which to post the tax amount

**`tax_id: int`**

**`Name`**

Tax

**`Comodel`**

[account.tax](https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_tax.html#model-account-tax)

**`tag_ids: Sequence[odoo.orm.commands.Command]`**

**`Name`**

Tax Grids

**`Comodel`**

[account.account.tag](https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_account_tag.html#model-account-account-tag)

**`use_in_tax_closing: bool`**

**`Name`**

Tax Closing Entry
