<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_account_tag.html · abgerufen 2026-10-02 -->

# Account Tag

## Original definition from `account`

**`model odoo.addons.account.models.account_account_tag.AccountAccountTag(env: Environment, ids: tuple[IdType, ...], prefetch_ids: Reversible[IdType])`**

**`_name = account.account.tag`**

**`name: str`**

**`Required`**

**`Name`**

Tag Name

**`applicability: str`**

**`Required`**

**`Name`**

Applicability

**`Selection`**

`accounts`: Accounts
`taxes`: Taxes
`products`: Products

**`Default`**

accounts

**`color: int`**

**`Name`**

Color Index

**`active: bool`**

**`Name`**

Active

**`Default`**

True

Set active to false to hide the Account Tag without removing it.

**`country_id: int`**

**`Name`**

Country

**`Comodel`**

res.country

**`Possible_values`**

[odoo/addons/base/data/res_country_data.xml](https://github.com/odoo/odoo/blob/19.0/odoo/addons/base/data/res_country_data.xml)

Country for which this tag is available, when applied on taxes.
