import json
import tomllib
import unittest

from hibench.agents import ROOT, list_agent_ids, load_agent


class AgentTests(unittest.TestCase):
    def test_agents_have_public_link_metadata(self) -> None:
        for agent_id in list_agent_ids():
            with self.subTest(agent_id=agent_id):
                links = load_agent(agent_id).raw.get("links")
                self.assertIsInstance(links, dict)
                self.assertTrue(links["official_url"].startswith("https://"))
                github_repo = links.get("github_repo", "")
                if github_repo:
                    self.assertEqual(github_repo.count("/"), 1)

    def test_codex_agent_loads(self) -> None:
        self.assertIn("codex", list_agent_ids())
        spec = load_agent("codex")
        self.assertEqual(spec.version, "0.139.0")
        self.assertEqual(spec.command[-1], "{prompt}")
        self.assertEqual(spec.parser_id, "codex")
        self.assertEqual(spec.version_build_arg, "CODEX_VERSION")
        self.assertEqual(
            spec.version_source, {"type": "npm", "package": "@openai/codex"}
        )

    def test_claude_code_agent_loads(self) -> None:
        self.assertIn("claude-code", list_agent_ids())
        spec = load_agent("claude-code")
        self.assertEqual(spec.version, "2.1.177")
        self.assertEqual(spec.command[:2], ["-p", "{prompt}"])
        self.assertEqual(spec.parser_id, "claude-code")
        self.assertEqual(spec.version_build_arg, "CLAUDE_CODE_VERSION")
        self.assertEqual(
            spec.version_source,
            {"type": "npm", "package": "@anthropic-ai/claude-code"},
        )
        self.assertEqual(
            spec.raw["benchmark_exclusions"],
            {
                "2.1.69": (
                    "Non-comparable benchmark capture; primary request includes "
                    "Claude Code deferred-tool bootstrap as a user message before "
                    "the actual prompt under the current harness."
                ),
                "2.1.105": (
                    "Non-comparable benchmark capture; session-title generation "
                    "request is captured before the primary coding-agent request "
                    "under the current harness."
                ),
                "2.1.107": (
                    "Non-comparable benchmark capture; session-title generation "
                    "request is captured before the primary coding-agent request "
                    "under the current harness."
                ),
            },
        )
        self.assertEqual(spec.env["ANTHROPIC_BASE_URL"], "{base_url_root}")

    def test_cline_agent_loads(self) -> None:
        self.assertIn("cline", list_agent_ids())
        spec = load_agent("cline")
        self.assertEqual(spec.version, "3.0.24")
        self.assertEqual(
            spec.command[:4], ["--json", "--cwd", "/workspace", "--data-dir"]
        )
        self.assertIn("--provider", spec.command)
        self.assertEqual(spec.parser_id, "cline")
        self.assertEqual(spec.version_build_arg, "CLINE_VERSION")
        self.assertEqual(spec.version_source, {"type": "npm", "package": "cline"})
        self.assertEqual(spec.raw["benchmark_version_policy"], "stable_semver")
        self.assertEqual(spec.raw["benchmark_min_version"], "3.0.3")
        self.assertIn("{base_url}", spec.env["HIBENCH_CLINE_PROVIDERS_JSON"])
        config = json.loads(spec.env["HIBENCH_CLINE_PROVIDERS_JSON"])
        provider = config["providers"]["openai-compatible"]["settings"]
        self.assertEqual(provider["provider"], "openai-compatible")
        self.assertEqual(provider["baseUrl"], "{base_url}")
        self.assertEqual(spec.env["CLINE_DATA_DIR"], "/cline-home/data")
        self.assertEqual(spec.env["HOME"], "/cline-home/home")
        self.assertEqual(spec.env["CLINE_TELEMETRY_DISABLED"], "1")
        self.assertEqual(spec.raw["capture"]["host_timeout_seconds"], 90)

    def test_opencode_agent_loads(self) -> None:
        self.assertIn("opencode", list_agent_ids())
        spec = load_agent("opencode")
        self.assertEqual(spec.version, "1.17.5")
        self.assertEqual(spec.command[:3], ["run", "--format", "json"])
        self.assertEqual(spec.parser_id, "opencode")
        self.assertEqual(spec.version_build_arg, "OPENCODE_VERSION")
        self.assertEqual(spec.version_source, {"type": "npm", "package": "opencode-ai"})
        self.assertIn("{base_url}", spec.env["OPENCODE_CONFIG_CONTENT"])

    def test_kilo_agent_loads(self) -> None:
        self.assertIn("kilo", list_agent_ids())
        spec = load_agent("kilo")
        self.assertEqual(spec.version, "7.3.45")
        self.assertEqual(spec.command[:3], ["run", "--format", "json"])
        self.assertEqual(spec.parser_id, "kilo")
        self.assertEqual(spec.version_build_arg, "KILO_VERSION")
        self.assertEqual(
            spec.version_source, {"type": "npm", "package": "@kilocode/cli"}
        )
        self.assertEqual(spec.raw["benchmark_version_policy"], "stable_semver")
        self.assertIn("{base_url}", spec.env["KILO_CONFIG_CONTENT"])
        self.assertEqual(spec.env["KILO_TEST_HOME"], "/kilo-home/home")
        self.assertEqual(spec.env["KILO_CONFIG_DIR"], "/kilo-home/config")
        self.assertEqual(spec.env["KILO_NO_DAEMON"], "1")
        self.assertEqual(spec.raw["capture"]["host_timeout_seconds"], 90)

    def test_github_cli_agent_loads(self) -> None:
        self.assertIn("github-cli", list_agent_ids())
        spec = load_agent("github-cli")
        self.assertEqual(spec.version, "1.0.62")
        self.assertEqual(spec.command[:2], ["-p", "{prompt}"])
        self.assertIn("--allow-all-tools", spec.command)
        self.assertEqual(spec.parser_id, "github-cli")
        self.assertEqual(spec.version_build_arg, "GITHUB_CLI_VERSION")
        self.assertEqual(
            spec.version_source, {"type": "npm", "package": "@github/copilot"}
        )
        self.assertEqual(spec.raw["benchmark_version_policy"], "stable_semver")
        self.assertEqual(spec.raw["benchmark_min_version"], "1.0.8")
        self.assertNotIn("benchmark_exclusions", spec.raw)
        self.assertEqual(spec.env["COPILOT_PROVIDER_BASE_URL"], "{base_url}")
        self.assertEqual(spec.env["COPILOT_PROVIDER_WIRE_API"], "responses")
        self.assertEqual(spec.env["COPILOT_OFFLINE"], "true")
        self.assertEqual(spec.env["COPILOT_HOME"], "/copilot-home/config")

    def test_droid_agent_loads(self) -> None:
        self.assertIn("droid", list_agent_ids())
        spec = load_agent("droid")
        self.assertEqual(spec.version, "0.153.1")
        self.assertEqual(spec.command[:3], ["exec", "{prompt}", "--cwd"])
        self.assertIn("--output-format", spec.command)
        self.assertEqual(spec.parser_id, "droid")
        self.assertEqual(spec.version_build_arg, "DROID_VERSION")
        self.assertEqual(spec.version_source, {"type": "npm", "package": "droid"})
        self.assertEqual(spec.raw["benchmark_version_policy"], "stable_semver")
        self.assertEqual(spec.raw["benchmark_min_version"], "0.62.1")
        self.assertEqual(spec.env["FACTORY_API_KEY"], "fk-hibench-dummy")
        self.assertEqual(spec.env["FACTORY_DROID_AUTO_UPDATE_ENABLED"], "false")
        self.assertEqual(spec.env["HOME"], "/droid-home/home")
        settings = json.loads(
            spec.env["HIBENCH_DROID_SETTINGS"].replace(
                "{base_url}", "http://example.test/v1"
            )
        )
        self.assertFalse(settings["cloudSessionSync"])
        self.assertFalse(settings["enableDroidShield"])
        self.assertEqual(settings["model"], "custom:HiBench-Droid-0")
        custom_model = settings["customModels"][0]
        self.assertEqual(custom_model["provider"], "openai")
        self.assertEqual(custom_model["baseUrl"], "http://example.test/v1")

    def test_gemini_cli_agent_loads(self) -> None:
        self.assertIn("gemini-cli", list_agent_ids())
        spec = load_agent("gemini-cli")
        self.assertEqual(spec.version, "0.47.0")
        self.assertEqual(spec.command[:2], ["-p", "{prompt}"])
        self.assertEqual(spec.parser_id, "gemini-cli")
        self.assertEqual(spec.version_build_arg, "GEMINI_CLI_VERSION")
        self.assertEqual(
            spec.version_source, {"type": "npm", "package": "@google/gemini-cli"}
        )
        self.assertEqual(spec.raw["benchmark_version_policy"], "stable_semver")
        self.assertEqual(spec.raw["benchmark_min_version"], "0.8.0")
        self.assertEqual(spec.env["GOOGLE_GEMINI_BASE_URL"], "{base_url_root}")
        self.assertEqual(spec.env["GEMINI_API_KEY"], "hibench-dummy-key")
        self.assertEqual(spec.env["GEMINI_CLI_TRUST_WORKSPACE"], "true")
        settings = json.loads(spec.env["HIBENCH_GEMINI_SETTINGS"])
        self.assertEqual(
            settings["security"]["auth"]["selectedType"], "gemini-api-key"
        )
        self.assertFalse(settings["general"]["enableAutoUpdate"])
        self.assertFalse(settings["privacy"]["usageStatisticsEnabled"])

    def test_devin_agent_loads(self) -> None:
        self.assertIn("devin", list_agent_ids())
        spec = load_agent("devin")
        self.assertEqual(spec.version, "2026.7.23")
        self.assertEqual(spec.command, ["-p", "{prompt}"])
        self.assertEqual(spec.parser_id, "devin")
        self.assertEqual(spec.version_build_arg, "DEVIN_VERSION")
        self.assertEqual(
            spec.version_source,
            {
                "type": "static-manifest",
                "url": "https://static.devin.ai/cli/current/manifest.json",
                "platform": "x86_64-unknown-linux",
            },
        )
        self.assertEqual(spec.raw["benchmark_version_policy"], "stable_semver")
        self.assertEqual(spec.env["HIBENCH_DEVIN_API_SERVER_URL"], "{base_url_root}")
        self.assertEqual(spec.env["HIBENCH_DEVIN_API_KEY"], "hibench-dummy-key")
        self.assertEqual(spec.env["HOME"], "/devin-home/home")
        self.assertNotIn("DEVIN_MODEL", spec.env)
        self.assertNotIn("OPENAI_API_KEY", spec.env)
        self.assertNotIn("ANTHROPIC_API_KEY", spec.env)

    def test_cursor_cli_agent_loads(self) -> None:
        self.assertIn("cursor-cli", list_agent_ids())
        spec = load_agent("cursor-cli")
        self.assertEqual(spec.version, "2026.06.12-19-59-36-f6aba9a")
        self.assertEqual(spec.command[:2], ["-p", "{prompt}"])
        self.assertIn("--authless", spec.command)
        self.assertIn("--trust", spec.command)
        self.assertEqual(spec.parser_id, "cursor-cli")
        self.assertEqual(spec.version_build_arg, "CURSOR_CLI_VERSION")
        self.assertEqual(
            spec.version_source,
            {
                "type": "cursor-install",
                "url": "https://cursor.com/install",
                "package": "agent-cli-local-package.tar.gz",
            },
        )
        self.assertEqual(spec.raw["benchmark_version_policy"], "all_versions")
        self.assertEqual(spec.env["CURSOR_LOCAL_AGENT_BASE_URL"], "{base_url}")
        self.assertEqual(spec.env["CURSOR_LOCAL_AGENT_API_KEY"], "hibench-dummy-key")
        self.assertEqual(spec.env["CURSOR_ENABLE_AUTHLESS"], "1")
        self.assertEqual(spec.env["AGENT_CLI_CREDENTIAL_STORE"], "memory")
        self.assertEqual(spec.env["HOME"], "/cursor-home/home")

    def test_grok_cli_agent_loads(self) -> None:
        self.assertIn("grok-cli", list_agent_ids())
        spec = load_agent("grok-cli")
        self.assertEqual(spec.version, "0.2.51")
        self.assertEqual(spec.command[:3], ["--no-auto-update", "-p", "{prompt}"])
        self.assertIn("--max-turns", spec.command)
        self.assertEqual(spec.parser_id, "grok-cli")
        self.assertEqual(spec.version_build_arg, "GROK_CLI_VERSION")
        self.assertEqual(
            spec.version_source, {"type": "npm", "package": "@xai-official/grok"}
        )
        self.assertEqual(spec.raw["benchmark_version_policy"], "stable_semver")
        self.assertIn("{base_url}", spec.env["HIBENCH_GROK_CONFIG"])
        self.assertIn(
            'permission_mode = "always-approve"', spec.env["HIBENCH_GROK_CONFIG"]
        )
        self.assertEqual(spec.env["HIBENCH_GROK_API_KEY"], "hibench-dummy-key")
        self.assertEqual(spec.env["HOME"], "/grok-home/home")
        self.assertNotIn("XAI_API_KEY", spec.env)

    def test_openclaw_agent_loads(self) -> None:
        self.assertIn("openclaw", list_agent_ids())
        spec = load_agent("openclaw")
        self.assertEqual(spec.version, "2026.6.6")
        self.assertEqual(
            spec.command[:6],
            ["agent", "--local", "--agent", "main", "--message", "{prompt}"],
        )
        timeout_index = spec.command.index("--timeout")
        self.assertEqual(spec.command[timeout_index + 1], "240")
        self.assertEqual(spec.parser_id, "openclaw")
        self.assertEqual(spec.version_build_arg, "OPENCLAW_VERSION")
        self.assertEqual(spec.version_source, {"type": "npm", "package": "openclaw"})
        self.assertEqual(
            spec.raw["benchmark_exclusions"],
            {
                "0.0.1": (
                    "Placeholder package version; no usable OpenClaw agent CLI for "
                    "benchmark capture."
                ),
                "2026.4.5": (
                    "Broken npm package for benchmark capture; CLI exits before "
                    "model capture because @buape/carbon is missing."
                ),
                "2026.4.25": (
                    "Broken npm package for benchmark capture; local capture fails "
                    "before producing a primary model request."
                ),
                "2026.4.26": (
                    "Broken npm package for benchmark capture; local capture fails "
                    "before producing a primary model request."
                ),
                "2026.4.27": (
                    "Broken npm package for benchmark capture; local capture fails "
                    "before producing a primary model request."
                ),
                "2026.5.12": (
                    "Broken npm package for benchmark capture; local capture fails "
                    "before producing a primary model request."
                ),
            },
        )
        self.assertIn("{base_url}", spec.env["HIBENCH_OPENCLAW_CONFIG"])
        config = json.loads(spec.env["HIBENCH_OPENCLAW_CONFIG"])
        self.assertEqual(
            config["agents"]["defaults"]["model"], {"primary": "hibench/gpt-5"}
        )
        self.assertNotIn("contextWindow", config["models"]["providers"]["hibench"])
        self.assertNotIn("maxTokens", config["models"]["providers"]["hibench"])
        self.assertEqual(spec.env["OPENCLAW_STATE_DIR"], "/openclaw-home/state")
        self.assertEqual(
            spec.env["OPENCLAW_CONFIG_PATH"], "/openclaw-home/state/openclaw.json"
        )
        self.assertEqual(spec.raw["capture"]["host_timeout_seconds"], 300)
        self.assertGreater(
            spec.raw["capture"]["host_timeout_seconds"],
            int(spec.command[timeout_index + 1]),
        )
        self.assertEqual(
            spec.raw["capture"]["workspace_permission_cleanup_paths"],
            ["/workspace/.openclaw"],
        )

    def test_hermes_agent_loads(self) -> None:
        self.assertIn("hermes", list_agent_ids())
        spec = load_agent("hermes")
        self.assertEqual(spec.version, "0.16.0")
        self.assertEqual(
            spec.command,
            ["--provider", "hibench", "--model", "gpt-5", "-z", "{prompt}"],
        )
        self.assertEqual(spec.parser_id, "hermes")
        self.assertEqual(spec.version_build_arg, "HERMES_VERSION")
        self.assertEqual(
            spec.version_source, {"type": "pypi", "package": "hermes-agent"}
        )
        self.assertIn("{base_url}", spec.env["HIBENCH_HERMES_CONFIG"])
        self.assertEqual(spec.env["HERMES_HOME"], "/hermes-home")
        self.assertEqual(spec.env["HOME"], "/hermes-home/home")

    def test_mistral_vibe_agent_loads(self) -> None:
        self.assertIn("mistral-vibe", list_agent_ids())
        spec = load_agent("mistral-vibe")
        self.assertEqual(spec.version, "2.16.1")
        self.assertEqual(
            spec.command,
            ["-p", "{prompt}", "--max-turns", "1", "--output", "json", "--trust"],
        )
        self.assertEqual(spec.parser_id, "mistral-vibe")
        self.assertEqual(spec.version_build_arg, "MISTRAL_VIBE_VERSION")
        self.assertEqual(
            spec.version_source, {"type": "pypi", "package": "mistral-vibe"}
        )
        self.assertEqual(spec.raw["benchmark_version_policy"], "stable_semver")
        self.assertIn("{base_url}", spec.env["HIBENCH_MISTRAL_VIBE_CONFIG"])
        config = tomllib.loads(
            spec.env["HIBENCH_MISTRAL_VIBE_CONFIG"].replace(
                "{base_url}", "http://example.test/v1"
            )
        )
        self.assertEqual(config["active_model"], "gpt-5")
        self.assertFalse(config["enable_telemetry"])
        self.assertFalse(config["enable_connectors"])
        self.assertFalse(config["vibe_code_enabled"])
        self.assertEqual(config["providers"][0]["name"], "hibench")
        self.assertEqual(config["providers"][0]["api_base"], "http://example.test/v1")
        self.assertEqual(config["providers"][0]["api_style"], "openai")
        self.assertEqual(config["providers"][0]["backend"], "generic")
        self.assertEqual(spec.env["VIBE_HOME"], "/mistral-vibe-home")
        self.assertEqual(spec.env["HOME"], "/mistral-vibe-home/home")
        self.assertEqual(spec.env["HIBENCH_MISTRAL_VIBE_API_KEY"], "hibench-dummy-key")
        self.assertNotIn("MISTRAL_API_KEY", spec.env)

    def test_openhands_agent_loads(self) -> None:
        self.assertIn("openhands", list_agent_ids())
        spec = load_agent("openhands")
        self.assertEqual(spec.version, "1.16.0")
        self.assertEqual(
            spec.command,
            ["--headless", "--json", "--override-with-envs", "-t", "{prompt}"],
        )
        self.assertEqual(spec.parser_id, "openhands")
        self.assertEqual(spec.version_build_arg, "OPENHANDS_VERSION")
        self.assertEqual(spec.version_source, {"type": "pypi", "package": "openhands"})
        self.assertEqual(spec.raw["benchmark_version_policy"], "stable_semver")
        self.assertEqual(spec.raw["benchmark_min_version"], "1.11.0")
        self.assertIn("1.15.1", spec.raw["benchmark_exclusions"])
        self.assertEqual(spec.env["LLM_BASE_URL"], "{base_url}")
        self.assertEqual(spec.env["LLM_MODEL"], "openai/gpt-5")
        self.assertEqual(spec.env["LLM_API_KEY"], "hibench-dummy-key")
        self.assertEqual(spec.env["OPENHANDS_HOME"], "/openhands-home")
        self.assertEqual(spec.env["HOME"], "/openhands-home/home")
        self.assertEqual(spec.env["OPENHANDS_SUPPRESS_BANNER"], "1")
        self.assertEqual(spec.raw["capture"]["host_timeout_seconds"], 120)

    def test_pi_agent_loads(self) -> None:
        self.assertIn("pi", list_agent_ids())
        spec = load_agent("pi")
        self.assertEqual(spec.version, "0.79.3")
        self.assertEqual(
            spec.command[:5], ["-p", "--provider", "hibench", "--model", "gpt-5"]
        )
        self.assertEqual(spec.parser_id, "pi")
        self.assertEqual(spec.version_build_arg, "PI_VERSION")
        self.assertEqual(
            spec.version_source,
            {
                "type": "npm",
                "package": "@earendil-works/pi-coding-agent",
                "packages": [
                    "@mariozechner/pi-coding-agent",
                    "@earendil-works/pi-coding-agent",
                ],
            },
        )
        self.assertIn("{base_url}", spec.env["HIBENCH_PI_MODELS_JSON"])
        self.assertNotIn("OPENAI_API_KEY", spec.env)
        self.assertEqual(spec.env["HOME"], "/pi-home")

    def test_codex_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("codex", version="0.138.0")
        self.assertEqual(spec.version, "0.138.0")
        self.assertEqual(spec.image, "hibench/codex:0.138.0")

    def test_claude_code_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("claude-code", version="2.1.153")
        self.assertEqual(spec.version, "2.1.153")
        self.assertEqual(spec.image, "hibench/claude-code:2.1.153")

    def test_cline_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("cline", version="3.0.23")
        self.assertEqual(spec.version, "3.0.23")
        self.assertEqual(spec.image, "hibench/cline:3.0.23")

    def test_opencode_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("opencode", version="1.17.4")
        self.assertEqual(spec.version, "1.17.4")
        self.assertEqual(spec.image, "hibench/opencode:1.17.4")

    def test_kilo_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("kilo", version="7.3.44")
        self.assertEqual(spec.version, "7.3.44")
        self.assertEqual(spec.image, "hibench/kilo:7.3.44")

    def test_github_cli_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("github-cli", version="1.0.61")
        self.assertEqual(spec.version, "1.0.61")
        self.assertEqual(spec.image, "hibench/github-cli:1.0.61")

    def test_droid_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("droid", version="0.153.0")
        self.assertEqual(spec.version, "0.153.0")
        self.assertEqual(spec.image, "hibench/droid:0.153.0")

    def test_devin_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("devin", version="2026.7.22")
        self.assertEqual(spec.version, "2026.7.22")
        self.assertEqual(spec.image, "hibench/devin:2026.7.22")

    def test_cursor_cli_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("cursor-cli", version="2026.06.13-00-00-00-test")
        self.assertEqual(spec.version, "2026.06.13-00-00-00-test")
        self.assertEqual(spec.image, "hibench/cursor-cli:2026.06.13-00-00-00-test")

    def test_grok_cli_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("grok-cli", version="0.2.50")
        self.assertEqual(spec.version, "0.2.50")
        self.assertEqual(spec.image, "hibench/grok-cli:0.2.50")

    def test_openclaw_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("openclaw", version="2026.6.5")
        self.assertEqual(spec.version, "2026.6.5")
        self.assertEqual(spec.image, "hibench/openclaw:2026.6.5")

    def test_hermes_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("hermes", version="0.15.2")
        self.assertEqual(spec.version, "0.15.2")
        self.assertEqual(spec.image, "hibench/hermes:0.15.2")

    def test_pi_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("pi", version="0.79.2")
        self.assertEqual(spec.version, "0.79.2")
        self.assertEqual(spec.image, "hibench/pi:0.79.2")

    def test_mistral_vibe_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("mistral-vibe", version="2.16.0")
        self.assertEqual(spec.version, "2.16.0")
        self.assertEqual(spec.image, "hibench/mistral-vibe:2.16.0")

    def test_openhands_agent_version_override_updates_image_tag(self) -> None:
        spec = load_agent("openhands", version="1.15.0")
        self.assertEqual(spec.version, "1.15.0")
        self.assertEqual(spec.image, "hibench/openhands:1.15.0")

    def test_codex_dockerfile_keeps_system_layer_version_independent(self) -> None:
        dockerfile = (ROOT / "docker/agents/codex/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        bun_install_index = dockerfile.index("https://bun.com/install")
        version_arg_index = dockerfile.index("ARG CODEX_VERSION")
        install_layer_index = dockerfile.index("bun install --global")

        self.assertLess(system_layer_index, bun_install_index)
        self.assertLess(bun_install_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)

    def test_claude_code_dockerfile_keeps_system_layer_version_independent(
        self,
    ) -> None:
        dockerfile = (ROOT / "docker/agents/claude-code/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        bun_install_index = dockerfile.index("https://bun.com/install")
        version_arg_index = dockerfile.index("ARG CLAUDE_CODE_VERSION")
        install_layer_index = dockerfile.index("bun install --global")

        self.assertLess(system_layer_index, bun_install_index)
        self.assertLess(bun_install_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)

    def test_cline_dockerfile_keeps_system_layer_version_independent(self) -> None:
        dockerfile = (ROOT / "docker/agents/cline/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        bun_install_index = dockerfile.index("https://bun.com/install")
        home_index = dockerfile.index("/cline-home/home")
        version_arg_index = dockerfile.index("ARG CLINE_VERSION")
        install_layer_index = dockerfile.index("bun install --global")

        self.assertLess(system_layer_index, bun_install_index)
        self.assertLess(bun_install_index, home_index)
        self.assertLess(home_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)
        self.assertIn('"cline@${CLINE_VERSION}"', dockerfile)
        self.assertIn("hibench-cline-entrypoint", dockerfile)

    def test_opencode_dockerfile_keeps_system_layer_version_independent(self) -> None:
        dockerfile = (ROOT / "docker/agents/opencode/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        bun_install_index = dockerfile.index("https://bun.com/install")
        version_arg_index = dockerfile.index("ARG OPENCODE_VERSION")
        install_layer_index = dockerfile.index("bun install --global")

        self.assertLess(system_layer_index, bun_install_index)
        self.assertLess(bun_install_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)

    def test_kilo_dockerfile_keeps_system_layer_version_independent(self) -> None:
        dockerfile = (ROOT / "docker/agents/kilo/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        bun_install_index = dockerfile.index("https://bun.com/install")
        version_arg_index = dockerfile.index("ARG KILO_VERSION")
        install_layer_index = dockerfile.index("bun install --global")

        self.assertLess(system_layer_index, bun_install_index)
        self.assertLess(bun_install_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)
        self.assertIn('"@kilocode/cli@${KILO_VERSION}"', dockerfile)
        self.assertIn("bun install --global --ignore-scripts", dockerfile)

    def test_github_cli_dockerfile_keeps_system_layer_version_independent(self) -> None:
        dockerfile = (ROOT / "docker/agents/github-cli/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        bun_install_index = dockerfile.index("https://bun.com/install")
        version_arg_index = dockerfile.index("ARG GITHUB_CLI_VERSION")
        install_layer_index = dockerfile.index("bun install --global")

        self.assertLess(system_layer_index, bun_install_index)
        self.assertLess(bun_install_index, version_arg_index)
        self.assertLess(system_layer_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)
        self.assertIn('"@github/copilot@${GITHUB_CLI_VERSION}"', dockerfile)

    def test_droid_dockerfile_keeps_system_layer_version_independent(self) -> None:
        dockerfile = (ROOT / "docker/agents/droid/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        bun_install_index = dockerfile.index("https://bun.com/install")
        home_index = dockerfile.index("/droid-home/home")
        version_arg_index = dockerfile.index("ARG DROID_VERSION")
        install_layer_index = dockerfile.index("bun install --global")

        self.assertLess(system_layer_index, bun_install_index)
        self.assertLess(bun_install_index, home_index)
        self.assertLess(home_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)
        self.assertIn('"droid@${DROID_VERSION}"', dockerfile)
        self.assertIn("hibench-droid-entrypoint", dockerfile)

    def test_devin_dockerfile_keeps_system_layer_version_independent(self) -> None:
        dockerfile = (ROOT / "docker/agents/devin/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        home_index = dockerfile.index("/devin-home/home")
        version_arg_index = dockerfile.index("ARG DEVIN_VERSION")
        install_layer_index = dockerfile.index("static.devin.ai/cli/${DEVIN_VERSION}")

        self.assertLess(system_layer_index, home_index)
        self.assertLess(home_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)
        self.assertIn("DEVIN_PLATFORM=x86_64-unknown-linux", dockerfile)
        self.assertIn("hibench-devin-entrypoint", dockerfile)
        self.assertIn("devin --version", dockerfile)

    def test_cursor_cli_dockerfile_keeps_system_layer_version_independent(self) -> None:
        dockerfile = (ROOT / "docker/agents/cursor-cli/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        home_index = dockerfile.index("/cursor-home/home")
        version_arg_index = dockerfile.index("ARG CURSOR_CLI_VERSION")
        install_layer_index = dockerfile.index("agent-cli-local-package.tar.gz")

        self.assertLess(system_layer_index, home_index)
        self.assertLess(home_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)
        self.assertIn("cursor-agent-local --version", dockerfile)

    def test_grok_cli_dockerfile_keeps_system_layer_version_independent(self) -> None:
        dockerfile = (ROOT / "docker/agents/grok-cli/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        bun_install_index = dockerfile.index("https://bun.com/install")
        version_arg_index = dockerfile.index("ARG GROK_CLI_VERSION")
        install_layer_index = dockerfile.index("bun install --global")

        self.assertLess(system_layer_index, bun_install_index)
        self.assertLess(bun_install_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)
        self.assertIn('"@xai-official/grok@${GROK_CLI_VERSION}"', dockerfile)
        self.assertIn("hibench-grok-entrypoint", dockerfile)

    def test_openclaw_dockerfile_keeps_system_layer_version_independent(self) -> None:
        dockerfile = (ROOT / "docker/agents/openclaw/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        bun_install_index = dockerfile.index("https://bun.com/install")
        version_arg_index = dockerfile.index("ARG OPENCLAW_VERSION")
        install_layer_index = dockerfile.index("bun install --global")

        self.assertLess(system_layer_index, bun_install_index)
        self.assertLess(bun_install_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)
        self.assertIn("bun install --global --ignore-scripts", dockerfile)

    def test_hermes_dockerfile_keeps_system_layer_version_independent(self) -> None:
        dockerfile = (ROOT / "docker/agents/hermes/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        browser_version_arg_index = dockerfile.index("ARG AGENT_BROWSER_VERSION=0.26.0")
        browser_package_index = dockerfile.index(
            '"agent-browser@${AGENT_BROWSER_VERSION}"'
        )
        browser_install_index = dockerfile.index("agent-browser install")
        uv_install_index = dockerfile.index("COPY --from=uv_source")
        version_arg_index = dockerfile.index("ARG HERMES_VERSION")
        install_layer_index = dockerfile.index("uv pip install")

        self.assertLess(system_layer_index, version_arg_index)
        self.assertLess(browser_version_arg_index, browser_package_index)
        self.assertLess(browser_package_index, browser_install_index)
        self.assertLess(browser_install_index, version_arg_index)
        self.assertLess(uv_install_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)

    def test_mistral_vibe_dockerfile_keeps_system_layer_version_independent(
        self,
    ) -> None:
        dockerfile = (ROOT / "docker/agents/mistral-vibe/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        uv_install_index = dockerfile.index("COPY --from=uv_source")
        home_index = dockerfile.index("/mistral-vibe-home/home")
        version_arg_index = dockerfile.index("ARG MISTRAL_VIBE_VERSION")
        install_layer_index = dockerfile.index("uv pip install")

        self.assertLess(system_layer_index, home_index)
        self.assertLess(home_index, uv_install_index)
        self.assertLess(uv_install_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)
        self.assertIn('"mistral-vibe==${MISTRAL_VIBE_VERSION}"', dockerfile)
        self.assertIn("hibench-mistral-vibe-entrypoint", dockerfile)

    def test_openhands_dockerfile_keeps_system_layer_version_independent(self) -> None:
        dockerfile = (ROOT / "docker/agents/openhands/Dockerfile").read_text(
            encoding="utf-8"
        )
        system_layer_index = dockerfile.index("apt-get install")
        home_index = dockerfile.index("/openhands-home/home")
        uv_install_index = dockerfile.index("COPY --from=uv_source")
        version_arg_index = dockerfile.index("ARG OPENHANDS_VERSION")
        install_layer_index = dockerfile.index("uv pip install")

        self.assertLess(system_layer_index, home_index)
        self.assertLess(home_index, uv_install_index)
        self.assertLess(uv_install_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)
        self.assertIn('"openhands==${OPENHANDS_VERSION}"', dockerfile)
        self.assertIn("openhands --version", dockerfile)

    def test_pi_dockerfile_keeps_system_layer_version_independent(self) -> None:
        dockerfile = (ROOT / "docker/agents/pi/Dockerfile").read_text(encoding="utf-8")
        system_layer_index = dockerfile.index("apt-get install")
        bun_install_index = dockerfile.index("https://bun.com/install")
        version_arg_index = dockerfile.index("ARG PI_VERSION")
        install_layer_index = dockerfile.index("bun install --global")

        self.assertLess(system_layer_index, bun_install_index)
        self.assertLess(bun_install_index, version_arg_index)
        self.assertLess(version_arg_index, install_layer_index)
