import os
import subprocess


class GitTools:
    """Provide basic Git operations."""

    @staticmethod
    def git_pull(repo_path: str = "~/thebuilder") -> str:
        """Run ``git pull`` in ``repo_path`` and return command output."""
        path = os.path.expanduser(repo_path)
        result = subprocess.run(
            ["git", "pull"],
            cwd=path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout.strip()
