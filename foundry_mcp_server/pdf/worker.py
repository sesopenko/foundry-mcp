"""One resource-limited PDF parse. Parent enforces wall time and output size.

No source text or parser exceptions are written to logs/stdout.
"""
import json
import resource
import re
import sys
from pathlib import Path


def extract(path):
    from pypdf import PdfReader
    reader = PdfReader(path, strict=False)
    if reader.is_encrypted: raise ValueError('encrypted')
    if not 0 < len(reader.pages) <= 2000: raise ValueError('page_limit')
    labels = reader.page_labels
    pages, entries = [], []
    def outline(items, parents=()):
        if len(parents)>32: raise ValueError("outline_depth")
        for item in items:
            if isinstance(item, list):
                outline(item, parents + ((entries[-1]['title'],) if entries else ()))
            else:
                n = reader.get_destination_page_number(item)
                title = str(item.title)[:160]
                if n is not None and 0 <= n < len(reader.pages):
                    entries.append(dict(title=title, page=n+1, context=list(parents[-6:]), provenance='bookmark'))
                    if len(entries)>20000: raise ValueError('entry_limit')
    outline(reader.outline)
    total = 0
    for n, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ''
        size = len(text.encode())
        total += size
        if size > 1048576 or total > 16777216: raise ValueError('text_limit')
        warnings = ['reading_order_unverified', 'table_structure_unverified', 'untrusted_source_content']
        if len(text.strip()) < 80: warnings.append('sparse_text_no_ocr')
        pages.append(dict(page=n, label=str(labels[n-1])[:100], text=text, warnings=warnings))
        # Conservative candidates, explicitly heuristics rather than authoritative classifications.
        lines = text.splitlines()
        for i,line in enumerate(lines):
            line = line.strip()
            stat = re.match(r"^(.{2,80}?)\s+(SPELL|FEAT|ITEM)\s+\d+\b", line)
            if stat: line=re.sub(r"\s*\[[^\]]{1,40}\]", "", stat.group(1)).strip()
            if 2 <= len(line) <= 100 and (line.isupper() or
                (line.istitle() and i+1 < len(lines) and any(w in lines[i+1].upper() for w in ('SPELL ', 'FEAT ', 'ITEM ', 'CONDITION')))):
                parents = [e for e in entries if e['provenance']=='bookmark' and e['page']<=n]
                context = (parents[-1]['context']+[parents[-1]['title']]) if parents else []
                entries.append(dict(title=line, page=n, context=context[-6:], provenance='heading_candidate'))
                if len(entries)>20000: raise ValueError('entry_limit')
    return dict(pages=pages, entries=entries)

if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (805306368,805306368))
    resource.setrlimit(resource.RLIMIT_CPU, (90,90))
    resource.setrlimit(resource.RLIMIT_FSIZE, (33554432,33554432))
    try:
        result = extract(sys.argv[1])
        Path(sys.argv[2]).write_text(json.dumps(result))
    except BaseException:
        sys.exit(2)
