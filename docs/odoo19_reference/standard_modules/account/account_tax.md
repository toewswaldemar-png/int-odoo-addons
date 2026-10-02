<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_tax.html · abgerufen 2026-10-02 -->

# Taxes

## Original definition from `account`

**`model odoo.addons.account.models.account_tax.AccountTax(env: Environment, ids: tuple[IdType, ...], prefetch_ids: Reversible[IdType])`**

**`_name = account.tax`**

**`name: str`**

**`Required`**

**`Name`**

Tax Name

**`type_tax_use: str`**

**`Required`**

**`Name`**

Tax Type

**`Selection`**

`sale`: Sales
`purchase`: Purchases
`none`: None

**`Default`**

sale

Determines where the tax is selectable. Note: ‚None‘ means a tax can’t be used by itself, however it can still be used in a group. ‚adjustment‘ is used to perform tax adjustment.

**`tax_scope: str`**

**`Name`**

Tax Scope

**`Selection`**

`service`: Services
`consu`: Goods

**`amount_type: str`**

**`Required`**

**`Name`**

Tax Computation

**`Selection`**

`group`: Group of Taxes
`fixed`: Fixed
`percent`: Percentage
`division`: Percentage Tax Included

**`Default`**

percent

- **`Group of Taxes: The tax is a set of sub taxes.`**

  - Fixed: The tax amount stays the same whatever the price.
  - **`Percentage: The tax amount is a % of the price:`**

    e.g 100 * (1 + 10%) = 110 (not price included)
    e.g 110 / (1 + 10%) = 100 (price included)
  - **`Percentage Tax Included: The tax amount is a division of the price:`**

    e.g 180 / (1 - 10%) = 200 (not price included)
    e.g 200 * (1 - 10%) = 180 (price included)

**`active: bool`**

**`Name`**

Active

**`Default`**

True

Set active to false to hide the tax without removing it.

**`children_tax_ids: Sequence[odoo.orm.commands.Command]`**

**`Name`**

Children Taxes

**`Comodel`**

account.tax

**`sequence: int`**

**`Required`**

**`Name`**

Sequence

**`Default`**

1

The sequence field is used to define order in which the tax lines are applied.

**`amount: float`**

**`Required`**

**`Name`**

Amount

**`Default`**

0.0

**`description: str`**

**`Name`**

Description

**`price_include: bool`**

**`Name`**

Price Include

**`Readonly`**

this field is not supposed to/cannot be set manually

**`Store`**

this field is there only for technical reasons

Determines whether the price you use on the product and invoices includes this tax.

**`include_base_amount: bool`**

**`Name`**

Affect Base of Subsequent Taxes

**`Default`**

False

If set, taxes with a higher sequence than this one will be affected by it, provided they accept it.

**`is_base_affected: bool`**

**`Name`**

Base Affected by Previous Taxes

**`Default`**

True

If set, taxes with a lower sequence might affect this one, provided they try to do it.

**`analytic: bool`**

**`Name`**

Include in Analytic Cost

If set, the amount computed by this tax will be assigned to the same analytic account as the invoice line (if any)

**`invoice_repartition_line_ids: Sequence[odoo.orm.commands.Command]`**

**`Name`**

Distribution for Invoices

**`Comodel`**

[account.tax.repartition.line](https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_tax_repartition.html#model-account-tax-repartition-line)

Distribution when the tax is used on an invoice

**`refund_repartition_line_ids: Sequence[odoo.orm.commands.Command]`**

**`Name`**

Distribution for Refund Invoices

**`Comodel`**

[account.tax.repartition.line](https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_tax_repartition.html#model-account-tax-repartition-line)

Distribution when the tax is used on a refund

**`tax_group_id: int`**

**`Required`**

**`Name`**

Tax Group

**`Comodel`**

account.tax.group

**`tax_exigibility: str`**

**`Name`**

Tax Exigibility

**`Selection`**

`on_invoice`: Based on Invoice
`on_payment`: Based on Payment

**`Default`**

on_invoice

Based on Invoice: the tax is due as soon as the invoice is validated.
Based on Payment: the tax is due as soon as the payment of the invoice is received.

**`cash_basis_transition_account_id: int`**

**`Name`**

Cash Basis Transition Account

**`Comodel`**

[account.account](https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_account.html#model-account-account)

Account used to transition the tax amount for cash basis taxes. It will contain the tax amount as long as the original invoice has not been reconciled ; at reconciliation, this amount cancelled on this account and put on the regular tax account.
