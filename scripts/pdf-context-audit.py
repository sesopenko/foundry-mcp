#!/usr/bin/env python3
"""Bounded offline evaluation on synthetic data or a read-only SQLite backup.

Never starts/restarts a service or touches source PDFs. No extracted content or
private selectors are printed. At most 400 searches/MCP calls and 120 seconds.
Run from the checkout with PYTHONPATH=. using the locked Python environment.
"""
import argparse
import ast
import asyncio
import hashlib
import json
import re
from pathlib import Path
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
import types
from unittest.mock import patch

from fastmcp import Client, FastMCP
from foundry_mcp_server.mcp_server.tools import mcp
from foundry_mcp_server.pdf import runtime
from foundry_mcp_server.pdf.config import PDFConfig
from foundry_mcp_server.pdf.library import Library
from foundry_mcp_server.mcp_server import selective as S, selective_models as M, pdfs

NAMED = [('player', 'Sure Strike', 362), ('player', 'Grabbed', 445),
         ('player', 'Persistent Damage', 446), ('player', 'Spellcasting Services', 296),
         ('gm', 'Free Archetype', 85), ('gm', 'Automatic Bonus Progression', 84),
         ('gm', 'Victory Points', 185), ('gm', 'Encounter Budget', 76),
         ('gm', 'DCs by Level', 54), ('gm', 'Treasure Table', 321),
         ('gm', 'Bracelet of Dashing', 287)]


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


def baseline_tool(library):
    """Reconstruct HEAD's published search contract on an isolated MCP server.

    Only trusted checkout Python model definitions and a literal description are
    evaluated. No remote code, service connection or previous library mutation.
    """
    def previous(path):
        return ast.parse(subprocess.check_output(['git','show','HEAD:'+path], text=True))
    models = previous('foundry_mcp_server/mcp_server/selective_models.py')
    selected = [node for node in models.body if isinstance(node, ast.ClassDef) and
                node.name in {'PdfSearchSelect','PdfSearchRequest','PdfCandidate','PdfResult'}]
    module = types.ModuleType('_pdf_audit_baseline_models')
    module.__dict__.update(M.__dict__)
    module.__dict__['__name__'] = '_pdf_audit_baseline_models'
    sys.modules[module.__name__] = module
    exec(compile(ast.Module(body=selected, type_ignores=[]), '<trusted HEAD PDF models>', 'exec'), module.__dict__)
    description = next(ast.literal_eval(node.value) for node in previous('foundry_mcp_server/mcp_server/selective.py').body
                       if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PDF_DOC' for t in node.targets))
    async def handler(request):
        result = library.search(request.query, request.document_id, request.offset, request.limit,
                                select=request.select.model_dump(), max_bytes=request.max_bytes, search_mode='text')
        return dict(result, contract_version=2)
    server = FastMCP('PDF baseline audit')
    server.add_tool(S.SelectiveTool(name='search_pdf_documents', description=description,
                    parameters=module.PdfSearchRequest.model_json_schema(), output_schema=module.PdfResult.model_json_schema(),
                    request_model=module.PdfSearchRequest, response_model=module.PdfResult, handler=handler,
                    annotations=S.ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False)))
    locate = next(node for node in previous('foundry_mcp_server/mcp_server/pdfs.py').body
                  if isinstance(node, ast.AsyncFunctionDef) and node.name=='locate_pdf_entry')
    namespace = dict(vars(pdfs), mcp=server)
    exec(compile(ast.Module(body=[locate], type_ignores=[]), '<trusted HEAD locate contract>', 'exec'), namespace)
    return server


def source_digest(library):
    digest = hashlib.sha256()
    with library.db() as db:
        for table, order in [('documents','id'), ('pages','document_id,page'),
                             ('entries','document_id,page,title,context,provenance')]:
            for row in db.execute(f'SELECT * FROM {table} ORDER BY {order}'):
                digest.update(json.dumps(list(row), ensure_ascii=False).encode())
    return digest.hexdigest()


def baseline_books(documents):
    """Select historical books explicitly; reject ambiguous duplicate editions."""
    books = {}
    for book in documents:
        name = book['name'].casefold()
        kind = ('player' if re.search(r'\bplayer\s+core\b(?!\s+\d)', name) else
                'gm' if re.search(r'\bgm\s+core\b', name) else None)
        if kind:
            if kind in books:
                raise ValueError('Ambiguous baseline editions; provide an isolated snapshot containing one edition per baseline book')
            books[kind] = book['id']
    return books


def synthetic(library):
    """Fixed challenge set; weights are not tuned using these constructed cases."""
    cases = []
    with library.db() as db:
        db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)',
                   ('a'*32, 'Synthetic.pdf', 'b'*64, 1, 'ready', 'b'*64, 10, None))
        titles = ['Infiltration','Exploration','Negotiation','Research','Influence',
                  'Chase','Reputation','Leadership','Discovery','Preparation']
        for n, title in enumerate(titles, 1):
            text = 'A checkpoint requires a careful approach. ' + 'Ordinary body sentence. '*30
            db.execute('INSERT INTO pages VALUES(?,?,?,?,?)', ('a'*32,n,str(n),text,'[]'))
            db.execute('INSERT INTO page_fts VALUES(?,?,?)', ('a'*32,n,text))
            db.execute('INSERT INTO entries VALUES(?,?,?,?,?)', ('a'*32,n,title,'["Subsystems"]','bookmark'))
            cases.append((title+' checkpoint', 'a'*32, n))
    return cases


async def audit(source):
    started = time.monotonic()
    calls = 0
    def bounded():
        nonlocal calls
        calls += 1
        if calls > 400 or time.monotonic()-started > 120:
            raise RuntimeError('Audit budget exceeded')
    with tempfile.TemporaryDirectory(prefix='pdf-context-audit-') as tmp:
        root = Path(tmp)
        library = Library(PDFConfig(True, root/'books', root/'state'))
        library.setup()
        if source:
            # SQLite backup API takes a consistent snapshot of an open database.
            with sqlite3.connect(source.resolve().as_uri()+'?mode=ro', uri=True) as original:
                with sqlite3.connect(root/'state'/'library.sqlite3') as copy:
                    original.backup(copy)
            with library.db() as db:
                docs = db.execute("SELECT id,name FROM documents WHERE status='ready'").fetchall()
            books = baseline_books(docs)
            cases = [(query, books[kind], page) for kind,query,page in NAMED if kind in books]
        else:
            cases = synthetic(library)
        # Measure a legacy-shaped snapshot, retaining its original body-only index.
        with library.db() as db:
            db.execute('DROP TABLE IF EXISTS page_context_fts')
            db.execute('DROP TABLE IF EXISTS pdf_context_index_state')
            db.execute('VACUUM')
        before_bytes = (root/'state'/'library.sqlite3').stat().st_size
        before = source_digest(library)
        build_start = time.monotonic()
        library.setup()
        build_ms = (time.monotonic()-build_start)*1000
        after_bytes = (root/'state'/'library.sqlite3').stat().st_size
        with library.db() as db:
            metadata_sizes = [sum(len(row[f].encode()) for f in ('bookmark_titles','bookmark_ancestors','heading_candidates'))
                              for row in db.execute('SELECT * FROM page_context_fts')]
            truncated_pages = db.execute("SELECT count(*) FROM page_context_fts WHERE context_warnings != '[]'").fetchone()[0]
        assert source_digest(library) == before, 'Source records changed'
        library.setup()
        assert source_digest(library) == before, 'Restart changed sources'
        summaries = {}
        for mode in ('text', 'contextual'):
            ranks, counts, latency = [], [], []
            for query,identifier,expected_page in cases:
                bounded()
                tick = time.monotonic()
                result = library.search(query, identifier, limit=20, locate=bool(source), search_mode=mode)
                latency.append((time.monotonic()-tick)*1000)
                pages = [r['physical_page'] for r in result['candidates']]
                ranks.append(pages.index(expected_page)+1 if expected_page in pages else 0)
                counts.append(len(pages))
                bounded()
                assert not library.search(query+' zzabsentnegativecontrol', identifier, search_mode=mode)['candidates']
            summaries[mode] = dict(queries=len(cases), recall_at_1=sum(r==1 for r in ranks)/max(1,len(ranks)),
                                  recall_at_5=sum(0<r<=5 for r in ranks)/max(1,len(ranks)),
                                  mrr=sum(1/r if r else 0 for r in ranks)/max(1,len(ranks)),
                                  returned_candidates=sum(counts), median_ms=statistics.median(latency) if latency else 0)
        if source:
            assert summaries['contextual']['recall_at_1'] >= summaries['text']['recall_at_1'], 'Named lookup regression'
        else:
            assert summaries['contextual']['recall_at_1'] == 1
            assert summaries['text']['recall_at_1'] == 0
        contracts = {}
        baseline_catalog = {}
        query = 'checkpoint' if not source else cases[0][0] if cases else 'rule'
        async def measure(client, label):
            bounded()
            tools = await client.list_tools()
            if label == 'baseline':
                baseline_catalog.update({t.name:t.model_dump(mode='json', exclude_none=True) for t in tools})
            tool = next(t for t in tools if t.name=='search_pdf_documents')
            values = dict(search_discovery_bytes=size(tool.model_dump(mode='json', exclude_none=True)))
            if label == 'current':
                values['catalog_bytes'] = size([t.model_dump(mode='json', exclude_none=True) for t in tools])
                contracts['baseline']['reconstructed_catalog_bytes'] = size([
                    baseline_catalog.get(t.name, t.model_dump(mode='json', exclude_none=True)) for t in tools])
            async def invoke(arguments):
                bounded()
                return (await client.call_tool('search_pdf_documents', arguments)).structured_content
            for name, selection in [('default', {}), ('snippet', {'snippet':True}),
                                    ('entries_context', {'snippet':True,'entries':True,'context':True}),
                                    ('expanded', dict(snippet=True,entries=True,context=True,
                                                      **({'match_details':True} if label=='current' else {})))]:
                result = await invoke(dict(query=query, select=selection))
                values[name] = dict(bytes=size(result), returned=len(result['candidates']), complete=result['next_offset'] is None)
            total_bytes, count, offset, pages = 0, 0, 0, 0
            while offset is not None:
                result = await invoke(dict(query=query, offset=offset, limit=3))
                total_bytes += size(result); count += len(result['candidates']); pages += 1
                offset = result['next_offset']
            values['complete_workflow'] = dict(calls=pages, bytes=total_bytes, returned=count, complete=True)
            contracts[label] = values
        async with Client(baseline_tool(library)) as client:
            await measure(client, 'baseline')
        with patch.object(runtime, 'library', library):
            async with Client(mcp) as client:
                await measure(client, 'current')
        print(json.dumps(dict(corpus='private_copy' if source else 'synthetic', source_records_unchanged=True,
                              baseline_revision=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
                              db_before_bytes=before_bytes, db_after_bytes=after_bytes, build_ms=build_ms,
                              indexed_pages=len(metadata_sizes), max_page_metadata_bytes=max(metadata_sizes,default=0),
                              truncated_pages=truncated_pages,
                              retrieval=summaries, contracts=contracts, bounded_calls=calls,
                              elapsed_seconds=time.monotonic()-started), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-state', type=Path, help='Existing private library.sqlite3, opened read-only and backed up to a temporary directory')
    args = parser.parse_args()
    asyncio.run(asyncio.wait_for(audit(args.source_state), 120))
