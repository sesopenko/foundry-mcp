"""Ordinary-player witness in a fresh context of the dedicated localhost development Chrome."""
import asyncio
from contextlib import asynccontextmanager
import itertools
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx2
import websockets


class Connection:
    def __init__(self, socket):
        self.socket=socket
        self.ids=itertools.count(1)

    async def command(self, method, params, session=None):
        key=next(self.ids)
        message=dict(id=key,method=method,params=params)
        if session:
            message['sessionId']=session
        await self.socket.send(json.dumps(message))
        async with asyncio.timeout(20):
            while True:
                reply=json.loads(await self.socket.recv())
                if reply.get('id')==key:
                    if 'error' in reply:
                        raise RuntimeError('Dedicated browser command failed: '+method)
                    return reply['result']

    async def evaluate(self, session, expression):
        reply=await self.command('Runtime.evaluate',dict(expression=expression,returnByValue=True,awaitPromise=True),session)
        if 'exceptionDetails' in reply:
            raise RuntimeError('Player fixture expression failed')
        return reply['result'].get('value')


@asynccontextmanager
async def player_browser(root, user, password):
    """Create and dispose one isolated context without changing the GM session."""
    lines=(Path(root)/'.browser-dev/chrome-profile/DevToolsActivePort').read_text().splitlines()
    port=int(lines[0])
    async with httpx2.AsyncClient(trust_env=False) as client:
        info=(await client.get(f'http://127.0.0.1:{port}/json/version')).json()
    ws=urlsplit(info['webSocketDebuggerUrl'])
    if ws.scheme!='ws' or ws.hostname!='127.0.0.1' or ws.port!=port or ws.path!=lines[1] or not ws.path.startswith('/devtools/browser/'):
        raise RuntimeError('Expected dedicated development debugger')
    async with websockets.connect(ws.geturl(),max_size=1_000_000) as socket:
        chrome=Connection(socket)
        context=(await chrome.command('Target.createBrowserContext',{'disposeOnDetach':True}))['browserContextId']
        try:
            target=(await chrome.command('Target.createTarget',dict(url='http://localhost:30000/join',browserContextId=context)))['targetId']
            session=(await chrome.command('Target.attachToTarget',dict(targetId=target,flatten=True)))['sessionId']
            for _ in range(100):
                if await chrome.evaluate(session,"location.origin==='http://localhost:30000' && location.pathname==='/join' && globalThis.game?.world?.id==='test' && !!document.querySelector('#join-username')"):
                    break
                await asyncio.sleep(.2)
            # Normal join form scoped to the newly created fixture User. Never print credentials.
            login="""(()=>{if(location.origin!=='http://localhost:30000'||location.pathname!=='/join'||game.world.id!=='test')return false;
            const u=document.querySelector('#join-username'),p=document.querySelector('#join-password');
            if(!u||!p||p.type!=='password'||!u.form||u.form!==p.form||![...u.options].some(o=>o.value===USER&&!o.disabled))return false;
            u.value=USER;u.dispatchEvent(new Event('change',{bubbles:true}));p.value=PASSWORD;
            setTimeout(()=>u.form.requestSubmit(u.form.querySelector('button[type="submit"]')),0);return true})()"""
            if not await chrome.evaluate(session,login.replace('USER',json.dumps(user)).replace('PASSWORD',json.dumps(password))):
                raise RuntimeError('Fixture player join form unavailable')
            for _ in range(120):
                if await chrome.evaluate(session,"!!globalThis.game?.ready && game.world.id==='test' && !game.user.isGM && game.user.id==="+json.dumps(user)):
                    break
                await asyncio.sleep(.25)
            else:
                raise RuntimeError('Fixture player login did not finish')
            async def witness(actor, item, marker, name, prose):
                data=json.dumps(dict(actor=actor,item=item,marker=marker,name=name,prose=prose,user=user))
                script="""(async a=>{
                if(location.origin!=='http://localhost:30000'||game.world.id!=='test'||game.user.id!==a.user||game.user.isGM)return false;
                const owner=await foundry.utils.fromUuid(a.actor);
                if(owner?.type!=='loot'||owner.getFlag('foundry-mcp','itemEditingFixture')!==a.marker)return false;
                const app=owner.sheet;app.render(true);
                try{
                  let row;
                  for(let n=0;n<80;n++){await new Promise(r=>setTimeout(r,100));row=document.getElementById(app.id)?.querySelector('[data-item-id="'+a.item+'"]');if(row)break;}
                  const link=row?.querySelector('[data-action="toggle-summary"]');
                  if(link?.textContent.trim()!==a.name)return false;
                  if(!row.querySelector('.item-summary:not([hidden])')?.textContent.includes(a.prose))link.click();
                  for(let n=0;n<40;n++){await new Promise(r=>setTimeout(r,100));if(row.querySelector('.item-summary:not([hidden])')?.textContent.includes(a.prose))return true;}
                  return false;
                }finally{await app.close();}
                })("""+data+")"
                return await chrome.evaluate(session,script)
            yield witness
        finally:
            await chrome.command('Target.disposeBrowserContext',{'browserContextId':context})
