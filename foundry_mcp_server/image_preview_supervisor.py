"""Compose preview admission, workspace, child ownership and resource policy."""
import asyncio
from pathlib import Path
import sys
import time
import weakref

from . import image_preview_limits as limits
from .image_preview_admission import MAX_QUEUED,PreviewAdmission
from .image_preview_child import PreviewChild,MAX_REQUEST_BYTES
from .image_preview_resources import MONITOR_INTERVAL,ResourceMonitor,WorkerMetrics
from .image_preview_workspace import PreviewWorkspace
from .image_preview_worker import PreviewFailure


class PreviewSupervisor:
    def __init__(self, *, max_rss=limits.WORKER_MAX_RSS,
                 max_scratch=limits.WORKER_MAX_SCRATCH,
                 timeout=limits.WORKER_TIMEOUT_SECONDS,
                 queue_timeout=limits.WORKER_TIMEOUT_SECONDS,
                 max_queued=MAX_QUEUED, interval=MONITOR_INTERVAL,
                 admission=None,workspace_factory=PreviewWorkspace,
                 child_factory=PreviewChild,monitor=None):
        self.timeout,self.interval = timeout,interval
        self.admission = admission if admission is not None else PreviewAdmission(
            max_queued=max_queued,queue_timeout=queue_timeout)
        self.workspace_factory,self.child_factory = workspace_factory,child_factory
        self.monitor = monitor if monitor is not None else ResourceMonitor(
            max_rss=max_rss,max_scratch=max_scratch)

    async def _run(self, payload, workspace, metrics, timeout):
        child = self.child_factory(workspace.environment())
        succeeded = False
        try:
            async with asyncio.timeout(timeout):
                await child.start()
                exchange = child.exchange(payload)
                while True:
                    try:
                        self.monitor.measure(child.pid,workspace.path,metrics)
                    except PermissionError:
                        # Linux can root-own /proc/<pid>/fd during normal exit,
                        # before asyncio's wait notification. Accept no invented
                        # sample: require this owned child's completion within
                        # one existing sampling interval, otherwise fail closed.
                        if not await child.wait_finished(self.interval):
                            raise
                        break
                    done,_ = await asyncio.wait({exchange},timeout=self.interval)
                    if done:
                        break
                result = await exchange
                succeeded = True
                return result
        finally:
            await child.close()
            if succeeded:
                self.monitor.final_scratch(workspace.path,metrics)

    async def run(self, payload, *, metrics=None, timeout=None):
        """Return bounded worker bytes only after child close and final scratch check.

        Components exclusively own permits, paths, processes and measurements.
        The coordinator owns processing deadline/error policy. Original snapshots
        and decoded image metadata belong to its caller, not these components.
        """
        if not isinstance(payload,bytes) or len(payload)>MAX_REQUEST_BYTES:
            raise PreviewFailure('InvalidOperation')
        if sys.platform!='linux' or not Path('/proc/self/status').is_file():
            raise PreviewFailure('ImageProcessingFailed')
        metrics = metrics if metrics is not None else WorkerMetrics()
        async with self.admission.permit():
            started = time.monotonic()
            try:
                with self.workspace_factory() as workspace:
                    return await self._run(payload,workspace,metrics,
                        self.timeout if timeout is None else timeout)
            except TimeoutError:
                raise PreviewFailure('ImageProcessingTimeout') from None
            except (OSError,ValueError,TypeError):
                raise PreviewFailure('ImageProcessingFailed') from None
            finally:
                metrics.elapsed_seconds = time.monotonic()-started


_supervisors = weakref.WeakKeyDictionary()


def current_supervisor():
    """One admission gate per server event loop, separate from upload locks."""
    loop = asyncio.get_running_loop()
    if loop not in _supervisors:
        _supervisors[loop] = PreviewSupervisor()
    return _supervisors[loop]
