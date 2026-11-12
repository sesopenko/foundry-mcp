import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';
import {contextWorld} from './map-context-world.js';
import {handleRpcMessage} from '../../../foundry-module/scripts/foundryBridge.js';
globalThis.crypto??=webcrypto;
for(const method of ['log','info','warn','error','debug'])console[method]=()=>{};
const input=JSON.parse(readFileSync(0,'utf8'));contextWorld(input);
process.stdout.write(JSON.stringify(await handleRpcMessage({id:'fixture',method:input.method,params:input.params})));
