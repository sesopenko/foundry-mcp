"""One operation's scratch ownership and native temporary-file environment."""
import os
from pathlib import Path
import tempfile


class PreviewWorkspace:
    def __enter__(self):
        self._directory = tempfile.TemporaryDirectory(prefix='foundry-preview-worker-')
        self.path = Path(self._directory.__enter__())
        return self

    def environment(self):
        """Only codec/cache scratch settings; server credentials are excluded."""
        return {
            **{key:value for key,value in os.environ.items()
               if not key.startswith(('FOUNDRY_MCP_','AUTH0_','AWS_'))},
            'VIPS_CONCURRENCY':'2','TMPDIR':str(self.path),'VIPS_TMPDIR':str(self.path),
            'VIPS_DISC_THRESHOLD':str(16*1024*1024),'XDG_CACHE_HOME':str(self.path),
        }

    def __exit__(self, *exception):
        return self._directory.__exit__(*exception)
