"""Restore authentication in the existing dedicated development browser.

Uses the normal localhost Foundry login form, existing server admin key and
optional git-ignored .local/dev-login.json GM credential. Never displays
credentials, changes passwords or creates an instance.
"""

import argparse
import asyncio
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

import httpx
import websockets


async def main(authenticate_admin=False, launch_world=None, join_gm=False):
    stage = 'development_tab'
    try:
        if (type(authenticate_admin) is not bool or type(join_gm) is not bool
                or sum((authenticate_admin, launch_world is not None, join_gm)) != 1
                or launch_world not in (None, 'test')):
            raise ValueError('Exactly one supported development action is required')
        root = Path(__file__).resolve().parent.parent
        port = (root / '.browser-dev/chrome-profile/DevToolsActivePort').read_text().splitlines()[0]
        if not port.isdecimal() or not 1 <= int(port) <= 65535:
            raise RuntimeError('Invalid development endpoint')
        async with httpx.AsyncClient(trust_env=False) as http:
            response = await http.get('http://127.0.0.1:' + port + '/json/list')
            response.raise_for_status()
            tabs = [tab for tab in response.json() if tab.get('type') == 'page'
                    and tab.get('url', '').startswith('http://localhost:30000/')]
        expected_path = '/auth' if authenticate_admin else '/join' if join_gm else '/setup'
        if len(tabs) != 1 or tabs[0]['url'].split('?', 1)[0] != 'http://localhost:30000' + expected_path:
            raise RuntimeError('Unexpected development page')
        endpoint = urlsplit(tabs[0]['webSocketDebuggerUrl'])
        if (endpoint.scheme != 'ws' or endpoint.hostname not in ('127.0.0.1', 'localhost')
                or endpoint.port != int(port) or not endpoint.path.startswith('/devtools/page/')
                or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment):
            raise RuntimeError('Unexpected development debugger endpoint')
        if authenticate_admin:
            stage = 'configured_admin_key'
            result = subprocess.run(
                ['docker', 'compose', 'exec', '-T', 'foundry', 'printenv', 'FOUNDRY_ADMIN_KEY'],
                cwd=root, capture_output=True, text=True, check=True,
            )
            key = result.stdout.rstrip('\r\n')
            if not key or len(key) > 4096:
                raise RuntimeError('Configured administrator credential unavailable')
            expression = """(() => {
if(location.origin!=='http://localhost:30000'||location.pathname!=='/auth')throw Error('Wrong development page');
const input=document.querySelector('#auth-password[name="adminPassword"]');
if(!(input instanceof HTMLInputElement)||input.type!=='password'||!input.form)throw Error('Unexpected login form');
input.value=KEY;
input.dispatchEvent(new Event('input',{bubbles:true}));
input.dispatchEvent(new Event('change',{bubbles:true}));
setTimeout(()=>input.form.requestSubmit(),0);
return JSON.stringify({submitted:true,action:'authenticate_admin'});
})()""".replace('KEY', json.dumps(key))
        elif launch_world:
            if launch_world != 'test':
                raise RuntimeError('Only the existing test world is authorized')
            expression = """(() => {
if(location.origin!=='http://localhost:30000'||location.pathname!=='/setup')throw Error('Wrong development page');
const decline=[...document.querySelectorAll('button[data-action="no"]')].find(b=>b.textContent.trim()==='Decline Sharing');
if(decline){decline.click();return JSON.stringify({submitted:true,action:'decline_optional_sharing',retry_launch:true});}
const world=document.querySelector('[data-package-id="test"]');
const launch=world?.querySelector('[data-action="worldLaunch"]');
if(!launch||launch.disabled)throw Error('Existing test world launch is unavailable');
setTimeout(()=>launch.click(),0);
return JSON.stringify({submitted:true,action:'launch_existing_test_world'});
})()"""
        else:
            stage = 'local_development_credential'
            credential = json.loads((root / '.local/dev-login.json').read_text())
            if credential.get('world_id') != 'test' or credential.get('user_name') != 'Gamemaster':
                raise RuntimeError('Unexpected local development credential scope')
            password = credential.get('password')
            if not isinstance(password, str) or len(password) > 4096:
                raise RuntimeError('Local development credential unavailable')
            expression = """(() => {
if(location.origin!=='http://localhost:30000'||location.pathname!=='/join'||globalThis.game?.world?.id!=='test')throw Error('Wrong development world');
const user=document.querySelector('#join-username[name="userId"]');
if(!(user instanceof HTMLSelectElement)||!user.form)throw Error('Unexpected join form');
const password=document.querySelector('#join-password[name="password"]');
if(!(password instanceof HTMLInputElement)||password.type!=='password'||password.form!==user.form)throw Error('Unexpected password form');
const options=[...user.options].filter(o=>o.textContent.trim()==='Gamemaster'&&o.value);
const join=[...user.form.querySelectorAll('button[type="submit"]')].find(b=>b.textContent.trim()==='Join Game Session');
if(options.length!==1||!join||join.disabled)throw Error('Existing GM join is unavailable');
user.value=options[0].value;
user.dispatchEvent(new Event('input',{bubbles:true}));
user.dispatchEvent(new Event('change',{bubbles:true}));
password.value=PASSWORD;
password.dispatchEvent(new Event('input',{bubbles:true}));
password.dispatchEvent(new Event('change',{bubbles:true}));
setTimeout(()=>join.click(),0);
return JSON.stringify({submitted:true,action:'join_existing_test_gm'});
})()""".replace('PASSWORD', json.dumps(password))
        stage = 'normal_login_form'
        async with websockets.connect(tabs[0]['webSocketDebuggerUrl']) as socket:
            await socket.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate',
                                         'params': {'expression': expression, 'returnByValue': True}}))
            while True:
                reply = json.loads(await asyncio.wait_for(socket.recv(), 10))
                if reply.get('id') != 1:
                    continue
                if 'error' in reply or 'exceptionDetails' in reply.get('result', {}):
                    raise RuntimeError('Development login submission failed')
                value = json.loads(reply['result']['result']['value'])
                expected_action = ('authenticate_admin' if authenticate_admin else
                                   'join_existing_test_gm' if join_gm else 'launch_existing_test_world')
                allowed = [{'submitted': True, 'action': expected_action}]
                if launch_world:
                    allowed.append({'submitted': True, 'action': 'decline_optional_sharing',
                                    'retry_launch': True})
                if (not isinstance(value, dict) or value.get('submitted') is not True
                        or ('retry_launch' in value and value['retry_launch'] is not True)
                        or value not in allowed):
                    raise RuntimeError('Unexpected development submission response')
                print(json.dumps(next(result for result in allowed if result == value)))
                return 0
    except Exception as error:
        print(json.dumps({'passed': False, 'stage': stage, 'exception_type': type(error).__name__}))
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--authenticate-admin', action='store_true')
    action.add_argument('--launch-world', choices=['test'])
    action.add_argument('--join-gm', action='store_true')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.authenticate_admin, args.launch_world, args.join_gm)))
