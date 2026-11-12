# Preview supervisor: Python and procfs lifecycle research

Requested by the user after the mandatory task05b diagnosis stop. This is
source inspection, not a claim that the failing recovery case is fixed.
No production correction or new test execution was performed for this research.
The later authorized refactor below supplies new runtime evidence and a correction.

## Exact runtime and source provenance

Local `.venv/bin/python --version` reports3.12.12; Dockerfile pins
python:3.12.12-slim-bookworm by digest for both build/runtime stages.
GitHub MCP fetched the official `python/cpython` tag `v3.12.12`.
Git blob SHA-1 hashes computed from installed standard-library files exactly
matched the returned upstream blob hashes for all9 inspected files:
tempfile.py, shutil.py, asyncio/subprocess.py, asyncio/base_subprocess.py,
asyncio/unix_events.py, asyncio/streams.py, asyncio/tasks.py, asyncio/locks.py,
and asyncio/timeouts.py. The local runtime's selected watcher is
ThreadedChildWatcher (inspected outside sandbox without creating a child).

Host kernel reports6.12.116+deb13-amd64. GitHub MCP also inspected upstream
stable `gregkh/linux` tag `v6.12.116`; this matches the base version, not a
byte-for-byte verification of Debian's built kernel or its downstream patches.

## Verified standard-library behavior

- [TemporaryDirectory](https://github.com/python/cpython/blob/v3.12.12/Lib/tempfile.py#L864)
  calls mkdtemp (mkdir mode0700), registers a weakref finalizer, and returns its
  pathname from enter. Exit calls cleanup synchronously with delete=true.
  Cleanup detaches the finalizer and recursively removes the directory through
  shutil.rmtree. Default ignore_cleanup_errors=false means unresolved deletion
  failures propagate. Permission recovery only applies inside that scratch
  deletion tree; it does not affect `/proc/<pid>/fd` permissions or kill workers.
- [shutil.rmtree](https://github.com/python/cpython/blob/v3.12.12/Lib/shutil.py#L641)
  chooses fd-based, symlink-resistant traversal on supported platforms. Directory
  deletion and child-process lifecycle are separate responsibilities.
- [asyncio Process](https://github.com/python/cpython/blob/v3.12.12/Lib/asyncio/subprocess.py#L118)
  delegates kill/wait to its transport. On POSIX,
  [Popen.kill](https://github.com/python/cpython/blob/v3.12.12/Lib/subprocess.py#L2176)
  sends SIGKILL; it does not synchronously complete pipe delivery or directory
  cleanup. [ThreadedChildWatcher](https://github.com/python/cpython/blob/v3.12.12/Lib/asyncio/unix_events.py#L1386)
  performs blocking waitpid in another thread and schedules the event-loop
  callback. OS exit/reaping and Python-visible transport returncode are therefore
  separate events, not an atomic liveness test for later procfs reads.
- [BaseSubprocessTransport](https://github.com/python/cpython/blob/v3.12.12/Lib/asyncio/base_subprocess.py#L225)
  sets returncode when notified; wait called after that returns immediately.
  Already-pending waiters are resolved through connection-lost handling after
  pipe disconnection. Thus some wait paths can be held up by an unread pipe.
- [StreamReader](https://github.com/python/cpython/blob/v3.12.12/Lib/asyncio/streams.py#L498)
  pauses transport when buffering exceeds twice its configured limit and
  resumes as reads drain it. The limit is a flow-control threshold, not a hard
  total-output cap. This supports our demonstrated drain-before-reap correction;
  the project separately enforces4096 returned bytes and discards residual data.
- [shield](https://github.com/python/cpython/blob/v3.12.12/Lib/asyncio/tasks.py#L867)
  preserves the referenced inner task while cancellation still reaches its
  caller. Our settle loop retains spawn/reap ownership and reports cancellation
  afterward. [timeout](https://github.com/python/cpython/blob/v3.12.12/Lib/asyncio/timeouts.py#L97)
  cancels its task and translates its own cancellation into TimeoutError;
  it does not independently kill a child. The project's finally blocks do that.
- [os.scandir](https://github.com/python/cpython/blob/v3.12.12/Modules/posixmodule.c#L15489)
  on POSIX calls opendir with the GIL released and reports OS errors with the
  path. It does not make procfs readable or coordinate with child reaping.

## How the supervisor combines these responsibilities

The parent admits a request, creates scratch, starts a child, exchanges bounded
data while sampling resources, kills/cancels/drains/reaps in its inner finally,
then exits TemporaryDirectory and releases admission in its outer finally.
The source snapshot's original file belongs to a separate owner and is not
removed by the worker supervisor. The observed errno13 arises in resource
sampling, not in TemporaryDirectory's recursive deletion.

## Stronger explanation for the remaining permission failure

Linux [task_dump_owner](https://github.com/gregkh/linux/blob/v6.12.116/fs/proc/base.c#L1864)
assigns restricted procfs entries root ownership when task->mm is absent.
The same source declares `/proc/<pid>/fd` owner-readable/searchable (0500).
[proc_fd_permission](https://github.com/gregkh/linux/blob/v6.12.116/fs/proc/fd.c#L339)
uses ordinary inode permissions with a same-thread-group exception; a parent
is a different thread group from its child.
[exit_mm](https://github.com/gregkh/linux/blob/v6.12.116/kernel/exit.c#L545)
sets current->mm=NULL before do_exit completes file teardown and exit
notification. Therefore a procfs entry can exist yet be inaccessible to a
nonroot parent during exit, before ENOENT/ESRCH or a Python returncode update.

Inference: our sampling can race this exit transition, including its final
sample after the exchange completes. This explains how a healthy short-lived
replacement can produce errno13 without a scratch-cleanup failure. It is a
better-supported lead than the earlier generic exec-credentials hypothesis,
but the failing test's exact kernel state was not captured. Source inspection
does not yet prove which transition caused that recorded failure.

Next diagnostic work must reproduce the exit/ownership boundary deterministically
and distinguish an exiting owned child from genuine denial while still alive.
Do not broadly suppress PermissionError, raise budgets, or treat existence/
returncode checks followed by procfs reads as atomic. A correction still needs
the unchanged failing/passing regression and focused/full/package checks.

## Later component refactor evidence

Following the user's explicit implementation request, the components were
extracted according to the saved refactor plan. A real process retained using
waitid(WEXITED|WNOWAIT) deterministically demonstrated stateZ, UID0 ownership of
its fd directory, and errno13 for ResourceMonitor. The coordinator's old policy
failed `test_unavailable_proc_observation_of_exited_child_requires_owned_completion`.
The same unchanged test passed after requiring owned wait completion within
one sampling interval for a denied proc observation. Denial for a still-running
child remains an error, no observation is retried or fabricated, and final
named scratch is checked after reaping. Full test/package evidence belongs to
task05b. This proves the lifecycle boundary defect; the historical failing
process's exact kernel state cannot be recovered retrospectively.
