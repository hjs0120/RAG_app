(function () {
  "use strict";

  const messagesEl = document.getElementById("messages");
  const queryInput = document.getElementById("queryInput");
  const sendBtn = document.getElementById("sendBtn");
  const serverUrlInput = document.getElementById("serverUrl");
  const sourceModal = document.getElementById("sourceModal");
  const sourceModalCaption = document.getElementById("sourceModalCaption");
  const sourceModalImage = document.getElementById("sourceModalImage");

  function getBaseUrl() {
    const url = (serverUrlInput && serverUrlInput.value || "").trim();
    return url || "http://127.0.0.1:8081";
  }

  function escapeHtml(s) {
    if (s == null) return "";
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function showSourceModal(imageUrl, caption) {
    if (!sourceModal || !sourceModalImage || !sourceModalCaption) return;
    const base = getBaseUrl().replace(/\/$/, "");
    const fullUrl = imageUrl.startsWith("http") ? imageUrl : base + imageUrl;
    sourceModalCaption.textContent = caption || "출처";
    sourceModalImage.src = fullUrl;
    sourceModalImage.alt = caption || "출처 페이지";
    sourceModal.style.display = "flex";
  }

  function closeSourceModal() {
    if (sourceModal) {
      sourceModal.style.display = "none";
      sourceModalImage.src = "";
    }
  }

  function addMessage(opts) {
    const div = document.createElement("div");
    div.className = "msg " + (opts.role || "bot");
    if (opts.isLoading) div.classList.add("loading");
    if (opts.isError) div.classList.add("error");
    if (opts.isRejected) div.classList.add("rejected");

    let label = "";
    if (opts.role === "user") label = "나";
    else if (opts.role === "bot") label = "봇";
    else if (opts.isError || opts.isRejected) label = "안내";

    let bubble = "";
    if (opts.isLoading) {
      bubble =
        '<div class="msg-bubble">' +
        '<span class="spinner"></span>' +
        '<span>답변 생성 중...</span>' +
        "</div>";
    } else {
      const text = escapeHtml(opts.text || "");
      bubble =
        (label ? '<div class="msg-label">' + escapeHtml(label) + "</div>" : "") +
        '<div class="msg-bubble">' +
        text +
        "</div>";
    }

    div.innerHTML = bubble;

    if (opts.sources && opts.sources.length > 0) {
      const wrap = document.createElement("div");
      wrap.className = "sources-wrap";
      wrap.innerHTML =
        '<div class="sources-toggle">출처 (' +
        opts.sources.length +
        ")</div>" +
        '<div class="sources-list">' +
        opts.sources
          .map(function (s) {
            const meta = s.metadata || {};
            const path = meta.structure_path || "-";
            const file = meta.file_name || "-";
            const page = meta.physical_page != null ? "p." + meta.physical_page : "";
            const imageUrl = meta.image_url || "";
            const cardClass = "source-card" + (imageUrl ? " clickable" : "");
            const pageNum = meta.physical_page != null ? String(meta.physical_page) : "";
            let dataAttrs = "";
            if (imageUrl) {
              dataAttrs =
                ' data-image-url="' +
                escapeHtml(imageUrl) +
                '" data-structure-path="' +
                escapeHtml(path) +
                '" data-file-name="' +
                escapeHtml(file) +
                '" data-page="' +
                escapeHtml(pageNum) +
                '"';
            }
            return (
              '<div class="' +
              cardClass +
              '"' +
              dataAttrs +
              ">" +
              '<div class="structure-path">' +
              escapeHtml(path) +
              "</div>" +
              '<div class="file-page">' +
              escapeHtml(file) +
              (page ? " · " + page : "") +
              "</div>" +
              "</div>"
            );
          })
          .join("") +
        "</div>";
      const toggle = wrap.querySelector(".sources-toggle");
      const list = wrap.querySelector(".sources-list");
      toggle.addEventListener("click", function () {
        list.classList.toggle("collapsed");
        toggle.classList.toggle("collapsed", list.classList.contains("collapsed"));
      });
      list.addEventListener("click", function (e) {
        const card = e.target && e.target.closest(".source-card.clickable");
        if (card && card.dataset.imageUrl) {
          const parts = [
            card.dataset.structurePath || "",
            card.dataset.fileName || "",
            card.dataset.page ? "p." + card.dataset.page : "",
          ].filter(Boolean);
          showSourceModal(card.dataset.imageUrl, parts.join(" · "));
        }
      });
      div.appendChild(wrap);
    }

    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function setLoading(div, loading) {
    if (!div) return;
    if (loading) {
      div.classList.add("loading");
      const bubble = div.querySelector(".msg-bubble");
      if (bubble) {
        bubble.innerHTML = '<span class="spinner"></span><span>답변 생성 중...</span>';
      }
    } else {
      div.classList.remove("loading");
    }
  }

  function replaceLoadingWithMessage(loadingDiv, opts) {
    if (!loadingDiv) return;
    loadingDiv.classList.remove("loading");
    loadingDiv.className = "msg " + (opts.role || "bot");
    if (opts.isError) loadingDiv.classList.add("error");
    if (opts.isRejected) loadingDiv.classList.add("rejected");

    const label = opts.isError || opts.isRejected ? "안내" : "봇";
    let html =
      '<div class="msg-label">' +
      escapeHtml(label) +
      "</div>" +
      '<div class="msg-bubble">' +
      escapeHtml(opts.text || "") +
      "</div>";
    if (opts.sources && opts.sources.length > 0) {
      html +=
        '<div class="sources-wrap">' +
        '<div class="sources-toggle">출처 (' +
        opts.sources.length +
        ")</div>" +
        '<div class="sources-list">' +
        opts.sources
          .map(function (s) {
            const meta = s.metadata || {};
            const path = meta.structure_path || "-";
            const file = meta.file_name || "-";
            const page = meta.physical_page != null ? "p." + meta.physical_page : "";
            const imageUrl = meta.image_url || "";
            const cardClass = "source-card" + (imageUrl ? " clickable" : "");
            const pageNum = meta.physical_page != null ? String(meta.physical_page) : "";
            let dataAttrs = "";
            if (imageUrl) {
              dataAttrs =
                ' data-image-url="' +
                escapeHtml(imageUrl) +
                '" data-structure-path="' +
                escapeHtml(path) +
                '" data-file-name="' +
                escapeHtml(file) +
                '" data-page="' +
                escapeHtml(pageNum) +
                '"';
            }
            return (
              '<div class="' +
              cardClass +
              '"' +
              dataAttrs +
              ">" +
              '<div class="structure-path">' +
              escapeHtml(path) +
              "</div>" +
              '<div class="file-page">' +
              escapeHtml(file) +
              (page ? " · " + page : "") +
              "</div>" +
              "</div>"
            );
          })
          .join("") +
        "</div>";
    }
    loadingDiv.innerHTML = html;
    if (opts.sources && opts.sources.length > 0) {
      const wrap = loadingDiv.querySelector(".sources-wrap");
      const toggle = wrap && wrap.querySelector(".sources-toggle");
      const list = wrap && wrap.querySelector(".sources-list");
      if (toggle && list) {
        toggle.addEventListener("click", function () {
          list.classList.toggle("collapsed");
          toggle.classList.toggle("collapsed", list.classList.contains("collapsed"));
        });
        list.addEventListener("click", function (e) {
          const card = e.target && e.target.closest(".source-card.clickable");
          if (card && card.dataset.imageUrl) {
            const parts = [
              card.dataset.structurePath || "",
              card.dataset.fileName || "",
              card.dataset.page ? "p." + card.dataset.page : "",
            ].filter(Boolean);
            showSourceModal(card.dataset.imageUrl, parts.join(" · "));
          }
        });
      }
    }
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function ask(query) {
    const base = getBaseUrl();
    const url = base.replace(/\/$/, "") + "/api/ask";
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query, top_k: 5 }),
    });
    if (!res.ok) {
      throw new Error("서버 오류: " + res.status);
    }
    return res.json();
  }

  function send() {
    const text = (queryInput && queryInput.value || "").trim();
    if (!text) return;

    if (sendBtn) sendBtn.disabled = true;
    queryInput.value = "";

    addMessage({ role: "user", text: text });
    const loadingDiv = addMessage({ role: "bot", isLoading: true });

    ask(text)
      .then(function (data) {
        if (data.status === "success") {
          replaceLoadingWithMessage(loadingDiv, {
            role: "bot",
            text: data.answer || "(답변 없음)",
            sources: data.sources || [],
          });
        } else if (data.status === "rejected") {
          replaceLoadingWithMessage(loadingDiv, {
            role: "bot",
            isRejected: true,
            text: data.message || data.answer || "서버가 혼잡하여 잠시 후에 이용해 주세요.",
          });
        } else {
          replaceLoadingWithMessage(loadingDiv, {
            role: "bot",
            isError: true,
            text: data.answer || "오류가 발생했습니다.",
          });
        }
      })
      .catch(function (err) {
        replaceLoadingWithMessage(loadingDiv, {
          role: "bot",
          isError: true,
          text: err.message || "연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.",
        });
      })
      .finally(function () {
        if (sendBtn) sendBtn.disabled = false;
        if (queryInput) queryInput.focus();
      });
  }

  if (sendBtn) {
    sendBtn.addEventListener("click", send);
  }
  if (queryInput) {
    queryInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });
  }

  var closeBtn = sourceModal && sourceModal.querySelector(".source-modal-close");
  var backdrop = sourceModal && sourceModal.querySelector(".source-modal-backdrop");
  if (closeBtn) closeBtn.addEventListener("click", closeSourceModal);
  if (backdrop) backdrop.addEventListener("click", closeSourceModal);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && sourceModal && sourceModal.style.display === "flex") {
      closeSourceModal();
    }
  });
})();
