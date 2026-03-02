#!/usr/bin/env python3
"""Basic LAP SDK usage."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from lap import LAPClient

client = LAPClient()
docs = client.load("../../output/stripe-charges.lap")

print(f"API: {docs.api_name} | Base: {docs.base_url} | Version: {docs.version}")
print(f"Endpoints: {len(docs.endpoints)}\n")

ep = docs.get_endpoint("POST", "/v1/charges")
if ep:
    print(f"=== {ep.method} {ep.path} ===")
    print(f"Summary: {ep.summary}")
    print(f"Required params: {[p.name for p in ep.required_params]}")
    print(f"Optional params: {[p.name for p in ep.optional_params]}")
    if ep.response_schema:
        print(f"Response: {ep.response_schema.status_code} - {ep.response_schema.description}")
