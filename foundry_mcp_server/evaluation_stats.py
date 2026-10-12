"""Summarize recorded events; no MCP/network/model access."""
import argparse
import collections
import json
import statistics
from datetime import datetime
from pathlib import Path


def summarize(records, run_id=None, task_id=None, include_calls=False):
    # Deduplicate by recorder instance/sequence when overlapping files are read.
    unique = {(r["instance_id"], r["sequence"]): r for r in records}
    groups = collections.defaultdict(list)
    sequences = collections.defaultdict(set)
    for r in unique.values():
        sequences[r["instance_id"]].add(r["sequence"])
        if r.get("event") not in {"call_started", "call_finished"}:
            continue
        if run_id is not None and r.get("run_id") != run_id:
            continue
        if task_id is not None and r.get("task_id") != task_id:
            continue
        key = (r.get("run_id"), r.get("task_id"), r.get("attempt_id"), r.get("client_session_sha256"))
        groups[key].append(r)
    warnings = []
    if any(min(s) != 1 or len(s) != max(s) for s in sequences.values()):
        warnings.append("Recorder sequences have missing records; include rotated files or mark this capture incomplete.")
    if any(r.get("write_failures", 0) for r in unique.values()):
        warnings.append("Recorder reported write failures; counts may be incomplete.")
    reports = []
    for (run, task, attempt, session), events in sorted(groups.items(), key=lambda item: str(item[0])):
        starts = {r["call_id"]: r for r in events if r["event"] == "call_started"}
        ends = {r["call_id"]: r for r in events if r["event"] == "call_finished"}
        counts = collections.Counter(r["tool"] for r in starts.values())
        signatures = collections.Counter((r["tool"], r["arguments_sha256"]) for r in starts.values())
        durations = [r["duration_ms"] for r in ends.values()]
        timestamps = [datetime.fromisoformat(r["timestamp"]) for r in events]
        report = {"run_id": run, "task_id": task, "attempt_id": attempt, "client_session_sha256": session,
                  "started_calls": len(starts), "finished_calls": len(ends),
                  "incomplete_calls": len(starts.keys() - ends.keys()),
                  "orphaned_finishes": len(ends.keys() - starts.keys()), "calls_by_tool": dict(counts),
                  "outcomes": dict(collections.Counter(r["outcome"] for r in ends.values())),
                  "errors": dict(collections.Counter(r["error_code"] for r in ends.values() if r.get("error_code"))),
                  "repeated_argument_calls": sum(n - 1 for n in signatures.values()),
                  "continuation_requests": sum(bool(r.get("arguments", {}).get("cursor")) for r in starts.values()),
                  "partial_responses": sum(r.get("complete") is False for r in ends.values()),
                  "response_payload_bytes": sum(r.get("response_payload_bytes", 0) for r in ends.values()),
                  "responses_with_byte_measurement": sum("response_payload_bytes" in r for r in ends.values()),
                  "structured_bytes": sum(r.get("structured_bytes") or 0 for r in ends.values()),
                  "source_utf16_units": sum(r.get("source_utf16_units", 0) for r in ends.values()),
                  "duration_ms_sum": round(sum(durations), 3),
                  "duration_ms_median": statistics.median(durations) if durations else None,
                  "duration_ms_max": max(durations) if durations else None,
                  "observed_tool_span_ms": round((max(timestamps) - min(timestamps)).total_seconds() * 1000, 3)}
        if include_calls:
            report["calls"] = [{"start": starts.get(call), "finish": ends.get(call)}
                               for call in sorted(starts.keys() | ends.keys(),
                                                  key=lambda c: (starts.get(c) or ends[c])["timestamp"])]
        reports.append(report)
    return {"schema_version": 1, "record_count": len(unique), "warnings": warnings, "runs": reports,
            "usage_note": "Bytes and tool timing are not GPT tokens, account quota, or full agent elapsed time."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="JSONL trace files, including rotations")
    parser.add_argument("--run", dest="run_id")
    parser.add_argument("--task", dest="task_id")
    parser.add_argument("--calls", action="store_true", help="Include chronological safe arguments and outcomes")
    args = parser.parse_args()
    records = []
    for path in args.paths:
        try:
            for line_number, line in enumerate(path.read_text().splitlines(), 1):
                if line.strip():
                    record = json.loads(line)
                    if not isinstance(record, dict) or "instance_id" not in record or "sequence" not in record:
                        parser.error(f"Invalid trace record: {path}:{line_number}")
                    records.append(record)
        except (OSError, ValueError) as exc:
            parser.error(f"Cannot read trace file {path}: {exc}")
    print(json.dumps(summarize(records, args.run_id, args.task_id, args.calls), indent=2))


if __name__ == "__main__":
    main()
