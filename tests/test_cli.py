"""Comprehensive tests for prior_tools.cli — every command, stdin merge, formatting, errors."""

import io
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from prior_tools.cli import _read_stdin_json, main


# ─── Helpers ────────────────────────────────────────────────

def make_stdin(text, is_tty=False):
    """Return a StringIO that behaves like piped stdin."""
    s = io.StringIO(text)
    s.isatty = lambda: is_tty
    return s


def mock_client(**overrides):
    """Build a MagicMock PriorClient with sensible defaults."""
    c = MagicMock()
    c.me.return_value = {"ok": True, "data": {
        "agentId": "ag_test", "agentName": "test-agent", "credits": 42,
        "tier": "free", "contributions": 5, "totalEarned": 100, "totalSpent": 58,
    }}
    c.search.return_value = {"ok": True, "data": {"results": [], "cost": {"creditsCharged": 0}}}
    c.contribute.return_value = {"ok": True, "data": {"id": "k_new123", "creditsEarned": 10}}
    c.feedback.return_value = {"ok": True, "data": {"creditsRefunded": 1}}
    c.get_entry.return_value = {"ok": True, "data": {
        "id": "k_abc", "title": "Test", "status": "active", "qualityScore": 0.8,
        "tags": ["python"], "content": "Some content",
    }}
    c.retract.return_value = None
    c.claim.return_value = {"ok": True, "data": {}}
    c.verify.return_value = {"ok": True, "data": {}}
    for k, v in overrides.items():
        getattr(c, k).return_value = v
    return c


@pytest.fixture
def client():
    return mock_client()


def run_cli(argv, client, monkeypatch, stdin_text=None):
    """Run main() with a mocked client and optional stdin, return capsys-like nothing."""
    if stdin_text is not None:
        monkeypatch.setattr("sys.stdin", make_stdin(stdin_text))
    else:
        monkeypatch.setattr("sys.stdin", make_stdin("", is_tty=True))
    with patch("prior_tools.cli.PriorClient", return_value=client):
        main(argv)


# ─── _read_stdin_json ───────────────────────────────────────

class TestReadStdinJson:
    def test_returns_none_when_tty(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", make_stdin("", is_tty=True))
        assert _read_stdin_json() is None

    def test_parses_valid_json(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", make_stdin('{"a": 1}'))
        assert _read_stdin_json() == {"a": 1}

    def test_returns_none_on_empty(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", make_stdin(""))
        assert _read_stdin_json() is None

    def test_returns_none_on_whitespace(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", make_stdin("   \n  "))
        assert _read_stdin_json() is None

    def test_exits_on_invalid_json(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", make_stdin("{bad"))
        with pytest.raises(SystemExit):
            _read_stdin_json()

    def test_exits_on_array(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", make_stdin("[1,2]"))
        with pytest.raises(SystemExit):
            _read_stdin_json()

    def test_exits_on_scalar(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", make_stdin('"hello"'))
        with pytest.raises(SystemExit):
            _read_stdin_json()


# ─── cmd_status ─────────────────────────────────────────────

class TestStatus:
    def test_human_output(self, client, monkeypatch, capsys):
        run_cli(["status"], client, monkeypatch)
        out = capsys.readouterr().out
        assert "ag_test" in out
        assert "42" in out
        assert "free" in out

    def test_json_output(self, client, monkeypatch, capsys):
        run_cli(["--json", "status"], client, monkeypatch)
        data = json.loads(capsys.readouterr().out)
        assert data["agentId"] == "ag_test"

    def test_error_response(self, monkeypatch):
        c = mock_client(me={"ok": False, "error": "unauthorized"})
        with pytest.raises(SystemExit):
            run_cli(["status"], c, monkeypatch)


# ─── cmd_search ─────────────────────────────────────────────

class TestSearch:
    def test_multi_word_query_joined(self, client, monkeypatch):
        run_cli(["search", "foo", "bar", "baz"], client, monkeypatch)
        client.search.assert_called_once()
        assert client.search.call_args[1]["max_results"] == 3
        # first positional is query
        assert client.search.call_args[0][0] == "foo bar baz"

    def test_max_results_alias(self, client, monkeypatch):
        run_cli(["search", "q", "-n", "7"], client, monkeypatch)
        assert client.search.call_args[1]["max_results"] == 7

    def test_no_results_message(self, client, monkeypatch, capsys):
        run_cli(["search", "nothing"], client, monkeypatch)
        assert "No results found" in capsys.readouterr().out

    def test_results_display(self, monkeypatch, capsys):
        c = mock_client(search={"ok": True, "data": {
            "results": [{"title": "Fix X", "id": "k_1", "relevanceScore": 0.85,
                          "trustLevel": "high", "tags": ["py"], "problem": "err",
                          "solution": "do Y"}],
            "cost": {"creditsCharged": 1, "balanceRemaining": 41},
        }})
        run_cli(["search", "err"], c, monkeypatch)
        out = capsys.readouterr().out
        assert "Fix X" in out
        assert "0.850" in out

    def test_json_flag(self, client, monkeypatch, capsys):
        run_cli(["--json", "search", "q"], client, monkeypatch)
        data = json.loads(capsys.readouterr().out)
        assert "results" in data

    def test_empty_query_errors(self, monkeypatch):
        # argparse requires at least one query word (nargs="+")
        with pytest.raises(SystemExit):
            run_cli(["search"], mock_client(), monkeypatch)

    def test_context_flags(self, client, monkeypatch):
        run_cli(["search", "q", "--context-os", "linux", "--context-shell", "bash",
                 "--context-tools", "docker", "git"], client, monkeypatch)
        ctx = client.search.call_args[1]["context"]
        assert ctx["os"] == "linux"
        assert ctx["shell"] == "bash"
        assert ctx["tools"] == ["docker", "git"]

    def test_min_quality_and_max_tokens(self, client, monkeypatch):
        run_cli(["search", "q", "--min-quality", "0.5", "--max-tokens", "1000"], client, monkeypatch)
        assert client.search.call_args[1]["min_quality"] == 0.5
        assert client.search.call_args[1]["max_tokens"] == 1000


# ─── cmd_contribute ─────────────────────────────────────────

class TestContribute:
    BASIC_JSON = json.dumps({"title": "T", "content": "C", "tags": ["py"]})

    def test_stdin_provides_all(self, client, monkeypatch, capsys):
        run_cli(["contribute"], client, monkeypatch, stdin_text=self.BASIC_JSON)
        out = capsys.readouterr().out
        assert "k_new123" in out
        assert "10" in out
        client.contribute.assert_called_once()
        kw = client.contribute.call_args
        assert kw[1]["title"] == "T"
        assert kw[1]["tags"] == ["py"]

    def test_cli_flags_override_stdin(self, client, monkeypatch):
        stdin = json.dumps({"title": "old", "content": "old", "tags": ["old"]})
        run_cli(["contribute", "--title", "new", "--content", "new", "--tags", "new"],
                client, monkeypatch, stdin_text=stdin)
        kw = client.contribute.call_args[1]
        assert kw["title"] == "new"
        assert kw["content"] == "new"
        assert kw["tags"] == ["new"]

    def test_partial_merge(self, client, monkeypatch):
        stdin = json.dumps({"title": "T", "tags": ["a"]})
        run_cli(["contribute", "--content", "C"], client, monkeypatch, stdin_text=stdin)
        kw = client.contribute.call_args[1]
        assert kw["title"] == "T"
        assert kw["content"] == "C"
        assert kw["tags"] == ["a"]

    def test_missing_title_errors(self, client, monkeypatch):
        stdin = json.dumps({"content": "C", "tags": ["a"]})
        with pytest.raises(SystemExit):
            run_cli(["contribute"], client, monkeypatch, stdin_text=stdin)

    def test_missing_content_errors(self, client, monkeypatch):
        stdin = json.dumps({"title": "T", "tags": ["a"]})
        with pytest.raises(SystemExit):
            run_cli(["contribute"], client, monkeypatch, stdin_text=stdin)

    def test_missing_tags_errors(self, client, monkeypatch):
        stdin = json.dumps({"title": "T", "content": "C"})
        with pytest.raises(SystemExit):
            run_cli(["contribute"], client, monkeypatch, stdin_text=stdin)

    def test_tags_from_stdin_array(self, client, monkeypatch):
        stdin = json.dumps({"title": "T", "content": "C", "tags": ["a", "b", "c"]})
        run_cli(["contribute"], client, monkeypatch, stdin_text=stdin)
        assert client.contribute.call_args[1]["tags"] == ["a", "b", "c"]

    def test_effort_from_stdin(self, client, monkeypatch):
        stdin = json.dumps({"title": "T", "content": "C", "tags": ["a"],
                            "effort": {"tokensUsed": 5000, "durationSeconds": 300}})
        run_cli(["contribute"], client, monkeypatch, stdin_text=stdin)
        assert client.contribute.call_args[1]["effort"] == {"tokensUsed": 5000, "durationSeconds": 300}

    def test_effort_cli_overrides_stdin(self, client, monkeypatch):
        stdin = json.dumps({"title": "T", "content": "C", "tags": ["a"],
                            "effort": {"tokensUsed": 100}})
        run_cli(["contribute", "--effort-tokens", "999"], client, monkeypatch, stdin_text=stdin)
        assert client.contribute.call_args[1]["effort"]["tokensUsed"] == 999

    def test_environment_from_stdin_object(self, client, monkeypatch):
        env = {"language": "python", "os": "linux"}
        stdin = json.dumps({"title": "T", "content": "C", "tags": ["a"], "environment": env})
        run_cli(["contribute"], client, monkeypatch, stdin_text=stdin)
        assert client.contribute.call_args[1]["environment"] == env

    def test_environment_cli_json_string(self, client, monkeypatch):
        env = {"language": "go"}
        run_cli(["contribute", "--title", "T", "--content", "C", "--tags", "a",
                 "--environment", json.dumps(env)], client, monkeypatch)
        assert client.contribute.call_args[1]["environment"] == env

    def test_error_messages_from_stdin(self, client, monkeypatch):
        stdin = json.dumps({"title": "T", "content": "C", "tags": ["a"],
                            "errorMessages": ["err1", "err2"]})
        run_cli(["contribute"], client, monkeypatch, stdin_text=stdin)
        assert client.contribute.call_args[1]["error_messages"] == ["err1", "err2"]

    def test_failed_approaches_from_stdin(self, client, monkeypatch):
        stdin = json.dumps({"title": "T", "content": "C", "tags": ["a"],
                            "failedApproaches": ["tried X"]})
        run_cli(["contribute"], client, monkeypatch, stdin_text=stdin)
        assert client.contribute.call_args[1]["failed_approaches"] == ["tried X"]

    def test_json_output(self, client, monkeypatch, capsys):
        run_cli(["--json", "contribute"], client, monkeypatch, stdin_text=self.BASIC_JSON)
        data = json.loads(capsys.readouterr().out)
        assert data["id"] == "k_new123"

    def test_model_default_unknown(self, client, monkeypatch):
        run_cli(["contribute"], client, monkeypatch, stdin_text=self.BASIC_JSON)
        assert client.contribute.call_args[1]["model"] == "unknown"

    def test_model_from_stdin(self, client, monkeypatch):
        stdin = json.dumps({"title": "T", "content": "C", "tags": ["a"], "model": "gpt-4"})
        run_cli(["contribute"], client, monkeypatch, stdin_text=stdin)
        assert client.contribute.call_args[1]["model"] == "gpt-4"


# ─── cmd_feedback ───────────────────────────────────────────

class TestFeedback:
    def test_positional_args(self, client, monkeypatch, capsys):
        run_cli(["feedback", "k_abc", "useful"], client, monkeypatch)
        out = capsys.readouterr().out
        assert "Refund: 1" in out
        client.feedback.assert_called_once()
        assert client.feedback.call_args[1]["entry_id"] == "k_abc"
        assert client.feedback.call_args[1]["outcome"] == "useful"

    def test_stdin_provides_fields(self, client, monkeypatch):
        stdin = json.dumps({"entryId": "k_xyz", "outcome": "not_useful", "reason": "old"})
        run_cli(["feedback"], client, monkeypatch, stdin_text=stdin)
        kw = client.feedback.call_args[1]
        assert kw["entry_id"] == "k_xyz"
        assert kw["outcome"] == "not_useful"
        assert kw["reason"] == "old"

    def test_cli_overrides_stdin(self, client, monkeypatch):
        stdin = json.dumps({"entryId": "k_old", "outcome": "useful"})
        run_cli(["feedback", "k_new", "not_useful"], client, monkeypatch, stdin_text=stdin)
        kw = client.feedback.call_args[1]
        assert kw["entry_id"] == "k_new"
        assert kw["outcome"] == "not_useful"

    def test_correction_from_stdin(self, client, monkeypatch):
        stdin = json.dumps({"entryId": "k_1", "outcome": "not_useful",
                            "correction": {"content": "x" * 100, "title": "Fixed"}})
        run_cli(["feedback"], client, monkeypatch, stdin_text=stdin)
        corr = client.feedback.call_args[1]["correction"]
        assert corr["title"] == "Fixed"
        assert len(corr["content"]) == 100

    def test_missing_entry_id_errors(self, client, monkeypatch):
        stdin = json.dumps({"outcome": "useful"})
        with pytest.raises(SystemExit):
            run_cli(["feedback"], client, monkeypatch, stdin_text=stdin)

    def test_missing_outcome_errors(self, client, monkeypatch):
        stdin = json.dumps({"entryId": "k_1"})
        with pytest.raises(SystemExit):
            run_cli(["feedback"], client, monkeypatch, stdin_text=stdin)

    def test_invalid_outcome_errors(self, monkeypatch):
        # argparse choices will reject "bad" as positional
        with pytest.raises(SystemExit):
            run_cli(["feedback", "k_1", "bad"], mock_client(), monkeypatch)

    def test_json_output(self, client, monkeypatch, capsys):
        run_cli(["--json", "feedback", "k_1", "useful"], client, monkeypatch)
        data = json.loads(capsys.readouterr().out)
        assert data["creditsRefunded"] == 1


# ─── cmd_get ────────────────────────────────────────────────

class TestGet:
    def test_human_output(self, client, monkeypatch, capsys):
        run_cli(["get", "k_abc"], client, monkeypatch)
        out = capsys.readouterr().out
        assert "Test" in out
        assert "Some content" in out

    def test_json_output(self, client, monkeypatch, capsys):
        run_cli(["--json", "get", "k_abc"], client, monkeypatch)
        data = json.loads(capsys.readouterr().out)
        assert data["id"] == "k_abc"

    def test_missing_id_errors(self, client, monkeypatch):
        with pytest.raises(SystemExit):
            run_cli(["get"], client, monkeypatch)


# ─── cmd_retract ────────────────────────────────────────────

class TestRetract:
    def test_retract_output(self, client, monkeypatch, capsys):
        run_cli(["retract", "k_abc"], client, monkeypatch)
        assert "Retracted: k_abc" in capsys.readouterr().out
        client.retract.assert_called_once_with("k_abc")


# ─── cmd_claim / cmd_verify ────────────────────────────────

class TestClaimVerify:
    def test_claim_output(self, client, monkeypatch, capsys):
        run_cli(["claim", "a@b.com"], client, monkeypatch)
        out = capsys.readouterr().out
        assert "a@b.com" in out
        client.claim.assert_called_once_with("a@b.com")

    def test_verify_output(self, client, monkeypatch, capsys):
        run_cli(["verify", "123456"], client, monkeypatch)
        assert "claimed successfully" in capsys.readouterr().out
        client.verify.assert_called_once_with("123456")

    def test_claim_json(self, client, monkeypatch, capsys):
        run_cli(["--json", "claim", "a@b.com"], client, monkeypatch)
        json.loads(capsys.readouterr().out)  # should be valid JSON

    def test_verify_json(self, client, monkeypatch, capsys):
        run_cli(["--json", "verify", "123456"], client, monkeypatch)
        json.loads(capsys.readouterr().out)


# ─── Help text ──────────────────────────────────────────────

class TestHelp:
    @pytest.mark.parametrize("cmd,keywords", [
        (["--help"], ["status", "search", "contribute", "feedback"]),
        (["status", "--help"], ["agent", "credit"]),
        (["search", "--help"], ["query", "max-results"]),
        (["contribute", "--help"], ["title", "content", "tags", "stdin"]),
        (["feedback", "--help"], ["outcome", "useful"]),
        (["get", "--help"], ["entry"]),
        (["retract", "--help"], ["retract"]),
        (["claim", "--help"], ["email"]),
        (["verify", "--help"], ["code"]),
    ])
    def test_help_contains_keywords(self, cmd, keywords, monkeypatch, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("prior_tools.cli.PriorClient"):
                main(cmd)
        assert exc_info.value.code == 0
        out = capsys.readouterr().out.lower()
        for kw in keywords:
            assert kw in out, f"'{kw}' not found in help for {cmd}"


# ─── No command → help ──────────────────────────────────────

class TestNoCommand:
    def test_no_command_exits_zero(self, monkeypatch, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("prior_tools.cli.PriorClient"):
                main([])
        assert exc_info.value.code == 0


# ─── Client init failure ───────────────────────────────────

class TestClientInitFailure:
    def test_client_init_error(self, monkeypatch):
        with patch("prior_tools.cli.PriorClient", side_effect=RuntimeError("no config")):
            with pytest.raises(SystemExit):
                main(["status"])
