import unittest

from hibench.analyze import count_tokens, summarize_request
from hibench.parsers import DEFAULT_PARSER_ID, get_parser


class ParserTests(unittest.TestCase):
    def test_summarize_request_parses_codex_instruction_sources_and_skills(
        self,
    ) -> None:
        permissions_text = "<permissions instructions>\nFilesystem sandboxing is read-only.\n</permissions instructions>"
        skills_text = """<skills_instructions>
## Skills
A skill is a set of local instructions.
### Available skills
- imagegen: Generate images. (file: /codex-home/skills/.system/imagegen/SKILL.md)
- openai-docs: Use official docs and MCP tools. (file: /codex-home/skills/.system/openai-docs/SKILL.md)
### How to use skills
- Subagents may still perform task work when the selected skill allows it.
</skills_instructions>"""
        environment_text = (
            "<environment_context>\n  <cwd>/workspace</cwd>\n</environment_context>"
        )
        tool_search_description = "# Tool discovery\nMulti-agent tools: Spawn sub-agents.\nFor MCP tool discovery, use tool_search."
        record = {
            "method": "POST",
            "path": "/v1/responses",
            "body_text": "{}",
            "json": {
                "model": "gpt-test",
                "instructions": "Main system instructions.",
                "input": [
                    {
                        "type": "message",
                        "role": "developer",
                        "content": [
                            {"type": "input_text", "text": permissions_text},
                            {"type": "input_text", "text": skills_text},
                        ],
                    },
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": environment_text}],
                    },
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "Hi"}],
                    },
                ],
                "tools": [
                    {
                        "type": "tool_search",
                        "description": tool_search_description,
                        "parameters": {},
                    }
                ],
            },
        }

        summary = summarize_request(record, parser_id="codex")
        by_source = summary["text_fields"]["by_source"]

        self.assertEqual(
            by_source["main_instructions"]["tokens"],
            count_tokens("Main system instructions."),
        )
        self.assertEqual(
            by_source["permissions_instructions"]["tokens"],
            count_tokens(permissions_text),
        )
        self.assertEqual(
            by_source["skills_instructions"]["tokens"], count_tokens(skills_text)
        )
        self.assertEqual(
            by_source["injected_user_context"]["tokens"], count_tokens(environment_text)
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("Hi"),
        )
        self.assertEqual(summary["skills"]["count"], 2)
        self.assertEqual(summary["skills"]["tokens"], count_tokens(skills_text))
        self.assertEqual(
            [item["name"] for item in summary["skills"]["items"]],
            ["imagegen", "openai-docs"],
        )
        self.assertEqual(summary["mcp"]["count"], 0)
        self.assertEqual(summary["mcp"]["mention_count"], 2)
        self.assertEqual(summary["subagents"]["count"], 0)
        self.assertEqual(summary["subagents"]["mention_count"], 2)

    def test_summarize_request_classifies_claude_code_messages(self) -> None:
        system_text = "You are Claude Code, Anthropic's official CLI for Claude."
        skill_text = (
            "<system-reminder>\n"
            "Available agent types for the Agent tool:\n"
            "- claude: Catch-all agent. (Tools: *)\n"
            "\n"
            "The following skills are available for use with the Skill tool:\n\n"
            "- verify: Verify a local code change.\n"
            "- code-review: Review the current diff."
            "\nTRIGGER — use before opening the target file."
            "\n</system-reminder>"
        )
        reminder_text = "<system-reminder>cwd is /workspace</system-reminder>"
        task_description = (
            "Launch a new agent to handle complex, multi-step tasks autonomously.\n\n"
            "Available agent types and the tools they have access to:\n"
            "- general-purpose: General-purpose agent for researching complex questions. (Tools: *)\n"
            "- Explore: Fast agent specialized for exploring codebases. (Tools: Read, Grep)\n"
        )
        record = {
            "method": "POST",
            "path": "/v1/messages",
            "body_text": "{}",
            "json": {
                "model": "claude-test",
                "system": [{"type": "text", "text": system_text}],
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": reminder_text}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": skill_text}],
                    },
                    {"role": "user", "content": [{"type": "text", "text": "Hi"}]},
                ],
                "tools": [
                    {"name": "Task", "description": task_description},
                    {
                        "name": "WebFetch",
                        "description": "Prefer an MCP-provided web fetch tool if available.",
                    },
                    {"name": "Bash", "description": "Run shell commands"},
                ],
            },
        }

        summary = summarize_request(record, parser_id="claude-code")
        by_category = summary["text_fields"]["by_category"]
        by_source = summary["text_fields"]["by_source"]

        self.assertEqual(
            by_category["system_prompt"]["tokens"],
            count_tokens(system_text) + count_tokens(skill_text),
        )
        self.assertEqual(
            by_source["main_instructions"]["tokens"], count_tokens(system_text)
        )
        self.assertEqual(
            by_source["skills_instructions"]["tokens"], count_tokens(skill_text)
        )
        self.assertEqual(
            by_category["environment_context"]["tokens"],
            count_tokens(reminder_text),
        )
        self.assertEqual(by_category["user_prompt"]["tokens"], count_tokens("Hi"))
        self.assertEqual(summary["tools"]["count"], 3)
        self.assertEqual(summary["skills"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["skills"]["items"]],
            ["verify", "code-review"],
        )
        self.assertEqual(
            summary["skills"]["items"][1]["description"],
            "Review the current diff. TRIGGER — use before opening the target file.",
        )
        self.assertEqual(summary["subagents"]["count"], 3)
        self.assertEqual(
            [
                item["name"]
                for item in summary["subagents"]["items"]
                if item["is_counted"]
            ],
            ["claude", "general-purpose", "Explore"],
        )
        self.assertEqual(summary["subagents"]["mention_count"], 0)
        self.assertTrue(summary["tools"]["items"][0]["is_subagent_related"])
        self.assertEqual(summary["mcp"]["count"], 0)
        self.assertEqual(summary["mcp"]["mention_count"], 1)

    def test_summarize_request_parses_cline_chat_payload(self) -> None:
        system_text = (
            "You are Cline, an AI coding agent.\n\n"
            "Environment you are running in:\n"
            "<env>\n"
            "1. Platform: linux\n"
            "2. IDE: Terminal Shell\n"
            "3. Working Directory: /workspace\n"
            "</env>\n\n"
            "Always gather all the necessary context before starting to work."
        )
        skills_description = (
            "Execute a skill within the main conversation. "
            "When users reference a slash command, invoke it with this tool. "
            "Available skills: find-skills."
        )
        record = {
            "method": "POST",
            "path": "/v1/chat/completions",
            "body_text": "{}",
            "json": {
                "model": "gpt-5",
                "messages": [
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": "Hi"},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "skills",
                            "description": skills_description,
                            "parameters": {},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "spawn_agent",
                            "description": "Spawn a sub-agent with a custom system prompt.",
                            "parameters": {},
                        },
                    },
                ],
            },
        }

        summary = summarize_request(record, parser_id="cline")

        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens(system_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("Hi"),
        )
        self.assertEqual(summary["skills"]["count"], 1)
        self.assertEqual(summary["skills"]["items"][0]["name"], "find-skills")
        self.assertEqual(
            summary["skills"]["tokens"], count_tokens("Available skills: find-skills")
        )
        self.assertEqual(summary["tools"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["tools"]["items"]],
            ["skills", "spawn_agent"],
        )
        self.assertEqual(summary["subagents"]["count"], 0)
        self.assertGreaterEqual(summary["subagents"]["mention_count"], 1)

    def test_summarize_request_parses_gemini_cli_payload(self) -> None:
        system_text = (
            "You are Gemini CLI.\n\n"
            "# Available Agent Skills\n"
            "<available_skills>\n"
            "  <skill>\n"
            "    <name>skill-creator</name>\n"
            "    <description>Create or update Gemini CLI skills.</description>\n"
            "  </skill>\n"
            "</available_skills>\n\n"
            "<available_subagents>\n"
            "  <subagent>\n"
            "    <name>codebase_investigator</name>\n"
            "    <description>Analyze codebases and architecture.</description>\n"
            "  </subagent>\n"
            "  <subagent>\n"
            "    <name>generalist</name>\n"
            "    <description>General-purpose agent with all tools.</description>\n"
            "  </subagent>\n"
            "</available_subagents>"
        )
        session_context = (
            "<session_context>\n"
            "This is the Gemini CLI.\n"
            "- **Workspace Directories:**\n"
            "  - /workspace\n"
            "</session_context>"
        )
        record = {
            "method": "POST",
            "path": "/v1beta/models/gemini-3.5-flash:streamGenerateContent?alt=sse",
            "body_text": "{}",
            "json": {
                "contents": [
                    {"role": "user", "parts": [{"text": session_context}]},
                    {"role": "user", "parts": [{"text": "Hi"}]},
                ],
                "systemInstruction": {
                    "role": "user",
                    "parts": [{"text": system_text}],
                },
                "tools": [
                    {
                        "functionDeclarations": [
                            {
                                "name": "read_file",
                                "description": "Read a file.",
                                "parametersJsonSchema": {"type": "object"},
                            },
                            {
                                "name": "invoke_agent",
                                "description": "Invoke a subagent.",
                                "parametersJsonSchema": {"type": "object"},
                            },
                        ]
                    }
                ],
            },
        }

        summary = summarize_request(record, parser_id="gemini-cli")

        self.assertEqual(summary["model"], "gemini-3.5-flash")
        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens(system_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_source"]["injected_user_context"]["tokens"],
            count_tokens(session_context),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("Hi"),
        )
        self.assertEqual(summary["tools"]["count"], 2)
        self.assertEqual(summary["tools"]["names"], ["invoke_agent", "read_file"])
        self.assertEqual(summary["skills"]["count"], 1)
        self.assertEqual(summary["skills"]["items"][0]["name"], "skill-creator")
        self.assertEqual(summary["subagents"]["count"], 2)
        self.assertEqual(
            [
                item["name"]
                for item in summary["subagents"]["items"]
                if item["is_counted"]
            ],
            ["codebase_investigator", "generalist"],
        )
        self.assertGreaterEqual(summary["subagents"]["mention_count"], 1)

    def test_summarize_request_classifies_gemini_cli_legacy_setup_context(
        self,
    ) -> None:
        system_text = "You are an interactive CLI agent."
        legacy_context = (
            "This is the Gemini CLI. We are setting up the context for our chat.\n"
            "Today's date is Monday, June 22, 2026.\n"
            "My operating system is: linux\n"
            "I'm currently working in the directory: /workspace\n"
            "My setup is complete. I will provide my first command in the next turn."
        )
        record = {
            "method": "POST",
            "path": "/v1beta/models/gemini-2.5-flash:streamGenerateContent?alt=sse",
            "body_text": "{}",
            "json": {
                "contents": [
                    {"role": "user", "parts": [{"text": legacy_context}]},
                    {"role": "user", "parts": [{"text": "Hi"}]},
                ],
                "systemInstruction": {
                    "role": "user",
                    "parts": [{"text": system_text}],
                },
            },
        }

        summary = summarize_request(record, parser_id="gemini-cli")

        self.assertEqual(
            summary["text_fields"]["by_source"]["injected_user_context"]["tokens"],
            count_tokens(legacy_context),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("Hi"),
        )

    def test_summarize_request_parses_opencode_chat_payload(self) -> None:
        skills_xml = (
            "<available_skills>\n"
            "  <skill>\n"
            "    <name>customize-opencode</name>\n"
            "    <description>Use when editing opencode configuration.</description>\n"
            "    <location>file:///opencode/customize-opencode/SKILL.md</location>\n"
            "  </skill>\n"
            "  <skill>\n"
            "    <name>plan</name>\n"
            "    <description>Use when planning implementation work.</description>\n"
            "  </skill>\n"
            "</available_skills>"
        )
        system_text = (
            "You are an AI coding agent.\n"
            "You are powered by the model named gpt-5.\n"
            "<env>\n  Working directory: /workspace\n</env>\n"
            "Skill inventory follows in XML.\n"
            "Use the skill tool to load a skill when a task matches its description.\n"
            f"{skills_xml}"
        )
        task_description = (
            "Launch a new agent.\n\n"
            "Available agent types and the tools they have access to:\n"
            "- general: General-purpose subagent.\n"
            "- explore: Explore the codebase. (Tools: read, grep)\n"
        )
        record = {
            "method": "POST",
            "path": "/v1/chat/completions",
            "body_text": "{}",
            "json": {
                "model": "gpt-5",
                "messages": [
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": "Hi"},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "task",
                            "description": task_description,
                            "parameters": {},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "shell",
                            "description": "Run a shell command",
                            "parameters": {},
                        },
                    },
                ],
            },
        }

        summary = summarize_request(record, parser_id="opencode")

        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens(system_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("Hi"),
        )
        self.assertEqual(summary["skills"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["skills"]["items"]],
            ["customize-opencode", "plan"],
        )
        self.assertEqual(summary["skills"]["items"][1]["file"], "")
        self.assertEqual(summary["skills"]["tokens"], count_tokens(skills_xml))
        self.assertEqual(summary["tools"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["tools"]["items"]], ["task", "shell"]
        )
        self.assertEqual(summary["subagents"]["count"], 2)
        self.assertEqual(
            [
                item["name"]
                for item in summary["subagents"]["items"]
                if item["is_counted"]
            ],
            ["general", "explore"],
        )
        self.assertTrue(summary["tools"]["items"][0]["is_subagent_related"])

    def test_summarize_request_parses_openhands_responses_payload(self) -> None:
        skills_xml = (
            "<available_skills>\n"
            "  <skill>\n"
            "    <name>github-actions</name>\n"
            "    <description>Create and debug GitHub Actions workflows.</description>\n"
            "  </skill>\n"
            "  <skill>\n"
            "    <name>release-notes</name>\n"
            "    <description>Generate formatted changelogs from git history.</description>\n"
            "  </skill>\n"
            "</available_skills>"
        )
        instructions = (
            "You are OpenHands agent, a helpful AI assistant that can interact "
            "with a computer to solve tasks.\n"
            "<SKILLS>\n"
            "Use the invoke_skill tool to load a matching skill.\n"
            f"{skills_xml}\n"
            "</SKILLS>\n"
            "Your current working directory is: /workspace\n"
            "User operating system: Linux"
        )
        task_description = (
            "Launch a subagent to handle complex, multi-step tasks autonomously.\n\n"
            "Available agent types and the tools they have access to:\n"
            "- **bash-runner**: Execute shell commands and inspect repositories. (Tools: terminal)\n"
            "- **code-reviewer**: Review a source diff for defects. (Tools: file_editor)\n"
        )
        record = {
            "method": "POST",
            "path": "/v1/responses",
            "body_text": "{}",
            "json": {
                "model": "gpt-5",
                "instructions": instructions,
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "Hi"}],
                    }
                ],
                "tools": [
                    {
                        "type": "function",
                        "name": "task",
                        "description": task_description,
                        "parameters": {},
                    },
                    {
                        "type": "function",
                        "name": "terminal",
                        "description": "Execute a shell command.",
                        "parameters": {},
                    },
                    {
                        "type": "function",
                        "name": "invoke_skill",
                        "description": "Invoke a skill by name.",
                        "parameters": {},
                    },
                ],
            },
        }

        summary = summarize_request(record, parser_id="openhands")

        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens(instructions),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("Hi"),
        )
        self.assertEqual(summary["skills"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["skills"]["items"]],
            ["github-actions", "release-notes"],
        )
        self.assertEqual(summary["skills"]["tokens"], count_tokens(skills_xml))
        self.assertEqual(summary["tools"]["count"], 3)
        self.assertEqual(
            [item["name"] for item in summary["tools"]["items"]],
            ["task", "terminal", "invoke_skill"],
        )
        self.assertEqual(summary["subagents"]["count"], 2)
        self.assertEqual(
            [
                item["name"]
                for item in summary["subagents"]["items"]
                if item["is_counted"]
            ],
            ["bash-runner", "code-reviewer"],
        )
        self.assertTrue(summary["tools"]["items"][0]["is_subagent_related"])

    def test_summarize_request_parses_kilo_chat_payload(self) -> None:
        skills_xml = (
            "<available_skills>\n"
            "  <skill>\n"
            "    <name>customize-opencode</name>\n"
            "    <description>Use when editing OpenCode or Kilo configuration.</description>\n"
            "    <location>file:///workspace/%3Cbuilt-in%3E</location>\n"
            "  </skill>\n"
            "  <skill>\n"
            "    <name>kilo-config</name>\n"
            "    <description>Guide for Kilo configuration.</description>\n"
            "    <location>file:///workspace/builtin</location>\n"
            "  </skill>\n"
            "</available_skills>"
        )
        system_text = (
            "You are Kilo, a highly skilled software engineer.\n"
            "<env>\n"
            "  Is directory a git repo: no\n"
            "  Platform: linux\n"
            "</env>\n"
            "Skills provide specialized instructions and workflows for specific tasks.\n"
            "Use the skill tool to load a skill when a task matches its description.\n"
            f"{skills_xml}"
        )
        environment_text = (
            "<environment_details>\n"
            "Current time: 2026-06-14T22:50:04+00:00\n"
            "Working directory: /workspace\n"
            "</environment_details>"
        )
        record = {
            "method": "POST",
            "path": "/v1/chat/completions",
            "body_text": "{}",
            "json": {
                "model": "gpt-5",
                "messages": [
                    {"role": "system", "content": system_text},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Hi"},
                            {"type": "text", "text": environment_text},
                        ],
                    },
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "task",
                            "description": "Launch a new agent to handle complex, multistep tasks autonomously.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "subagent_type": {
                                        "type": "string",
                                        "description": "The type of specialized agent to use for this task",
                                    }
                                },
                                "required": ["description", "prompt", "subagent_type"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "skill",
                            "description": "Load a specialized skill.",
                            "parameters": {},
                        },
                    },
                ],
            },
        }

        summary = summarize_request(record, parser_id="kilo")

        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens(system_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("Hi"),
        )
        self.assertEqual(
            summary["text_fields"]["by_source"]["injected_user_context"]["tokens"],
            count_tokens(environment_text),
        )
        self.assertEqual(summary["skills"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["skills"]["items"]],
            ["customize-opencode", "kilo-config"],
        )
        self.assertEqual(summary["skills"]["tokens"], count_tokens(skills_xml))
        self.assertEqual(summary["tools"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["tools"]["items"]],
            ["task", "skill"],
        )
        self.assertEqual(summary["subagents"]["count"], 0)
        self.assertGreaterEqual(summary["subagents"]["mention_count"], 1)

    def test_summarize_request_parses_mistral_vibe_chat_payload(self) -> None:
        skills_xml = (
            "<available_skills>\n"
            "  <skill>\n"
            "    <name>vibe</name>\n"
            "    <description>Authoritative reference for Mistral Vibe &quot;CLI&quot;.</description>\n"
            "    <path>/mistral-vibe/skills/vibe/SKILL.md</path>\n"
            "  </skill>\n"
            "</available_skills>"
        )
        system_text = (
            "You are Mistral Vibe, a CLI coding agent built by Mistral AI.\n"
            "# Available Skills\n"
            "You have access to the following skills.\n"
            f"{skills_xml}\n"
            "# Available Subagents\n"
            "The following subagents can be spawned via the Task tool:\n"
            "- **explore**: Read-only subagent for codebase exploration\n"
        )
        task_description = (
            "Delegate a task to a subagent for independent execution. "
            "The agent parameter must be a subagent."
        )
        record = {
            "method": "POST",
            "path": "/v1/chat/completions",
            "body_text": "{}",
            "json": {
                "model": "gpt-5",
                "messages": [
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": "Hi"},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "task",
                            "description": task_description,
                            "parameters": {},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "skill",
                            "description": "Load a specialized skill.",
                            "parameters": {},
                        },
                    },
                ],
            },
        }

        summary = summarize_request(record, parser_id="mistral-vibe")

        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens(system_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("Hi"),
        )
        self.assertEqual(summary["skills"]["count"], 1)
        self.assertEqual(summary["skills"]["items"][0]["name"], "vibe")
        self.assertEqual(
            summary["skills"]["items"][0]["description"],
            'Authoritative reference for Mistral Vibe "CLI".',
        )
        self.assertEqual(
            summary["skills"]["items"][0]["file"],
            "/mistral-vibe/skills/vibe/SKILL.md",
        )
        self.assertEqual(summary["skills"]["tokens"], count_tokens(skills_xml))
        self.assertEqual(summary["subagents"]["count"], 1)
        self.assertEqual(summary["subagents"]["items"][0]["name"], "explore")
        self.assertGreaterEqual(summary["subagents"]["mention_count"], 1)
        self.assertEqual(
            [item["name"] for item in summary["tools"]["items"]], ["task", "skill"]
        )
        self.assertTrue(summary["tools"]["items"][0]["is_subagent_related"])

    def test_summarize_request_parses_pi_chat_payload(self) -> None:
        skills_xml = (
            "<available_skills>\n"
            "  <skill>\n"
            "    <name>find-skills</name>\n"
            "    <description>Find installable skills.</description>\n"
            "    <location>/pi-home/.agents/skills/find-skills/SKILL.md</location>\n"
            "  </skill>\n"
            "</available_skills>"
        )
        system_text = (
            "You are an expert coding assistant operating inside pi.\n"
            "Available tools:\n"
            "- read: Read file contents\n"
            "- bash: Execute bash commands\n"
            f"{skills_xml}\n"
            "Current working directory: /workspace"
        )
        record = {
            "method": "POST",
            "path": "/v1/chat/completions",
            "body_text": "{}",
            "json": {
                "model": "gpt-5",
                "messages": [
                    {"role": "system", "content": system_text},
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "Hi"}],
                    },
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "read",
                            "description": "Read the contents of a file.",
                            "parameters": {},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "bash",
                            "description": "Execute bash commands.",
                            "parameters": {},
                        },
                    },
                ],
            },
        }

        summary = summarize_request(record, parser_id="pi")

        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens(system_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("Hi"),
        )
        self.assertEqual(summary["skills"]["count"], 1)
        self.assertEqual(summary["skills"]["items"][0]["name"], "find-skills")
        self.assertEqual(summary["skills"]["tokens"], count_tokens(skills_xml))
        self.assertEqual(summary["tools"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["tools"]["items"]], ["read", "bash"]
        )

    def test_summarize_request_parses_github_cli_responses_payload(self) -> None:
        skills_xml = (
            "<available_skills>\n"
            "<skill>\n"
            "  <name>customize-cloud-agent</name>\n"
            "  <description>Customize the Copilot cloud agent environment.</description>\n"
            "  <location>builtin</location>\n"
            "</skill>\n"
            "</available_skills>"
        )
        system_text = (
            "You are the GitHub Copilot CLI, a terminal assistant built by GitHub.\n"
            "<environment_context>\n"
            "Current working directory: /workspace\n"
            "</environment_context>"
        )
        user_text = (
            "<current_datetime>2026-06-14T20:05:59Z</current_datetime>\n\n"
            "Hi\n\n"
            "<system_reminder>\n"
            "<sql_tables>Available tables: todos, todo_deps</sql_tables>\n"
            "</system_reminder>"
        )
        task_description = (
            "Custom agent: Launch specialized agents in separate context windows.\n\n"
            "Available agent types:\n"
            "- **explore**: Fast agent for codebase exploration. (Tools: grep/glob/view)\n"
            "\n"
            "- **task**: Agent for executing commands with verbose output.\n"
            "\n"
            "- **general-purpose**: Full-capability agent running in a subprocess.\n"
            "\n"
            "- **code-review**: Agent for reviewing code changes.\n"
            "\n"
            "- **research**: Research subagent that executes thorough searches.\n"
            "\n"
            "When NOT to use Task tool:\n"
            "- Reading specific file paths you already know - use view tool instead\n"
        )
        record = {
            "method": "POST",
            "path": "/v1/responses",
            "body_text": "{}",
            "json": {
                "model": "gpt-5",
                "instructions": system_text,
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": user_text}],
                    }
                ],
                "tools": [
                    {
                        "type": "function",
                        "name": "skill",
                        "description": (
                            "Execute a skill within the main conversation.\n"
                            f"{skills_xml}"
                        ),
                        "parameters": {},
                    },
                    {
                        "type": "function",
                        "name": "task",
                        "description": task_description,
                        "parameters": {},
                    },
                ],
            },
        }

        summary = summarize_request(record, parser_id="github-cli")

        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens(system_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens(user_text),
        )
        self.assertEqual(summary["skills"]["count"], 1)
        self.assertEqual(summary["skills"]["items"][0]["name"], "customize-cloud-agent")
        self.assertEqual(summary["skills"]["tokens"], count_tokens(skills_xml))
        self.assertEqual(summary["tools"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["tools"]["items"]], ["skill", "task"]
        )
        self.assertEqual(summary["subagents"]["count"], 5)
        self.assertEqual(
            [
                item["name"]
                for item in summary["subagents"]["items"]
                if item["is_counted"]
            ],
            ["explore", "task", "general-purpose", "code-review", "research"],
        )
        self.assertTrue(summary["tools"]["items"][1]["is_subagent_related"])

    def test_summarize_request_parses_cursor_cli_chat_payload(self) -> None:
        system_text = (
            "You are an AI coding assistant, powered by gpt-5.\n"
            "You are an interactive CLI tool that helps users with software engineering tasks."
        )
        user_context = (
            "<user_info>\n"
            "OS Version: linux\n"
            "Shell: bash\n"
            "Workspace Path: /workspace\n"
            "</user_info>\n\n"
            "<git_status>\n"
            "## No commits yet on master\n"
            "</git_status>\n\n"
            "<agent_transcripts>\n"
            "Agent transcripts live under ~/.cursor/projects.\n"
            "</agent_transcripts>"
        )
        task_description = (
            "Launch a new agent to handle complex, multi-step tasks autonomously.\n\n"
            "The Task tool launches specialized subagents (subprocesses)."
        )
        subagent_type_description = (
            "Subagent type to use for this task. Must be one of: "
            "generalPurpose, explore, cursor-guide, best-of-n-runner."
        )
        record = {
            "method": "POST",
            "path": "/v1/chat/completions",
            "body_text": "{}",
            "json": {
                "model": "gpt-5",
                "messages": [
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": user_context},
                    {"role": "user", "content": "<user_query>\nHi\n</user_query>"},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "Task",
                            "description": task_description,
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "subagent_type": {
                                        "type": "string",
                                        "enum": [
                                            "generalPurpose",
                                            "explore",
                                            "cursor-guide",
                                            "best-of-n-runner",
                                        ],
                                        "description": subagent_type_description,
                                    }
                                },
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "ListMcpResources",
                            "description": "List available resources from configured MCP servers.",
                            "parameters": {},
                        },
                    },
                ],
            },
        }

        summary = summarize_request(record, parser_id="cursor-cli")

        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens(system_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_source"]["injected_user_context"]["tokens"],
            count_tokens(user_context),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("<user_query>\nHi\n</user_query>"),
        )
        self.assertEqual(summary["tools"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["tools"]["items"]],
            ["Task", "ListMcpResources"],
        )
        self.assertEqual(summary["subagents"]["count"], 4)
        self.assertEqual(
            [
                item["name"]
                for item in summary["subagents"]["items"]
                if item["is_counted"]
            ],
            ["generalPurpose", "explore", "cursor-guide", "best-of-n-runner"],
        )
        self.assertTrue(summary["tools"]["items"][0]["is_subagent_related"])
        self.assertEqual(summary["mcp"]["count"], 1)
        self.assertTrue(summary["tools"]["items"][1]["is_mcp_related"])

    def test_summarize_request_parses_grok_cli_chat_payload(self) -> None:
        system_text = (
            "You are Grok 4.3 released by xAI in April 2026. "
            "You are an autonomous agent that completes software engineering tasks."
        )
        user_info = (
            "<user_info>\n"
            "OS Version: linux\n"
            "Shell: /bin/sh\n"
            "Workspace Path: /workspace\n"
            "</user_info>"
        )
        skills_text = (
            "<system-reminder>\n"
            "The following skills are available for use:\n\n"
            "- help: Grok documentation and configuration help\n"
            "  Use when: users ask about setup or configuration.\n"
            "  Absolute path: /grok-home/home/.grok/skills/help/SKILL.md\n"
            "- check-work: Check your work with a verification subagent.\n"
            "  Use when: asked to verify changes.\n"
            "  Absolute path: /grok-home/home/.grok/skills/check-work/SKILL.md\n"
            "</system-reminder>"
        )
        record = {
            "method": "POST",
            "path": "/v1/chat/completions",
            "body_text": "{}",
            "json": {
                "model": "gpt-5",
                "messages": [
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": user_info},
                    {"role": "user", "content": skills_text},
                    {"role": "user", "content": "<user_query>\nHi\n</user_query>"},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "run_terminal_command",
                            "description": "Run a shell command.",
                            "parameters": {},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "spawn_subagent",
                            "description": (
                                "Launch a new agent to handle complex tasks.\n\n"
                                "Available agent types and the tools they have "
                                "access to:\n\n"
                                "- **general-purpose**: General-purpose agent for "
                                "research and multi-step tasks.\n"
                                "- **explore**: Fast agent specialized for exploring "
                                "codebases.\n"
                                "- **plan**: Software architect agent for designing "
                                "implementation plans.\n\n"
                                "When using the spawn_subagent tool, specify a "
                                "subagent_type parameter."
                            ),
                            "parameters": {},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_command_or_subagent_output",
                            "description": "Get command or subagent output.",
                            "parameters": {},
                        },
                    },
                ],
            },
        }

        summary = summarize_request(record, parser_id="grok-cli")

        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens(system_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_source"]["injected_user_context"]["tokens"],
            count_tokens(user_info),
        )
        self.assertEqual(
            summary["text_fields"]["by_source"]["skills_instructions"]["tokens"],
            count_tokens(skills_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("<user_query>\nHi\n</user_query>"),
        )
        self.assertEqual(summary["skills"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["skills"]["items"]],
            ["help", "check-work"],
        )
        self.assertEqual(
            summary["skills"]["items"][0]["description"],
            (
                "Grok documentation and configuration help "
                "Use when: users ask about setup or configuration."
            ),
        )
        self.assertEqual(
            summary["skills"]["items"][0]["file"],
            "/grok-home/home/.grok/skills/help/SKILL.md",
        )
        self.assertEqual(summary["tools"]["count"], 3)
        self.assertEqual(
            [item["name"] for item in summary["tools"]["items"]],
            [
                "run_terminal_command",
                "spawn_subagent",
                "get_command_or_subagent_output",
            ],
        )
        self.assertEqual(summary["subagents"]["count"], 3)
        self.assertEqual(
            [
                item["name"]
                for item in summary["subagents"]["items"]
                if item["is_counted"]
            ],
            ["general-purpose", "explore", "plan"],
        )
        self.assertTrue(summary["tools"]["items"][1]["is_subagent_related"])
        self.assertTrue(summary["tools"]["items"][2]["is_subagent_related"])

    def test_summarize_request_parses_openclaw_responses_payload(self) -> None:
        skills_xml = (
            "<available_skills>\n"
            "  <skill>\n"
            "    <name>github</name>\n"
            "    <description>Use GitHub CLI for issues and PRs.</description>\n"
            "    <location>/openclaw/skills/github/SKILL.md</location>\n"
            "    <version>sha256:abc123</version>\n"
            "  </skill>\n"
            "  <skill>\n"
            "    <name>taskflow</name>\n"
            "    <description>Plan and manage multi-step work.</description>\n"
            "    <location>/openclaw/skills/taskflow/SKILL.md</location>\n"
            "    <version>sha256:def456</version>\n"
            "  </skill>\n"
            "</available_skills>"
        )
        system_text = (
            "You are a personal assistant running inside OpenClaw.\n"
            "Use sessions_spawn for larger work and sessions_yield to wait.\n"
            "## Skills\n"
            "Scan <available_skills> and read SKILL.md when relevant.\n"
            f"{skills_xml}"
        )
        timestamp_context = "[Sun 2026-06-21 10:21 UTC]"
        record = {
            "method": "POST",
            "path": "/v1/responses",
            "body_text": "{}",
            "json": {
                "model": "gpt-5",
                "input": [
                    {
                        "type": "message",
                        "role": "system",
                        "content": [{"type": "input_text", "text": system_text}],
                    },
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": f"{timestamp_context} Hi"}
                        ],
                    },
                ],
                "tools": [
                    {
                        "type": "function",
                        "name": "sessions_spawn",
                        "description": "Spawn an isolated sub-agent session.",
                        "parameters": {},
                    },
                    {
                        "type": "function",
                        "name": "subagents",
                        "description": "List available subagents.",
                        "parameters": {},
                    },
                    {
                        "type": "function",
                        "name": "read",
                        "description": "Read file contents.",
                        "parameters": {},
                    },
                ],
            },
        }

        summary = summarize_request(record, parser_id="openclaw")

        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens(system_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("Hi"),
        )
        self.assertEqual(
            summary["text_fields"]["by_source"]["injected_user_context"]["tokens"],
            count_tokens(timestamp_context),
        )
        self.assertEqual(summary["skills"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["skills"]["items"]],
            ["github", "taskflow"],
        )
        self.assertEqual(
            summary["skills"]["items"][0]["file"],
            "/openclaw/skills/github/SKILL.md",
        )
        self.assertEqual(summary["skills"]["tokens"], count_tokens(skills_xml))
        self.assertEqual(summary["tools"]["count"], 3)
        self.assertEqual(
            [item["name"] for item in summary["tools"]["items"]],
            ["sessions_spawn", "subagents", "read"],
        )
        self.assertEqual(summary["subagents"]["count"], 0)
        self.assertGreaterEqual(summary["subagents"]["mention_count"], 2)
        self.assertNotIn(
            "tool_declaration",
            {item["source_type"] for item in summary["subagents"]["items"]},
        )

    def test_summarize_request_classifies_hermes_chat_payload(self) -> None:
        system_text = (
            "You are Hermes Agent, an intelligent AI assistant.\n"
            "Use memory only for durable facts.\n"
            "Use delegate_task for independent subagent work."
        )
        record = {
            "method": "POST",
            "path": "/v1/chat/completions",
            "body_text": "{}",
            "json": {
                "model": "gpt-5",
                "messages": [
                    {"role": "developer", "content": system_text},
                    {"role": "user", "content": "Hi"},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "delegate_task",
                            "description": "Spawn one or more subagents.",
                            "parameters": {},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "memory",
                            "description": "Save durable information.",
                            "parameters": {},
                        },
                    },
                ],
            },
        }

        summary = summarize_request(record, parser_id="hermes")

        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens(system_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("Hi"),
        )
        self.assertEqual(summary["tools"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["tools"]["items"]],
            ["delegate_task", "memory"],
        )
        self.assertEqual(summary["skills"]["count"], 0)
        self.assertEqual(summary["subagents"]["count"], 0)
        self.assertGreaterEqual(summary["subagents"]["mention_count"], 1)

    def test_summarize_request_parses_devin_connect_payload(self) -> None:
        system_text = (
            "You are Devin, an interactive command line agent from Cognition.\n\n"
            "Available subagent profiles for the `run_subagent` tool:\n"
            "- `subagent_explore`: Read-only subagent for codebase exploration.\n"
            "- `subagent_general`: General-purpose subagent with full tool access."
        )
        environment_text = (
            "<system_info>\n"
            "Current workspace directories:\n"
            "  /workspace (cwd)\n"
            "Platform: linux\n"
            "</system_info>"
        )
        skills_text = (
            "<available_skills>\n"
            "The following skills can be invoked using the `skill` tool.\n\n"
            "- **devin-for-terminal**: Look up Devin CLI documentation "
            "(source: /devin/docs)\n"
            "- **declarative-repo-setup**: Generate environment.yaml "
            "(source: builtin:drs)\n"
            "</available_skills>"
        )
        run_subagent_schema = (
            '{"type":"object","properties":{"profile":{"type":"string",'
            '"description":"The profile to use (e.g. \\"subagent_explore\\", '
            '\\"subagent_general\\")."}}}'
        )
        body_text = "\x00".join(
            [
                "chisel",
                "2026.7.23",
                "dummy-key",
                system_text,
                "$b95ce9fd-6295-419d-af38-4a39d2e9a5ab",
                environment_text,
                "$9c43377d-7dda-47e4-8af4-183c6b21d6f4",
                "Hi",
                "$70926316-a443-4ad8-a040-4317fbac5861",
                skills_text + "8",
                "ask_user_question",
                "Present multiple-choice questions to the user.",
                '{"type":"object","properties":{}}',
                "mcp_call_tool",
                "Execute a tool on an MCP server.",
                '{"type":"object","properties":{}}',
                "webfetch",
                "<Fetches a web page and returns its content as readable text.",
                '{"type":"object","properties":{}}',
                "run_subagent",
                "Launch an independent subagent to handle a task autonomously.",
                run_subagent_schema,
                "swe-1-6-fast",
            ]
        )
        record = {
            "method": "POST",
            "path": "/exa.api_server_pb.ApiServerService/GetChatMessage",
            "body_text": body_text,
            "json": None,
        }

        normalized = get_parser("devin").normalize_body(record, body_text)
        self.assertEqual(normalized["skills"]["content"], skills_text)
        self.assertEqual(
            [
                item["description"]
                for item in normalized["tools"]
                if item["name"] == "webfetch"
            ],
            ["Fetches a web page and returns its content as readable text."],
        )

        summary = summarize_request(record, parser_id="devin")

        self.assertEqual(summary["model"], "swe-1-6-fast")
        self.assertGreater(summary["body_tokens"], 0)
        self.assertEqual(
            summary["text_fields"]["by_source"]["main_instructions"]["tokens"],
            count_tokens(system_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_source"]["injected_user_context"]["tokens"],
            count_tokens(environment_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_source"]["skills_instructions"]["tokens"],
            count_tokens(skills_text),
        )
        self.assertEqual(
            summary["text_fields"]["by_category"]["user_prompt"]["tokens"],
            count_tokens("Hi"),
        )
        self.assertEqual(summary["skills"]["count"], 2)
        self.assertEqual(
            [item["name"] for item in summary["skills"]["items"]],
            ["devin-for-terminal", "declarative-repo-setup"],
        )
        self.assertEqual(summary["tools"]["count"], 4)
        self.assertEqual(
            [item["name"] for item in summary["tools"]["items"]],
            ["ask_user_question", "mcp_call_tool", "webfetch", "run_subagent"],
        )
        self.assertEqual(summary["mcp"]["count"], 1)
        self.assertEqual(summary["subagents"]["count"], 3)
        self.assertEqual(
            [
                item["name"]
                for item in summary["subagents"]["items"]
                if item["is_counted"]
            ],
            ["subagent_explore", "subagent_general", "run_subagent"],
        )

        title_summary = summarize_request(
            {
                "method": "POST",
                "path": "/exa.api_server_pb.ApiServerService/GetChatMessage",
                "body_text": "\x00".join(
                    [
                        "You are a session title generator.",
                        "Hi8",
                        "swe-1-6-fast",
                    ]
                ),
                "json": None,
            },
            parser_id="devin",
        )
        self.assertTrue(get_parser("devin").is_auxiliary_request(title_summary))

    def test_default_parser_is_generic_and_unknown_parser_errors(self) -> None:
        self.assertEqual(DEFAULT_PARSER_ID, "generic")
        self.assertEqual(get_parser().parser_id, "generic")
        self.assertEqual(get_parser("claude-code").parser_id, "claude-code")
        self.assertEqual(get_parser("cline").parser_id, "cline")
        self.assertEqual(get_parser("cursor-cli").parser_id, "cursor-cli")
        self.assertEqual(get_parser("devin").parser_id, "devin")
        self.assertEqual(get_parser("droid").parser_id, "droid")
        self.assertEqual(get_parser("gemini-cli").parser_id, "gemini-cli")
        self.assertEqual(get_parser("github-cli").parser_id, "github-cli")
        self.assertEqual(get_parser("grok-cli").parser_id, "grok-cli")
        self.assertEqual(get_parser("hermes").parser_id, "hermes")
        self.assertEqual(get_parser("kilo").parser_id, "kilo")
        self.assertEqual(get_parser("mistral-vibe").parser_id, "mistral-vibe")
        self.assertEqual(get_parser("openclaw").parser_id, "openclaw")
        self.assertEqual(get_parser("opencode").parser_id, "opencode")
        self.assertEqual(get_parser("openhands").parser_id, "openhands")
        self.assertEqual(get_parser("pi").parser_id, "pi")
        with self.assertRaises(ValueError):
            get_parser("unknown-agent")
