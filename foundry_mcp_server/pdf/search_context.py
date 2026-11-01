"""Deterministic, disposable page search projection from persisted source metadata.

Bookmark ancestry is navigation metadata. Heuristic ancestry is deliberately
ignored. No section spans, filenames, labels or generated aliases are indexed.
"""
import hashlib
import json

BUILD_VERSION = 1
METADATA_BYTES = 8192
FIELDS = ('body', 'bookmark_titles', 'bookmark_ancestors', 'heading_candidates')
# Positional weights include both UNINDEXED selectors and warnings.
BM25_WEIGHTS = '0,0,1.0,3.0,0.5,0.75,0'


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def project(pages, entries):
    """Return rows and a source fingerprint; reject malformed persisted metadata.

    Stable lexicographic admission: bookmark titles, ancestors, then heuristic
    titles. Admit whole whitespace-normalized strings within 8192 UTF-8 bytes,
    counting separating spaces. Deduplicate across metadata fields by casefold.
    """
    pages = sorted((dict(p) for p in pages), key=lambda p: p['page'])
    records = []
    for entry in entries:
        e = dict(entry)
        context = json.loads(e['context']) if isinstance(e['context'], str) else e['context']
        if not isinstance(e['title'], str) or not isinstance(context, list) or any(not isinstance(s, str) for s in context):
            raise ValueError('Invalid search metadata')
        records.append((e['page'], e['title'], context, e['provenance']))
    records.sort(key=compact)
    fingerprint = hashlib.sha256(compact([BUILD_VERSION,
        [[p['page'], p['text']] for p in pages], records]).encode()).hexdigest()
    by_page = {}
    for page, title, ancestors, provenance in records:
        fields = by_page.setdefault(page, [[], [], []])
        if provenance == 'bookmark':
            fields[0].append(title)
            fields[1].extend(ancestors)
        elif provenance == 'heading_candidate':
            fields[2].append(title)
    rows = []
    for p in pages:
        seen, used, truncated, output = set(), 0, False, []
        for values in by_page.get(p['page'], [[], [], []]):
            admitted = []
            for value in sorted({' '.join(v.split()) for v in values}, key=lambda s: (s.casefold(), s)):
                key = value.casefold()
                if not value or key in seen:
                    continue
                seen.add(key)
                size = len(value.encode()) + bool(admitted)
                if used + size > METADATA_BYTES:
                    truncated = True
                    continue
                admitted.append(value)
                used += size
            output.append(' '.join(admitted))
        rows.append((p['page'], ' '.join(p['text'].split()), *output,
                     compact(['search_context_truncated'] if truncated else [])))
    return rows, fingerprint


def estimated_growth(rows):
    """Conservative headroom for two FTS indexes, metadata and rollback journal.

    This is a reservation, not a measured storage multiplier. SQLite page/FTS
    overhead has a fixed allowance even for empty/small documents.
    """
    return 262144 + sum((len(r[1].encode()) * 12 +
                        sum(len(s.encode()) for s in r[2:5]) * 8 + 1024) for r in rows)


def remove_context(db, identifier):
    for table in ('page_context_fts', 'pdf_context_index_state'):
        db.execute('DELETE FROM '+table+' WHERE document_id=?', (identifier,))


def write_context(db, identifier, revision, rows, fingerprint):
    """Replace projection and completion marker inside the caller's transaction."""
    remove_context(db, identifier)
    db.executemany('INSERT INTO page_context_fts VALUES(?,?,?,?,?,?,?)',
                   [(identifier, *row) for row in rows])
    db.execute('INSERT INTO pdf_context_index_state VALUES(?,?,?,?,?)',
               (identifier, revision, BUILD_VERSION, fingerprint, len(rows)))
