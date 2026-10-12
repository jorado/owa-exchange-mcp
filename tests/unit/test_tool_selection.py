"""Unit test: the EXCHANGE_MCP_TOOLS / --tools allowlist (exchange_mcp/tool_selection.py).

No mailbox, no browser, no EXCHANGE_OWA_URL: a bare MCPServer with a handful of
dummy tools stands in for the real 65.

What this pins:
1. Parsing: commas and/or whitespace separate names; blank means *no filter*,
   never "allow nothing".
2. Applying: every tool not named is removed, named ones stay, and None is a
   no-op.
3. Diagnosis: allowlisted names that match no tool come back as `unknown`
   (a typo must not silently hide a tool), and leaving out the sign-in tools
   is reported.
4. The real server: every name in a read-only + drafts set
   exists, so documentation built on it cannot drift into a typo.

Run:
    python -m tests.unit.test_tool_selection
"""

import sys

from mcp.server.mcpserver import MCPServer

from exchange_mcp import tool_selection as ts

_failures: list[str] = []

# A read-only + drafts selection: the case EXCHANGE_MCP_TOOLS exists for.
READ_AND_DRAFTS = (
    "check_session,login,get_emails,get_email,search_emails,get_folders,"
    "get_email_links,download_attachments,find_person,get_calendar_events,"
    "get_calendar_event,find_free_time,find_meeting_time,create_draft,create_reply_draft"
)


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  OK   {name}")
        return
    _failures.append(f"{name}{': ' + detail if detail else ''}")
    print(f"  FAIL {name}{': ' + detail if detail else ''}")


def _server(*names: str) -> MCPServer:
    mcp = MCPServer()
    for name in names:
        mcp.add_tool(lambda: "", name=name)
    return mcp


def test_parse() -> None:
    print("parse_tool_allowlist")
    check("commas", ts.parse_tool_allowlist("a,b") == frozenset({"a", "b"}))
    check("commas + spaces + newlines", ts.parse_tool_allowlist(" a, b\n c ,, ") == frozenset({"a", "b", "c"}))
    default = ts.parse_tool_allowlist(ts.DEFAULT_SELECTION)
    check("None -> the default selection", ts.parse_tool_allowlist(None) == default)
    check("empty -> the default selection", ts.parse_tool_allowlist("") == default)
    check("whitespace/commas only -> the default selection", ts.parse_tool_allowlist(" , \n") == default)
    check("'all' -> no filter", ts.parse_tool_allowlist("all") is None)
    check("'all' wins over names", ts.parse_tool_allowlist("get_emails, all") is None)


def test_presets() -> None:
    print("presets expand and combine")
    read_drafts = frozenset(ts.PRESETS["read-drafts"])
    check("preset expands", ts.parse_tool_allowlist("read-drafts") == read_drafts)
    check("preset + extra name", ts.parse_tool_allowlist("read-drafts,send_email") == read_drafts | {"send_email"})
    check("read-drafts keeps the sign-in tools", set(ts.SIGN_IN_TOOLS) <= read_drafts)
    check("the default selection parses to all or a known preset",
          ts.DEFAULT_SELECTION == ts.ALL or ts.DEFAULT_SELECTION in ts.PRESETS, ts.DEFAULT_SELECTION)


def test_apply() -> None:
    print("apply_tool_allowlist")
    mcp = _server("login", "check_session", "get_emails", "send_email", "delete_email")
    result = ts.apply_tool_allowlist(mcp, frozenset({"login", "check_session", "get_emails"}))
    remaining = set(ts.registered_tool_names(mcp))
    check("only allowlisted tools remain", remaining == {"login", "check_session", "get_emails"}, repr(remaining))
    check("excluded reported", result["excluded"] == ["delete_email", "send_email"], repr(result))
    check("kept reported", result["kept"] == ["check_session", "get_emails", "login"], repr(result))
    check("nothing unknown", result["unknown"] == [], repr(result))
    check("sign-in tools present", result["missing_sign_in"] == [], repr(result))

    mcp = _server("get_emails", "send_email")
    result = ts.apply_tool_allowlist(mcp, None)
    check("None removes nothing", set(ts.registered_tool_names(mcp)) == {"get_emails", "send_email"})
    check("None excludes nothing", result["excluded"] == [], repr(result))


def test_diagnosis() -> None:
    print("unknown names and missing sign-in tools are reported")
    mcp = _server("login", "check_session", "get_emails")
    result = ts.apply_tool_allowlist(mcp, frozenset({"get_emails", "get_emial"}))
    check("typo reported as unknown", result["unknown"] == ["get_emial"], repr(result))
    check("missing sign-in tools reported", result["missing_sign_in"] == ["login", "check_session"], repr(result))
    check("typo did not keep anything extra", set(ts.registered_tool_names(mcp)) == {"get_emails"})


def test_documented_selection_exists() -> None:
    print("every tool in the documented read-only + drafts set is a real tool")
    from exchange_mcp.server import mcp  # importing it registers all tool modules
    import exchange_mcp.tools.email  # noqa: F401  (registration side effect)

    real = set(ts.registered_tool_names(mcp))
    wanted = ts.parse_tool_allowlist(READ_AND_DRAFTS)
    check("15 names in the documented set", len(wanted) == 15, str(len(wanted)))
    check("matches the read-drafts preset", wanted == frozenset(ts.PRESETS["read-drafts"]),
          repr(sorted(wanted ^ frozenset(ts.PRESETS["read-drafts"]))))
    for name, tools in ts.PRESETS.items():
        check(f"every tool in preset {name!r} exists", set(tools) <= real, repr(sorted(set(tools) - real)))
    check("all exist", wanted <= real, repr(sorted(wanted - real)))
    check("no send/reply/forward tool in it",
          not wanted & {"send_email", "reply_email", "forward_email"}, repr(sorted(wanted)))


def main() -> bool:
    for test in (test_parse, test_presets, test_apply, test_diagnosis, test_documented_selection_exists):
        test()
    print()
    if _failures:
        print(f"{len(_failures)} check(s) failed:")
        for failure in _failures:
            print(f"  - {failure}")
        return False
    print("All checks passed.")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
