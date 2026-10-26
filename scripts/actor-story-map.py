#!/usr/bin/env python3
"""Validate the Actor/Item backlog DAG and report dependency-aware progress.

Reads tracked Markdown only; no game access, network, or state mutation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
IDENTIFIER = re.compile(r'\b(?:ACT|ITEM|CORE|M)-[A-Za-z]+\b')
STATUSES = {'Not started', 'In progress', 'Source implemented', 'Complete', 'Blocked', 'Deferred'}
ACTORS = {'character', 'npc', 'familiar'}
ITEMS = set('melee action feat spell spellcastingEntry lore condition effect affliction ancestry heritage background class deity weapon armor shield equipment consumable ammo backpack book kit treasure'.split())


@dataclass
class Task:
    identifier: str
    stage: int
    dependencies: set[str]
    status: str
    owner: str

    @property
    def delivered(self) -> bool:
        return self.status == 'Complete' or (self.identifier.startswith('ACT-') and self.status == 'Source implemented')


def field(text: str, name: str, default: str | None = None) -> str:
    match = re.search(r'^\| ' + re.escape(name) + r' \| ([^|]+) \|$', text, re.M)
    if match:
        return match[1].strip()
    if default is not None:
        return default
    raise ValueError(f'Missing tracking field: {name}')


def load_map(directory: Path) -> dict[str, Task]:
    """Read and validate story headers, checkpoint rows and the Mermaid edge set."""
    tasks: dict[str, Task] = {}
    for path in sorted((directory / 'stories').glob('*.md')):
        text = path.read_text()
        status = field(text, 'Implementation status')
        if status not in STATUSES:
            raise ValueError(f'{path.stem}: unknown status {status!r}')
        if status == 'Source implemented' and not path.stem.startswith('ACT-'):
            raise ValueError(f'{path.stem}: source checkpoint status is Actor-only')
        tasks[path.stem] = Task(path.stem, int(field(text, 'Stage')),
                                set(IDENTIFIER.findall(field(text, 'Prerequisites'))), status, path.stem)
    if {key[4:] for key in tasks if key.startswith('ACT-')} != ACTORS:
        raise ValueError('Expected exactly character, npc, familiar Actor stories')
    if {key[5:] for key in tasks if key.startswith('ITEM-')} != ITEMS:
        raise ValueError('Expected exactly the 24 recorded Item stories')
    if len(tasks) != 39:
        raise ValueError('Expected 39 recorded implementation stories')
    index = (directory / 'index.md').read_text()
    indexed = set()
    for row in index.splitlines():
        if not row.startswith('| ['):
            continue
        cells = [cell.strip() for cell in row.split('|')[1:-1]]
        identifier = IDENTIFIER.search(cells[0])
        if not identifier:
            continue
        key = identifier.group()
        if key.startswith('M-'):
            owners = re.findall(r'ACT-[A-Za-z]+', cells[0])
            if not owners or owners[0] not in tasks:
                raise ValueError(f'{key}: missing checkpoint owner')
            owner = owners[0]
            text = (directory / 'stories' / f'{owner}.md').read_text()
            status = field(text, 'Integrated status', 'Not started')
            if status not in STATUSES - {'Source implemented'}:
                raise ValueError(f'{key}: invalid integrated status')
            tasks[key] = Task(key, 3, set(IDENTIFIER.findall(cells[1])), status, owner)
        elif key in tasks:
            indexed.add(key)
            if tasks[key].dependencies != set(IDENTIFIER.findall(cells[3])):
                raise ValueError(f'{key}: story prerequisites disagree with index')
    if indexed != {key for key in tasks if not key.startswith('M-')}:
        raise ValueError('Index must contain every implementation story')
    if {key for key in tasks if key.startswith('M-')} != {'M-NPC', 'M-PC', 'M-FAMILIAR'}:
        raise ValueError('Expected all three Actor integration checkpoints')
    for key, task in tasks.items():
        for dependency in task.dependencies:
            if dependency not in tasks:
                raise ValueError(f'{key}: unknown dependency {dependency}')
            if task.status != 'Deferred' and tasks[dependency].status == 'Deferred':
                raise ValueError(f'{key}: active task has deferred dependency {dependency}')
            if tasks[dependency].stage > task.stage:
                raise ValueError(f'{key}: prerequisite {dependency} belongs to a later stage')
    visiting, visited = set(), set()

    def visit(key: str) -> None:
        if key in visiting:
            raise ValueError(f'Dependency cycle involving {key}')
        if key in visited:
            return
        visiting.add(key)
        for dependency in tasks[key].dependencies:
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key in tasks:
        visit(key)
    match = re.search(r'```mermaid\n(.*?)```', index, re.S)
    if not match:
        raise ValueError('Missing Mermaid dependency graph')
    graph = match[1]
    aliases = {key.replace('-', '_'): key for key in tasks}
    defined = set(re.findall(r'^\s+(\w+)\[', graph, re.M))
    if defined != set(aliases):
        raise ValueError('Mermaid nodes disagree with story/checkpoint inventory')
    edges = re.findall(r'^\s+(\w+) --> (\w+)\s*$', graph, re.M)
    expected = {(dep.replace('-', '_'), key.replace('-', '_')) for key, task in tasks.items() for dep in task.dependencies}
    if set(edges) != expected or len(edges) != len(expected):
        raise ValueError('Mermaid edges disagree with direct prerequisites')
    for key, task in tasks.items():
        if task.delivered and any(not tasks[dep].delivered for dep in task.dependencies):
            raise ValueError(f'{key}: marked delivered before its prerequisites')
        if key.startswith('M-') and tasks[task.owner].status == 'Complete' and not task.delivered:
            raise ValueError(f'{task.owner}: complete before its integrated checkpoint')
    return tasks


def report(tasks: dict[str, Task]) -> str:
    """Keep source checkpoints distinct from completed Actor stories."""
    stories = [task for task in tasks.values() if not task.identifier.startswith('M-')]
    delivery = [task for task in stories if task.status != 'Deferred']
    counts = Counter(task.status for task in delivery)
    progress = 100 * counts['Complete'] / len(delivery) if delivery else 0
    result = [f'Current delivery stories: {len(delivery)}; recorded stories: {len(stories)}; deferred: {len(stories)-len(delivery)}; complete: {counts["Complete"]}; progress: {progress:.1f}%; in progress: {counts["In progress"]}; source implemented: {counts["Source implemented"]}; blocked: {counts["Blocked"]}; not started: {counts["Not started"]}.',
              'Ready work (all direct prerequisites delivered):']
    ready = [task for task in tasks.values() if not task.delivered and task.status not in ('Blocked', 'Deferred')
             and all(tasks[dep].delivered for dep in task.dependencies)]
    result.extend(f'- {task.identifier}: {task.status} (owner {task.owner})' for task in sorted(ready, key=lambda t: (t.stage, t.identifier)))
    if not ready:
        result.append('- None; inspect blocked tasks and unresolved evidence gates.')
    result.append('Incomplete work and remaining prerequisites:')
    for task in sorted(tasks.values(), key=lambda t: (t.stage, t.identifier)):
        if task.delivered or task.status == 'Deferred':
            continue
        remaining = ', '.join(sorted(dep for dep in task.dependencies if not tasks[dep].delivered)) or 'none'
        result.append(f'- {task.identifier}: {task.status}; remaining prerequisites: {remaining}')
    result.append('Deferred backlog (outside current delivery scope):')
    deferred = sorted((task for task in tasks.values() if task.status == 'Deferred'), key=lambda task: task.identifier)
    result.extend(f'- {task.identifier}: Deferred (owner {task.owner}); not complete and excluded from delivery progress.' for task in deferred)
    if not deferred:
        result.append('- None.')
    result.append('Effective/live evidence gates remain in docs/actor-item-story-map/evidence.md; delivered source checkpoints do not close them.')
    return '\n'.join(result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'status'), nargs='?', default='status')
    arguments = parser.parse_args()
    try:
        tasks = load_map(ROOT / 'docs/actor-item-story-map')
    except (ValueError, OSError) as error:
        parser.exit(1, f'actor-story-map: {error}\n')
    if arguments.command == 'check':
        stories = [task for task in tasks.values() if not task.identifier.startswith('M-')]
        delivery = sum(task.status != 'Deferred' for task in stories)
        print(f'PASS: {delivery} delivery stories, {len(stories)} recorded stories, {len(stories)-delivery} deferred; {len(tasks)} dependency nodes, {sum(len(t.dependencies) for t in tasks.values())} edges; acyclic; statuses and Mermaid consistent.')
    else:
        print(report(tasks))


if __name__ == '__main__':
    main()
