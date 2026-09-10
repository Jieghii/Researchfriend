(function () {
  var form = qs("#login-form");
  if (form) {
    var nick = qs("#nickname");
    var pw = qs("#password");
    var btn = qs("#login-btn");
    function sync() { btn.disabled = !(nick.value.trim() && pw.value); }
    nick.addEventListener("input", sync);
    pw.addEventListener("input", sync);
    sync();
    form.addEventListener("submit", function () { btn.classList.add("loading"); btn.disabled = true; });
    qs("#pw-toggle") && qs("#pw-toggle").addEventListener("click", function () {
      pw.type = pw.type === "password" ? "text" : "password";
    });
  }

  var onboard = qs("#onboard");
  if (onboard) {
    var step = 1;
    var role = null;
    var years = null;
    var tags = [];
    function show(n) {
      step = n;
      qsa("[data-step]").forEach(function (el) { el.style.display = el.getAttribute("data-step") == n ? "block" : "none"; });
      qs("#prog").style.width = (n / 3 * 100) + "%";
      qs("#prog-label").textContent = n + "/3";
    }
    qsa("[data-role]").forEach(function (el) {
      el.addEventListener("click", function () {
        qsa("[data-role]").forEach(function (x) { x.classList.remove("on"); });
        el.classList.add("on");
        role = el.getAttribute("data-role");
        qs("#next-1").disabled = false;
      });
    });
    qsa("[data-years]").forEach(function (el) {
      el.addEventListener("click", function () {
        qsa("[data-years]").forEach(function (x) { x.classList.remove("on"); });
        el.classList.add("on");
        years = el.getAttribute("data-years");
        qs("#next-2").disabled = false;
      });
    });
    qs("#next-1").addEventListener("click", function () { if (role) show(2); });
    qs("#next-2").addEventListener("click", function () { if (years) show(3); });
    qs("#back-2").addEventListener("click", function () { show(1); });
    qs("#back-3").addEventListener("click", function () { show(2); });

    var search = qs("#tag-search");
    search.addEventListener("input", function () { filterTags(search.value.trim()); });
    search.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        var v = search.value.trim();
        if (!v) return;
        if (!document.querySelector('[data-add-tag][data-name="' + v + '"]') && qs("#custom-hint").style.display !== "none") {
          addTag(v, "industry");
        }
      }
    });
    function filterTags(q) {
      var any = false;
      qsa("[data-add-tag]").forEach(function (el) {
        var ok = !q || el.getAttribute("data-name").indexOf(q) >= 0;
        el.style.display = ok ? "inline-flex" : "none";
        if (ok) any = true;
      });
      var hint = qs("#custom-hint");
      if (q && !any) { hint.style.display = "block"; hint.textContent = "没找到「" + q + "」，回车直接添加为自定义标签"; }
      else hint.style.display = "none";
    }
    function addTag(name, kind) {
      if (tags.some(function (t) { return t.name === name; })) return;
      if (tags.length >= 10) { showToast("最多选 10 个，先取消一个再加吧", "err"); return; }
      tags.push({ name: name, kind: kind || "industry" });
      render();
    }
    function render() {
      qs("#selected").innerHTML = tags.map(function (t, i) {
        return '<span class="pill common x">' + t.name + ' <button type="button" class="icon-btn" data-rm="' + i + '" aria-label="删除">×</button></span>';
      }).join(" ");
      qsa("[data-rm]").forEach(function (b) {
        b.addEventListener("click", function () { tags.splice(+b.getAttribute("data-rm"), 1); render(); });
      });
    }
    qsa("[data-add-tag]").forEach(function (el) {
      el.addEventListener("click", function () {
        var name = el.getAttribute("data-name");
        var exists = tags.findIndex(function (t) { return t.name === name; });
        if (exists >= 0) { tags.splice(exists, 1); render(); return; }
        addTag(name, el.getAttribute("data-kind"));
      });
    });

    function submit(skip) {
      api("/api/onboard", { method: "POST", body: JSON.stringify({ role: role, years: years, tags: skip ? [] : tags, skip_tags: !!skip }) }).then(function (data) {
        if (data.ok) location.href = "/match";
        else showToast(data.error || "请填完资料", "err");
      });
    }
    qs("#start-match").addEventListener("click", function () { submit(false); });
    qs("#skip-tags").addEventListener("click", function () { submit(true); });
  }

  var topicSearch = qs("#topic-search");
  if (topicSearch) {
    var drop = qs("#topic-drop");
    function esc(s) {
      return String(s).replace(/[&<>"']/g, function (c) {
        return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
      });
    }
    function hideDrop() { drop.innerHTML = ""; drop.hidden = true; }
    topicSearch.addEventListener("input", function () {
      var q = topicSearch.value.trim();
      if (!q) { hideDrop(); return; }
      api("/api/topics/search?q=" + encodeURIComponent(q)).then(function (data) {
        drop.hidden = false;
        var items = data.items || [];
        if (!items.length) {
          drop.innerHTML = '<div class="caption" style="padding:12px">没有「' + esc(q) + '」这个话题 <button type="button" class="btn btn-ghost" id="create-topic" data-name="' + esc(q) + '">创建话题</button></div>';
          return;
        }
        drop.innerHTML = items.map(function (t) {
          return '<a class="list-row" href="/topics/' + t.id + '">' + esc(t.name) + "</a>";
        }).join("");
      });
    });
    drop.addEventListener("click", function (e) {
      var btn = e.target.closest("#create-topic");
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      var name = (btn.getAttribute("data-name") || topicSearch.value || "").trim();
      if (!name) return;
      btn.disabled = true;
      api("/api/topics/create", { method: "POST", body: JSON.stringify({ name: name }) }).then(function (d) {
        if (d.ok && d.id) { location.href = "/topics/" + d.id; return; }
        btn.disabled = false;
        showToast(d.error || "创建失败，再试一次？", "err");
      }).catch(function () {
        btn.disabled = false;
        showToast("创建失败，再试一次？", "err");
      });
    });
  }

  var matchBtn = qs("#sys-match");
  if (matchBtn) {
    matchBtn.addEventListener("click", function () {
      openModal("matching-modal");
      var lines = ["正在找和你最聊得来的人…", "按重合度筛选在线研究员…", "正在匹配共同话题里的人…"];
      qs("#match-line").textContent = lines[Math.floor(Math.random() * lines.length)];
      setTimeout(function () {
        api("/api/topics/" + matchBtn.dataset.tag + "/match", { method: "POST" }).then(function (data) {
          closeModal("matching-modal");
          if (!data.ok) { showToast("这个话题暂时没人在线，去别的话题看看？", "neutral"); return; }
          location.href = "/chat/" + data.user_id + "?topic=" + matchBtn.dataset.tag;
        });
      }, 1000);
    });
  }

  qsa("[data-accept]").forEach(function (b) {
    b.addEventListener("click", function () {
      var id = b.getAttribute("data-accept");
      api("/api/requests/" + id + "/accept", { method: "POST" }).then(function (data) {
        if (!data.ok) return;
        showToast("已添加「" + data.nickname + "」为好友", "ok");
        var card = b.closest(".req-card");
        card.innerHTML = '<div class="empty"><p>已添加</p><a class="btn btn-primary" href="/chat/' + data.user_id + '">去打个招呼</a></div>';
        setTimeout(function () { location.reload(); }, 1600);
      });
    });
  });
  qsa("[data-reject]").forEach(function (b) {
    b.addEventListener("click", function () {
      api("/api/requests/" + b.getAttribute("data-reject") + "/reject", { method: "POST" }).then(function () {
        showToast("已拒绝", "neutral");
        b.closest(".req-card").remove();
        if (!qs(".req-card")) location.reload();
      });
    });
  });
  qsa("[data-cancel-req]").forEach(function (b) {
    b.addEventListener("click", function () {
      api("/api/requests/" + b.getAttribute("data-cancel-req") + "/cancel", { method: "POST" }).then(function (data) {
        if (!data.ok) { showToast(data.error || "撤回失败", "error"); return; }
        showToast("已撤回请求", "neutral");
        b.closest(".req-card").remove();
        if (!qs(".req-card")) location.reload();
      });
    });
  });

  qs("#save-profile") && qs("#save-profile").addEventListener("click", function () {
    api("/api/profile", { method: "POST", body: JSON.stringify({ role: qs("#edit-role").value, years: qs("#edit-years").value }) }).then(function () {
      showToast("资料已更新", "ok");
      closeModal("edit-profile");
      location.reload();
    });
  });

  var tagEditor = qs("#save-tags");
  if (tagEditor) {
    var TAG_MAX = 10;
    var cur = JSON.parse(tagEditor.getAttribute("data-tags") || "[]");
    cur = cur.map(function (t) { return typeof t === "string" ? { name: t } : t; });
    function addMeTag(name, kind) {
      name = (name || "").trim();
      if (!name) return;
      if (cur.some(function (t) { return t.name === name; })) return;
      if (cur.length >= TAG_MAX) { showToast("最多选 10 个，先取消一个再加吧", "err"); return; }
      cur.push({ name: name, kind: kind || "industry" });
      renderMeTags();
    }
    function renderMeTags() {
      qs("#me-selected").innerHTML = cur.map(function (t, i) {
        return '<span class="pill common x">' + t.name + ' <button type="button" data-rm="' + i + '" aria-label="删除">×</button></span>';
      }).join(" ");
      var count = qs("#me-tag-count");
      if (count) count.textContent = cur.length + "/" + TAG_MAX;
      qsa("#me-selected [data-rm]").forEach(function (b) {
        b.addEventListener("click", function () { cur.splice(+b.getAttribute("data-rm"), 1); renderMeTags(); });
      });
    }
    if (qs("#me-selected")) renderMeTags();
    qsa("[data-me-add]").forEach(function (el) {
      el.addEventListener("click", function () {
        var name = el.getAttribute("data-me-add");
        var exists = cur.findIndex(function (t) { return t.name === name; });
        if (exists >= 0) { cur.splice(exists, 1); renderMeTags(); return; }
        addMeTag(name, "industry");
      });
    });
    var meSearch = qs("#me-tag-search");
    function filterMeTags(q) {
      var any = false;
      qsa("[data-me-add]").forEach(function (el) {
        var ok = !q || el.getAttribute("data-me-add").indexOf(q) >= 0;
        el.style.display = ok ? "inline-flex" : "none";
        if (ok) any = true;
      });
      var hint = qs("#me-custom-hint");
      if (!hint) return;
      if (q && !any) {
        hint.style.display = "block";
        hint.textContent = "没找到「" + q + "」，回车直接添加为自定义标签";
      } else {
        hint.style.display = "none";
      }
    }
    if (meSearch) {
      meSearch.addEventListener("input", function () { filterMeTags(meSearch.value.trim()); });
      meSearch.addEventListener("keydown", function (e) {
        if (e.key !== "Enter") return;
        e.preventDefault();
        var v = meSearch.value.trim();
        if (!v) return;
        addMeTag(v, "industry");
        meSearch.value = "";
        filterMeTags("");
      });
    }
    tagEditor.addEventListener("click", function () {
      api("/api/tags", { method: "POST", body: JSON.stringify({ tags: cur }) }).then(function (data) {
        if (!data.ok) { showToast(data.error || "失败", "err"); return; }
        showToast("标签已更新，匹配结果会变", "ok");
        closeModal("tags-modal");
        location.reload();
      });
    });
  }

  qs("#logout-btn") && qs("#logout-btn").addEventListener("click", function () {
    if (confirm("确定退出吗？")) {
      var f = document.createElement("form");
      f.method = "post"; f.action = "/logout"; document.body.appendChild(f); f.submit();
    }
  });

  qs("#invite-btn") && qs("#invite-btn").addEventListener("click", function () {
    showToast("演示版暂不支持分享", "neutral");
  });
})();
