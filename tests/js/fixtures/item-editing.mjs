/** Synthetic world Item for the budgeted FastMCP integration checks. */
import {createInterface} from 'node:readline';
import {handleRpcMessage} from '../../../foundry-module/scripts/foundryBridge.js';
import {world} from './item-sheet-world.js';

const source = {
  name: 'Dogslicer', type: 'weapon', img: 'icons/blade.webp',
  system: {
    quantity: 1, size: 'med', price: {value: {sp: 1}, per: 1}, bulk: {value: 0.1},
    category: 'martial', group: 'sword', baseItem: 'dogslicer', range: null,
    usage: {value: 'held-in-one-hand'}, level: {value: 0},
    damage: {dice: 1, die: 'd6', damageType: 'slashing', modifier: 0, persistent: null},
    traits: {rarity: 'uncommon', value: ['agile'], otherTags: []},
    material: {type: null, grade: null}, runes: {potency: 1, striking: 1, property: ['wounding']},
    specific: null, splashDamage: {value: 0}, publication: {license: 'ORC', remaster: true},
    identification: {status: 'unidentified', unidentified: null},
    description: {value: 'A chipped blade. 🗡 '.repeat(130)}, rules: [],
  },
};
const item = {
  uuid: 'Item.blade', id: 'blade', name: 'Jagged Goblin Blade', type: 'weapon', documentName: 'Item',
  parent: null, testUserPermission: () => true, canUserModify: () => true,
  toObject: () => structuredClone(source),
};
world();
game.items.set(item.id,item);
item.update=async patch=>{
  for(const [path,value] of Object.entries(patch)){
    const keys=path.split('.');let obj=source;
    for(const key of keys.slice(0,-1)){obj[key]??={};obj=obj[key];}
    obj[keys.at(-1)]=structuredClone(value);
  }
  return item;
};
globalThis.foundry = {utils: {fromUuid: async uuid => uuid === item.uuid ? item : null}};
console.debug = () => {};
for await (const line of createInterface({input: process.stdin})) {
  process.stdout.write(JSON.stringify(await handleRpcMessage(JSON.parse(line))) + '\n');
}
