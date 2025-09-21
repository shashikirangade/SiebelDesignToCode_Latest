// static/js/app.js  — SAFE for all pages (guards for missing elements)

const $ = (sel) => document.querySelector(sel);

// ---------- UI Helpers (null-safe) ----------
function showError(msg) {
  const b = $("#errorBanner");
  if (!b) return;
  b.textContent = msg;
  b.style.display = "block";
}
function clearError() {
  const b = $("#errorBanner");
  if (!b) return;
  b.style.display = "none";
}
function showLoading(on = true) {
  const l = $("#dtc-loading");
  if (!l) return;
  l.style.display = on ? "flex" : "none";
}
function toast(msg, ms = 2200) {
  const t = $("#dtc-toaster");
  if (!t) return;
  t.textContent = msg;
  t.style.display = "block";
  setTimeout(() => (t.style.display = "none"), ms);
}
function copyCode(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const text = el.innerText;
  if (!navigator.clipboard) return;
  navigator.clipboard.writeText(text).then(() => toast("Copied to clipboard!"));
}

// ---------- Siebel WebTemplate generation ----------
let currentWorkdir = null;

async function generateSiebel() {
  const fd = new FormData();
  if (currentWorkdir) fd.append("workdir", currentWorkdir);

  const res = await fetch("/api/generate_siebel", { method: "POST", body: fd });
  const raw = await res.text();
  let data;
  try {
    data = JSON.parse(raw);
  } catch (e) {
    console.error("Non-JSON response:", raw);
    showError("Server returned an invalid response.");
    return;
  }

  if (data.ok) {
    // Fetch the actual files to render previews if present on page
    const viewCodeEl = document.getElementById("viewCode");
    if (viewCodeEl && data.files?.view) {
      try {
        const viewResp = await fetch(data.files.view);
        viewCodeEl.innerText = await viewResp.text();
      } catch (e) {
        console.warn("Failed to fetch view file:", e);
      }
    }

    const appletCodeEl = document.getElementById("appletCode");
    if (appletCodeEl && Array.isArray(data.files?.applets) && data.files.applets.length > 0) {
      try {
        const first = data.files.applets[0];
        const firstAppletUrl =
          typeof first === "string" ? first : first.file || first.url || "";
        if (firstAppletUrl) {
          const appletResp = await fetch(firstAppletUrl);
          appletCodeEl.innerText = await appletResp.text();
        }
      } catch (e) {
        console.warn("Failed to fetch applet file:", e);
      }
    }

    const codeCompare = document.getElementById("codeCompare");
    if (codeCompare) codeCompare.style.display = "block";
  } else {
    showError(data.error || "Generation failed.");
  }
}

// ---------- Page Initializers (each runs only if its elements exist) ----------
function initUploadConvertSection() {
  const uploadForm   = $("#uploadForm");
  if (!uploadForm) return; // this page doesn't have upload; skip

  const modelSel     = $("#modelSelect");
  const previewBlock = $("#previewBlock");
  const iframe       = $("#previewFrame");
  const btnRetry     = $("#btnRetry");
  const btnGenerate  = $("#btnGenerate");
  const btnRaw       = $("#btnRaw");
  const btnHtml      = $("#btnHtml");
  const imageInput   = $("#imageInput");

  // Submit (convert)
  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearError();

    const file = imageInput && imageInput.files ? imageInput.files[0] : null;
    if (!file) {
      showError("Please select an image to upload.");
      return;
    }

    const fd = new FormData();
    fd.append("image", file);
    if (modelSel) fd.append("model", modelSel.value || "");
    // harmless if backend ignores; kept for backward compatibility
    fd.append("max_tokens", "6000");

    showLoading(true);
    try {
      const res = await fetch("/api/convert", { method: "POST", body: fd });
      const data = await res.json();
      if (!data.ok) {
        showError(data.error || "Conversion failed.");
        return;
      }
      currentWorkdir = data.workdir;

      if (iframe) iframe.src = `/preview/${currentWorkdir}`;
      if (previewBlock) previewBlock.style.display = "block";
      if (btnRaw)  btnRaw.href  = `/download/${currentWorkdir}/raw_response.txt`;
      if (btnHtml) btnHtml.href = `/download/${currentWorkdir}/generated.html`;
      toast("Preview generated.");
    } catch (err) {
      showError("Network error during conversion.");
    } finally {
      showLoading(false);
    }
  });

  // Retry
  if (btnRetry) {
    btnRetry.addEventListener("click", async () => {
      if (!currentWorkdir) return;
      clearError();
      showLoading(true);

      const fd = new FormData();
      fd.append("workdir", currentWorkdir);
      if (modelSel) fd.append("model", modelSel.value || "");
      fd.append("max_tokens", "6000");

      try {
        const res = await fetch("/api/retry", { method: "POST", body: fd });
        const data = await res.json();
        if (!data.ok) {
          showError(data.error || "Retry failed.");
          return;
        }
        currentWorkdir = data.workdir;

        const frame = $("#previewFrame"); if (frame) frame.src = `/preview/${currentWorkdir}`;
        const r = $("#btnRaw");  if (r) r.href  = `/download/${currentWorkdir}/raw_response.txt`;
        const h = $("#btnHtml"); if (h) h.href = `/download/${currentWorkdir}/generated.html`;
        toast("New version generated.");
      } catch (e) {
        showError("Network error during retry.");
      } finally {
        showLoading(false);
      }
    });
  }

  // Generate Siebel WebTemplate
  if (btnGenerate) {
    btnGenerate.addEventListener("click", async () => {
      if (!currentWorkdir) return;
      clearError();
      showLoading(true);

      try {
        const fd = new FormData();
        fd.append("workdir", currentWorkdir);
        const res = await fetch("/api/generate_siebel", { method: "POST", body: fd });

        const raw = await res.text();
        let data;
        try { data = JSON.parse(raw); }
        catch (e) {
          console.error("Non-JSON response:", raw);
          showError("Server returned an invalid response.");
          return;
        }

        if (!res.ok || !data || data.ok !== true) {
          console.error("Generation error:", data);
          showError((data && data.error) || "Generation failed.");
          return;
        }

        toast(data.message || "Generated Siebel WebTemplate.");

        // Auto download zip if provided
        if (data.zip) window.location.href = data.zip;

        // Render links to individual files
        const linksEl = $("#generated-links");
        if (linksEl && data.files) {
          const items = [];

          const viewUrl = data.files.view;
          if (viewUrl) items.push(`<li><a href="${viewUrl}" target="_blank">view_template.swt</a></li>`);

          const applets = Array.isArray(data.files.applets) ? data.files.applets : [];
          applets.forEach((a) => {
            const url =
              typeof a === "string"
                ? a
                : a.url || (a.file ? `/download/${currentWorkdir}/webtemplate/${a.file}` : "");
            const label =
              (typeof a === "string" && a.split("/").pop()) ||
              a.file || a.safe || "applet";
            if (url) items.push(`<li><a href="${url}" target="_blank">${label}</a></li>`);
          });

          linksEl.innerHTML = items.length ? `<ul>${items.join("")}</ul>` : "";
        }
      } catch (e) {
        console.error(e);
        showError("Network error during generation.");
      } finally {
        showLoading(false);
      }
    });
  }
}

function initClientScriptBot() {
  const send = $("#chatSend");
  const msg  = $("#chatMsg");
  const win  = $("#chatWindow");
  const ctx  = $("#ctxType");
  if (!send || !msg || !win) return; // not on bot page

  const bubble = (txt, who) => {
    const d = document.createElement("div");
    d.className = "chat-bubble " + who;
  
    if (who === "bot-html") {
      d.innerHTML = txt;   // render as HTML
    } else {
      d.textContent = txt; // normal text
    }
  
    win.appendChild(d);
    win.scrollTop = win.scrollHeight;
  };
  

  send.addEventListener("click", async () => {
    const q = (msg.value || "").trim();
    if (!q) return;
    bubble(q, "user");
    msg.value = "";

    try {
      const r = await fetch("/api/client-script/ask", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ message: q, context_type: ctx ? ctx.value : "" })
      });
      const data = await r.json();
      if (data.html) {
        bubble(data.answer || "", "bot-html");
      } else {
        bubble(data.answer || (data.error || "Error"), "bot");
      }
    } catch (e) {
      bubble("Network error", "bot");
    }
  });
}

// ---------- Boot ----------
window.addEventListener("DOMContentLoaded", () => {
  // Optional: scope by page via data attribute
  // const page = document.body?.dataset?.page;

  initUploadConvertSection(); // harmless on pages without upload section
  initClientScriptBot();      // harmless on pages without bot
});
