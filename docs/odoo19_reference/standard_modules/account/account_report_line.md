<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_report_line.html · abgerufen 2026-10-02 -->

# Report Line

## Original definition from `account`

**`model odoo.addons.account.models.account_report.AccountReportLine(env: Environment, ids: tuple[IdType, ...], prefetch_ids: Reversible[IdType])`**

**`_name = account.report.line`**

**`name: str`**

**`Required`**

**`Name`**

Name

**`expression_ids: Sequence[odoo.orm.commands.Command]`**

**`Name`**

Expressions

**`Comodel`**

account.report.expression

**`report_id: int`**

**`Required`**

**`Name`**

Parent Report

**`Comodel`**

[account.report](https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/account/account_report.html#model-account-report)

**`hierarchy_level: int`**

**`Required`**

**`Name`**

Level

**`parent_id: int`**

**`Name`**

Parent Line

**`Comodel`**

account.report.line

**`children_ids: Sequence[odoo.orm.commands.Command]`**

**`Name`**

Child Lines

**`Comodel`**

account.report.line

**`foldable: bool`**

**`Name`**

Foldable

By default, we always unfold the lines that can be. If this is checked, the line won’t be unfolded by default, and a folding button will be displayed.

**`print_on_new_page: bool`**

**`Name`**

Print On New Page

When checked this line and everything after it will be printed on a new page.

**`action_id: int`**

**`Name`**

Action

**`Comodel`**

ir.actions.actions

Setting this field will turn the line into a link, executing the action when clicked.

**`hide_if_zero: bool`**

**`Name`**

Hide if Zero

This line and its children will be hidden when all of their columns are 0.
