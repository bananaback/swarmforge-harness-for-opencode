#!/usr/bin/env python3
"""
Regenerate deepseek-report.html from the OpenCode SQLite database.

Scope: sessions created from 5 Sep 2026 up to now, DeepSeek family models only.

Per-session token fields map to the report as:
  ti  = tokens_input
  to  = tokens_output + tokens_reasoning
  tr  = tokens_reasoning
  tcr = tokens_cache_read
Requests = number of messages in the session.
"""

import sqlite3, datetime, json, os, re, sys

DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deepseek-report.html")
START_DATE = datetime.datetime(2026, 9, 5)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def model_key(model_json):
    try:
        model = json.loads(model_json)
    except (TypeError, ValueError):
        return None
    mid = model.get("id", "")
    if not mid.startswith("deepseek"):
        return None
    variant = model.get("variant")
    return mid + (f" ({variant})" if variant else "")


def empty():
    return {"requests": 0, "ti": 0, "to": 0, "tr": 0, "tcr": 0, "cost": 0}


def add(bucket, ti, to, tr, tcr, cost):
    bucket["ti"] += ti
    bucket["to"] += to + tr
    bucket["tr"] += tr
    bucket["tcr"] += tcr
    bucket["cost"] += cost


def collect(db_path, start, end):
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    msg_counts = dict(
        cur.execute("SELECT session_id, COUNT(*) FROM message GROUP BY session_id").fetchall()
    )
    cur.execute(
        """
        SELECT id, time_created, model, agent, tokens_input, tokens_output,
               tokens_reasoning, tokens_cache_read, cost
        FROM session WHERE time_created >= ? AND time_created < ?
        ORDER BY time_created
        """,
        (start_ms, end_ms),
    )
    rows = cur.fetchall()
    cur.execute(
        """
        SELECT COUNT(*) FROM message m JOIN session s ON s.id = m.session_id
        WHERE s.time_created >= ? AND s.time_created < ?
        """,
        (start_ms, end_ms),
    )
    all_requests = cur.fetchone()[0]
    conn.close()

    days, by_model, by_model_agent, grand = {}, {}, {}, empty()
    for sid, ts, model_json, agent, ti, to, tr, tcr, cost in rows:
        key = model_key(model_json)
        if key is None:
            continue
        agent = agent or "build"
        req = msg_counts.get(sid, 0)
        day = datetime.datetime.fromtimestamp(ts / 1000).strftime("%m/%d")
        day_bucket = days.setdefault(day, {"models": {}, "total": empty()})
        add(day_bucket["models"].setdefault(key, empty()), ti, to, tr, tcr, cost)
        day_bucket["models"][key]["requests"] += req
        add(day_bucket["total"], ti, to, tr, tcr, cost)
        day_bucket["total"]["requests"] += req
        add(by_model.setdefault(key, empty()), ti, to, tr, tcr, cost)
        by_model[key]["requests"] += req
        add(grand, ti, to, tr, tcr, cost)
        grand["requests"] += req
        ma = by_model_agent.setdefault(
            (key, agent),
            {"model": key, "agent": agent, "requests": 0, "ti": 0, "to": 0, "cost": 0},
        )
        ma["requests"] += req
        ma["ti"] += ti
        ma["to"] += to + tr
        ma["cost"] += cost

    day_list = []
    cursor = start
    while cursor < end:
        label = cursor.strftime("%m/%d")
        bucket = days.get(label, {"models": {}, "total": empty()})
        day_list.append({"date": label, "models": bucket["models"], "total": bucket["total"]})
        cursor += datetime.timedelta(days=1)

    by_model_list = [dict(model=k, **v) for k, v in
                     sorted(by_model.items(), key=lambda kv: kv[1]["requests"], reverse=True)]
    by_model_agent_list = sorted(by_model_agent.values(),
                                 key=lambda r: r["requests"], reverse=True)
    return {
        "days": day_list,
        "by_model": by_model_list,
        "by_model_agent": by_model_agent_list,
        "grand": grand,
        "all_requests": all_requests,
    }


def date_range_label(start, end):
    if start.year == end.year and start.month == end.month:
        return f"{start.day}-{end.day} {MONTHS[start.month - 1]} {start.year}"
    return (f"{start.day} {MONTHS[start.month - 1]} - "
            f"{end.day} {MONTHS[end.month - 1]} {end.year}")


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    now = datetime.datetime.now()
    data = collect(db_path, START_DATE, now)
    label = date_range_label(START_DATE, now)

    html = open(REPORT, encoding="utf-8").read()
    html = re.sub(r"const D = \{.*?\};\n", "const D = " + json.dumps(data) + ";\n",
                  html, count=1, flags=re.S)
    html = re.sub(r"<title>.*?</title>", f"<title>DeepSeek Usage Report \u2014 {label}</title>", html)
    html = re.sub(r'<div class="sub">.*?</div>',
                  f'<div class="sub">{label} &middot; All requests using DeepSeek family models</div>',
                  html, count=1)
    html = re.sub(r"<h2>\d[^<]*Total</h2>", f"<h2>{label} Total</h2>", html, count=1)
    open(REPORT, "w", encoding="utf-8").write(html)
    g = data["grand"]
    print(f"updated {REPORT}: {data['days'][0]['date']}..{data['days'][-1]['date']}, "
          f"{g['requests']} requests, {g['ti'] + g['to'] + g['tcr']:,} tokens, ${g['cost']:.4f}")


if __name__ == "__main__":
    main()
