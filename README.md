# Clearbook

MCP server for the UK home-buying journey. Agents find and evaluate conveyancers and mortgage brokers using official regulatory data.

## Why this exists

Buying a house in the UK means trusting professionals you found on Google. Clearbook lets AI agents query official regulatory registers so you can evaluate conveyancers and mortgage brokers on facts, not SEO.

It queries the **SRA Solicitors Register**, **FCA Financial Services Register**, and **Companies House API** in real-time, cross-references them, and returns enriched provider profiles with regulatory status, disciplinary history, and company health data.

## Example

Ask your agent: _"Find me conveyancers near SE22"_

```
┌─────────────────────────┬──────────┬───────────────┬──────────────┬───────────┐
│ Firm                    │ Status   │ Trading Since │ Insolvency   │ Officers  │
├─────────────────────────┼──────────┼───────────────┼──────────────┼───────────┤
│ GT Stewart Limited      │ Active   │ 2011-02-15    │ None         │ 3         │
│ Austen-Jones Solicitors │ Active   │ 2011-02-11    │ None         │ 3         │
│ William Bailey          │ Authorised│ —            │ —            │ —         │
└─────────────────────────┴──────────┴───────────────┴──────────────┴───────────┘
```

Real firms. Real regulatory data. Cross-referenced with Companies House.

## Tools

| Tool | What it does |
|------|-------------|
| `search_conveyancers` | Find SRA-regulated conveyancing firms by UK postcode |
| `search_mortgage_brokers` | Find FCA-authorised mortgage brokers by postcode |
| `get_provider_profile` | Full enriched profile: regulatory + company health |
| `get_disciplinary_history` | Check SRA/FCA enforcement actions |
| `compare_providers` | Side-by-side factual comparison |

## Data sources

| Source | What it provides | Freshness |
|--------|-----------------|-----------|
| **SRA** (Solicitors Regulation Authority) | 25,098 regulated firms, practice areas, offices | Updated daily |
| **FCA** (Financial Conduct Authority) | Mortgage brokers, permissions, disciplinary history | Real-time |
| **Companies House** | Company status, insolvency, charges, officers, incorporation date | Updated daily |

## Setup

### Claude Code

Add to your `~/.mcp.json`:

```json
{
  "mcpServers": {
    "clearbook": {
      "command": "python3",
      "args": ["-m", "clearbook"],
      "env": {
        "SRA_API_KEY": "your_key",
        "FCA_AUTH_EMAIL": "your_email",
        "FCA_AUTH_KEY": "your_key",
        "COMPANIES_HOUSE_API_KEY": "your_key"
      }
    }
  }
}
```

### From source

```bash
git clone https://github.com/ElliotJLT/clearbook.git
cd clearbook
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m clearbook
```

## API keys (all free)

| Source | Register | Link |
|--------|----------|------|
| SRA | Subscribe to "SRA Data Share API V1" | [sra-prod-apim.developer.azure-api.net](https://sra-prod-apim.developer.azure-api.net/signup) |
| FCA | Click "Retrieve API Key" | [register.fca.org.uk/Developer](https://register.fca.org.uk/Developer/s/) |
| Companies House | Create an application | [developer.company-information.service.gov.uk](https://developer.company-information.service.gov.uk/) |

## Important

Clearbook provides **factual data only**. No recommendations, no "best for you" rankings. It presents regulatory status, disciplinary history, and company health — the user decides. This is a regulatory requirement (FCA information vs advice boundary).
