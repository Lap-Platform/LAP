#!/usr/bin/env python3
"""LangChain integration example."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from lap.middleware import LAPDocLoader

loader = LAPDocLoader("../../output/stripe-charges.lap")
docs = loader.load()

print(f"Loaded {len(docs)} endpoint documents\n")
for doc in docs:
    print(f"--- {doc.metadata['method']} {doc.metadata['path']} ---")
    print(doc.page_content[:200])
    print()

# Full context mode
full = loader.load_full()
print(f"Full context: {len(full[0].page_content)} chars")
