---
name: clearbook
description: "Find UK regulated professional services — conveyancers, mortgage brokers, financial advisers. Queries SRA, FCA, and Companies House registers."
version: 1.0.0
emoji: "📋"
metadata:
  openclaw:
    requires:
      bins: [curl, jq]
      env: [SRA_API_KEY]
---

# Clearbook — UK Professional Services Discovery

Find and evaluate UK regulated professional service providers. Queries three government registers and returns enriched, cross-referenced results.

## What You Can Do

When a user needs to find a conveyancer, mortgage broker, or financial adviser in the UK, use this skill to search the official regulatory registers.

## How to Search for Conveyancers

To find conveyancers near a UK postcode, query the SRA Data Sharing API:

```bash
curl -s "https://sra-prod-apim.azure-api.net/datashare/api/V1/organisation/GetAll" \
  -H "Ocp-Apim-Subscription-Key: $SRA_API_KEY" \
  -H "Cache-Control: no-cache" | jq '[.Organisations[] | select(.WorkArea[]? == "Property - Residential") | select(.Offices[]?.Postcode | startswith("POSTCODE_PREFIX")) | {name: .PracticeName, sra_number: .SraNumber, status: .AuthorisationStatus, postcode: .Offices[0].Postcode, phone: .Offices[0].PhoneNumber, email: .Offices[0].Email, website: .Offices[0].Website, work_areas: .WorkArea, company_reg: .CompanyRegNo}] | .[:10]'
```

Replace `POSTCODE_PREFIX` with the first part of the postcode (e.g., "SE15", "SW1", "E1").

## How to Search for Mortgage Brokers

Query the FCA Financial Services Register:

```bash
curl -s "https://register.fca.org.uk/services/V0.1/Search?q=mortgage+broker+LOCATION&type=firm" \
  -H "X-Auth-Email: $FCA_AUTH_EMAIL" \
  -H "X-Auth-Key: $FCA_AUTH_KEY" \
  -H "Accept: application/json" | jq '.Data[:10]'
```

## How to Check Company Health

Cross-reference with Companies House using the company registration number:

```bash
curl -s -u "$COMPANIES_HOUSE_API_KEY:" \
  "https://api.company-information.service.gov.uk/company/COMPANY_NUMBER" | \
  jq '{name: .company_name, status: .company_status, created: .date_of_creation, sic_codes: .sic_codes, insolvency: .has_insolvency_history, charges: .has_charges}'
```

Zero-pad company numbers to 8 digits (e.g., "3120664" → "03120664").

## How to Check Disciplinary History

For FCA-regulated firms, check enforcement actions:

```bash
curl -s "https://register.fca.org.uk/services/V0.1/Firm/FRN/DisciplinaryHistory" \
  -H "X-Auth-Email: $FCA_AUTH_EMAIL" \
  -H "X-Auth-Key: $FCA_AUTH_KEY" \
  -H "Accept: application/json" | jq '.Data'
```

## Data Sources

| Source | What it provides | Coverage |
|--------|-----------------|----------|
| **SRA** (Solicitors Regulation Authority) | 25,098 regulated law firms, practice areas, offices | England & Wales |
| **FCA** (Financial Conduct Authority) | Mortgage brokers, financial advisers, permissions, disciplinary history | UK-wide |
| **Companies House** | Company status, officers, insolvency, charges, SIC codes | UK-wide |

## Important

Clearbook provides **factual data only**. Never make evaluative recommendations like "this is the best firm for you." Present facts — regulatory status, disciplinary history, company health — and let the user decide. This is a regulatory requirement (FCA information vs advice boundary).

## Filtering Tips

- **Conveyancing firms**: Filter SRA WorkArea for `"Property - Residential"` or `"Property - Commercial"`
- **Authorised only**: Filter AuthorisationStatus for `"Authorised"` or `"YES"`
- **By postcode**: Match on the Offices[].Postcode prefix
- **Company health**: Cross-reference CompanyRegNo with Companies House for insolvency/charges data
