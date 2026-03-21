# Clearbook

MCP server for discovering UK regulated professional services. Agents find conveyancers, mortgage brokers, and financial advisers.

## Quick Start

```bash
pip install -e ".[dev]"
python -m clearbook
```

## What it does

Clearbook aggregates data from UK regulatory registers (SRA, FCA, Companies House) into a single MCP server that AI agents can query to find and evaluate professional service providers.

## Tools

- `search_conveyancers` — Find SRA-regulated conveyancing firms by postcode
- `search_mortgage_brokers` — Find FCA-authorised mortgage brokers by postcode
- `get_provider_profile` — Full enriched profile with regulatory + company health data
- `get_disciplinary_history` — Check enforcement actions
- `compare_providers` — Side-by-side factual comparison
