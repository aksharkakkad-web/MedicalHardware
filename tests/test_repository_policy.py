import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositoryPolicyTests(unittest.TestCase):
    def test_generated_and_secret_files_are_ignored(self) -> None:
        rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for expected in (".DS_Store", "__pycache__/", "*.py[cod]", ".env*", "!.env.example"):
            self.assertIn(expected, rules)

    def test_greptile_rechecks_updates_and_gates_on_clean_reviews(self) -> None:
        config = json.loads((ROOT / ".greptile/config.json").read_text(encoding="utf-8"))
        self.assertTrue(config["triggerOnUpdates"])
        self.assertTrue(config["statusCheck"])
        self.assertTrue(config["includeConfidenceScore"])
        self.assertTrue(config["autoApprove"]["enabled"])
        self.assertEqual(config["autoApprove"]["riskCeiling"], "high")

    def test_greptile_context_files_exist(self) -> None:
        manifest = json.loads((ROOT / ".greptile/files.json").read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            self.assertTrue((ROOT / entry["path"]).is_file(), entry["path"])

    def test_pull_requests_run_validation_and_enable_squash_automerge(self) -> None:
        validation = (ROOT / ".github/workflows/repository-validation.yml").read_text(encoding="utf-8")
        automerge = (ROOT / ".github/workflows/enable-automerge.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", validation)
        self.assertIn("python3 -m unittest discover", validation)
        self.assertIn("pull_request_target:", automerge)
        self.assertIn("gh pr merge --auto --squash", automerge)
        self.assertIn("head.repo.full_name == github.repository", automerge)
        self.assertIn("vars.AUTO_MERGE_ENABLED == 'true'", automerge)

    def test_graphify_hooks_are_portable(self) -> None:
        for relative in (".claude/settings.json", ".codex/hooks.json"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("/Users/", text)
            json.loads(text)

    def test_shared_skill_links_resolve(self) -> None:
        skills = ROOT / ".agents/skills"
        expected = {
            "agent-browser",
            "agent-reach",
            "check-before-build",
            "ego-browser",
            "graphify",
            "greploop",
            "last30days",
            "twitter-algorithm-optimizer",
        }
        self.assertEqual({path.name for path in skills.iterdir()}, expected)
        for skill in skills.iterdir():
            self.assertTrue(skill.is_symlink(), skill)
            self.assertTrue((skill / "SKILL.md").is_file(), skill)


if __name__ == "__main__":
    unittest.main()
