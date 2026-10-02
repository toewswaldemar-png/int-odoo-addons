<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_fiscal_position.html · abgerufen 2026-10-02 -->

# Fiscal Position

## Original definition from `account`

**`model odoo.addons.account.models.partner.AccountFiscalPosition(env: Environment, ids: tuple[IdType, ...], prefetch_ids: Reversible[IdType])`**

**`_name = account.fiscal.position`**

**`sequence: int`**

**`Name`**

Sequence

**`name: str`**

**`Required`**

**`Name`**

Fiscal Position

**`account_ids: Sequence[odoo.orm.commands.Command]`**

**`Name`**

Account Mapping

**`Comodel`**

account.fiscal.position.account

**`tax_ids: Sequence[odoo.orm.commands.Command]`**

**`Name`**

Taxes

**`Comodel`**

[account.tax](https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_tax.html#model-account-tax)

**`note: str`**

**`Name`**

Notes

Legal mentions that have to be printed on the invoices.

**`auto_apply: bool`**

**`Name`**

Detect Automatically

Apply tax & account mappings on invoices automatically if the matching criterias (VAT/Country) are met.

**`vat_required: bool`**

**`Name`**

VAT required

Apply only if partner has a VAT number.

**`country_id: int`**

**`Name`**

Country

**`Comodel`**

res.country

**`Possible_values`**

[odoo/addons/base/data/res_country_data.xml](https://github.com/odoo/odoo/blob/19.0/odoo/addons/base/data/res_country_data.xml)

Apply only if delivery country matches.

**`country_group_id: int`**

**`Name`**

Country Group

**`Comodel`**

res.country.group

Apply only if delivery country matches the group.

**`state_ids: Sequence[odoo.orm.commands.Command]`**

**`Name`**

Federal States

**`Comodel`**

res.country.state

**`zip_from: str`**

**`Name`**

Zip Range From

**`zip_to: str`**

**`Name`**

Zip Range To
