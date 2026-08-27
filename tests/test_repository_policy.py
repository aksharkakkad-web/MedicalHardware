import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositoryPolicyTests(unittest.TestCase):

    def run_git(self, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
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
        self.assertIn("actions/setup-python@v5", validation)
        self.assertIn("python3 -m pip install -e '.[dev]'", validation)
        self.assertIn("python3 -m pytest -q", validation)
        self.assertIn("python3 -m unittest discover", validation)
        self.assertLess(
            validation.index("python3 -m pip install -e '.[dev]'"),
            validation.index("python3 -m pytest -q"),
        )
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

    def test_agents_automatically_prepare_owned_work_branches(self) -> None:
        helper = ROOT / "scripts/start-work.sh"
        self.assertTrue(helper.is_file())
        self.assertTrue(helper.stat().st_mode & 0o111)

        help_result = subprocess.run(
            [str(helper), "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("backend", help_result.stdout)
        self.assertIn("frontend", help_result.stdout)

        agent_rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        claude_rules = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        skill = (ROOT / ".claude/skills/check-before-build/SKILL.md").read_text(encoding="utf-8")
        for rules in (agent_rules, claude_rules):
            self.assertIn("scripts/start-work.sh", rules)
            self.assertIn("Do not ask the founder to create a branch", rules)
        self.assertIn("scripts/start-work.sh", skill)
        self.assertIn("frontend", skill)
        self.assertIn("backend", skill)

    def test_work_branch_helper_creates_only_safe_owned_branches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            remote = temporary_root / "origin.git"
            seed = temporary_root / "seed"
            helper = ROOT / "scripts/start-work.sh"

            self.run_git("init", "--bare", str(remote), cwd=temporary_root)
            self.run_git("init", "-b", "main", str(seed), cwd=temporary_root)
            self.run_git("config", "user.name", "Test User", cwd=seed)
            self.run_git("config", "user.email", "test@example.com", cwd=seed)
            (seed / "scripts").mkdir()
            shutil.copy2(helper, seed / "scripts/start-work.sh")
            (seed / "README.md").write_text("test repository\n", encoding="utf-8")
            self.run_git("add", ".", cwd=seed)
            self.run_git("commit", "-m", "seed", cwd=seed)
            self.run_git("remote", "add", "origin", str(remote), cwd=seed)
            self.run_git("push", "-u", "origin", "main", cwd=seed)
            self.run_git("--git-dir", str(remote), "symbolic-ref", "HEAD", "refs/heads/main", cwd=temporary_root)

            client = temporary_root / "client"
            self.run_git("clone", str(remote), str(client), cwd=temporary_root)
            result = subprocess.run(
                [str(client / "scripts/start-work.sh"), "backend", "Device API"],
                cwd=client,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.run_git("branch", "--show-current", cwd=client).stdout.strip(), "akshar/backend-device-api")

            existing_branch = "akshar/backend-existing-task"
            self.run_git("branch", existing_branch, cwd=seed)
            self.run_git("push", "origin", existing_branch, cwd=seed)
            duplicate_client = temporary_root / "duplicate-client"
            self.run_git("clone", str(remote), str(duplicate_client), cwd=temporary_root)
            duplicate = subprocess.run(
                [str(duplicate_client / "scripts/start-work.sh"), "backend", "Existing Task"],
                cwd=duplicate_client,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(duplicate.returncode, 4)
            self.assertIn("already exists on origin", duplicate.stderr)

            ahead_client = temporary_root / "ahead-client"
            self.run_git("clone", str(remote), str(ahead_client), cwd=temporary_root)
            self.run_git("config", "user.name", "Test User", cwd=ahead_client)
            self.run_git("config", "user.email", "test@example.com", cwd=ahead_client)
            self.run_git("commit", "--allow-empty", "-m", "local only", cwd=ahead_client)
            ahead = subprocess.run(
                [str(ahead_client / "scripts/start-work.sh"), "frontend", "Resident Dashboard"],
                cwd=ahead_client,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(ahead.returncode, 3)
            self.assertIn("does not match origin/main", ahead.stderr)
            self.assertEqual(self.run_git("branch", "--show-current", cwd=ahead_client).stdout.strip(), "main")


if __name__ == "__main__":
    unittest.main()
