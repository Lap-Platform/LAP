# Stripe Charges API API Documentation

Base URL: https://api.stripe.com

Version: 2024-12-18

## Authentication

Bearer bearer

## POST /v1/charges

Create a charge

### Required Parameters

- **amount** (int):  - Amount intended to be collected by this payment, in cents.
- **currency** (str):  - Three-letter ISO 4217 currency code, in lowercase.

### Optional Parameters

- **source** (str):  - A payment source to be charged. This can be the ID of a card, a bank account, a source, a token, or a connected account.
- **customer** (str):  - The ID of an existing customer that will be charged in this request.
- **description** (str):  - An arbitrary string attached to the object. Often useful for displaying to users.
- **metadata** (map):  - Set of key-value pairs for storing additional information about the charge.
- **receipt_email** (str):  - The email address to which the receipt for this charge will be sent.
- **shipping** (map):  - Shipping information for the charge.
- **statement_descriptor** (str):  - For card charges, use statement_descriptor_suffix. Otherwise, you can use this value as the complete description.
- **capture** (bool):  - Whether to immediately capture the charge. Defaults to true.
- **transfer_data** (map):  - An optional dictionary including the account to automatically transfer to as part of a destination charge.
- **application_fee_amount** (int):  - A fee in cents that will be applied to the charge and transferred to the application owner's Stripe account.
- **on_behalf_of** (str):  - The Stripe account ID for which these funds are intended.

## GET /v1/charges

List all charges

### Optional Parameters

- **customer** (str):  - Only return charges for the customer specified by this customer ID.
- **created** (map):  - A filter on the list based on the created field.
- **limit** (int):  - A limit on the number of objects to be returned. Limit can range between 1 and 100.
- **starting_after** (str):  - A cursor for pagination. starting_after is the ID of the last object.
- **ending_before** (str):  - A cursor for pagination. ending_before is the ID of the first object.

## GET /v1/charges/{charge}

Retrieve a charge

### Required Parameters

- **charge** (str):  - The identifier of the charge to be retrieved.

## POST /v1/charges/{charge}

Update a charge

### Required Parameters

- **charge** (str):  - The identifier of the charge to be updated.

### Optional Parameters

- **description** (str):  - An arbitrary string attached to the object.
- **metadata** (map):  - Set of key-value pairs for additional information.
- **receipt_email** (str):  - The email address to send the receipt to.
- **shipping** (map):  - Shipping information for the charge.
- **fraud_details** (map):  - A set of key-value pairs for fraud details reporting.
- **transfer_group** (str):  - A string that identifies this transaction as part of a group.

## POST /v1/charges/{charge}/capture

Capture a charge

### Required Parameters

- **charge** (str):  - The identifier of the charge to be captured.

### Optional Parameters

- **amount** (int):  - The amount to capture, which must be less than or equal to the original amount.
- **receipt_email** (str):  - The email address to send the receipt to.
- **statement_descriptor** (str):  - For card charges, use statement_descriptor_suffix.
- **application_fee_amount** (int):  - An application fee amount to capture, must be less than or equal to the original amount.
- **transfer_data** (map):  - Transfer data for destination charges.
