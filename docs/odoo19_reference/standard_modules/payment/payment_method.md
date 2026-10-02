<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/payment/payment_method.html · abgerufen 2026-10-02 -->

# Payment Method

**`class odoo.addons.payment.models.payment_method.PaymentMethod`**

**`_get_compatible_payment_methods(provider_ids, partner_id, currency_id=None, force_tokenization=False, is_express_checkout=False, report=None, **kwargs)`**

Search and return the payment methods matching the compatibility criteria.

The compatibility criteria are that payment methods must: be supported by at least one of
the providers; support the country of the partner if it exists; be primary payment methods
(not a brand). If provided, the optional keyword arguments further refine the criteria.

**`Parameter`**

- **provider_ids** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)) – The list of providers by which the payment methods must be at
  least partially supported to be considered compatible, as a list
  of `payment.provider` ids.
- **partner_id** ([*int*](https://docs.python.org/3/library/functions.html#int)) – The partner making the payment, as a `res.partner` id.
- **currency_id** ([*int*](https://docs.python.org/3/library/functions.html#int)) – The payment currency, if known beforehand, as a `res.currency` id.
- **force_tokenization** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Whether only payment methods supporting tokenization can be
  matched.
- **is_express_checkout** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Whether the payment is made through express checkout.
- **report** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – The report in which each provider’s availability status and reason must
  be logged.
- **kwargs** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – Optional data. This parameter is not used here.

**`Rückgabe`**

The compatible payment methods.

**`Rückgabetyp`**

payment.method

**`_get_from_code(code, mapping=None)`**

Get the payment method corresponding to the given provider-specific code.

If a mapping is given, the search uses the generic payment method code that corresponds to
the given provider-specific code.

**`Parameter`**

- **code** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – The provider-specific code of the payment method to get.
- **mapping** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – A non-exhaustive mapping of generic payment method codes to
  provider-specific codes.

**`Rückgabe`**

The corresponding payment method, if any.

**`Rückgabetyp`**

payment.method
