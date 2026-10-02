<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/payment/payment_provider.html · abgerufen 2026-10-02 -->

# Payment Provider

**`class odoo.addons.payment.models.payment_provider.PaymentProvider`**

**`_build_request_auth(**kwargs)`**

Set the basic HTTP Auth of the request

This method serves as a hook to allow providers to build the request’s basic HTTP Auth.

**`Parameter`**

**kwargs** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – Provider-specific data.

**`Rückgabe`**

The basic HTTP Auth, if any.

**`Rückgabetyp`**

[tuple](https://docs.python.org/3/library/stdtypes.html#tuple)

**`_build_request_headers(method, endpoint, payload, **kwargs)`**

Build the headers of the request.

This method serves as a hook to allow providers to build the request headers.

**`Parameter`**

- **method** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – The HTTP method of the request.
- **endpoint** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – The endpoint of the API to reach with the request.
- **payload** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – The payload of the request.
- **kwargs** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – Provider-specific data.

**`Rückgabe`**

The request headers.

**`Rückgabetyp`**

[dict](https://docs.python.org/3/library/stdtypes.html#dict)

**`_build_request_url(endpoint, **kwargs)`**

Build the URL of the request.

This method serves as a hook to allow providers to build the request URL.

**`Parameter`**

- **endpoint** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – The endpoint of the API to reach with the request.
- **kwargs** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – Provider-specific data.

**`Rückgabe`**

The request URL.

**`Rückgabetyp`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`_compute_feature_support_fields()`**

Compute the feature support fields based on the provider.

Feature support fields are used to specify which additional features are supported by a
given provider. These fields are as follows:

- `support_express_checkout`: Whether the „express checkout“ feature is supported. `False`
  by default.
- `support_manual_capture`: Whether the „manual capture“ feature is supported. `False` by
  default.
- `support_refund`: Which type of the „refunds“ feature is supported: `None`,
  `'full_only'`, or `'partial'`. `None` by default.
- `support_tokenization`: Whether the „tokenization feature“ is supported. `False` by
  default.

For a provider to specify that it supports additional features, it must override this method
and set the related feature support fields to the desired value on the appropriate
`payment.provider` records.

**`Rückgabe`**

None

**`_get_code()`**

Return the code of the provider.

Note: `self.ensure_one()`

**`Rückgabe`**

The code of the provider.

**`Rückgabetyp`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`_get_compatible_providers(company_id, partner_id, amount, currency_id=None, force_tokenization=False, is_express_checkout=False, is_validation=False, report=None, **kwargs)`**

Search and return the providers matching the compatibility criteria.

The compatibility criteria are that providers must: not be disabled; be in the company that
is provided; support the country of the partner if it exists; be compatible with the
currency if provided. If provided, the optional keyword arguments further refine the
criteria.

**`Parameter`**

- **company_id** ([*int*](https://docs.python.org/3/library/functions.html#int)) – The company to which providers must belong, as a `res.company` id.
- **partner_id** ([*int*](https://docs.python.org/3/library/functions.html#int)) – The partner making the payment, as a `res.partner` id.
- **amount** ([*float*](https://docs.python.org/3/library/functions.html#float)) – The amount to pay. `0` for validation transactions.
- **currency_id** ([*int*](https://docs.python.org/3/library/functions.html#int)) – The payment currency, if known beforehand, as a `res.currency` id.
- **force_tokenization** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Whether only providers allowing tokenization can be matched.
- **is_express_checkout** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Whether the payment is made through express checkout.
- **is_validation** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Whether the operation is a validation.
- **report** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – The report in which each provider’s availability status and reason must
  be logged.
- **kwargs** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – Optional data. This parameter is not used here.

**`Rückgabe`**

The compatible providers.

**`Rückgabetyp`**

payment.provider

**`_get_default_payment_method_codes()`**

Return the default payment methods for this provider.

Note: `self.ensure_one()`

**`Rückgabe`**

The default payment method codes.

**`Rückgabetyp`**

[set](https://docs.python.org/3/library/stdtypes.html#set)

**`_get_redirect_form_view(is_validation=False)`**

Return the view of the template used to render the redirect form.

For a provider to return a different view depending on whether the operation is a
validation, it must override this method and return the appropriate view.

Note: `self.ensure_one()`

**`Parameter`**

**is_validation** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Whether the operation is a validation.

**`Rückgabe`**

The view of the redirect form template.

**`Rückgabetyp`**

record of `ir.ui.view`

**`_get_provider_domain(provider_code, **kwargs)`**

Return the payment provider domain.

**`Parameter`**

- **provider_code** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – The code of the provider to search for.
- **kwargs** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – Additional keyword arguments.

**`Rückgabe`**

The domain to search for the provider.

**`Rückgabetyp`**

[list](https://docs.python.org/3/library/stdtypes.html#list)[[tuple](https://docs.python.org/3/library/stdtypes.html#tuple)]

**`_get_removal_values()`**

Return the values to update a provider with when its module is uninstalled.

For a module to specify additional removal values, it must override this method and complete
the generic values with its specific values.

**`Rückgabe`**

The removal values to update the removed provider with.

**`Rückgabetyp`**

[dict](https://docs.python.org/3/library/stdtypes.html#dict)

**`_get_supported_currencies()`**

Return the supported currencies for the payment provider.

By default, all currencies are considered supported, including the inactive ones. For a
provider to filter out specific currencies, it must override this method and return the
subset of supported currencies.

Note: `self.ensure_one()`

**`Rückgabe`**

The supported currencies.

**`Rückgabetyp`**

res.currency

**`_get_validation_amount()`**

Return the amount to use for validation operations.

For a provider to support tokenization, it must override this method and return the
validation amount. If it is `0`, it is not necessary to create the override.

Note: `self.ensure_one()`

**`Rückgabe`**

The validation amount.

**`Rückgabetyp`**

[float](https://docs.python.org/3/library/functions.html#float)

**`_get_validation_currency()`**

Return the currency to use for validation operations.

The validation currency must be supported by both the provider and the payment method. If
the payment method is not passed, only the provider’s supported currencies are considered.
If no suitable currency is found, the provider’s company’s currency is returned instead.

For a provider to support tokenization and specify a different validation currency, it must
override this method and return the appropriate validation currency.

Note: `self.ensure_one()`

**`Rückgabe`**

The validation currency.

**`Rückgabetyp`**

recordset of `res.currency`

**`_is_tokenization_required(**kwargs)`**

Return whether tokenizing the transaction is required given its context.

For a module to make the tokenization required based on the payment context, it must
override this method and return whether it is required.

**`Parameter`**

**kwargs** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – The payment context. This parameter is not used here.

**`Rückgabe`**

Whether tokenizing the transaction is required.

**`Rückgabetyp`**

[bool](https://docs.python.org/3/library/functions.html#bool)

**`_parse_response_content(response, **kwargs)`**

Retrieve the JSON-formatted content of the response.

This method serves as a hook to allow providers to parse the response content.

**`Parameter`**

- **response** (*requests.Response*) – The response to parse.
- **kwargs** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – Provider-specific data.

**`Rückgabe`**

The response content.

**`Rückgabetyp`**

[dict](https://docs.python.org/3/library/stdtypes.html#dict)

**`_parse_response_error(response)`**

Retrieve the error message from the response.

This method serves as a hook to allow providers to parse the response’s error message.

**`Parameter`**

**response** (*requests.Response*) – The response to parse.

**`Rückgabe`**

The error message.

**`Rückgabetyp`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`_send_api_request(method, endpoint, *, params=None, data=None, json=None, reference=None, **kwargs)`**

Send a request to the API.

Whenever possible, calls to this method should be wrapped in a try-except block to prevent
the `ValidationError` that is raised when the request fails from bubbling up. Exceptions to
this rule include calls from a controller that must return the error message to the client.

Note: `self.ensure_one()`

**`Parameter`**

- **method** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – The HTTP method of the request.
- **endpoint** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – The endpoint of the API to reach with the request.
- **params** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – The query string parameters of the request.
- **data** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)*|*[*str*](https://docs.python.org/3/library/stdtypes.html#str)) – The body of the request.
- **json** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – The JSON-formatted body of the request.
- **reference** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – The reference of the transaction, if any.
- **kwargs** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – Provider-specific data forwarded to the specialized helper methods.

**`Rückgabe`**

The formatted content of the response.

**`Rückgabetyp`**

[dict](https://docs.python.org/3/library/stdtypes.html#dict)|[str](https://docs.python.org/3/library/stdtypes.html#str)

**`Verursacht`**

[**ValidationError**](https://www.odoo.com/documentation/19.0/de/developer/reference/backend/orm.html#odoo.exceptions.ValidationError) – If an HTTP error occurs.

**`_should_build_inline_form(is_validation=False)`**

Return whether the inline payment form should be instantiated.

For a provider to handle both direct payments and payments with redirection, it must
override this method and return whether the inline payment form should be instantiated (i.e.
if the payment should be direct) based on the operation (online payment or validation).

**`Parameter`**

**is_validation** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Whether the operation is a validation.

**`Rückgabe`**

Whether the inline form should be instantiated.

**`Rückgabetyp`**

[bool](https://docs.python.org/3/library/functions.html#bool)
