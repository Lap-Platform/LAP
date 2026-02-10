#!/usr/bin/env python3
"""Token comparison demo — full vs lean LAP."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from lap import LAPClient

client = LAPClient()
docs = client.load("../../output/stripe-charges.lap")

full_tokens = docs.token_count(lean=False)
lean_tokens = docs.token_count(lean=True)
savings = ((full_tokens - lean_tokens) / full_tokens * 100) if full_tokens else 0

print(f"API: {docs.api_name}")
print(f"Full docs:  {full_tokens:,} tokens")
print(f"Lean mode:  {lean_tokens:,} tokens")
print(f"Savings:    {savings:.1f}%")
print(f"\n--- Full context preview (first 300 chars) ---")
print(docs.to_context(lean=False)[:300])
print(f"\n--- Lean context preview (first 300 chars) ---")
print(docs.to_context(lean=True)[:300])
