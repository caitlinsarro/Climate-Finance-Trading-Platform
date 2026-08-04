# Free Authoritative Data Access

This project uses free official data where possible. Credentials are configured
only through local environment variables. Keys, passwords, and registration
details must never be committed, logged, written to the workbook, or included
in release manifests.

Use:

```text
python3 scripts/ingest_authoritative_data.py status
```

The command reports only `configured: true/false`; it never prints a credential
value.

## Free keys

### EIA Open Data

- **Cost:** free.
- **Registration:** <https://www.eia.gov/opendata/register.php>
- **Required information:** name, email, user category, and intended use.
- **Delivery:** EIA sends the key to the registered email address.
- **No-key alternative:** EIA states that its bulk download facility does not
  require a key.
- **Local variable:** `EIA_API_KEY`.

### FRED / ALFRED

- **Cost:** free API and free personal account.
- **Account/key page:**
  <https://fred.stlouisfed.org/docs/api/fred/v2/api_key.html>
- **Process:** create or sign in to a FRED account, then request a distinct key
  for this application.
- **Important terms:** preserve data-owner copyright notices, identify FRED,
  and do not imply Federal Reserve endorsement.
- **Local variable:** `FRED_API_KEY`.

### BEA Data API

- **Cost:** public registration; no fee is identified in the official signup
  or API guide.
- **Registration:** <https://apps.bea.gov/api/signup/>
- **Required information:** name or organization, durable email address, and
  acceptance of the terms. Disposable email addresses are prohibited.
- **Delivery:** BEA emails a 36-character UserID and activation link.
- **Local variable:** `BEA_API_KEY`.

## No key required

| Source | Access control | Project rule |
|---|---|---|
| U.S. Treasury daily par yields | Public XML feed; no API key | Preserve raw XML and hash; use only as the risk-free leg, never as a complete issuer WACC |
| SEC EDGAR Financial Statement Data Sets | No authentication or API key; identifiable User-Agent with real contact information; no more than 10 requests/second | Completed: all 69 published quarters from 2009 Q1 through 2026 Q1 are locally preserved in `CFP-2026-003-R6-20260801T003356Z`; the contact email is not persisted |
| NWS API | No key; identifiable User-Agent; rate limits | Hazard context only; alerts are not probabilities, issuer exposure, or losses |
| NOAA Storm Events bulk CSV | No registration or key | Preserve raw gzip and hash; reported damage remains incomplete context |
| OpenFEMA API | No registration | Respect terms and dataset-specific limitations |
| EPA eGRID downloads | Direct public XLSX/CSV downloads | Record release vintage and methodology |
| EIA bulk downloads | No key | Record source release and do not falsely attribute transformations to EIA |
| NASA NEX-GDDP-CMIP6 public data services/AWS Open Data | No API key for public paths | Record model, scenario, ensemble, version, units, spatial method, and license |
| NGFS Scenario Explorer Phase 5.1 API | Public guest access subject to license; ephemeral token is not persisted | Official USA transition pathways are loaded; scenarios are conditional and model ranges are not probabilities; affected physical-damage variables remain excluded |

## Local setup

1. Copy `.env.example` to an ignored local file or export variables directly
   from the terminal.
2. Fill only the keys you obtained from the official providers.
3. Do not paste secrets into chat, source code, Excel, JSON manifests, issues,
   commits, or pull requests.
4. Verify:

```text
python3 scripts/ingest_authoritative_data.py status
```

The ingestion script supports no-key NWS, NOAA Storm Events, and U.S. Treasury
releases. Credentialed EIA, FRED/ALFRED, and BEA ingestion will be implemented
only after local keys are configured.

Example Treasury ingestion:

```text
python3 scripts/ingest_authoritative_data.py treasury \
  --release-id CFP-2026-003-R2-YYYYMMDDTHHMMZ \
  --treasury-year 2026
```

Release IDs are immutable. Never rerun ingestion into an existing release ID.

Example NGFS transition ingestion:

```text
python3 scripts/ingest_authoritative_data.py ngfs-transition \
  --release-id CFP-2026-003-RX-YYYYMMDDTHHMMZ \
  --ngfs-region USA \
  --ngfs-end-year 2050
```

Example SEC history ingestion after setting a compliant `SEC_USER_AGENT` only
in the local environment:

```text
python3 scripts/ingest_authoritative_data.py sec-financials \
  --release-id CFP-2026-003-RX-YYYYMMDDTHHMMZ \
  --sec-start-year 2009 \
  --sec-end-year 2026 \
  --sec-end-quarter 1
```

This is 69 quarterly archives. Raw ZIP bytes are local and Git-ignored; the
manifest records source URLs, retrieval state, and hashes. The resumable command
reuses an already downloaded archive only after its immutable path is resolved.

The governed processed release is `CFP-2026-003-R8-20260801T005207Z`. It reads
the immutable R6 raw archive, applies controlled historical registrant aliases
(including XOM's historical CIK), and records hashes for both the facts and
coverage CSV files. Loaded financial history does not authorize FCFF use until
the selected filings and accounting boundaries are manually tied out.
