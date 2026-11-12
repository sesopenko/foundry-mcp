"""Bounded Linux measurements and preview budget decisions, without child ownership.

Procfs can disappear or deny access during exit. PermissionError is an unavailable
measurement, never fabricated zero usage. The coordinator must reconcile that
with owned child completion or fail closed. See the recorded lifecycle research.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import stat

from . import image_preview_limits as limits
from .image_preview_worker import PreviewFailure

MONITOR_INTERVAL = 0.025
MAX_SCRATCH_ENTRIES = 4096


@dataclass
class WorkerMetrics:
    """Private aggregate measurements; no source identity or MCP representation."""
    peak_rss_bytes: int = 0
    peak_scratch_bytes: int = 0
    elapsed_seconds: float = 0
    samples: int = 0


def sample_resources(pid, scratch):
    """Measure RSS/high-water and logical/allocated scratch, including open unlinks."""
    rss = 0
    if pid is not None:
        try:
            with open(f'/proc/{pid}/status') as stream:
                for line in stream:
                    if line.startswith(('VmRSS:', 'VmHWM:')):
                        rss = max(rss,int(line.split()[1])*1024)
        except (FileNotFoundError,ProcessLookupError):
            pass
    seen,total,count = set(),0,0

    def account(info):
        nonlocal total
        key = (info.st_dev,info.st_ino)
        if stat.S_ISREG(info.st_mode) and key not in seen:
            seen.add(key)
            total += max(info.st_size,info.st_blocks*512)

    directories = [Path(scratch)]
    while directories:
        with os.scandir(directories.pop()) as entries:
            for entry in entries:
                count += 1
                if count>MAX_SCRATCH_ENTRIES:
                    raise PreviewFailure('ImageScratchLimit')
                try:
                    info = entry.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if stat.S_ISDIR(info.st_mode):
                    directories.append(Path(entry.path))
                else:
                    account(info)
    if pid is not None:
        try:
            with os.scandir(f'/proc/{pid}/fd') as descriptors:
                for descriptor in descriptors:
                    count += 1
                    if count>MAX_SCRATCH_ENTRIES:
                        raise PreviewFailure('ImageScratchLimit')
                    try:
                        target = os.readlink(descriptor.path).removesuffix(' (deleted)')
                        if target.startswith(str(scratch)+os.sep):
                            account(os.stat(descriptor.path))
                    except (FileNotFoundError,ProcessLookupError):
                        continue
        except (FileNotFoundError,ProcessLookupError):
            pass
    return rss,total


class ResourceMonitor:
    def __init__(self, *, max_rss=limits.WORKER_MAX_RSS, max_scratch=limits.WORKER_MAX_SCRATCH):
        self.max_rss = max_rss
        self.max_scratch = max_scratch

    def measure(self, pid, scratch, metrics):
        rss,usage = sample_resources(pid,scratch)
        metrics.peak_rss_bytes = max(metrics.peak_rss_bytes,rss)
        metrics.peak_scratch_bytes = max(metrics.peak_scratch_bytes,usage)
        metrics.samples += 1
        if rss>self.max_rss:
            raise PreviewFailure('ImageMemoryLimit')
        if usage>self.max_scratch:
            raise PreviewFailure('ImageScratchLimit')

    def final_scratch(self, scratch, metrics):
        """Check named outputs after close/reap without looking up a numeric PID."""
        self.measure(None,scratch,metrics)
