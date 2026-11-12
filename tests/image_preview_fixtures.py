"""Trusted real-child adapter shared by preview component/integration tests."""
import asyncio
from pathlib import Path
import sys


class FixtureChildren:
    def __init__(self, mode='good'):
        self.mode = mode
        self.children = []
        self.scratch = []
        self.started = asyncio.Event()

    async def spawn(self, *command, **options):
        if command != (sys.executable,'-m','foundry_mcp_server.image_preview_worker'):
            raise AssertionError('Production worker command changed')
        if options['stderr'] != asyncio.subprocess.DEVNULL or options['limit'] != 4096:
            raise AssertionError('Production pipe policy changed')
        scratch = Path(options['env']['TMPDIR'])
        self.scratch.append(scratch)
        self.permissions = scratch.stat().st_mode & 0o777
        child = await asyncio.create_subprocess_exec(sys.executable,
            str(Path(__file__).parent/'fixtures'/'preview_resource_child.py'),self.mode,**options)
        self.children.append(child)
        self.started.set()
        return child
