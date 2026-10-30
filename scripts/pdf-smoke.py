#!/usr/bin/env python3
"""Synthetic PDF-only smoke for an isolated test server; never run on a gaming bridge."""
import asyncio
import base64
from io import BytesIO
import json
import httpx2 as httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
import websockets

async def check(base, verify_only=False):
    writer=PdfWriter();page=writer.add_blank_page(600,800)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 50 750 Td (SYNTHETIC RULE) Tj 0 -16 Td (Use the documented synthetic result.) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream)
    writer.add_outline_item('Synthetic Rule',0)
    output=BytesIO();writer.write(output);data=output.getvalue()+b'\n'*70000
    async with httpx.AsyncClient(trust_env=False) as http:
        assert (await http.get(base+'/health')).json()['foundry_clients']==[], 'Never run against a connected gaming bridge'
        assert (await http.post(base+'/mcp/mcp')).status_code==401
    async with Client(StreamableHttpTransport(base+'/mcp/mcp',auth=httpx.BasicAuth('smoke','smoke-password'))) as client:
        if verify_only:
            docs=(await client.call_tool('list_pdf_documents',{})).data['documents']
            ready=[d for d in docs if d['name']=='Synthetic.pdf' and d['status']=='ready']
            assert ready, 'Synthetic book did not survive container replacement'
            page=(await client.call_tool('read_pdf_pages',{'document_id':ready[0]['document_id'],'physical_page':1})).data
            assert 'documented synthetic result' in page['text']
            print('PASS: indexed source survives container replacement without a browser')
            async with websockets.connect(base.replace('http','ws',1)+'/ws/foundry') as ws:
                await ws.send(json.dumps({'type':'auth','token':'smoke-bridge'}));await ws.recv()
                await ws.send(json.dumps({'type':'pdf.upload.authorize','request_id':'delete-auth','protocol':1,'token':'smoke-private-upload'}))
                assert json.loads(await ws.recv())['type']=='pdf.upload.authorize_ack'
                await ws.send(json.dumps({'type':'pdf.upload.delete','request_id':'delete-book','protocol':1,
                    'document_id':ready[0]['document_id'],'revision':ready[0]['revision']}))
                deleted=json.loads(await ws.recv());assert deleted['type']=='pdf.upload.delete_ack' and deleted['deleted'] is True
            docs=(await client.call_tool('list_pdf_documents',{})).data['documents']
            assert all(d['document_id']!=ready[0]['document_id'] for d in docs)
            missing=await client.call_tool('read_pdf_pages',{'document_id':ready[0]['document_id'],'physical_page':1},raise_on_error=False)
            assert missing.is_error
            print('PASS: authenticated browser deletion removes source retrieval and library metadata')
            return
        await client.call_tool('refresh_pdf_index',{})
        async with websockets.connect(base.replace('http','ws',1)+'/ws/foundry') as ws:
            await ws.send(json.dumps({'type':'auth','token':'smoke-bridge'}));assert json.loads(await ws.recv())['status']=='ok'
            counter=0
            async def request(kind,**fields):
                nonlocal counter
                counter+=1
                await ws.send(json.dumps(dict(type='pdf.upload.'+kind,request_id=str(counter),protocol=1,**fields)))
                return json.loads(await ws.recv())
            assert (await request('list'))['type']=='pdf.upload.error'
            assert (await request('authorize',token='world-bridge-is-insufficient'))['type']=='pdf.upload.error'
            assert (await request('authorize',token='smoke-private-upload'))['type']=='pdf.upload.authorize_ack'
            begin=await request('begin',name='Synthetic.pdf',size_bytes=len(data));upload=begin['upload_id']
            for seq,start in enumerate(range(0,len(data),32768)):
                chunk=data[start:start+32768]
                ack=await request('chunk',upload_id=upload,seq=seq,data_base64=base64.b64encode(chunk).decode())
                assert ack['accepted_bytes']==min(start+32768,len(data))
                # Existing gameplay RPC is still usable during the transfer.
                call=asyncio.create_task(client.call_tool('get_player_names',{}))
                rpc=json.loads(await ws.recv());assert rpc['method']=='getPlayerNameList'
                await ws.send(json.dumps({'id':rpc['id'],'result':['Synthetic GM']}));assert not (await call).is_error
            done=await request('finish',upload_id=upload);identifier=done['document_id']
            for _ in range(60):
                status=await request('index_status',document_id=identifier)
                if status['status'] in {'ready','failed'}:break
                await asyncio.sleep(.25)
            assert status['status']=='ready',status
        # Retrieval does not need a connected browser.
        result=(await client.call_tool('locate_pdf_entry',{'name':'Synthetic Rule','document_id':identifier})).data
        assert result['candidates'][0]['physical_page']==1
        page=(await client.call_tool('read_pdf_pages',{'document_id':identifier,'physical_page':1})).data
        assert 'documented synthetic result' in page['text']
        print('PASS: capability denials, multi-chunk ACK integrity, concurrent gameplay RPC, indexing, no-browser source lookup',identifier)

if __name__=='__main__':
    import sys
    asyncio.run(check(sys.argv[1], '--verify-only' in sys.argv))
