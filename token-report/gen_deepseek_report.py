#!/usr/bin/env python3
"""
Regenerate deepseek-report.html from the OpenCode SQLite database.

Scope: provider requests made from --since (default 5 Sep 2026) up to now,
DeepSeek family models only.

What counts as a request
------------------------
opencode writes exactly one `step-finish` part per provider call:

  * the session step loop creates a fresh assistant message per step and calls
    the processor once per step (packages/opencode/src/session/prompt.ts),
  * the processor runs one llm.stream() per call and, on the response, writes a
    `step-finish` part carrying that request's tokens and cost, accumulating
    them onto the assistant message (packages/opencode/src/session/processor.ts).

Session cost/tokens are the sum of those parts, so:

    one step-finish part == one billable request to the provider

A user message is not a request: it has no usage and no cost, it is only the
parent of the turn's assistant messages. Each request is bucketed by the day it
was made (part.time_created) and attributed to the model recorded on its own
message, not to the session's creation day or final model.

Two costs are reported, for the same requests, so they can be compared
----------------------------------------------------------------------
* `go_reported` - the value stored in the DB, i.e. what OpenCode Go (the
              subscription provider `opencode-go`) recorded for the request.
              Session.getUsage prices a request as input*input +
              (output+reasoning)*output + cache_read*cache_read +
              cache_write*cache_write (packages/opencode/src/session/session.ts)
              using the rates in models.json, and those rates are DeepSeek's
              OFF-PEAK rates only - so peak traffic is recorded at half price.
* `go_cost` - the same tokens priced with the OpenCode Go table below, picking
              the peak or off-peak rate per request. This is the peak-aware
              figure; the gap against `go_reported` is the undercount.

Both cover only requests served by the `opencode-go` provider; the direct
`deepseek` provider is billed differently (and was free for the expiring model).

Peak hours are 01:00-04:00 and 06:00-10:00 UTC, Monday-Friday; everything else,
including weekends, is off-peak.

Per-request token fields map to the report as:
  ti  = tokens.input
  to  = tokens.output + tokens.reasoning
  tr  = tokens.reasoning
  tcr = tokens.cache.read
  tcw = tokens.cache.write

Known gap: opencode's title generation (session/prompt.ts ensureTitle) calls
llm.stream() directly and discards the usage event, so those requests cost money
but leave no message, part, or cost behind. They are counted, not costed, as
`unrecorded_title_calls` (one per titled top-level session).

The report HTML reads one embedded object, `const D = {...};`, and derives every
number it shows from it; that line is the only thing this script rewrites.
"""

import argparse
import datetime
import json
import os
import re
import sqlite3

from deepseek_report import (
    ALIASES,
    Request,
    is_go_priced,
    is_peak,
    request_cost,
)

DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deepseek-report.html")
DEFAULT_SINCE = "2026-09-05"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Display names for the priced DeepSeek models, keyed by resolved model id.
MODEL_NAMES = {
    "deepseek-v4.1-flash": "DeepSeek V4.1 Flash",
    "deepseek-v4-flash": "DeepSeek V4 Flash",
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "deepseek-v4-flash-vision-exp": "DeepSeek V4 Flash Vision Exp",
}

# One row per billable request: the step-finish part and its message's model.
REQUESTS_SQL = """
SELECT p.time_created,
       json_extract(m.data, '$.providerID'),
       json_extract(m.data, '$.modelID'),
       json_extract(m.data, '$.variant'),
       json_extract(p.data, '$.tokens.input'),
       json_extract(p.data, '$.tokens.output'),
       json_extract(p.data, '$.tokens.reasoning'),
       json_extract(p.data, '$.tokens.cache.read'),
       json_extract(p.data, '$.tokens.cache.write'),
       json_extract(p.data, '$.cost')
FROM part p
JOIN message m ON m.id = p.message_id
WHERE json_extract(p.data, '$.type') = 'step-finish'
  AND p.time_created >= ? AND p.time_created < ?
  AND json_extract(m.data, '$.modelID') LIKE 'deepseek%'
"""

# Top-level sessions that got a title: each is one unrecorded provider request.
TITLED_SESSIONS_SQL = """
SELECT title FROM session
WHERE time_created >= ? AND time_created < ?
  AND parent_id IS NULL
  AND json_extract(model, '$.id') LIKE 'deepseek%'
"""

DEFAULT_TITLE = re.compile(
    r"^(New session - |Child session - )\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
)


def model_key(model_id, variant):
    if not model_id or not model_id.startswith("deepseek"):
        return None
    # opencode omits the variant when it is the default one (session/prompt.ts
    # serializes "default" as absent, and resolves it back to "default").
    return f"{model_id} ({variant or 'default'})"


def empty():
    return {"requests": 0, "ti": 0, "to": 0, "tr": 0, "tcr": 0, "tcw": 0, "cost": 0.0,
            "go_reported": 0.0, "go_cost": 0.0, "go_requests": 0,
            "peak_cost": 0.0, "offpeak_cost": 0.0}


def add(bucket, ti, to, tr, tcr, tcw, cost):
    bucket["requests"] += 1
    bucket["ti"] += ti
    bucket["to"] += to + tr
    bucket["tr"] += tr
    bucket["tcr"] += tcr
    bucket["tcw"] += tcw
    bucket["cost"] += cost


def collect(db_path, start, end):
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    rows = cur.execute(REQUESTS_SQL, (start_ms, end_ms)).fetchall()
    titles = [r[0] or "" for r in cur.execute(TITLED_SESSIONS_SQL, (start_ms, end_ms))]
    conn.close()

    days, by_model, grand = {}, {}, empty()
    for ts, provider, mid, variant, ti, to, tr, tcr, tcw, cost in rows:
        key = model_key(mid, variant)
        if key is None:
            continue
        ti, to, tr = ti or 0, to or 0, tr or 0
        tcr, tcw, cost = tcr or 0, tcw or 0, cost or 0
        moment = datetime.datetime.fromtimestamp(ts / 1000, datetime.timezone.utc)
        request = Request(
            timestamp=moment,
            provider=provider or "",
            model=mid,
            input=ti,
            output=to,
            reasoning=tr,
            cache_read=tcr,
            cache_write=tcw,
            stored_cost=cost,
        )
        peak = is_peak(moment)
        priced = is_go_priced(request)
        # reasoning is billed at the output rate (Session.getUsage), so price
        # output + reasoning together, exactly as `add()` records them.
        go = request_cost(request) if priced else 0.0
        day = datetime.datetime.fromtimestamp(ts / 1000).strftime("%m/%d")
        bm = by_model.setdefault(key, {**empty(), "model": key, "id": mid,
                                       "go_model": MODEL_NAMES.get(ALIASES.get(mid, mid))})
        for bucket in (days.setdefault(day, empty()), bm, grand):
            add(bucket, ti, to, tr, tcr, tcw, cost)
            if priced:
                bucket["go_requests"] += 1
                bucket["go_cost"] += go
                bucket["go_reported"] += cost
                bucket["peak_cost" if peak else "offpeak_cost"] += go

    day_list = []
    cursor = start
    while cursor < end:
        label = cursor.strftime("%m/%d")
        day_list.append({"date": label, **days.get(label, empty())})
        cursor += datetime.timedelta(days=1)

    by_model_list = [v for _, v in
                     sorted(by_model.items(), key=lambda kv: kv[1]["go_cost"], reverse=True)]
    return {
        "range": date_range_label(start, end),
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "unrecorded_title_calls": sum(1 for t in titles if not DEFAULT_TITLE.match(t)),
        "cycle": build_cycle(start, end, grand, days),
        "grand": grand,
        "days": day_list,
        "by_model": by_model_list,
    }


def build_cycle(start, end, grand, days):
    """The Go billing cycle runs 5th -> 5th; project the spend rate to its end."""
    year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    cycle_end = start.replace(year=year, month=month)
    total_days = (cycle_end - start).days
    elapsed = max((end - start).total_seconds() / 86400, 1e-9)
    per_day = grand["go_cost"] / elapsed

    labels, reported, actual, projected = [], [], [], []
    cum = rep = 0.0
    for i in range(total_days + 1):
        day = start + datetime.timedelta(days=i)
        label = day.strftime("%m/%d")
        labels.append(label)
        if day.date() <= end.date():
            bucket = days.get(label, empty())
            cum += bucket["go_cost"]
            rep += bucket["go_reported"]
            actual.append(round(cum, 6))
            reported.append(round(rep, 6))
            projected.append(round(cum, 6) if day.date() == end.date() else None)
        else:
            actual.append(None)
            reported.append(None)
            projected.append(round(cum + per_day * (day.date() - end.date()).days, 6))

    return {
        "start": start.strftime("%d %b %Y"),
        "end": cycle_end.strftime("%d %b %Y"),
        "total_days": total_days,
        "elapsed_days": round(elapsed, 1),
        "per_day": round(per_day, 4),
        "projected_go_cost": round(per_day * total_days, 4),
        "labels": labels,
        "reported": reported,
        "actual": actual,
        "projected": projected,
    }


def date_range_label(start, end):
    if start.year == end.year and start.month == end.month:
        return f"{start.day}-{end.day} {MONTHS[start.month - 1]} {start.year}"
    if start.year == end.year:
        return (f"{start.day} {MONTHS[start.month - 1]} - "
                f"{end.day} {MONTHS[end.month - 1]} {end.year}")
    return (f"{start.day} {MONTHS[start.month - 1]} {start.year} - "
            f"{end.day} {MONTHS[end.month - 1]} {end.year}")


def main():
    parser = argparse.ArgumentParser(description="Regenerate the DeepSeek usage report")
    parser.add_argument("db", nargs="?", default=None, help="path to opencode.db")
    parser.add_argument("--db", dest="db_flag", default=None, help="path to opencode.db")
    parser.add_argument("--since", default=DEFAULT_SINCE,
                        help="first day to include, YYYY-MM-DD (default %(default)s)")
    args = parser.parse_args()

    start = datetime.datetime.strptime(args.since, "%Y-%m-%d")
    now = datetime.datetime.now()
    data = collect(args.db_flag or args.db or DB_PATH, start, now)

    html = open(REPORT, encoding="utf-8").read()
    html = re.sub(r"const D = \{.*?\};\n",
                  lambda _: "const D = " + json.dumps(data) + ";\n",
                  html, count=1, flags=re.S)
    html = re.sub(r"<title>.*?</title>",
                  lambda _: f"<title>DeepSeek Usage Report \u2014 {data['range']}</title>",
                  html, count=1)
    open(REPORT, "w", encoding="utf-8").write(html)

    g, cy = data["grand"], data["cycle"]
    print(f"updated {REPORT}: {data['range']}, {g['requests']} requests, "
          f"{g['ti'] + g['to'] + g['tcr'] + g['tcw']:,} tokens")
    print(f"  reported ${g['go_reported']:.4f} | peak-aware ${g['go_cost']:.4f} "
          f"(peak ${g['peak_cost']:.4f}, off-peak ${g['offpeak_cost']:.4f}) "
          f"| projected {cy['end']} ${cy['projected_go_cost']:.2f} "
          f"at ${cy['per_day']:.4f}/day, day {cy['elapsed_days']}/{cy['total_days']}")
    print(f"  +{data['unrecorded_title_calls']} unrecorded title calls, "
          f"{g['requests'] - g['go_requests']} requests not on Go")


if __name__ == "__main__":
    main()
