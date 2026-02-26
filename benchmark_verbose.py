"""
Plaid API integration: balance-based conditional bank transfer management.

Uses the Plaid Bank Transfer API endpoints as documented in the OpenAPI spec
(version 2020-09-14_1.334.0) at https://production.plaid.com.

Endpoints used:
  - POST /accounts/balance/get
  - POST /bank_transfer/create
  - POST /bank_transfer/list
  - POST /bank_transfer/cancel
"""

import uuid
import requests


PLAID_BASE_URL = "https://sandbox.plaid.com"


def manage_recurring_transfer(
    access_token: str,
    account_x_id: str,
    account_y_id: str,
    client_id: str,
    secret: str,
    base_url: str = PLAID_BASE_URL,
    transfer_amount: str = "5.00",
    balance_threshold: float = 100.0,
    user_legal_name: str = "Account Holder",
    network: str = "ach",
    custom_tag: str = "recurring_monthly_5",
) -> dict:
    """
    Check the balance of account X, then either create a $5 transfer to
    account Y or cancel all existing pending/cancellable transfers.

    Logic:
      1. Fetch the balance for account_x_id via /accounts/balance/get.
      2. If the available balance (falling back to current) is above
         $balance_threshold, create a bank transfer of $transfer_amount
         from account X to account Y via /bank_transfer/create.
      3. If the balance is at or below $balance_threshold, list all
         bank transfers via /bank_transfer/list and cancel every one
         that is still cancellable via /bank_transfer/cancel.

    Args:
        access_token: Plaid access token for the Item containing the accounts.
        account_x_id: The Plaid account_id to check the balance of (source).
        account_y_id: The Plaid account_id to transfer funds to (destination).
        client_id: Plaid API client_id.
        secret: Plaid API secret.
        base_url: Plaid environment base URL (default: sandbox).
        transfer_amount: Decimal string amount to transfer (default "5.00").
        balance_threshold: Dollar threshold above which a transfer is created.
        user_legal_name: Legal name of the destination account holder.
        network: ACH network to use ("ach", "same-day-ach", or "wire").
        custom_tag: Tag applied to created transfers for identification.

    Returns:
        A dict with keys:
          - "action": "transfer_created" | "transfers_cancelled" | "no_action"
          - "balance": the balance value that was checked
          - "details": action-specific payload (created transfer or cancel results)
    """

    # -----------------------------------------------------------------
    # Step 1: Get account balance for account X
    # POST /accounts/balance/get
    # -----------------------------------------------------------------
    balance_url = f"{base_url}/accounts/balance/get"
    balance_payload = {
        "client_id": client_id,
        "secret": secret,
        "access_token": access_token,
        "options": {
            "account_ids": [account_x_id],
        },
    }

    balance_response = requests.post(balance_url, json=balance_payload)
    balance_response.raise_for_status()
    balance_data = balance_response.json()

    # Find account X in the response
    account_x = None
    for account in balance_data.get("accounts", []):
        if account["account_id"] == account_x_id:
            account_x = account
            break

    if account_x is None:
        raise ValueError(
            f"Account {account_x_id} not found in balance response. "
            f"Available accounts: {[a['account_id'] for a in balance_data.get('accounts', [])]}"
        )

    # Prefer available balance; fall back to current balance
    balances = account_x["balances"]
    balance_value = balances.get("available")
    if balance_value is None:
        balance_value = balances.get("current", 0)

    # -----------------------------------------------------------------
    # Step 2: If balance > $100, create a bank transfer of $5
    # POST /bank_transfer/create
    # -----------------------------------------------------------------
    if balance_value > balance_threshold:
        create_url = f"{base_url}/bank_transfer/create"

        # Generate a unique idempotency key (max 50 chars)
        idempotency_key = uuid.uuid4().hex[:50]

        create_payload = {
            "client_id": client_id,
            "secret": secret,
            "access_token": access_token,
            "account_id": account_y_id,
            "idempotency_key": idempotency_key,
            "type": "credit",
            "network": network,
            "amount": transfer_amount,
            "iso_currency_code": "USD",
            "description": "Mo transfer",
            "ach_class": "ppd",
            "user": {
                "legal_name": user_legal_name,
            },
            "custom_tag": custom_tag,
        }

        create_response = requests.post(create_url, json=create_payload)
        create_response.raise_for_status()
        create_data = create_response.json()

        return {
            "action": "transfer_created",
            "balance": balance_value,
            "details": {
                "bank_transfer": create_data["bank_transfer"],
                "request_id": create_data["request_id"],
            },
        }

    # -----------------------------------------------------------------
    # Step 3: If balance <= $100, cancel ALL cancellable bank transfers
    # POST /bank_transfer/list  then  POST /bank_transfer/cancel
    # -----------------------------------------------------------------
    else:
        list_url = f"{base_url}/bank_transfer/list"
        cancel_url = f"{base_url}/bank_transfer/cancel"

        cancelled = []
        skipped = []
        offset = 0
        page_size = 25  # API maximum per page

        # Paginate through all transfers
        while True:
            list_payload = {
                "client_id": client_id,
                "secret": secret,
                "count": page_size,
                "offset": offset,
            }

            list_response = requests.post(list_url, json=list_payload)
            list_response.raise_for_status()
            list_data = list_response.json()

            transfers = list_data.get("bank_transfers", [])
            if not transfers:
                break

            for transfer in transfers:
                transfer_id = transfer["id"]
                is_cancellable = transfer.get("cancellable", False)
                status = transfer.get("status", "")

                if is_cancellable and status not in ("cancelled", "failed", "reversed"):
                    cancel_payload = {
                        "client_id": client_id,
                        "secret": secret,
                        "bank_transfer_id": transfer_id,
                    }

                    try:
                        cancel_response = requests.post(cancel_url, json=cancel_payload)
                        cancel_response.raise_for_status()
                        cancelled.append({
                            "bank_transfer_id": transfer_id,
                            "request_id": cancel_response.json().get("request_id"),
                        })
                    except requests.exceptions.HTTPError as e:
                        skipped.append({
                            "bank_transfer_id": transfer_id,
                            "error": str(e),
                        })
                else:
                    skipped.append({
                        "bank_transfer_id": transfer_id,
                        "reason": f"not cancellable (status={status}, cancellable={is_cancellable})",
                    })

            # If we got fewer results than page_size, we have reached the end
            if len(transfers) < page_size:
                break

            offset += page_size

        action = "transfers_cancelled" if cancelled else "no_action"

        return {
            "action": action,
            "balance": balance_value,
            "details": {
                "cancelled": cancelled,
                "skipped": skipped,
                "total_cancelled": len(cancelled),
                "total_skipped": len(skipped),
            },
        }
