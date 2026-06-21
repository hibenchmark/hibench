from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hibench.github_stars import (
    GitHubStarsUpdater,
    agent_links,
    fetch_github_stars,
    github_stars_settings_from_env,
    load_github_stars,
)


class GitHubStarsTests(unittest.TestCase):
    def test_agent_links_load_from_agent_metadata(self) -> None:
        links = agent_links("codex")

        self.assertEqual(links.official_url, "https://openai.com/codex/")
        self.assertEqual(links.github_repo, "openai/codex")
        self.assertEqual(links.github_url, "https://github.com/openai/codex")

    def test_fetch_github_stars_reads_stargazer_count(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return json.dumps({"stargazers_count": 1234}).encode()

        with patch(
            "hibench.github_stars.urlopen", return_value=FakeResponse()
        ) as open_:
            stars = fetch_github_stars(
                "openai/codex",
                api_base_url="https://api.github.test",
                token="test-token",
            )

        self.assertEqual(stars, 1234)
        request = open_.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.github.test/repos/openai/codex")
        self.assertEqual(request.headers["Authorization"], "Bearer test-token")

    def test_settings_load_token_from_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / ".env").write_text("GITHUB_TOKEN=dotenv-token\n", encoding="utf-8")
            old_cwd = Path.cwd()
            try:
                os.chdir(path)
                with patch.dict(os.environ, {}, clear=True):
                    settings = github_stars_settings_from_env()
            finally:
                os.chdir(old_cwd)

        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["token_env"], "GITHUB_TOKEN")
        self.assertTrue(settings["token_present"])
        self.assertEqual(Path(settings["dotenv_path"]).name, ".env")

    def test_updater_writes_star_snapshot_for_eligible_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            updater = GitHubStarsUpdater(
                out_dir=tmp,
                api_base_url="https://api.github.test",
                token="test-token",
                fetcher=lambda *_args, **_kwargs: 4321,
            )

            result = updater.update_agent("codex")

            self.assertTrue(result.updated)
            self.assertEqual(result.github_stars, 4321)
            data = load_github_stars(Path(tmp) / "github_stars.json")
            self.assertEqual(data["agents"]["codex"]["github_repo"], "openai/codex")
            self.assertEqual(data["agents"]["codex"]["github_stars"], 4321)
            self.assertTrue(data["agents"]["codex"]["updated_at"])

    def test_updater_fetches_each_agent_once_per_process(self) -> None:
        calls = 0

        def fake_fetcher(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            return 4321

        with tempfile.TemporaryDirectory() as tmp:
            updater = GitHubStarsUpdater(out_dir=tmp, fetcher=fake_fetcher)

            first = updater.update_agent("codex")
            second = updater.update_agent("codex")

            self.assertTrue(first.updated)
            self.assertEqual(second.status, "already_attempted")
            self.assertEqual(calls, 1)

    def test_updater_skips_agents_without_github_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            updater = GitHubStarsUpdater(out_dir=tmp)

            result = updater.update_agent("cursor-cli")

            self.assertEqual(result.status, "not_eligible")
            self.assertFalse((Path(tmp) / "github_stars.json").exists())


if __name__ == "__main__":
    unittest.main()
