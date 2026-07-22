# pl-holidays-mcp

Local MCP server for **Polish public holidays and business-day arithmetic**. Wraps the open [Nager.Date](https://date.nager.at/) holiday database and adds bookkeeping-friendly business-day math on top.

Part of the [honest-mcp family](https://github.com/bartosz-kuc?tab=repositories) of small, auditable, local-first MCP servers.

## Why

Every Polish accountant, JDG owner, or HR person has this problem:

- "Payment term is **14 dni roboczych** from invoice date — what's the actual due date?"
- "Is the client's 'termin płatności 2026-05-01' the same as `next_business_day(2026-05-01)`? (No — that's Święto Pracy.)"
- "Deadline for JPK_V7 is the 25th — but 2026-04-25 is a Saturday, does it slip to Monday?"

This server hands both raw holiday data and business-day arithmetic to your AI. No more spreadsheet calendars.

Supports any country Nager.Date covers (110+), but the API defaults to Poland and the bookkeeping angle is Poland-centric.

## Features

Six tools:

- `list_holidays` — all public holidays in a given year
- `is_holiday` — is this specific date a public holiday?
- `is_business_day` — is this date Mon–Fri and not a holiday? Includes reason (weekend / holiday / business_day)
- `count_business_days` — inclusive business-day count between two dates
- `add_business_days` — start_date + N business days = ? (N can be negative)
- `next_holidays` — upcoming N holidays from a given date

## Data source

- Endpoint: [date.nager.at/api/v3](https://date.nager.at/)
- No API key
- MIT-licensed holiday data
- In-memory year cache — one round trip per year per session

## Requirements

- Python 3.10+

## Setup

```bash
git clone https://github.com/bartosz-kuc/pl-holidays-mcp.git
cd pl-holidays-mcp
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Register with Claude Code:

```bash
claude mcp add pl-holidays /absolute/path/to/venv/bin/python /absolute/path/to/server.py
```

Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "pl-holidays": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

## Example usage

> "Invoice issued today with 14 working-day payment term — when is it due?"

`add_business_days(start_date="2026-07-22", days=14)` → the due date, skipping weekends and Polish public holidays.

> "How many working days between 2026-04-01 and 2026-04-30?"

`count_business_days(from_date="2026-04-01", to_date="2026-04-30")`

> "Is May 1st 2026 a business day in Poland?"

`is_business_day(date="2026-05-01")` → false, reason: holiday (Święto Pracy).

## Data flow

```
Your AI client
     ↕  MCP stdio
This server (Python, on your machine)
     ↕  HTTPS
date.nager.at (Nager.Date open holiday DB)
```

No cloud middle for anything but the initial holiday-date fetch. No telemetry.

## Author

**Bartosz Kuć** — Warsaw-based developer, JDG owner running [skanfirmy.pl](https://skanfirmy.pl).

- GitHub: https://github.com/bartosz-kuc

- Email: firma@bartosza.pl

## Consulting

Available for consulting on Polish tax and business integrations (KSeF, GUS/NFZ/GIOŚ APIs, mBank data), MCP server design, and AI-assisted tooling for JDGs and small teams. Reach out via email.

## License

MIT — see [LICENSE](LICENSE).

## Related

- Part of the honest-mcp family — see the [family index](https://github.com/bartosz-kuc?tab=repositories).
