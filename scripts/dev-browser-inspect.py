"""Inspect only the existing dedicated Foundry development browser's login UI.

Never displays password values, cookies or raw console arguments. Select-option
labels/IDs and fixed error categories are diagnostic metadata. Does not change
browser state, create worlds or attach to an ordinary browser profile.
"""

import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx2 as httpx
import websockets


async def main():
    try:
        root = Path(__file__).resolve().parent.parent
        port = (root / '.browser-dev/chrome-profile/DevToolsActivePort').read_text().splitlines()[0]
        if not port.isdecimal() or not 1 <= int(port) <= 65535:
            raise RuntimeError('Invalid development endpoint')
        async with httpx.AsyncClient(trust_env=False) as http:
            response = await http.get('http://127.0.0.1:' + port + '/json/list')
            response.raise_for_status()
            tabs = [tab for tab in response.json() if tab.get('type') == 'page'
                    and tab.get('url', '').startswith('http://localhost:30000/')]
        if len(tabs) != 1:
            raise RuntimeError('Expected one existing development Foundry tab')
        endpoint = urlsplit(tabs[0]['webSocketDebuggerUrl'])
        if (endpoint.scheme != 'ws' or endpoint.hostname not in ('127.0.0.1', 'localhost')
                or endpoint.port != int(port) or not endpoint.path.startswith('/devtools/page/')
                or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment):
            raise RuntimeError('Unexpected development debugger endpoint')
        expression = """JSON.stringify({
path:location.pathname,world:globalThis.game?.world?.id,
login_status:{password_message:[...document.querySelectorAll('.notification,[role="alert"]')].some(e=>/password/i.test(e.textContent)),password_required:!!document.querySelector('input[type="password"]')?.required},
inputs:[...document.querySelectorAll('input,select')].slice(0,30).map(e=>({tag:e.tagName,id:e.id,name:e.name,type:e.type,...(e.tagName==='SELECT'?{options:[...e.options].map(o=>({label:o.textContent.trim(),id:o.value,disabled:o.disabled}))}:{})})),
buttons:[...document.querySelectorAll('button')].slice(0,40).map(e=>({id:e.id,type:e.type,action:e.dataset.action,text:e.textContent.trim().slice(0,80)})),
packages:[...document.querySelectorAll('[data-world-id],[data-package-id]')].slice(0,30).map(e=>({world:e.dataset.worldId,package:e.dataset.packageId,actions:[...e.querySelectorAll('[data-action]')].map(b=>b.dataset.action)}))
})"""
        async with websockets.connect(tabs[0]['webSocketDebuggerUrl']) as socket:
            await socket.send(json.dumps({'id': 2, 'method': 'Runtime.enable'}))
            categories = set()
            while True:
                event = json.loads(await asyncio.wait_for(socket.recv(), 10))
                if event.get('method') == 'Runtime.consoleAPICalled':
                    for argument in event.get('params', {}).get('args', []):
                        message = argument.get('value')
                        if not isinstance(message, str):
                            continue
                        lowered = message.lower()
                        if 'password' in lowered:
                            categories.add('password')
                        elif 'already' in lowered and ('login' in lowered or 'logged' in lowered or 'active' in lowered):
                            categories.add('already_active')
                        elif 'user' in lowered and ('select' in lowered or 'invalid' in lowered):
                            categories.add('user_selection')
                if event.get('id') == 2:
                    break
            await socket.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate',
                                         'params': {'expression': expression, 'returnByValue': True}}))
            while True:
                reply = json.loads(await asyncio.wait_for(socket.recv(), 10))
                if reply.get('id') != 1:
                    continue
                if 'error' in reply or 'exceptionDetails' in reply.get('result', {}):
                    raise RuntimeError('Development page inspection failed')
                summary = json.loads(reply['result']['result']['value'])
                summary['login_console_categories'] = sorted(categories)
                print(json.dumps(summary))
                return 0
    except Exception as error:
        print(json.dumps({'passed': False, 'exception_type': type(error).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
