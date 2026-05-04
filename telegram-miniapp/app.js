/**
 * Telegram Mini App → POST /api/v1/analyze (zip_code + image)
 * Задайте window.__API_BASE__ в index.html или через ?api=https://...
 */
(function () {
  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    const p = tg.themeParams || {};
    if (p.bg_color) {
      document.documentElement.style.setProperty("--bg", p.bg_color);
    }
    if (p.secondary_bg_color) {
      document.documentElement.style.setProperty("--bg-card", p.secondary_bg_color + "ee");
    }
    if (p.text_color) {
      document.documentElement.style.setProperty("--text", p.text_color);
    }
    if (p.hint_color) {
      document.documentElement.style.setProperty("--muted", p.hint_color);
    }
    if (p.button_color) {
      document.documentElement.style.setProperty("--accent", p.button_color);
    }
  }

  const params = new URLSearchParams(window.location.search);
  const API_BASE = (
    params.get("api") ||
    window.__API_BASE__ ||
    window.location.origin
  ).replace(/\/+$/, "");

  const zipInput = document.getElementById("zip");
  const fileInput = document.getElementById("photo");
  const uploadZone = document.getElementById("uploadZone");
  const preview = document.getElementById("preview");
  const previewImg = document.getElementById("previewImg");
  const btn = document.getElementById("submitBtn");
  const loader = document.getElementById("loader");
  const errEl = document.getElementById("error");
  const resultEl = document.getElementById("result");
  const verdictEl = document.getElementById("verdict");
  const regionEl = document.getElementById("region");
  const detailsEl = document.getElementById("details");
  const toggleDetails = document.getElementById("toggleDetails");

  function showError(msg) {
    errEl.textContent = msg;
    errEl.classList.add("visible");
  }

  function hideError() {
    errEl.classList.remove("visible");
    errEl.textContent = "";
  }

  uploadZone.addEventListener("click", () => fileInput.click());

  uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.classList.add("dragover");
  });
  uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("dragover"));
  uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f && f.type.startsWith("image/")) {
      fileInput.files = e.dataTransfer.files;
      syncPreview();
    }
  });

  fileInput.addEventListener("change", syncPreview);

  function syncPreview() {
    const f = fileInput.files && fileInput.files[0];
    if (!f) {
      preview.classList.remove("visible");
      uploadZone.classList.remove("has-file");
      previewImg.removeAttribute("src");
      return;
    }
    uploadZone.querySelector(".big").textContent = f.name;
    uploadZone.querySelector(".small").textContent =
      (f.size / 1024).toFixed(0) + " KB · готово к отправке";
    uploadZone.classList.add("has-file");
    const url = URL.createObjectURL(f);
    previewImg.onload = () => URL.revokeObjectURL(url);
    previewImg.src = url;
    preview.classList.add("visible");
  }

  toggleDetails.addEventListener("click", () => {
    detailsEl.classList.toggle("open");
    toggleDetails.textContent = detailsEl.classList.contains("open")
      ? "Скрыть детали"
      : "Подробнее (распознавание)";
  });

  btn.addEventListener("click", async () => {
    hideError();
    resultEl.classList.remove("visible");

    const zip = zipInput.value.trim();
    if (!zip) {
      showError("Укажите почтовый индекс (7 цифр).");
      return;
    }

    const digits = zip.replace(/\D/g, "");
    if (digits.length !== 7) {
      showError("Индекс должен содержать 7 цифр (можно с дефисом).");
      return;
    }

    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      showError("Выберите фото предмета.");
      return;
    }

    btn.disabled = true;
    loader.classList.add("visible");

    try {
      const fd = new FormData();
      fd.append("zip_code", zip);
      fd.append("district_id", "");
      fd.append("image", file);

      const res = await fetch(API_BASE + "/api/v1/analyze", {
        method: "POST",
        body: fd,
      });

      const text = await res.text();
      let body;
      try {
        body = JSON.parse(text);
      } catch {
        body = { detail: text };
      }

      if (!res.ok) {
        const msg =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body);
        throw new Error(msg);
      }

      verdictEl.textContent = body.verdict_ru || "Ответ пуст.";
      const label = body.district_label_ru || "";
      const did = body.district_id || "";
      regionEl.innerHTML =
        label && did
          ? `<strong>${escapeHtml(label)}</strong><br/><span style="opacity:.85">district_id: ${escapeHtml(did)}</span>`
          : escapeHtml(did || "");

      const v = body.vision || {};
      let detailsHtml = `
        <dl>
          <dt>Предмет</dt><dd>${escapeHtml(v.object || "—")}</dd>
          <dt>Материал</dt><dd>${escapeHtml(v.material || "—")}</dd>
          <dt>Размер (см)</dt><dd>${v.size_cm != null ? escapeHtml(String(v.size_cm)) : "—"}</dd>
          <dt>Чистота</dt><dd>${v.is_clean ? "да" : "нет"}</dd>
        </dl>`;
      if (Array.isArray(body.rag_excerpts) && body.rag_excerpts.length) {
        detailsHtml +=
          `<p style="margin-top:.85rem;font-weight:700;color:var(--text);opacity:.9">Фрагменты правил</p>` +
          `<ul style="margin:0;padding-left:1rem;">` +
          body.rag_excerpts.map((x) => "<li>" + escapeHtml(x) + "</li>").join("") +
          `</ul>`;
      }
      detailsEl.innerHTML = detailsHtml;

      detailsEl.classList.remove("open");
      toggleDetails.textContent = "Подробнее (распознавание)";
      resultEl.classList.add("visible");

      if (tg && tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred("success");
      }
    } catch (e) {
      showError(e.message || String(e));
      if (tg && tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred("error");
      }
    } finally {
      btn.disabled = false;
      loader.classList.remove("visible");
    }
  });

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }
})();
