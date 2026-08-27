from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path


def _suite(max_tags: int, max_title: int) -> unittest.TestSuite:
    from registry_app import Registry, ValidationError

    class RegistryContract(unittest.TestCase):
        def setUp(self) -> None:
            self.temporary = tempfile.TemporaryDirectory()
            self.path = Path(self.temporary.name) / "registry.json"

        def tearDown(self) -> None:
            self.temporary.cleanup()

        def test_add_get_and_exact_shape(self) -> None:
            registry = Registry(self.path)
            item = registry.add(
                "alpha-1",
                "  Alpha  ",
                "https://example.com/a",
                [" Work ", "work", "News"],
            )
            self.assertEqual(
                item,
                {
                    "id": "alpha-1",
                    "title": "Alpha",
                    "url": "https://example.com/a",
                    "tags": ["news", "work"],
                },
            )
            self.assertEqual(registry.get("alpha-1"), item)

        def test_persists_across_instances_and_sorts(self) -> None:
            first = Registry(self.path)
            first.add("zeta", "Zeta", "http://example.org/z", [])
            first.add("beta", "Beta", "https://example.org/b", ["x"])
            second = Registry(self.path)
            self.assertEqual([item["id"] for item in second.list_items()], ["beta", "zeta"])
            self.assertEqual(second.get("beta")["title"], "Beta")

        def test_filter_and_delete_are_persistent(self) -> None:
            registry = Registry(self.path)
            registry.add("one", "One", "https://example.com/1", ["Red", "blue"])
            registry.add("two", "Two", "https://example.com/2", ["blue"])
            self.assertEqual(
                [item["id"] for item in registry.list_items(" BLUE ")],
                ["one", "two"],
            )
            self.assertTrue(registry.delete("one"))
            self.assertFalse(registry.delete("one"))
            self.assertIsNone(Registry(self.path).get("one"))

        def test_duplicate_id_does_not_overwrite(self) -> None:
            registry = Registry(self.path)
            original = registry.add("same", "Original", "https://example.com/original", [])
            with self.assertRaises(ValidationError):
                registry.add("same", "Replacement", "https://example.com/new", [])
            self.assertEqual(Registry(self.path).get("same"), original)

        def test_rejects_invalid_identity_title_and_url(self) -> None:
            registry = Registry(self.path)
            invalid = [
                ("Bad ID", "Title", "https://example.com"),
                ("ok", "   ", "https://example.com"),
                ("ok", "x" * (max_title + 1), "https://example.com"),
                ("ok", "Title", "ftp://example.com/file"),
                ("ok", "Title", "https:///missing-host"),
            ]
            for item_id, title, url in invalid:
                with self.subTest(item_id=item_id, title=title, url=url):
                    with self.assertRaises(ValidationError):
                        registry.add(item_id, title, url, [])
            self.assertEqual(registry.list_items(), [])

        def test_tag_constraints_and_normalization(self) -> None:
            registry = Registry(self.path)
            tags = [f"tag{index}" for index in range(max_tags)]
            item = registry.add(
                "tags",
                "Tags",
                "https://example.com/t",
                list(reversed(tags)),
            )
            self.assertEqual(item["tags"], sorted(tags))
            with self.assertRaises(ValidationError):
                registry.add("too-many", "Too many", "https://example.com/m", tags + ["extra"])
            with self.assertRaises(ValidationError):
                registry.add("empty-tag", "Empty", "https://example.com/e", [" "])

        def test_malformed_persistence_is_rejected(self) -> None:
            self.path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(ValidationError):
                Registry(self.path)
            self.path.write_text(json.dumps({"unexpected": []}), encoding="utf-8")
            with self.assertRaises(ValidationError):
                Registry(self.path)

        def test_storage_is_json_and_none_tags_are_supported(self) -> None:
            registry = Registry(self.path)
            registry.add("safe", "Safe", "https://example.com", None)
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.assertIsInstance(payload, (dict, list))

    return unittest.defaultTestLoader.loadTestsFromTestCase(RegistryContract)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-tags", type=int, required=True)
    parser.add_argument("--max-title", type=int, required=True)
    args = parser.parse_args()
    suite = _suite(args.max_tags, args.max_title)
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    print(json.dumps({
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
    }))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
