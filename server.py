"""pl-holidays-mcp — MCP server for Polish public holidays and business-day math.

Wraps https://date.nager.at/api/v3/ — Nager.Date's open holiday database
(no auth, MIT-licensed data) — and adds Polish-specific business-day logic
on top: is_business_day(), count_business_days(), and add_business_days().
The weekend is always Saturday + Sunday, whatever `country` is passed; only
the holiday list depends on the country.

Primary use case: Polish JDG bookkeeping — invoice payment terms are
counted in business days ("14 dni roboczych"), VAT return deadlines shift
around public holidays, and manual calendar math is error-prone.

Tools: list_holidays, is_holiday, is_business_day, count_business_days,
add_business_days, next_holidays.

Author: Bartosz Kuć <firma@bartosza.pl>
Repo:   https://github.com/bartosz-kuc/honest-pl-holidays-mcp
License: MIT
"""

import asyncio
import json
import re
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

import requests
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

NAGER_BASE = "https://date.nager.at/api/v3"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_date(s: str) -> date:
    if not DATE_RE.match(s):
        raise ValueError(f"Date must be YYYY-MM-DD, got {s!r}")
    return date.fromisoformat(s)


@lru_cache(maxsize=32)
def _fetch_year(year: int, country: str = "PL") -> tuple[dict, ...]:
    resp = requests.get(f"{NAGER_BASE}/PublicHolidays/{year}/{country}", timeout=30)
    resp.raise_for_status()
    return tuple(resp.json())


def _holiday_dates(year: int, country: str = "PL") -> set[date]:
    return {_parse_date(h["date"]) for h in _fetch_year(year, country)}


def _is_business_day(d: date, country: str = "PL") -> bool:
    # Weekend is hard-coded to Saturday/Sunday for every country.
    if d.weekday() >= 5:
        return False
    return d not in _holiday_dates(d.year, country)


server = Server("pl-holidays")


async def _list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_holidays",
            description=(
                "List all Polish public holidays in a given year. Each holiday has date, localName (Polish name), "
                "name (English name), and type. Defaults to Poland but supports any ISO 3166-1 alpha-2 country code."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "4-digit year"},
                    "country": {"type": "string", "default": "PL", "description": "ISO 3166-1 alpha-2 country code (default PL)"},
                },
                "required": ["year"],
            },
        ),
        Tool(
            name="is_holiday",
            description="Check whether a specific date is a public holiday in Poland. Returns holiday details if yes, null if no.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "country": {"type": "string", "default": "PL", "description": "ISO 3166-1 alpha-2 country code (default PL)"},
                },
                "required": ["date"],
            },
        ),
        Tool(
            name="is_business_day",
            description=(
                "Check whether a date is a Polish business day — Monday–Friday and not a public holiday. "
                "Returns the answer plus the reason (weekend / holiday / business_day). "
                "The weekend is always Saturday + Sunday, whatever `country` is passed; only the holiday list "
                "changes per country, so results are wrong for countries with a different weekend."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "country": {"type": "string", "default": "PL", "description": "ISO 3166-1 alpha-2 country code for the holiday list (default PL); does not change the Sat/Sun weekend"},
                },
                "required": ["date"],
            },
        ),
        Tool(
            name="count_business_days",
            description=(
                "Count business days between two dates (inclusive), skipping weekends and Polish public holidays. "
                "Useful for enforcing '14-dni-roboczych' style payment terms. "
                "The weekend is always Saturday + Sunday, whatever `country` is passed; only the holiday list "
                "changes per country."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "from_date": {"type": "string", "description": "YYYY-MM-DD (inclusive)"},
                    "to_date": {"type": "string", "description": "YYYY-MM-DD (inclusive)"},
                    "country": {"type": "string", "default": "PL", "description": "ISO 3166-1 alpha-2 country code for the holiday list (default PL); does not change the Sat/Sun weekend"},
                },
                "required": ["from_date", "to_date"],
            },
        ),
        Tool(
            name="add_business_days",
            description=(
                "Add N business days to a start date and return the resulting date. N can be negative to subtract. "
                "Skips weekends and Polish public holidays. If start_date is itself a non-business day, counting starts "
                "from the next business day (the previous one when N is negative). "
                "The weekend is always Saturday + Sunday, whatever `country` is passed; only the holiday list "
                "changes per country."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "days": {"type": "integer", "description": "Number of business days to add (negative to subtract)"},
                    "country": {"type": "string", "default": "PL", "description": "ISO 3166-1 alpha-2 country code for the holiday list (default PL); does not change the Sat/Sun weekend"},
                },
                "required": ["start_date", "days"],
            },
        ),
        Tool(
            name="next_holidays",
            description="Get the upcoming public holidays (default: next 5) from a given date. Handy for planning around long weekends.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_date": {"type": "string", "description": "YYYY-MM-DD, defaults to today"},
                    "count": {"type": "integer", "default": 5, "description": "How many upcoming holidays to return"},
                    "country": {"type": "string", "default": "PL", "description": "ISO 3166-1 alpha-2 country code (default PL)"},
                },
            },
        ),
    ]


async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    country = arguments.get("country", "PL").upper()

    if name == "list_holidays":
        year = int(arguments["year"])
        holidays = list(_fetch_year(year, country))
        return [TextContent(type="text", text=json.dumps({"year": year, "country": country, "count": len(holidays), "holidays": holidays}, ensure_ascii=False, indent=2))]

    if name == "is_holiday":
        d = _parse_date(arguments["date"])
        holidays = _fetch_year(d.year, country)
        for h in holidays:
            if h["date"] == d.isoformat():
                return [TextContent(type="text", text=json.dumps({"date": d.isoformat(), "is_holiday": True, "holiday": h}, ensure_ascii=False, indent=2))]
        return [TextContent(type="text", text=json.dumps({"date": d.isoformat(), "is_holiday": False, "holiday": None}, ensure_ascii=False, indent=2))]

    if name == "is_business_day":
        d = _parse_date(arguments["date"])
        weekday = d.weekday()
        if weekday >= 5:
            reason = "weekend"
            answer = False
        elif d in _holiday_dates(d.year, country):
            reason = "holiday"
            answer = False
        else:
            reason = "business_day"
            answer = True
        return [TextContent(type="text", text=json.dumps({
            "date": d.isoformat(),
            "is_business_day": answer,
            "reason": reason,
            "weekday": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][weekday],
        }, ensure_ascii=False, indent=2))]

    if name == "count_business_days":
        start = _parse_date(arguments["from_date"])
        end = _parse_date(arguments["to_date"])
        if end < start:
            raise ValueError("to_date must be on or after from_date")
        count = 0
        d = start
        while d <= end:
            if _is_business_day(d, country):
                count += 1
            d += timedelta(days=1)
        return [TextContent(type="text", text=json.dumps({
            "from_date": start.isoformat(),
            "to_date": end.isoformat(),
            "business_days": count,
            "total_days": (end - start).days + 1,
        }, ensure_ascii=False, indent=2))]

    if name == "add_business_days":
        start = _parse_date(arguments["start_date"])
        n = int(arguments["days"])
        step = 1 if n >= 0 else -1
        remaining = abs(n)
        d = start
        # Align to next/prev business day if start isn't one, without counting it.
        while not _is_business_day(d, country):
            d += timedelta(days=step)
        while remaining > 0:
            d += timedelta(days=step)
            if _is_business_day(d, country):
                remaining -= 1
        return [TextContent(type="text", text=json.dumps({
            "start_date": start.isoformat(),
            "days_added": n,
            "result_date": d.isoformat(),
        }, ensure_ascii=False, indent=2))]

    if name == "next_holidays":
        from_str = arguments.get("from_date")
        d = _parse_date(from_str) if from_str else date.today()  # noqa: DTZ011
        count = int(arguments.get("count", 5))
        collected: list[dict] = []
        year = d.year
        while len(collected) < count and year <= d.year + 3:
            holidays = _fetch_year(year, country)
            for h in holidays:
                hd = _parse_date(h["date"])
                if hd > d:
                    collected.append(h)
                    if len(collected) >= count:
                        break
            year += 1
        return [TextContent(type="text", text=json.dumps({"from_date": d.isoformat(), "country": country, "count": len(collected), "holidays": collected}, ensure_ascii=False, indent=2))]

    raise ValueError(f"Unknown tool: {name}")


async def on_list_tools(ctx, params) -> ListToolsResult:
    return ListToolsResult(tools=await _list_tools())


async def on_call_tool(ctx, params) -> CallToolResult:
    return CallToolResult(content=await _call_tool(params.name, params.arguments or {}))


server.add_request_handler("tools/list", types.PaginatedRequestParams, on_list_tools)
server.add_request_handler("tools/call", types.CallToolRequestParams, on_call_tool)


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def sync_main():
    """Sync entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    sync_main()
