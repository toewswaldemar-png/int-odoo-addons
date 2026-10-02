<!-- Quelle: https://www.odoo.com/documentation/19.0/de/developer/reference/standard_modules/payment/payment_token.html · abgerufen 2026-10-02 -->

# Payment Token

**`class odoo.addons.payment.models.payment_token.PaymentToken`**

**`_get_available_tokens(providers_ids, partner_id, is_validation=False, **kwargs)`**

Return the available tokens linked to the given providers and partner.

For a module to retrieve the available tokens, it must override this method and add
information in the kwargs to define the context of the request.

**`Parameter`**

- **providers_ids** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)) – The ids of the providers available for the transaction.
- **partner_id** ([*int*](https://docs.python.org/3/library/functions.html#int)) – The id of the partner.
- **is_validation** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Whether the transaction is a validation operation.
- **kwargs** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – Locally unused keywords arguments.

**`Rückgabe`**

The available tokens.

**`Rückgabetyp`**

payment.token

**`_build_display_name(*args, max_length=34, should_pad=True, **kwargs)`**

Build a token name of the desired maximum length with the format `•••• 1234`.

The payment details are padded on the left with up to four padding characters. The padding
is only added if there is enough room for it. If not, it is either reduced or not added at
all. If there is not enough room for the payment details either, they are trimmed from the
left.

For a module to customize the display name of a token, it must override this method and
return the customized display name.

Note: `self.ensure_one()`

**`Parameter`**

- **args** ([*list*](https://docs.python.org/3/library/stdtypes.html#list)) – The arguments passed by QWeb when calling this method.
- **max_length** ([*int*](https://docs.python.org/3/library/functions.html#int)) – The desired maximum length of the token name. The default is `34` to
  fit the largest IBANs.
- **should_pad** ([*bool*](https://docs.python.org/3/library/functions.html#bool)) – Whether the token should be padded.
- **kwargs** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – Optional data used in overrides of this method.

**`Rückgabe`**

The padded token name.

**`Rückgabetyp`**

[str](https://docs.python.org/3/library/stdtypes.html#str)

**`_get_specific_create_values(provider_code, values)`**

Complete the values of the `create` method with provider-specific values.

For a provider to add its own create values, it must overwrite this method and return a
dict of values. Provider-specific values take precedence over those of the dict of generic
create values.

**`Parameter`**

- **provider_code** ([*str*](https://docs.python.org/3/library/stdtypes.html#str)) – The code of the provider managing the token.
- **values** ([*dict*](https://docs.python.org/3/library/stdtypes.html#dict)) – The original create values.

**`Rückgabe`**

The dict of provider-specific create values.

**`Rückgabetyp`**

[dict](https://docs.python.org/3/library/stdtypes.html#dict)

**`_handle_archiving()`**

Handle the archiving of tokens.

For a module to perform additional operations when a token is archived, it must override
this method.

**`Rückgabe`**

None

**`get_linked_records_info()`**

Return a list of information about records linked to the current token.

For a module to implement payments and link documents to a token, it must override this
method and add information about linked document records to the returned list.

The information must be structured as a dict with the following keys:

- `description`: The description of the record’s model (e.g. „Subscription“).
- `id`: The id of the record.
- `name`: The name of the record.
- `url`: The url to access the record.

Note: `self.ensure_one()`

**`Rückgabe`**

The list of information about the linked document records.

**`Rückgabetyp`**

[list](https://docs.python.org/3/library/stdtypes.html#list)
