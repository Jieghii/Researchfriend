(function () {
  var lastVis = localStorage.getItem("thought-vis") || "public";

  qsa("[data-like]").forEach(bindLike);
  document.addEventListener("click", function (e) {
    var like = e.target.closest("[data-like]");
    if (like && !like._bound) bindLike(like);
  });

  function bindLike(el) {
    el._bound = true;
    el.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      var id = el.getAttribute("data-like");
      api("/api/thoughts/" + id + "/like", { method: "POST" }).then(function (data) {
        if (!data.ok) return;
        el.classList.add("pop");
        el.querySelector("[data-n]").textContent = data.likes;
        el.classList.toggle("on", data.liked);
        setTimeout(function () { el.classList.remove("pop"); }, 240);
      });
    });
  }

  var compose = qs("#compose-open") || qs("[data-open-compose]");
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-open-compose]")) {
      qs("#vis-" + lastVis) && (qs("#vis-" + lastVis).classList.add("on"));
      openModal("compose-modal");
    }
  });

  qsa(".vis-card").forEach(function (c) {
    c.addEventListener("click", function () {
      qsa(".vis-card").forEach(function (x) { x.classList.remove("on"); });
      c.classList.add("on");
      lastVis = c.dataset.vis;
      localStorage.setItem("thought-vis", lastVis);
    });
  });

  var body = qs("#compose-body");
  if (body) {
    body.addEventListener("input", function () {
      qs("#compose-count").textContent = body.value.length + "/500";
      qs("#compose-send").disabled = !body.value.trim();
    });
  }
  var selectedTags = [];
  qs("#pick-topic") && qs("#pick-topic").addEventListener("click", function () {
    openModal("tagpick-modal");
  });
  qsa("[data-pick-tag]").forEach(function (el) {
    el.addEventListener("click", function () {
      var id = el.getAttribute("data-pick-tag");
      var name = el.getAttribute("data-name");
      if (selectedTags.some(function (t) { return t.id == id; })) return;
      selectedTags.push({ id: id, name: name });
      renderSel();
    });
  });
  function renderSel() {
    var box = qs("#compose-tags");
    if (!box) return;
    box.innerHTML = selectedTags.map(function (t) {
      return '<span class="pill common x" data-rm="' + t.id + '">#' + t.name + " ×</span>";
    }).join(" ");
    qsa("[data-rm]", box).forEach(function (p) {
      p.addEventListener("click", function () {
        selectedTags = selectedTags.filter(function (t) { return t.id != p.getAttribute("data-rm"); });
        renderSel();
      });
    });
  }

  qs("#compose-send") && qs("#compose-send").addEventListener("click", function () {
    var btn = qs("#compose-send");
    btn.disabled = true;
    btn.classList.add("loading");
    api("/api/thoughts", {
      method: "POST",
      body: JSON.stringify({
        body: body.value,
        visibility: lastVis,
        tag_ids: selectedTags.map(function (t) { return t.id; })
      })
    }).then(function (data) {
      btn.classList.remove("loading");
      if (!data.ok) {
        btn.disabled = false;
        qs("#compose-err").textContent = data.error || "发布失败，再试一次？";
        return;
      }
      closeModal("compose-modal");
      showToast("已发布", "ok");
      location.reload();
    }).catch(function () {
      btn.disabled = false;
      btn.classList.remove("loading");
      qs("#compose-err").textContent = "发布失败，再试一次？";
    });
  });

  var more = qs("#load-more");
  var page = 1;
  var loadingMore = false;
  if (more) {
    var scroller = document.querySelector(".content") || window;
    scroller.addEventListener("scroll", function () {
      if (loadingMore || more.dataset.done) return;
      var near = scroller === window
        ? window.innerHeight + window.scrollY >= document.body.offsetHeight - 80
        : scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 80;
      if (near) {
        loadingMore = true;
        page += 1;
        var scope = more.dataset.scope || "all";
        var tag = more.dataset.tag || "";
        var sort = more.dataset.sort || "new";
        api("/api/thoughts?page=" + page + "&scope=" + scope + "&sort=" + encodeURIComponent(sort) + (tag ? "&tag=" + tag : "")).then(function (data) {
          loadingMore = false;
          (data.items || []).forEach(function (it) {
            more.parentNode.insertBefore(renderCard(it), more);
          });
          if (!data.has_more) { more.dataset.done = "1"; more.textContent = "没有更多了"; }
        });
      }
    });
  }

  function renderCard(it) {
    var div = document.createElement("article");
    div.className = "card thought-card card-hover";
    div.innerHTML = '<a href="/thoughts/' + it.id + '"><div class="thought-body clamp"></div></a>';
    div.querySelector(".thought-body").textContent = it.body;
    return div;
  }

  var csend = qs("#comment-send");
  if (csend) {
    csend.addEventListener("click", function () {
      var tid = csend.dataset.tid;
      var inp = qs("#comment-input");
      if (!inp.value.trim()) return;
      api("/api/thoughts/" + tid + "/comments", { method: "POST", body: JSON.stringify({ content: inp.value }) }).then(function (data) {
        if (!data.ok) return;
        location.reload();
      });
    });
  }

  qsa("[data-del-thought]").forEach(function (el) {
    el.addEventListener("click", function () {
      if (!confirm("删除这条随想？")) return;
      api("/api/thoughts/" + el.getAttribute("data-del-thought"), { method: "DELETE" }).then(function () { location.href = "/thoughts"; });
    });
  });
  qsa("[data-del-comment]").forEach(function (el) {
    el.addEventListener("click", function () {
      api("/api/comments/" + el.getAttribute("data-del-comment"), { method: "DELETE" }).then(function () { el.closest(".c-item").remove(); });
    });
  });

  var tagSearch = qs("#thought-tag-search");
  var tagDrop = qs("#thought-tag-drop");
  if (tagSearch && tagDrop) {
    function hideTagDrop() { tagDrop.innerHTML = ""; tagDrop.hidden = true; }
    tagSearch.addEventListener("input", function () {
      var q = tagSearch.value.trim();
      if (!q) { hideTagDrop(); return; }
      api("/api/topics/search?q=" + encodeURIComponent(q)).then(function (data) {
        var items = data.items || [];
        tagDrop.hidden = false;
        if (!items.length) {
          tagDrop.innerHTML = '<div class="caption" style="padding:12px">没有「' + q + '」这个话题</div>';
          return;
        }
        var scope = tagSearch.getAttribute("data-scope") || "all";
        var sort = tagSearch.getAttribute("data-sort") || "new";
        tagDrop.innerHTML = items.map(function (t) {
          var href = "/thoughts?scope=" + encodeURIComponent(scope) + "&sort=" + encodeURIComponent(sort) + "&tag=" + t.id;
          return '<a class="list-row" href="' + href + '">#' + t.name + "</a>";
        }).join("");
      });
    });
    document.addEventListener("click", function (e) {
      if (!e.target.closest(".thought-tag-search")) hideTagDrop();
    });
  }
})();
