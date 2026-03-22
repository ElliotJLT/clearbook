"""FastMCP application instance — shared across server and tools."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Clearbook",
    instructions=(
        "Discover and evaluate UK regulated professional service providers. "
        "Search conveyancers, mortgage brokers, and financial advisers with "
        "regulatory status, disciplinary history, and company health data. "
        "Also includes conveyancing knowledge tools: stamp duty calculator, "
        "lease term checker, search result explainer, survey issue explainer, "
        "title register analyser, and transaction tracker."
    ),
)
