import { gmOnly, pdfRequest } from "./pdfChannel.js";
import { PDFUpload } from "./pdfUpload.js";

/** Only our own dialog content is queried; never Foundry UI DOM structure. */
export function registerPDFManager() {
  gmOnly();
  const DialogV2 = foundry.applications.api.DialogV2;
  class PDFLibraryManager extends DialogV2 {
    constructor(options = {}) {
      gmOnly();
      super({ ...options, window: { title: "Manage PDF Library (GM private)" },
        content: `<section data-pdf-manager>
          <p>Upload PDFs to your reference library. Configure the PDF upload password in the module settings.</p>
          <input name="pdf-file" type="file" accept=".pdf,application/pdf">
          <p data-pdf="selected">Select a PDF.</p>
          <progress data-pdf="progress" max="1" value="0"></progress>
          <p data-pdf="status" role="status">Checking PDF library connection…</p>
          <button type="button" data-pdf="upload">Upload</button>
          <button type="button" data-pdf="cancel">Cancel upload</button>
          <button type="button" data-pdf="refresh">Refresh PDFs</button>
          <ul data-pdf="documents" style="max-height:40vh;overflow:auto"></ul></section>`,
        buttons: [{ action: "close", label: "Close" }] });
    }
  }
  const controllers = new WeakMap();
  Hooks.on("renderPDFLibraryManager", (application, element) => {
    gmOnly();
    const root = element.querySelector("[data-pdf-manager]");
    if (!root) return;
    const client = new PDFUpload(); controllers.set(application,client);
    const field = name => root.querySelector(`[data-pdf="${name}"]`);
    const input = name => root.querySelector(`[name="pdf-${name}"]`);
    const status = text => { field("status").textContent = text; };
    let busy = false;
    const act = fn => async () => { try { gmOnly(); await fn(); } catch(error) { status(error.message); } };
    async function list({updateStatus=true,authorize=true}={}) {
      gmOnly();
      if (updateStatus) status("Connecting to PDF library…");
      let count = 0;
      if (authorize) await client.authorize();
      field("documents").replaceChildren();
      let offset = 0;
      do {
        gmOnly();
        const result = await pdfRequest("pdf.upload.list", { offset });
        count += result.documents.length;
        for (const book of result.documents) {
          const li = document.createElement("li");
          li.textContent = `${book.name}: ${book.status} (${book.page_count} pages)${book.error ? " — " + book.error : ""}. Warnings: ${(book.warnings || []).join(", ") || "none reported yet"}. No OCR.`;
          const remove = document.createElement("button");
          remove.type="button";
          remove.textContent="Delete PDF";
          remove.disabled=!['ready','failed'].includes(book.status);
          remove.title=remove.disabled ? "Wait for processing to finish before deleting." : "Delete this PDF and its searchable index.";
          remove.addEventListener("click",act(async () => {
            if (busy) { status("Finish the current operation before deleting PDFs."); return; }
            busy=true; remove.disabled=true; field("upload").disabled=true;
            try {
              // Filename is rendered only as text in the list, never interpolated into HTML.
              const name=String(book.name).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
              const confirmed=await DialogV2.confirm({window:{title:"Delete PDF?"},
                content:`<p>Permanently delete <strong>${name}</strong> and its searchable pages from the MCP library? Keep your original file if you want to upload it again.</p>`,
                rejectClose:false,modal:true});
              if (!confirmed) return;
              gmOnly();
              await client.authorize();
              const result=await pdfRequest("pdf.upload.delete",{document_id:book.document_id,revision:book.revision});
              if (result.type!=="pdf.upload.delete_ack" || result.document_id!==book.document_id || result.deleted!==true)
                throw new Error("Deletion was not confirmed by the server. Refresh PDFs to check its status.");
              await list();
            } finally { busy=false; remove.disabled=false; field("upload").disabled=false; }
          }));
          li.append(remove);
          field("documents").append(li);
        }
        offset = result.next_offset;
      } while(offset !== null);
      if (updateStatus) status(count ? `Connected. ${count} PDF${count === 1 ? "" : "s"} in the library.` : "Connected. No PDFs uploaded yet.");
    }
    void act(list)();
    input("file").addEventListener("change",act(async () => {
      const file=input("file").files[0]; field("selected").textContent=file?`${file.name} (${file.size} bytes)`:"Select a PDF.";
    }));
    field("refresh").addEventListener("click",act(async () => { if (!busy) await list(); }));
    field("cancel").addEventListener("click",act(async () => { await client.cancel(); status("Transfer cancelled. Completed documents remain saved."); }));
    field("upload").addEventListener("click",act(async () => {
      if (busy) return;
      busy=true; field("upload").disabled=true;
      field("progress").value=0;
      let completed=false;
      try {
        status("Validating selection and authorization…");
        const result=await client.upload(input("file").files[0], value => {
          field("progress").value=value.accepted/value.total;
          status(value.stage==="uploading"?`Uploading: ${value.accepted} / ${value.total} bytes acknowledged`:`Bytes durably received. ${value.stage}; not yet searchable.`);
        });
        let current=result;
        const processingStatus = state => ({queued:"Upload complete. Waiting to process PDF…",validating:"Upload complete. Validating PDF and extracting text…",indexing:"Upload complete. Building the searchable index…"}[state] || `Upload complete. Processing: ${state}.`);
        if (!['ready','failed'].includes(current.status)) {
          field("progress").removeAttribute("value");
          status(processingStatus(current.status));
        }
        await list({updateStatus:false,authorize:false});
        while (!['ready','failed'].includes(current.status)) {
          gmOnly(); if (client.cancelled) break;
          await new Promise(resolve=>setTimeout(resolve,1000));
          current=await pdfRequest("pdf.upload.index_status",{document_id:result.document_id});
          if (!['ready','failed'].includes(current.status)) status(processingStatus(current.status));
          await list({updateStatus:false,authorize:false});
        }
        if (current.status==='ready') {
          completed=true;
          status(result.replacing ? "Ready / Searchable. Existing PDF replaced." : "Ready / Searchable. PDF added to the library.");
        }
        else if (current.status==='failed') status(current.error || "Indexing failed; document is not searchable.");
        if (!client.cancelled) await list({updateStatus:false,authorize:false});
      } finally {
        field("progress").value=completed ? 1 : 0;
        busy=false; field("upload").disabled=false;
      }
    }));
  });
  Hooks.on("closePDFLibraryManager", application => { const c=controllers.get(application); if(c) c.cancel().catch(()=>{}); });
  game.settings.registerMenu("foundry-mcp","pdfLibrary",{name:"PDF Library",label:"Manage PDF Library",hint:"Upload and inspect the private MCP reference library (GM only).",icon:"fas fa-book",type:PDFLibraryManager,restricted:true});
}
