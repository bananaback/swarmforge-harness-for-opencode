#!/usr/bin/env python3
"""
Token Usage Calculator — OpenCode Sessions

Formulas:
  Total Input   = tokens_input + tokens_cache_read
  Output        = tokens_output + tokens_reasoning
  Cache Hit     = cache_read / (input + cache_read)
  Output Ratio  = output / (input + cache_read)

Usage:
  python3 calc.py                  # both 14-15 Sep 2026
  python3 calc.py --date 2026-09-14
  python3 calc.py --from 2026-09-14 --to 2026-09-16
  python3 calc.py --session ses_xxx # single session detail
"""

import sqlite3, datetime, json, argparse, sys, os

DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")

def get_sessions(start_ms, end_ms, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Request counts from message table, token/cost from session table (already aggregated)
    cur.execute("""
        SELECT s.id, s.title, s.parent_id, s.agent, s.model,
               s.tokens_input, s.tokens_output, s.tokens_reasoning,
               s.tokens_cache_read, s.tokens_cache_write, s.cost, s.time_created,
               COALESCE(m.cnt, 0) as requests
        FROM session s
        LEFT JOIN (SELECT session_id, COUNT(*) as cnt FROM message GROUP BY session_id) m
          ON m.session_id = s.id
        WHERE s.time_created >= ? AND s.time_created < ?
        ORDER BY s.time_created
    """, (start_ms, end_ms))
    rows = cur.fetchall()
    conn.close()
    sessions = []
    for r in rows:
        sid, title, parent_id, agent, model, ti, to, tr, tcr, tcw, cost, ts, requests = r
        try:
            m = json.loads(model)
            model_name = m.get('id', model)
        except:
            model_name = model
        sessions.append({
            'id': sid, 'title': title or '(no title)', 'parent_id': parent_id,
            'agent': agent or 'build', 'model': model_name,
            'ti': ti or 0, 'to': to or 0, 'tr': tr or 0,
            'tcr': tcr or 0, 'tcw': tcw or 0, 'cost': cost or 0, 'ts': ts,
            'requests': requests or 0
        })
    return sessions

def stats(info):
    ti = info['ti']
    output = info['to'] + info['tr']
    total_input = ti + info['tcr']
    cache_hit = info['tcr'] / total_input if total_input > 0 else 0
    output_ratio = output / total_input if total_input > 0 else 0
    total = ti + output
    return {
        'input': ti, 'output': output, 'reasoning': info['tr'],
        'cache_read': info['tcr'], 'cache_hit': cache_hit,
        'output_ratio': output_ratio, 'total': total,
        'cost': info['cost']
    }

def summarize(sessions):
    ti = to = tr = tcr = tcw = cost = requests = 0
    for s in sessions:
        ti += s['ti']; to += s['to']; tr += s['tr']
        tcr += s['tcr']; tcw += s['tcw']; cost += s['cost']
        requests += s.get('requests', 0)
    total_input = ti + tcr
    output = to + tr
    return {
        'sessions': len(sessions), 'requests': requests,
        'input': ti, 'output': output, 'reasoning': tr,
        'cache_read': tcr, 'cache_write': tcw,
        'total_input': total_input,
        'cache_hit': tcr / total_input if total_input > 0 else 0,
        'output_ratio': output / total_input if total_input > 0 else 0,
        'cost': cost
    }

def fmt(n):
    return f"{n:>12,}"

def print_summary(label, sessions):
    s = summarize(sessions)
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Sessions:    {s['sessions']:>12}")
    print(f"  Requests:    {s['requests']:>12}")
    print(f"  Input:       {fmt(s['input'])}")
    print(f"  Output:      {fmt(s['output'])}  (reasoning {s['reasoning']:,})")
    print(f"  CacheRead:   {fmt(s['cache_read'])}")
    print(f"  CacheHit:    {s['cache_hit']:>11.1%}")
    print(f"  OutputRatio: {s['output_ratio']:>11.1%}")
    print(f"  Cost:        ${s['cost']:>11.4f}")
    print(f"{'='*60}")
    return s

def main():
    parser = argparse.ArgumentParser(description='OpenCode token usage calculator')
    parser.add_argument('--date', help='Single date (YYYY-MM-DD)')
    parser.add_argument('--from', dest='from_date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--to', help='End date exclusive (YYYY-MM-DD)')
    parser.add_argument('--session', help='Single session ID')
    parser.add_argument('--db', default=DB_PATH, help='Database path')
    args = parser.parse_args()

    db_path = args.db

    if args.session:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id, s.title, s.parent_id, s.agent, s.model,
                   s.tokens_input, s.tokens_output, s.tokens_reasoning,
                   s.tokens_cache_read, s.tokens_cache_write, s.cost, s.time_created,
                   COALESCE(m.cnt, 0) as requests
            FROM session s
            LEFT JOIN (SELECT session_id, COUNT(*) as cnt FROM message GROUP BY session_id) m
              ON m.session_id = s.id
            WHERE s.id = ?
        """, (args.session,))
        r = cur.fetchone()
        conn.close()
        if not r:
            print(f"Session {args.session} not found"); sys.exit(1)
        sid, title, parent_id, agent, model, ti, to, tr, tcr, tcw, cost, ts, requests = r
        try:
            m = json.loads(model)
            model_name = m.get('id', model)
        except:
            model_name = model
        sess = {'id': sid, 'title': title or '(no title)', 'parent_id': parent_id,
                'agent': agent or 'build', 'model': model_name,
                'ti': ti or 0, 'to': to or 0, 'tr': tr or 0,
                'tcr': tcr or 0, 'tcw': tcw or 0, 'cost': cost or 0, 'ts': ts}
        s = stats(sess)
        print(f"\nSession: {sess['title']}")
        print(f"  Agent: {sess['agent']}  Model: {sess['model']}")
        created = datetime.datetime.fromtimestamp(sess['ts']/1000).strftime('%Y-%m-%d %H:%M')
        print(f"  Created: {created}")
        print(f"  Requests: {requests}")
        print(f"  Input: {s['input']:,}  Output: {s['output']:,}  Reasoning: {s['reasoning']:,}")
        print(f"  CacheRead: {s['cache_read']:,}  CacheHit: {s['cache_hit']:.1%}  OutRatio: {s['output_ratio']:.1%}")
        print(f"  Cost: ${s['cost']:.4f}")
        return

    if args.date:
        d = datetime.datetime.strptime(args.date, '%Y-%m-%d')
        dates = [(args.date, d, d + datetime.timedelta(days=1))]
    elif args.from_date or args.to:
        start = datetime.datetime.strptime(args.from_date or '2026-09-14', '%Y-%m-%d')
        end = datetime.datetime.strptime(args.to or '2026-09-16', '%Y-%m-%d')
        dates = []
        cur_d = start
        while cur_d < end:
            nxt = cur_d + datetime.timedelta(days=1)
            dates.append((cur_d.strftime('%Y-%m-%d'), cur_d, nxt))
            cur_d = nxt
    else:
        dates = [
            ('14 Sep', datetime.datetime(2026, 9, 14), datetime.datetime(2026, 9, 15)),
            ('15 Sep', datetime.datetime(2026, 9, 15), datetime.datetime(2026, 9, 16)),
        ]

    all_sessions = []
    for label, start_d, end_d in dates:
        start_ms = int(start_d.timestamp() * 1000)
        end_ms = int(end_d.timestamp() * 1000)
        sessions = get_sessions(start_ms, end_ms, db_path)
        print_summary(label, sessions)
        all_sessions.extend(sessions)

    if len(dates) > 1:
        print_summary("TOTAL", all_sessions)

if __name__ == '__main__':
    main()
