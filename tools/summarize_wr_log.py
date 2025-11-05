#!/usr/bin/env python3
import argparse, csv, json, os, re, sys

RE_INTERIM = re.compile(r'INTERIM RESULT:\s*colors\s*=\s*(\d+)\s*time\s*=\s*([\d.]+)\s*s', re.I)
RE_IMPROVE = re.compile(r'\[IMPROVE\].*?(\d+)\s*(?:→|->)\s*(\d+)', re.U)
RE_TIME = re.compile(r'time\s*=\s*([\d.]+)\s*s', re.I)
RE_FINAL = re.compile(r'FINAL RESULT:\s*colors\s*=\s*(\d+).*?conflicts\s*=\s*(\d+).*?time\s*=\s*([\d.]+)\s*s', re.I)
RE_TDA = re.compile(r'\bTDA\s*=\s*(true|false)\b', re.I)
RE_TDA_GPU = re.compile(r'\bTDA\s*GPU\s*=\s*(true|false)\b', re.I)
RE_TDA_ACCEL = re.compile(r'GPU-accelerated TDA', re.I)

def infer_seed_profile(base_config: str):
    if not base_config:
        return None, None
    base = os.path.basename(base_config)
    seed = None
    m = re.search(r'seed_(\d+)', base)
    if m:
        try:
            seed = int(m.group(1))
        except ValueError:
            seed = None
    profile = 'aggr' if 'aggr' in base else 'regular'
    return seed, profile

def parse_log(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[summarize] failed to read log: {e}", file=sys.stderr)
        sys.exit(2)

    interim = []  # list of dicts: {colors, time_s, line_no}
    improvements = []  # list: {old, new, time_s, line_no, text}
    best_colors = None
    best_time = None
    first_interim = None
    last_time_seen = None
    interim_count = 0
    final = None
    tda = None
    tda_gpu = None

    for i, line in enumerate(lines):
        m_time = RE_TIME.search(line)
        if m_time:
            try:
                last_time_seen = float(m_time.group(1))
            except ValueError:
                pass

        m_interim = RE_INTERIM.search(line)
        if m_interim:
            try:
                c = int(m_interim.group(1)); t = float(m_interim.group(2))
            except ValueError:
                continue
            interim_count += 1
            last_time_seen = t
            entry = {"colors": c, "time_s": t, "line_no": i}
            interim.append(entry)
            if first_interim is None:
                first_interim = entry
            if best_colors is None or c < best_colors:
                best_colors, best_time = c, t

        m_impr = RE_IMPROVE.search(line)
        if m_impr:
            try:
                old = int(m_impr.group(1)); new = int(m_impr.group(2))
            except ValueError:
                old = new = None
            t = None
            m_t2 = RE_TIME.search(line)
            if m_t2:
                try:
                    t = float(m_t2.group(1))
                    last_time_seen = t
                except ValueError:
                    t = None
            if t is None:
                t = last_time_seen
            improvements.append({"old": old, "new": new, "time_s": t, "line_no": i, "text": line.strip()})
            if new is not None and (best_colors is None or new < best_colors):
                best_colors, best_time = new, t

        m_final = RE_FINAL.search(line)
        if m_final:
            try:
                final = {
                    "colors": int(m_final.group(1)),
                    "conflicts": int(m_final.group(2)),
                    "time_s": float(m_final.group(3)),
                    "line_no": i
                }
            except ValueError:
                final = None

        m_tda = RE_TDA.search(line)
        if m_tda:
            tda = (m_tda.group(1).lower() == 'true')
        m_tda_gpu = RE_TDA_GPU.search(line)
        if m_tda_gpu:
            tda_gpu = (m_tda_gpu.group(1).lower() == 'true')
        if RE_TDA_ACCEL.search(line):
            tda = True
            tda_gpu = True

    last_improve_time = None
    if improvements:
        for ev in reversed(improvements):
            if ev.get("time_s") is not None:
                last_improve_time = ev["time_s"]
                break

    summary = {
        "first_interim": first_interim,
        "best": {"colors": best_colors, "time_s": best_time} if best_colors is not None else None,
        "interim_count": interim_count,
        "improve_events": improvements,
        "improve_count": sum(1 for ev in improvements if ev.get("new") is not None and ev.get("old") is not None and ev["new"] < ev["old"]),
        "last_improve_time_s": last_improve_time,
        "final": final,
        "tda": tda,
        "tda_gpu": tda_gpu,
    }
    return summary

def append_csv_row(csv_path, row):
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    fields = [
        "seed","profile","base_config","log_file",
        "first_colors","first_time_s","best_colors","best_time_s",
        "improve_events","last_improve_time_s","tda","tda_gpu",
        "interim_count","final_colors","final_conflicts","final_time_s"
    ]
    with open(csv_path, 'a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})

def main():
    ap = argparse.ArgumentParser(description="Summarize DSJC1000 WR log into CSV/JSON.")
    ap.add_argument("log", help="Path to log file")
    ap.add_argument("--base-config", default="", help="Path to base config used (optional)")
    ap.add_argument("--csv-append", default="", help="Append summary row to this CSV path")
    ap.add_argument("--json-out", default="", help="Write detailed JSON summary to this path")
    args = ap.parse_args()

    summary = parse_log(args.log)
    seed, profile = infer_seed_profile(args.base_config)

    first = summary["first_interim"] or {}
    best = summary["best"] or {}
    final = summary["final"] or {}

    csv_row = {
        "seed": seed if seed is not None else "",
        "profile": profile or "",
        "base_config": args.base_config,
        "log_file": args.log,
        "first_colors": first.get("colors", ""),
        "first_time_s": first.get("time_s", ""),
        "best_colors": best.get("colors", ""),
        "best_time_s": best.get("time_s", ""),
        "improve_events": summary["improve_count"],
        "last_improve_time_s": summary["last_improve_time_s"] if summary["last_improve_time_s"] is not None else "",
        "tda": "" if summary["tda"] is None else str(summary["tda"]).lower(),
        "tda_gpu": "" if summary["tda_gpu"] is None else str(summary["tda_gpu"]).lower(),
        "interim_count": summary["interim_count"],
        "final_colors": final.get("colors", ""),
        "final_conflicts": final.get("conflicts", ""),
        "final_time_s": final.get("time_s", ""),
    }

    # Human-friendly print
    print("=== WR Log Summary ===")
    print(f"log: {args.log}")
    if args.base_config:
        print(f"base_config: {args.base_config}")
    if seed is not None or profile:
        print(f"seed: {seed if seed is not None else 'unknown'} | profile: {profile or 'unknown'}")
    print(f"interim_count: {summary['interim_count']}")
    if first:
        print(f"first_interim: colors={first.get('colors')} time={first.get('time_s')}s")
    if best:
        print(f"best: colors={best.get('colors')} time={best.get('time_s')}s")
    print(f"improve_events: {summary['improve_count']}{' (last at ' + str(csv_row['last_improve_time_s']) + 's)' if csv_row['last_improve_time_s'] != '' else ''}")
    if summary["tda"] is not None or summary["tda_gpu"] is not None:
        print(f"tda: {csv_row['tda']} | tda_gpu: {csv_row['tda_gpu']}")
    if final:
        print(f"final: colors={final.get('colors')} conflicts={final.get('conflicts')} time={final.get('time_s')}s")

    if args.csv_append:
        append_csv_row(args.csv_append, csv_row)
        print(f"[summary] appended CSV row -> {args.csv_append}")
    if args.json_out:
        os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
        with open(args.json_out, 'w', encoding='utf-8') as jf:
            json.dump({
                "meta": {
                    "log_file": args.log,
                    "base_config": args.base_config,
                    "seed": seed,
                    "profile": profile
                },
                "summary": summary
            }, jf, ensure_ascii=False, indent=2)
        print(f"[summary] wrote JSON -> {args.json_out}")

if __name__ == "__main__":
    main()