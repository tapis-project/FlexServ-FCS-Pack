"""Check the reviewed deployment catalog and optional pinned upstream parity."""
import json
from pathlib import Path
import re
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[1]
UPSTREAM = REPO.parent / "mistral.rs"
CATALOG = REPO / "docs/catalogs/mistralrs-0.9.5.json"


def documented_options(text):
    options = {}
    for line in text.splitlines():
        if not line.startswith("| `-"):
            continue
        syntax, default, _ = re.split(r"(?<!\\)\|", line)[1:-1]
        name = re.search(r"--([a-z0-9-]+)", syntax)[1]
        default = default.strip().strip("`")
        try:
            default = json.loads(default)
        except ValueError:
            default = default or None
        options[name] = default
    return options


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text())
        cls.flags = {flag["id"]: flag for flag in cls.catalog["flags"]}

    def test_ui_metadata_and_references(self):
        self.assertEqual(len(self.flags), len(self.catalog["flags"]))
        spellings = set()
        for name, flag in self.flags.items():
            with self.subTest(flag=name):
                for field in ("label", "group", "description", "when_to_set", "syntax", "sources"):
                    self.assertTrue(flag[field])
                self.assertEqual(flag["flag"], "--" + name)
                for spelling in [flag["flag"], *flag["aliases"]]:
                    self.assertNotIn(spelling, spellings)
                    spellings.add(spelling)
                self.assertIn(flag["values"]["type"], {"string", "boolean", "integer", "number", "path", "count", "json_object", "string_array"})
                if "enum" in flag["values"] and flag["cli_default"] is not None:
                    self.assertIn(flag["cli_default"], flag["values"]["enum"])
                self.assertIn(flag["omission"]["kind"], {"inferred", "fixed", "disabled"})
                self.assertEqual(flag["omission"]["best_effort"], flag["omission"]["kind"] == "inferred")
                self.assertTrue(flag["omission"]["behavior"])
                for relation in ("requires_all", "requires_any", "conflicts"):
                    self.assertTrue(set(flag[relation]) <= self.flags.keys())
                    self.assertNotIn(name, flag[relation])
                self.assertIn(flag["ui"]["visibility"], {"common", "advanced", "managed"})

    def test_counts_and_feature_gates(self):
        counts = self.catalog["counts"]
        self.assertEqual(counts["configuration_options"], len(self.flags))
        self.assertEqual(counts["configuration_options"], counts["serve_specific"] + counts["inherited_global"])
        self.assertEqual(counts["including_help_and_version"], len(self.flags) + len(self.catalog["informational_flags"]))
        gated = sum("code-execution" in f["applicability"]["build_features"] for f in self.flags.values())
        self.assertEqual(counts["configuration_without_code_execution"], len(self.flags) - gated)

    def test_launch_policy_is_separate_from_upstream_defaults(self):
        policy = self.catalog["launch_policy"]
        self.assertEqual(policy["required_environment"], {"MISTRALRS_NO_NCCL": "1"})
        self.assertEqual(policy["nodes"], 1)
        self.assertIn("RING_CONFIG", policy["forbidden_environment"])
        self.assertIn("MISTRALRS_MN_*", policy["forbidden_environment"])
        self.assertEqual(policy["gpu_visibility_environment"], "CUDA_VISIBLE_DEVICES")
        self.assertNotIn("cuda-visible-devices", self.flags)
        self.assertIsNone(self.flags["quant"]["cli_default"])
        self.assertFalse(self.flags["no-ui"]["cli_default"])
        self.assertIn("no-ui", policy["recommended_switches"])
        self.assertEqual(self.catalog["presets"]["speedy"]["tune_profile"], "fast")

    @unittest.skipUnless((UPSTREAM / "mistralrs-cli/src/args/mod.rs").exists(), "adjacent upstream checkout unavailable")
    def test_pinned_upstream_inventory_and_defaults(self):
        head = subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip()
        self.assertEqual(head, self.catalog["upstream"]["git_commit"], "Review the catalog for the new upstream revision")
        docs = UPSTREAM / "docs/src/content/docs/reference/cli"
        serve = (docs / "serve.md").read_text().split("## mistralrs serve auto")[0]
        expected = documented_options(serve)
        expected.update(documented_options((docs / "index.md").read_text()))
        self.assertEqual(set(expected), set(self.flags))
        for name, default in expected.items():
            with self.subTest(flag=name):
                self.assertEqual(self.flags[name]["cli_default"], default)
                for source in self.flags[name]["sources"]:
                    self.assertTrue((UPSTREAM / source).is_file(), source)

    @unittest.skipUnless((UPSTREAM / "mistralrs-cli/src/args/mod.rs").exists(), "adjacent upstream checkout unavailable")
    def test_build_feature_parity(self):
        source = (UPSTREAM / "mistralrs-cli/src/args/mod.rs").read_text()
        agent = source.split("pub struct AgentCliOptions {")[1].split("impl AgentCliOptions")[0]
        gated = re.findall(r'#\[cfg\(feature = "code-execution"\)\]\s*#\[arg\(long\)\]\s*pub (\w+):', agent)
        recorded = [name for name, f in self.flags.items() if "code-execution" in f["applicability"]["build_features"]]
        self.assertEqual({name.replace("_", "-") for name in gated}, set(recorded))


if __name__ == "__main__":
    unittest.main()
