"""Operator-chosen tool allowlist (`EXCHANGE_MCP_TOOLS` / `--tools`).

A deployment that only wants a subset of the 65 tools - e.g. "read mail and
calendar, write drafts, never send" - names that subset once, and every client
(OpenCode, Codex, Claude Code ...) sees the same reduced listing. Doing it here
rather than in each client's config is the point: client-side filters differ
per tool, some have none, and a filter that lives in one client's config is
silently absent from the next one someone connects.

Pure logic, no Playwright: takes the `MCPServer` as a parameter, like
`hot_reload.py`, so it stays unit-testable and importable from both
`server.py` and `hot_reload.py` without a cycle.

Besides tool names, a selection may name a **preset** (`PRESETS`), which
expands to its tools and can be combined with further names
(`read-drafts,send_email`), or `all`, which turns the filter off. When nothing
is configured, `DEFAULT_SELECTION` applies - `read-drafts` in this fork, so an
unconfigured server can read and draft but never send; `all` restores every
tool.

Two rules are load-bearing:

- **Unset means the default.** An empty or whitespace-only value is
  `DEFAULT_SELECTION`, never "allow nothing" - an env var that exists but is
  blank is what a config template leaves behind, and a server with zero tools
  is not what anyone asked for.
- **Unknown names are reported, not ignored.** A typo in an allowlist hides
  a tool the operator meant to keep, and the only symptom would be the agent
  never using it. So every name that matches no registered tool comes back in
  `unknown` for the startup log.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

# Tools without which a reduced listing can't recover from an expired session:
# the operator is warned (not overruled) when the allowlist leaves them out.
SIGN_IN_TOOLS: tuple[str, ...] = ("login", "check_session")

# The selection word that disables filtering, wherever it appears.
ALL = "all"

# Named selections. `read-drafts`: read mail, calendar and the directory, and
# write drafts - nothing that sends, deletes, moves or changes an item, so a
# human reviews everything that leaves the mailbox (create_draft and
# create_reply_draft are SaveOnly by construction).
PRESETS: dict[str, tuple[str, ...]] = {
    "read-drafts": (
        *SIGN_IN_TOOLS,
        "get_emails", "get_email", "search_emails", "get_folders",
        "get_email_links", "download_attachments",
        "find_person",
        "get_calendar_events", "get_calendar_event", "find_free_time", "find_meeting_time",
        "create_draft", "create_reply_draft",
    ),
}

# What applies when EXCHANGE_MCP_TOOLS / --tools is unset or blank.
DEFAULT_SELECTION = "read-drafts"


def parse_tool_allowlist(raw: str | None) -> frozenset[str] | None:
    """Parse a selection into tool names; None means "no filter".

    `"a, b c"` -> `{"a", "b", "c"}`; a preset name expands to its tools; `all`
    anywhere -> None. Unset or blank falls back to `DEFAULT_SELECTION`.
    """
    words = [part for part in re.split(r"[\s,]+", raw or "") if part]
    if not words:
        words = [part for part in re.split(r"[\s,]+", DEFAULT_SELECTION) if part]
    if ALL in words:
        return None
    names: set[str] = set()
    for word in words:
        names.update(PRESETS.get(word, (word,)))
    return frozenset(names) or None


def registered_tool_names(mcp: "MCPServer") -> list[str]:
    return [t.name for t in mcp._tool_manager.list_tools()]


def apply_tool_allowlist(mcp: "MCPServer", allowlist: frozenset[str] | None) -> dict[str, Any]:
    """Remove every registered tool not in `allowlist`. No-op for None.

    Returns what happened, for the caller to log: `excluded` (removed),
    `kept`, `unknown` (allowlisted names matching no tool) and
    `missing_sign_in` (sign-in tools the allowlist leaves out).
    """
    registered = registered_tool_names(mcp)
    if allowlist is None:
        return {"excluded": [], "kept": sorted(registered), "unknown": [], "missing_sign_in": []}

    excluded = sorted(name for name in registered if name not in allowlist)
    for name in excluded:
        mcp.remove_tool(name)
    return {
        "excluded": excluded,
        "kept": sorted(name for name in registered if name in allowlist),
        "unknown": sorted(allowlist - set(registered)),
        "missing_sign_in": [name for name in SIGN_IN_TOOLS if name not in allowlist],
    }
