"""Run the real commit hook in isolated Git repositories with a recording runner."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


HOOK = Path(__file__).resolve().parents[1] / ".githooks/pre-commit"


class PreCommitTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("GIT_")}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_AUTHOR_NAME="Hook test", GIT_AUTHOR_EMAIL="test@example.invalid",
                        GIT_COMMITTER_NAME="Hook test",
                        GIT_COMMITTER_EMAIL="test@example.invalid")
        self.git("init", "--quiet")
        scripts = self.root / "scripts"
        scripts.mkdir()
        runner = scripts / "test.sh"
        runner.write_text('#!/bin/sh\nprintf "called\\n" >> runner-calls\n'
                          'exit "${RUNNER_STATUS:-0}"\n')
        runner.chmod(0o755)
        self.write("existing.md")
        self.write("code.py")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "baseline")
        hooks = self.root / ".githooks"
        hooks.mkdir()
        shutil.copy2(HOOK, hooks / "pre-commit")
        self.git("config", "core.hooksPath", ".githooks")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, env=self.env,
                              capture_output=True, text=True, check=True, timeout=10)

    def write(self, name, content="initial content\n"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def check_hook(self, *, skipped=False, status=0, cwd=None):
        result = subprocess.run([str(self.root / ".githooks/pre-commit")],
                                cwd=cwd or self.root, env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, status, result.stderr)
        self.assertEqual((self.root / "runner-calls").exists(), not skipped)
        self.assertEqual("Skipping" in result.stdout, skipped and status == 0)

    def test_empty_staging_runs_tests(self):
        self.check_hook()

    def test_code_only_runs_tests(self):
        self.write("new.py")
        self.git("add", "new.py")
        self.check_hook()

    def test_markdown_addition_and_edit_skip(self):
        self.write("new.md")
        self.write("existing.md", "changed\n")
        self.git("add", "new.md", "existing.md")
        self.check_hook(skipped=True)

    def test_initial_commit_markdown_skips(self):
        self.git("checkout", "--orphan", "initial")
        self.git("rm", "-r", "--cached", ".")
        self.git("add", "existing.md")
        self.check_hook(skipped=True)

    def test_mixed_changes_run_tests(self):
        self.write("existing.md", "changed\n")
        self.write("code.py", "changed\n")
        self.git("add", "existing.md", "code.py")
        self.check_hook()

    def test_unstaged_code_does_not_prevent_skip(self):
        self.write("existing.md", "changed\n")
        self.git("add", "existing.md")
        self.write("code.py", "unstaged\n")
        self.write("untracked.py")
        self.check_hook(skipped=True)

    def test_unstaged_markdown_does_not_hide_staged_code(self):
        self.write("code.py", "changed\n")
        self.git("add", "code.py")
        self.write("existing.md", "unstaged\n")
        self.check_hook()

    def test_deletions(self):
        self.git("rm", "existing.md")
        self.check_hook(skipped=True)
        self.git("rm", "code.py")
        self.check_hook()

    def test_renames(self):
        for old, new, skipped in [("existing.md", "renamed.md", True),
                                  ("existing.md", "renamed.py", False),
                                  ("code.py", "renamed.md", False),
                                  ("code.py", "renamed.py", False)]:
            with self.subTest(old=old, new=new):
                self.git("mv", old, new)
                try:
                    self.check_hook(skipped=skipped)
                finally:
                    (self.root / "runner-calls").unlink(missing_ok=True)
                    self.git("reset", "--hard", "HEAD")

    def test_unusual_markdown_names(self):
        for name in ["space name.md", "tab\tname.md", "line\nbreak.md",
                     "-leading.md", "quote'\"slash\\.md", "nested/日本語.md"]:
            self.write(name)
            self.git("add", "--", name)
        self.check_hook(skipped=True)

    def test_non_markdown_suffixes(self):
        for name in ["upper.MD", "README", "file.md.txt", "name.md\ncode.py"]:
            with self.subTest(name=name):
                self.write(name)
                self.git("add", "--", name)
                self.check_hook()
                (self.root / "runner-calls").unlink()
                self.git("reset", "--hard", "HEAD")

    def test_runner_failure_propagates(self):
        self.env["RUNNER_STATUS"] = "23"
        self.check_hook(status=23)

    def test_runs_from_subdirectory(self):
        self.check_hook(cwd=self.root / "scripts")

    def test_git_commit_skips_markdown_even_with_failing_runner(self):
        self.write("existing.md", "changed\n")
        self.git("add", "existing.md")
        self.env["RUNNER_STATUS"] = "23"
        result = self.git("commit", "-m", "documentation")
        self.assertIn("Skipping", result.stdout + result.stderr)
        self.assertFalse((self.root / "runner-calls").exists())

    def test_git_commit_is_blocked_by_runner_failure(self):
        self.write("code.py", "changed\n")
        self.git("add", "code.py")
        self.env["RUNNER_STATUS"] = "23"
        before = self.git("rev-parse", "HEAD").stdout
        with self.assertRaises(subprocess.CalledProcessError):
            self.git("commit", "-m", "code")
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, before)
        self.assertEqual((self.root / "runner-calls").read_text(), "called\n")

    def test_git_inspection_failure_blocks_without_runner(self):
        binary = self.root / "bin"
        binary.mkdir()
        wrapper = binary / "git"
        wrapper.write_text('#!/bin/sh\nif [ "$1" = "$FAIL_GIT_COMMAND" ]; then\n'
                           '  printf "existing.md\\0"\n  exit 42\nfi\n'
                           'exec "$REAL_GIT" "$@"\n')
        wrapper.chmod(0o755)
        self.env["REAL_GIT"] = shutil.which("git", path=self.env["PATH"])
        self.env["PATH"] = str(binary) + os.pathsep + self.env["PATH"]
        for command in ["diff", "rev-parse"]:
            with self.subTest(command=command):
                self.env["FAIL_GIT_COMMAND"] = command
                self.check_hook(skipped=True, status=42)


if __name__ == "__main__":
    unittest.main()
