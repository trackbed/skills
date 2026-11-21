"""Behavioral tests for the shared transcript interface."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "lib"))
import transcripts


class TranscriptsTests(unittest.TestCase):
    def test_event_iteration_counts_malformed_lines_and_resumes(self):
        claude = {"type": "user", "message": {"content": "Continue with the changes"}}
        codex = {"type": "response_item", "payload": {"type": "message", "role": "assistant"}}
        cursor = {"role": "user", "message": {"content": "Finish the changes"}}
        for platform, event in (("claude", claude), ("codex", codex), ("cursor", cursor)):
            with self.subTest(platform=platform):
                notes = transcripts.TranscriptDiagnostics()
                lines = ["", "not JSON", "[1, 2]", '{"type":"unknown"}', json.dumps(event), json.dumps(event)]
                self.assertEqual(list(transcripts.iter_events(lines, notes)), [(platform, event)] * 2)
                self.assertEqual((notes.lines, notes.parse_errors), (5, 2))

    def test_user_text_excludes_tool_results_and_supports_codex_event_variants(self):
        blocks = [{"type": "text", "text": "Proceed"}, {"type": "tool_result", "content": "private output"}]
        claude = {"type": "user", "message": {"content": blocks}}
        cursor = {"role": "user", "message": {"content": "Proceed"}}
        codex_message = {
            "type": "response_item",
            "payload": {"role": "user", "type": "message", "content": [{"type": "input_text", "text": "Proceed"}]},
        }
        codex_event = {"type": "event_msg", "payload": {"type": "user_message", "message": "Proceed"}}
        for platform, event in (
            ("claude", claude),
            ("cursor", cursor),
            ("codex", codex_message),
            ("codex", codex_event),
        ):
            with self.subTest(platform=platform, event=event.get("type", "message")):
                self.assertEqual(transcripts.user_text(event, platform), ["Proceed"])
        claude["message"]["content"] = [None, *blocks]
        with self.assertRaises(transcripts.TranscriptShapeError):
            transcripts.user_text(claude, "claude")
        self.assertEqual(transcripts.user_text(claude, "claude", strict=False), ["Proceed"])

    def test_tool_calls_keep_names_inputs_and_ids(self):
        arguments = {"file_path": "src/example.py"}
        block = {"type": "tool_use", "name": "Read", "id": "c1", "input": arguments}
        message = {"content": [block, {"type": "text", "text": "Reading"}]}
        for platform, event in (
            ("claude", {"type": "assistant", "message": message}),
            ("cursor", {"role": "assistant", "message": message}),
            (
                "codex",
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "Read",
                        "call_id": "c1",
                        "arguments": json.dumps(arguments),
                    },
                },
            ),
        ):
            with self.subTest(platform=platform):
                expected = json.dumps(arguments) if platform == "codex" else arguments
                self.assertEqual(transcripts.tool_calls(event, platform), [("Read", expected, "c1")])

    def test_codex_commands_support_argument_and_action_forms(self):
        self.assertEqual(transcripts.codex_command({"arguments": '{"cmd": "pytest -q"}'}), "pytest -q")
        action = {"command": ["/bin/bash", "-lc", "printf '%s' 'two words'"]}
        self.assertEqual(transcripts.codex_command({"arguments": "malformed", "action": action}), action["command"][2])
        vector = ["printf", "%s", "literal; npm test"]
        self.assertEqual(list(transcripts.shell_segments(transcripts.shell_command(vector))), [vector])

    def test_shell_segments_keep_quoted_and_escaped_operators_in_arguments(self):
        command = r"""printf '%s' ';' "a&&b" a\|b && (pytest -q) # ignore ; npm lint
cat path 2>&1
cat</repo/skills/demo/SKILL.md"""
        self.assertEqual(
            list(transcripts.shell_segments(command)),
            [
                ["printf", "%s", ";", "a&&b", "a|b"],
                ["pytest", "-q"],
                ["cat", "path", "2", ">&", "1"],
                ["cat", "<", "/repo/skills/demo/SKILL.md"],
            ],
        )
        self.assertEqual(list(transcripts.shell_segments("pytest && echo 'unterminated; npm test")), [])

    def test_shell_segments_handle_line_continuations_and_escaped_comment_boundaries(self):
        command = "npm " + "\\" + "\n" + r""" ci && printf '%s' one\ #literal && go te""" + "\\" + "\n" + "st ./..."
        self.assertEqual(
            list(transcripts.shell_segments(command)),
            [["npm", "ci"], ["printf", "%s", "one #literal"], ["go", "test", "./..."]],
        )

    def test_shell_segments_keep_quoted_redirects_and_skip_heredoc_bodies(self):
        command = """cat <<-'EOF' <<"OTHER"
	This isn't a command
	pytest
	EOF
sh -c 'fake
OTHER
npm install >test && printf '%s' '>'"""
        self.assertEqual(
            list(transcripts.shell_segments(command, include_redirections=False)),
            [["cat"], ["npm", "install"], ["printf", "%s", ">"]],
        )
        self.assertEqual(
            list(transcripts.shell_segments(command)),
            [["cat", "<<-", "EOF", "<<", "OTHER"], ["npm", "install", ">", "test"], ["printf", "%s", ">"]],
        )

    def test_discovery_respects_relocated_stores_and_deduplicates_codex_roots(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp).resolve()
            claude = home / "claude-config"
            codex = home / "codex-config"
            fallback = home / ".agents" / "sessions"
            events = (
                (claude / "projects" / "-work-repo" / "session.jsonl", 10),
                (claude / "projects" / "-work-repo" / "subagents" / "agent.jsonl", 20),
                (claude / "projects" / "-work-neighbor" / "session.jsonl", 20),
                (codex / "sessions" / "session.jsonl", 20),
                (fallback / "nested" / "rollout.jsonl", 30),
                (fallback / "expired.jsonl", 1),
            )
            for path, timestamp in events:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
                os.utime(path, (timestamp, timestamp))
            env = {"HOME": str(home), "CLAUDE_CONFIG_DIR": str(claude), "CODEX_HOME": str(codex)}
            with patch.dict(os.environ, env):
                self.assertEqual(
                    transcripts.discover(["/work/repo"], 5),
                    [(30, "codex", events[4][0]), (20, "codex", events[3][0]), (10, "claude", events[0][0])],
                )
                with patch.dict(os.environ, {"CODEX_HOME": str(fallback.parent)}):
                    self.assertEqual(
                        transcripts.discover([], 5, platform="codex"),
                        [(30, "codex", events[4][0])],
                    )


if __name__ == "__main__":
    unittest.main()
