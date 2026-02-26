"""
Plaid recurring transfer management based on account balance.

Endpoints used (from Plaid DocLean spec):
  POST /accounts/balance/get   -- Retrieve real-time balance data
  POST /transfer/recurring/create -- Create a recurring transfer
  POST /transfer/recurring/list   -- List recurring transfers
  POST /transfer/recurring/cancel -- Cancel a recurring transfer
"""

import uuid
from datetime import date

import requests


BASE_URL = "https://production.plaid.com"


def manage_recurring_transfer(
    client_id: str,
    secret: str,
    access_token: str,
    account_x_id: str,
    account_y_id: str,
    user_legal_name: str = "Account Holder",
    balance_threshold: float = 100.0,
    transfer_amount: str = "5.00",
) -> dict:
    """Check balance on account X and manage recurring transfers accordingly.

    If the current balance on account X is above *balance_threshold* (default
    $100), a monthly recurring credit transfer of *transfer_amount* (default
    $5.00) is created to account Y.

    If the balance is at or below the threshold, ALL active recurring transfers
    are cancelled.

    Parameters
    ----------
    client_id : str
        Plaid API client_id.
    secret : str
        Plaid API secret.
    access_token : str
        Access token for the Item that owns both accounts.
    account_x_id : str
        Plaid account_id whose balance is checked.
    account_y_id : str
        Plaid account_id that will receive the recurring transfer.
    user_legal_name : str
        Legal name of the account holder (required by /transfer/recurring/create).
    balance_threshold : float
        Dollar threshold above which the transfer is created (default 100).
    transfer_amount : str
        Decimal-string dollar amount for the recurring transfer (default "5.00").

    Returns
    -------
    dict
        A summary with keys:
          - "action": "created" | "cancelled_all" | "no_action"
          - "balance": the current balance found on account X
          - "details": API response body or list of cancel results
    """
    headers = {"Content-Type": "application/json"}

    # ------------------------------------------------------------------
    # 1. Retrieve real-time balance for account X
    #    POST /accounts/balance/get
    #    @required {access_token}
    #    @optional {client_id, secret, options}
    #    @returns  {accounts: [map], item: map, request_id: str}
    # ------------------------------------------------------------------
    balance_payload = {
        "client_id": client_id,
        "secret": secret,
        "access_token": access_token,
        "options": {
            "account_ids": [account_x_id],
        },
    }

    balance_resp = requests.post(
        f"{BASE_URL}/accounts/balance/get",
        json=balance_payload,
        headers=headers,
    )
    balance_resp.raise_for_status()
    balance_data = balance_resp.json()

    # Locate account X in the returned accounts list.
    account_x = None
    for acct in balance_data.get("accounts", []):
        if acct.get("account_id") == account_x_id:
            account_x = acct
            break

    if account_x is None:
        raise ValueError(
            f"Account {account_x_id} not found in balance response. "
            f"Returned accounts: {[a.get('account_id') for a in balance_data.get('accounts', [])]}"
        )

    # The balances object contains 'current', 'available', etc.
    current_balance = account_x.get("balances", {}).get("current")
    if current_balance is None:
        raise ValueError(
            f"No current balance available for account {account_x_id}."
        )

    # ------------------------------------------------------------------
    # 2a. Balance > threshold --> create monthly recurring transfer to Y
    #     POST /transfer/recurring/create
    #     @required {access_token, account_id, amount, description, device,
    #                idempotency_key, network, schedule, type, user, user_present}
    #     @optional {ach_class, client_id, funding_account_id,
    #                iso_currency_code, secret, test_clock_id}
    #     @returns  {decision, decision_rationale?, recurring_transfer, request_id}
    # ------------------------------------------------------------------
    if current_balance > balance_threshold:
        create_payload = {
            "client_id": client_id,
            "secret": secret,
            "access_token": access_token,
            "account_id": account_y_id,
            "amount": transfer_amount,
            "description": "Monthly recurring transfer",
            "type": "credit",
            "network": "ach",
            "ach_class": "ppd",
            "user": {
                "legal_name": user_legal_name,
            },
            "user_present": False,
            "device": {
                "ip_address": "0.0.0.0",
                "user_agent": "PlaidRecurringManager/1.0",
            },
            "schedule": {
                "interval_unit": "month",
                "interval_count": 1,
                "interval_execution_day": 1,
                "start_date": date.today().isoformat(),
            },
            "idempotency_key": uuid.uuid4().hex[:50],
        }

        create_resp = requests.post(
            f"{BASE_URL}/transfer/recurring/create",
            json=create_payload,
            headers=headers,
        )
        create_resp.raise_for_status()
        create_data = create_resp.json()

        return {
            "action": "created",
            "balance": current_balance,
            "details": create_data,
        }

    # ------------------------------------------------------------------
    # 2b. Balance <= threshold --> cancel ALL recurring transfers
    #     Step 1: list them via POST /transfer/recurring/list
    #       @optional {client_id, secret, count, offset, start_time, end_time,
    #                  funding_account_id}
    #       @returns  {recurring_transfers: [map], request_id}
    #
    #     Step 2: cancel each via POST /transfer/recurring/cancel
    #       @required {recurring_transfer_id}
    #       @optional {client_id, secret}
    #       @returns  {request_id}
    # ------------------------------------------------------------------
    list_payload = {
        "client_id": client_id,
        "secret": secret,
        "count": 250,
        "offset": 0,
    }

    list_resp = requests.post(
        f"{BASE_URL}/transfer/recurring/list",
        json=list_payload,
        headers=headers,
    )
    list_resp.raise_for_status()
    list_data = list_resp.json()

    recurring_transfers = list_data.get("recurring_transfers", [])

    if not recurring_transfers:
        return {
            "action": "no_action",
            "balance": current_balance,
            "details": "No recurring transfers found to cancel.",
        }

    cancel_results = []
    for rt in recurring_transfers:
        rt_id = rt.get("recurring_transfer_id")
        rt_status = rt.get("status", "")

        # Only cancel transfers that are still active (not already cancelled/expired).
        if rt_status in ("cancelled", "expired"):
            continue

        cancel_payload = {
            "client_id": client_id,
            "secret": secret,
            "recurring_transfer_id": rt_id,
        }

        cancel_resp = requests.post(
            f"{BASE_URL}/transfer/recurring/cancel",
            json=cancel_payload,
            headers=headers,
        )
        cancel_resp.raise_for_status()
        cancel_results.append(
            {
                "recurring_transfer_id": rt_id,
                "cancel_response": cancel_resp.json(),
            }
        )

    if not cancel_results:
        return {
            "action": "no_action",
            "balance": current_balance,
            "details": "All recurring transfers were already cancelled or expired.",
        }

    return {
        "action": "cancelled_all",
        "balance": current_balance,
        "details": cancel_results,
    }
