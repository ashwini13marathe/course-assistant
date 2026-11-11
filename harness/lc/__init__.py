"""The LangChain layer: thin wrappers around harness.ops.

    AppContext    per-run context set by the app (role, username, runtime, guardrails)
    build_tools   the 18 tools, each a few lines around Workspace
    middleware    tool filter, context assembly, permission gate, approvals, call limit
    build_agent   create_agent with all of the above
"""
