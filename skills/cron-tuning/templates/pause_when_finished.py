"""Pause through scheduler API; never rewrite shared jobs.json."""
from __future__ import annotations

def corpus_finished(counts: dict) -> bool:
    required = ("total", "accepted", "pending", "rejected", "needs_review", "needs_context")
    if any(type(counts.get(k)) is not int or counts[k] < 0 for k in required):
        return False
    return counts["total"] > 0 and counts["accepted"] == counts["total"] and all(counts[k] == 0 for k in required[2:])

def pause_finished_job(job_id: str, jobs_file=None, *, reason: str, scheduler=None) -> str:
    """Caller validates canonical first. Run under the authorized Hermes profile.
    Legacy file-path calls fail closed. Scheduler injection supports isolated tests.
    """
    if jobs_file is not None:
        raise ValueError("direct jobs.json writes retired; use scheduler API")
    if not isinstance(job_id, str) or not job_id.strip() or not reason.strip():
        raise ValueError("exact job_id and reason required")
    if scheduler is None:
        from cron import jobs as scheduler
    job = scheduler.get_job(job_id)
    if job is None:
        return "missing"
    if job.get("id") != job_id:
        raise ValueError("scheduler did not resolve exact job ID")
    if job.get("enabled") is False and job.get("state") == "paused":
        return "already_paused"
    scheduler.pause_job(job_id, reason=reason)
    after = scheduler.get_job(job_id)
    if not after or after.get("id") != job_id or after.get("enabled") is not False or after.get("state") != "paused":
        raise RuntimeError("pause readback failed")
    return "paused"
