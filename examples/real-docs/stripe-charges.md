# Stripe Charges API Documentation

Source: https://docs.stripe.com/api/charges (fetched 2026-02-08)

The Charge object represents a single attempt to move money into your Stripe account. PaymentIntent confirmation is the most common way to create Charges, but Account Debits may also create Charges. Some legacy payment flows create Charges directly, which is not recommended for new integrations.

## The Charge Object

### Attributes

- **id** (string): Unique identifier for the object.
- **amount** (integer): Amount intended to be collected by this payment. A positive integer representing how much to charge in the smallest currency unit (e.g., 100 cents to charge $1.00 or 100 to charge ¥100, a zero-decimal currency). The minimum amount is $0.50 US or equivalent in charge currency. The amount value supports up to eight digits (e.g., a value of 99999999 for a USD charge of $999,999.99).
- **balance_transaction** (nullable string, Expandable): ID of the balance transaction that describes the impact of this charge on your account balance (not including refunds or disputes).
- **billing_details** (object): Billing information associated with the payment method at the time of the transaction.
- **currency** (enum)
- **customer** (nullable string, Expandable): ID of the customer this charge is for if one exists.
- **description** (nullable string): An arbitrary string attached to the object. Often useful for displaying to users.
- **disputed** (boolean): Whether the charge has been disputed.
- **metadata** (object): Set of key-value pairs that you can attach to an object. This can be useful for storing additional information about the object in a structured format.
- **payment_intent** (nullable string, Expandable): ID of the PaymentIntent associated with this charge, if one exists.
- **payment_method_details** (nullable object): Details about the payment method at the time of the transaction.
- **receipt_email** (nullable string): This is the email address that the receipt for this charge was sent to.
- **refunded** (boolean): Whether the charge has been fully refunded. If the charge is only partially refunded, this attribute will still be false.
- **shipping** (nullable object): Shipping information for the charge.
- **statement_descriptor** (nullable string): For a non-card charge, text that appears on the customer's statement as the statement descriptor. This value overrides the account's default statement descriptor.
- **statement_descriptor_suffix** (nullable string): Provides information about a card charge. Concatenated to the account's statement descriptor prefix to form the complete statement descriptor that appears on the customer's statement.
- **status** (enum): The status of the payment is either succeeded, pending, or failed.
- **object** (string)
- **amount_captured** (integer)
- **amount_refunded** (integer)
- **application** (nullable string, Expandable, Connect only)
- **application_fee** (nullable string, Expandable, Connect only)
- **application_fee_amount** (nullable integer, Connect only)
- **calculated_statement_descriptor** (nullable string)
- **captured** (boolean)
- **created** (timestamp)
- **failure_balance_transaction** (nullable string, Expandable)
- **failure_code** (nullable string)
- **failure_message** (nullable string)
- **fraud_details** (nullable object)
- **livemode** (boolean)
- **on_behalf_of** (nullable string, Expandable, Connect only)
- **outcome** (nullable object)
- **paid** (boolean)
- **payment_method** (nullable string)
- **presentment_details** (nullable object)
- **radar_options** (nullable object)
- **receipt_number** (nullable string)
- **receipt_url** (nullable string)
- **refunds** (nullable object, Expandable)
- **review** (nullable string, Expandable)
- **source_transfer** (nullable string, Expandable, Connect only)
- **transfer** (nullable string, Expandable, Connect only)
- **transfer_data** (nullable object, Connect only)
- **transfer_group** (nullable string, Connect only)

## Create a charge

`POST /v1/charges`

This method is no longer recommended—use the Payment Intents API to initiate a new payment instead.

### Parameters

- **amount** (integer, Required): Amount intended to be collected by this payment. A positive integer representing how much to charge in the smallest currency unit.
- **currency** (enum, Required)
- **customer** (string): The ID of an existing customer that will be charged in this request. The maximum length is 500 characters.
- **description** (string): An arbitrary string which you can attach to a Charge object. It is displayed when in the web interface alongside the charge.
- **metadata** (object): Set of key-value pairs that you can attach to an object.
- **receipt_email** (string): The email address to which this charge's receipt will be sent. The maximum length is 800 characters.
- **shipping** (object): Shipping information for the charge. Helps prevent fraud on charges for physical goods.
- **source** (string)
- **statement_descriptor** (string): For a non-card charge, text that appears on the customer's statement as the statement descriptor.
- **statement_descriptor_suffix** (string): Provides information about a card charge.
- **application_fee_amount** (integer, Connect only)
- **capture** (boolean)
- **on_behalf_of** (string, Connect only)
- **radar_options** (object)
- **transfer_data** (object, Connect only)
- **transfer_group** (string, Connect only)

### Returns

Returns the charge object if the charge succeeded. This call raises an error if something goes wrong. A common source of error is an invalid or expired card, or a valid card with insufficient available balance.

## Update a charge

`POST /v1/charges/:id`

Updates the specified charge by setting the values of the parameters passed. Any parameters not provided will be left unchanged.

### Parameters

- **customer** (string): The ID of an existing customer that will be associated with this request.
- **description** (string): An arbitrary string which you can attach to a charge object.
- **metadata** (object): Set of key-value pairs that you can attach to an object.
- **receipt_email** (string): This is the email address that the receipt for this charge will be sent to.
- **shipping** (object): Shipping information for the charge.
- **fraud_details** (object)
- **transfer_group** (string, Connect only)

### Returns

Returns the charge object if the update succeeded.

## Retrieve a charge

`GET /v1/charges/:id`

Retrieves the details of a charge that has previously been created. Supply the unique charge ID that was returned from your previous request.

### Parameters

No parameters.

### Returns

Returns a charge if a valid identifier was provided, and raises an error otherwise.

## List all charges

`GET /v1/charges`

Returns a list of charges you have previously created. The charges are returned in sorted order, with the most recent charges appearing first.

## Capture a charge

`POST /v1/charges/:id/capture`

Capture the payment of an existing, uncaptured charge. This is the second half of the two-step payment flow, where first you created a charge with the capture option set to false.
