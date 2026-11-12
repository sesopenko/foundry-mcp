import test from 'node:test';
import assert from 'node:assert/strict';
import {resolvePreviewSource} from '../../foundry-module/scripts/journalImages.js';

const code = value => error => error.rpcError?.code === value;
function fixture({prefix = '', s3 = false} = {}) {
  const state = {calls: [], listings: new Map(), sources: {data: {}, public: {}, ...(s3 ? {s3: {buckets: ['test-bucket']}} : {})}};
  globalThis.location = {origin: 'https://foundry.example', href: 'https://foundry.example' + prefix + '/game'};
  globalThis.game = {ready: true, version: '14.369', world: {id: 'test'}, user: {isGM: true, id: 'gm'}};
  class Picker {
    constructor() {this.sources = state.sources;}
    static async browse(source, directory, options) {
      state.calls.push({source, directory, options});
      await state.onBrowse?.(source, directory, options);
      const value = state.listings.get([source, directory, options.bucket ?? ''].join('|'));
      if (value instanceof Error) throw value;
      return value ?? {target: directory, dirs: [], files: []};
    }
  }
  globalThis.foundry = {applications: {apps: {FilePicker: {implementation: Picker}}}, utils: {getRoute: path => prefix + '/' + path}};
  state.set = (source, directory, files, extra = {}) => state.listings.set([source, directory, extra.bucket ?? ''].join('|'),
    {target: directory, dirs: [], files, ...extra});
  return state;
}

test('bare local reference browses only its parent in configured sources then exact fresh membership', async () => {
  const f = fixture();
  f.set('data', 'worlds/test/maps', ['worlds/test/maps/floor.png']);
  const result = await resolvePreviewSource({src: 'worlds/test/maps/floor.png'});
  assert.deepEqual(result, {image: {source: 'data', directory: 'worlds/test/maps', src: 'worlds/test/maps/floor.png'},
    fetch_url: 'https://foundry.example/worlds/test/maps/floor.png', credentials: 'same-origin', world_id: 'test', user_id: 'gm'});
  assert.deepEqual(f.calls.map(c => [c.source, c.directory]), [['data','worlds/test/maps'], ['public','worlds/test/maps'], ['data','worlds/test/maps']]);
  assert.deepEqual(f.calls[0].options, {extensions: ['.apng','.avif','.bmp','.gif','.jpeg','.jpg','.png','.svg','.tiff','.webp'], wildcard: false});
});

test('canonical input skips source discovery but always checks exact membership', async () => {
  const f = fixture(); f.set('public', 'icons/svg', ['icons/svg/anchor.svg']);
  const image = {source: 'public', directory: 'icons/svg', src: 'icons/svg/anchor.svg'};
  assert.deepEqual((await resolvePreviewSource({image})).image, image);
  assert.equal(f.calls.length, 1);
  f.set('public', 'icons/svg', []);
  await assert.rejects(resolvePreviewSource({image}), code('ImageNotFound'));
  assert.equal(f.calls.length, 2);
});

test('escaping, spaces, Unicode, percent literals, prefix and harmless local query hints', async () => {
  const f = fixture({prefix: '/table'});
  const directory = 'worlds/test/%CE%B1%20maps';
  const src = directory + '/50%25%20floor.png';
  f.set('data', directory, [src]);
  for (const reference of [src, src+'?v=123', 'https://foundry.example/table/'+src+'?cb=abc', '/table/'+src]) {
    const result = await resolvePreviewSource({src: reference});
    assert.equal(result.image.src, src);
    assert.equal(result.fetch_url, 'https://foundry.example/table/'+src);
  }
  // Alternate Unicode/space spelling normalizes once while the returned
  // canonical selector still comes verbatim from the fresh picker response.
  f.set('data', 'worlds/test/%CE%B1%20maps', [src]);
  const unicode = await resolvePreviewSource({src: 'worlds/test/α maps/50%25 floor.png'});
  assert.equal(unicode.image.src, src);
  assert.ok(f.calls.every(c => c.directory === directory));
});

test('equal paths across data/public are ambiguous with bounded safe recovery', async () => {
  const f = fixture();
  for (const source of ['data','public']) f.set(source, 'assets', ['assets/a.png']);
  await assert.rejects(resolvePreviewSource({src: 'assets/a.png'}), error => {
    assert.equal(error.rpcError.code, 'AmbiguousSource');
    assert.match(error.rpcError.message, /browse_journal_images.*"limit":10,"max_bytes":8000/);
    return true;
  });
  assert.equal(f.calls.length, 2);
});

test('empty versus failed listings remain distinct when no readable match is established', async () => {
  const f = fixture();
  await assert.rejects(resolvePreviewSource({src: 'assets/a.png'}), code('ImageNotFound'));
  f.listings.set('public|assets|', Error('secret upstream credentials'));
  await assert.rejects(resolvePreviewSource({src: 'assets/a.png'}), error => code('BrowseFailed')(error) && !error.rpcError.message.includes('secret'));
});

test('a verified readable match survives another unavailable source without claiming absent coverage', async () => {
  const f = fixture();
  f.set('public','icons/svg',['icons/svg/anchor.svg']);
  f.listings.set('data|icons/svg|', Error('missing or denied'));
  const result = await resolvePreviewSource({src:'icons/svg/anchor.svg'});
  assert.equal(result.image.source, 'public');
  assert.equal(result.scope_status, 'partial');
  assert.ok(result.limitations.some(text => text.includes('unavailable')));
  assert.equal(f.calls.length, 3);
  assert.equal(f.calls.at(-1).source, 'public');
});

test('S3 uses configured bucket parent and picker-selected signed target privately without credentials', async () => {
  const f = fixture({s3: true});
  const src = 'https://test-bucket.s3.example/maps/a%20map.png?signature=secret';
  f.set('s3', 'maps', [src], {bucket: 'test-bucket'});
  const selected = await resolvePreviewSource({src: src.replace('signature=secret', 'signature=old')});
  assert.equal(selected.image.source, 's3');
  assert.equal(selected.fetch_url, src);
  assert.equal(selected.credentials, 'omit');
  assert.ok(f.calls.every(c => c.source === 's3' && c.directory === 'maps' && c.options.bucket === 'test-bucket'));
  assert.equal(f.calls.length, 2);
  assert.equal((await resolvePreviewSource({image: selected.image})).fetch_url, src);
  await assert.rejects(resolvePreviewSource({src: 'https://unrelated.example/maps/a%20map.png?signature=secret'}), error =>
    code('ImageNotFound')(error) && !error.rpcError.message.includes('secret'));
});

test('S3 path-style URLs and duplicate buckets preserve source ambiguity', async () => {
  const f = fixture({s3: true});
  const src = 'https://s3.example/test-bucket/maps/a.png';
  f.set('s3', 'maps', [src], {bucket: 'test-bucket'});
  assert.equal((await resolvePreviewSource({src})).image.directory, 'maps');
  f.sources.s3.buckets.push('another-bucket');
  f.set('s3', 'test-bucket/maps', [src], {bucket: 'another-bucket'});
  await assert.rejects(resolvePreviewSource({src}), error => code('AmbiguousSource')(error) && !error.rpcError.message.includes('https://'));
});

test('unconfigured sources, too many buckets, and oversized native listing fail explicitly', async () => {
  const f = fixture();
  await assert.rejects(resolvePreviewSource({src: 'https://unrelated.example/a.png'}), code('UnsupportedSource'));
  await assert.rejects(resolvePreviewSource({image: {source:'s3', directory:'', bucket:'absent', src:'https://s3.example/a.png'}}), code('UnsupportedSource'));
  f.sources.s3 = {buckets: Array.from({length:101}, (_,i) => 'bucket-'+i)};
  await assert.rejects(resolvePreviewSource({src:'a.png'}), code('SourceTooLarge'));
  delete f.sources.s3;
  f.set('data', 'assets', Array.from({length:10001}, (_,i) => `assets/${i}.png`));
  await assert.rejects(resolvePreviewSource({src:'assets/a.png'}), code('DirectoryTooLarge'));
});

test('dangerous schemes, traversal, separators, malformed paths and selector combinations fail before listing', async () => {
  const f = fixture();
  for (const src of ['javascript:a.png', 'file:///etc/a.png', 'C:\\private\\a.png', '../a.png', 'assets/../a.png',
    'assets/%2e%2e/a.png', 'assets/a%2fb.png', 'assets/a%5cb.png', 'assets/%zz.png', '//other.example/a.png',
    'https://foundry.example/assets/../a.png', 'https://user:password@foundry.example/a.png',
    'assets/a.png#part', 'assets/a.png?token=secret', 'assets/a.png?v=unsafe%20value', 'a.txt', '', true, 'a'.repeat(4097)+'.png']) {
    await assert.rejects(resolvePreviewSource({src}), code('InvalidRequest'), String(src).slice(0,50));
  }
  for (const args of [{}, {image:null}, {src:null}, {src:'a.png', image:{}}, {src:'a.png', extra:true}]) {
    await assert.rejects(resolvePreviewSource(args), code('InvalidRequest'));
  }
  assert.equal(f.calls.length, 0);
});

test('socket, world, GM and readiness checked before and after awaits and final recheck', async () => {
  const f = fixture(); f.set('data','assets',['assets/a.png']);
  for (const change of [() => {game.user={isGM:true,id:'other'};}, () => {game.world.id='other';}, () => {game.user.isGM=false;}, () => {game.ready=false;}]) {
    const g = fixture(); g.set('data','assets',['assets/a.png']); g.onBrowse=change;
    await assert.rejects(resolvePreviewSource({src:'assets/a.png'}), error => ['ContextChanged','PermissionDenied','NotReady'].includes(error.rpcError?.code));
  }
  const g = fixture(); let current = true;
  g.onBrowse = () => {current=false;};
  await assert.rejects(resolvePreviewSource({src:'assets/a.png'}, () => current), code('ContextChanged'));
  const h = fixture(); h.set('data','assets',['assets/a.png']);
  h.onBrowse = () => {if(h.calls.length===3)h.set('data','assets',[]);};
  await assert.rejects(resolvePreviewSource({src:'assets/a.png'}), code('ImageNotFound'));
  fixture(); game.user.isGM=false;
  await assert.rejects(resolvePreviewSource({src:'a.png'}), code('PermissionDenied'));
});
