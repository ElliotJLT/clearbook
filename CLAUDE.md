# Clearbook — MCP Server for UK Professional Services Discovery

## What This Is
An MCP server that agents call to find and evaluate UK regulated professional service providers. Aggregates SRA, FCA, and Companies House data into one queryable interface.

## The Rule
Clearbook provides **factual data only**. Never evaluative. Never "recommended for you." The agent presents options, the human decides. This is a regulatory requirement (FCA information vs advice boundary), not a design choice.

## Tech Stack
- Python 3.10+
- FastMCP (mcp[cli])
- httpx (async HTTP)
- pydantic (models)
- pytest + pytest-asyncio (tests)

## Data Sources
| Source | What it gives us | Auth |
|--------|-----------------|------|
| SRA API | Conveyancing firms, practice areas, status | API key (Azure) |
| FCA Register API | Mortgage brokers, permissions, disciplinary history | Email + Key |
| Companies House API | Company health, officers, insolvency | API key (Basic Auth) |

## Architecture
```
server.py          — MCP tool definitions (the interface)
service.py         — Orchestration layer (combines data sources)
models.py          — Pydantic domain models
clients/
  sra.py           — SRA Data Sharing API client
  fca.py           — FCA Register API client
  companies_house.py — Companies House API client
```

## Key Constraints
- All API clients are async (httpx)
- Cache responses (SRA: 24hr, FCA: 1hr, CH: 24hr)
- Rate limit respect (FCA: 50/10s, CH: 600/5min)
- No evaluative language in tool descriptions or responses
- Factual filtering only (location, specialisation, authorisation status)

## Running
```bash
pip install -e ".[dev]"
python -m clearbook.server
```

## Testing
```bash
pytest
```
