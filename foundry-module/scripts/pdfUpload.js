import { gmOnly, pdfRequest } from "./pdfChannel.js";

export class PDFUpload {
  constructor(request = pdfRequest) { this.request = request; this.cancelled = false; this.uploadId = null; }
  async authorize() {
    gmOnly();
    const token = game.settings.get("foundry-mcp", "pdfUploadToken");
    if (!token) throw new Error("Set the PDF upload password in Configure Settings → Foundry MCP Proxy.");
    await this.request("pdf.upload.authorize", { token });
  }
  async cancel() {
    gmOnly(); this.cancelled = true;
    if (this.uploadId) await this.request("pdf.upload.cancel", { upload_id: this.uploadId });
  }
  async upload(file, progress = () => {}) {
    gmOnly(); this.cancelled = false;
    if (!file || !file.name.toLowerCase().endsWith(".pdf") || !Number.isSafeInteger(file.size) || file.size <= 0)
      throw new Error("Choose a nonempty PDF file.");
    await this.authorize();
    gmOnly();
    if (this.cancelled) throw new Error("Upload cancelled.");
    const begin = await this.request("pdf.upload.begin", { name: file.name, size_bytes: file.size, content_type: "application/pdf" });
    this.uploadId = begin.upload_id;
    if (begin.chunk_bytes !== 32768 || begin.accepted_bytes !== 0 || typeof this.uploadId !== "string") throw new Error("Invalid upload negotiation.");
    let accepted = 0, seq = 0;
    progress({ stage: "uploading", accepted, total: file.size });
    try {
      while (accepted < file.size) {
        gmOnly(); if (this.cancelled) throw new Error("Upload cancelled.");
        const bytes = new Uint8Array(await file.slice(accepted, Math.min(file.size, accepted + 32768)).arrayBuffer());
        gmOnly(); if (this.cancelled) throw new Error("Upload cancelled.");
        let binary = ""; for (const byte of bytes) binary += String.fromCharCode(byte);
        const ack = await this.request("pdf.upload.chunk", { upload_id: this.uploadId, seq, data_base64: btoa(binary) });
        if (ack.type !== "pdf.upload.ack" || ack.upload_id !== this.uploadId || ack.next_seq !== seq + 1 ||
            ack.accepted_bytes !== accepted + bytes.length || ack.accepted_bytes > file.size)
          throw new Error("Invalid server acknowledgment; restart the upload.");
        accepted = ack.accepted_bytes; seq++;
        progress({ stage: "uploading", accepted, total: file.size });
      }
      gmOnly(); if (this.cancelled) throw new Error("Upload cancelled.");
      const result = await this.request("pdf.upload.finish", { upload_id: this.uploadId });
      this.uploadId = null;
      progress({ stage: result.status, accepted, total: file.size, document_id: result.document_id });
      return result;
    } catch (error) {
      if (this.uploadId && game.user?.isGM) {
        try { await this.request("pdf.upload.cancel", { upload_id: this.uploadId }); } catch { /* stale or removed session */ }
      }
      this.uploadId = null;
      throw error;
    }
  }
}
