#!/usr/bin/env python3
"""Tests for LAP SDK."""
import sys
import os
import unittest
from pathlib import Path

# Setup paths -- SDK package and project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from lap import LAPClient, Registry
from lap.middleware import LAPDocLoader

from lap.core.parser import parse_lap as _parse_lap

FIXTURES = Path(__file__).resolve().parents[2] / ".." / "output"
STRIPE = str(FIXTURES / "stripe-charges.lap")


class TestLAPClient(unittest.TestCase):
    def setUp(self):
        self.client = LAPClient()
        if not Path(STRIPE).exists():
            self.skipTest("stripe-charges.lap not found")
        self.docs = self.client.load(STRIPE)

    def test_load_api_name(self):
        self.assertIn("Stripe", self.docs.api_name)

    def test_endpoints_loaded(self):
        self.assertGreater(len(self.docs.endpoints), 0)

    def test_get_endpoint(self):
        ep = self.docs.get_endpoint("POST", "/v1/charges")
        self.assertIsNotNone(ep)
        self.assertEqual(ep.method, "POST")
        self.assertGreater(len(ep.required_params), 0)

    def test_get_endpoint_not_found(self):
        ep = self.docs.get_endpoint("DELETE", "/nope")
        self.assertIsNone(ep)

    def test_to_context(self):
        ctx = self.docs.to_context(lean=False)
        self.assertIn("@endpoint", ctx)

    def test_lean_smaller(self):
        full = self.docs.to_context(lean=False)
        lean = self.docs.to_context(lean=True)
        self.assertLess(len(lean), len(full))

    def test_token_count(self):
        count = self.docs.token_count()
        self.assertGreater(count, 0)

    def test_required_params(self):
        ep = self.docs.get_endpoint("POST", "/v1/charges")
        names = [p.name for p in ep.required_params]
        self.assertIn("amount", names)
        self.assertIn("currency", names)


class TestRegistry(unittest.TestCase):
    def setUp(self):
        if not FIXTURES.exists():
            self.skipTest("output/ not found")
        self.registry = Registry(str(FIXTURES))

    def test_list(self):
        items = self.registry.list()
        self.assertGreater(len(items), 0)

    def test_get(self):
        doc = self.registry.get("stripe")
        self.assertIsNotNone(doc)

    def test_search(self):
        results = self.registry.search("stripe")
        self.assertGreater(len(results), 0)

    def test_get_missing(self):
        doc = self.registry.get("nonexistent-api-xyz")
        self.assertIsNone(doc)


class TestMiddleware(unittest.TestCase):
    def setUp(self):
        if not Path(STRIPE).exists():
            self.skipTest("stripe-charges.lap not found")

    def test_load_documents(self):
        loader = LAPDocLoader(STRIPE)
        docs = loader.load()
        self.assertGreater(len(docs), 0)
        self.assertIn("method", docs[0].metadata)

    def test_load_full(self):
        loader = LAPDocLoader(STRIPE)
        docs = loader.load_full()
        self.assertEqual(len(docs), 1)
        self.assertIn("@endpoint", docs[0].page_content)


class TestParser(unittest.TestCase):
    def test_parse_minimal(self):
        text = """@lap v0.1
@api Test API
@base https://example.com

@endpoint GET /test
@required {id: str}
@returns(200) {result: str}
"""
        spec = _parse_lap(text)
        self.assertEqual(spec.api_name, "Test API")
        self.assertEqual(len(spec.endpoints), 1)
        self.assertEqual(spec.endpoints[0].method, "get")


if __name__ == "__main__":
    unittest.main()
