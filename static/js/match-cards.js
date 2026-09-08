(function () {
  var stage = qs("#match-stage");
  if (!stage) return;
  var cards = [];
  var offset = 0;
  var loading = false;
  var empty = false;
  var current = null;
  var exclude = [];
  var greetTarget = null;

  function renderCard(c) {
    var common = (c.common || []).map(function (t) { return '<span class="pill common">' + t.name + "</span>"; }).join(" ");
    if (c.common_extra) common += ' <span class="lo">+' + c.common_extra + "</span>";
    var other = (c.other || []).map(function (t) { return '<span class="pill">' + t.name + "</span>"; }).join(" ");
    var pctHtml = c.has_common && c.pct != null
      ? '<div class="pct-badge numeric-l">' + c.pct + "<small>%</small><div class=\"caption\">重合度</div></div>"
      : '<div class="pct-badge caption">暂无共同兴趣</div>';
    var html = '<div class="card match-card in" data-id="' + c.id + '">' +
      pctHtml +
      '<div class="avatar lg av-' + c.avatar + '">' + c.nickname.slice(0, 1) + "</div>" +
      '<div class="h1 mt-16">' + c.nickname + "</div>" +
      '<div class="caption mt-8">' + c.role + " · " + c.years + "</div>" +
      '<div class="caption mt-8"><span class="dot ' + (c.online ? "on" : "") + '"></span> ' + (c.online ? "在线" : c.active_text + (c.active_text.indexOf("小时") >= 0 ? "活跃" : "")) + "</div>" +
      '<div class="mt-16 caption" style="align-self:stretch;text-align:left">共同兴趣</div>' +
      '<div class="flex wrap gap-8 mt-8" style="align-self:stretch">' + (common || '<span class="lo">暂无</span>') + "</div>" +
      '<div class="mt-16 caption" style="align-self:stretch;text-align:left">其他兴趣</div>' +
      '<div class="flex wrap gap-8 mt-8" style="align-self:stretch">' + (other || "") + "</div></div>";
    stage.innerHTML = html;
    current = c;
    qs(".match-card").addEventListener("click", function (e) {
      if (e.target.closest(".round-btn")) return;
      location.href = "/users/" + c.id;
    });
    bindSwipe(qs(".match-card"));
  }

  function showEmpty() {
    empty = true;
    stage.innerHTML = '<div class="empty"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8 12h8"/></svg>' +
      '<div class="display">今天的推荐都刷完啦</div>' +
      '<p class="caption mt-8">去「共同话题」里找人聊，或者改改你的兴趣标签</p>' +
      '<div class="flex gap-12 center" style="justify-content:center;margin-top:16px">' +
      '<a class="btn btn-primary" href="/topics">去话题广场</a>' +
      '<a class="btn btn-ghost" href="/me">改兴趣标签</a></div></div>';
  }

  function load() {
    if (loading || empty) return;
    loading = true;
    qs("#match-skel").style.display = "block";
    api("/api/match/batch?offset=" + offset + (exclude.length ? "&exclude=" + exclude.join(",") : "")).then(function (data) {
      loading = false;
      qs("#match-skel").style.display = "none";
      if (!data.cards || !data.cards.length) { showEmpty(); return; }
      if (data.zero_overlap && data.cards && data.cards[0] && data.cards[0].has_common) {
        var hint = qs("#skip-hint");
        if (hint && data.zero_overlap > 0) {
          hint.style.display = "none";
        }
      }
      cards = cards.concat(data.cards);
      offset = data.offset + data.cards.length;
      if (!current) next(false);
    }).catch(function () {
      loading = false;
      qs("#match-skel").style.display = "none";
      qs("#match-err").style.display = "flex";
    });
  }

  function next(fly) {
    current = null;
    if (!cards.length) { load(); return; }
    renderCard(cards.shift());
    if (cards.length < 3) load();
  }

  function fly(dir, done) {
    var el = qs(".match-card");
    if (!el) return;
    el.classList.remove("in");
    el.classList.add(dir === "right" ? "fly-right" : "fly-left");
    setTimeout(done, 420);
  }

  function doSkip() {
    if (!current) return;
    var id = current.id;
    exclude.push(id);
    fly("left", function () {
      api("/api/match/skip", { method: "POST", body: JSON.stringify({ user_id: id }) });
      next();
    });
  }

  function doLike() {
    if (!current) return;
    greetTarget = current;
    var first = (current.common[0] && current.common[0].name) || "白酒";
    qs("#greet-title").textContent = "给「" + current.nickname + "」打个招呼";
    qs("#greet-text").value = "我也在看" + first + "，最近怎么看？";
    updateCount();
    qs("#greet-err").textContent = "";
    openModal("greet-modal");
  }

  function updateCount() {
    var t = qs("#greet-text").value || "";
    if (t.length > 100) { qs("#greet-text").value = t.slice(0, 100); t = t.slice(0, 100); }
    qs("#greet-count").textContent = t.length + "/100";
  }

  qs("#greet-text") && qs("#greet-text").addEventListener("input", updateCount);
  qs("#greet-send") && qs("#greet-send").addEventListener("click", function () {
    if (!greetTarget) return;
    var btn = qs("#greet-send");
    btn.classList.add("loading");
    btn.disabled = true;
    api("/api/match/greet", { method: "POST", body: JSON.stringify({ user_id: greetTarget.id, greeting: qs("#greet-text").value }) }).then(function (data) {
      btn.classList.remove("loading");
      btn.disabled = false;
      if (!data.ok) { qs("#greet-err").textContent = data.error || "没发出去，再试一次？"; return; }
      closeModal("greet-modal");
      showToast("已发送，等对方回应", "ok");
      var id = greetTarget.id;
      exclude.push(id);
      if (qs(".match-card")) fly("right", function () { next(); });
      else location.reload();
    }).catch(function () {
      btn.classList.remove("loading");
      btn.disabled = false;
      qs("#greet-err").textContent = "没发出去，再试一次？";
    });
  });

  qs("#btn-skip") && qs("#btn-skip").addEventListener("click", doSkip);
  qs("#btn-like") && qs("#btn-like").addEventListener("click", doLike);
  qs("#match-retry") && qs("#match-retry").addEventListener("click", function () {
    qs("#match-err").style.display = "none";
    load();
  });

  document.addEventListener("keydown", function (e) {
    if (qs("#greet-modal") && qs("#greet-modal").classList.contains("open")) return;
    if (e.key === "ArrowLeft") doSkip();
    if (e.key === "ArrowRight") doLike();
  });

  function bindSwipe(el) {
    var x0 = 0, dragging = false;
    el.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; dragging = true; }, { passive: true });
    el.addEventListener("touchmove", function (e) {
      if (!dragging) return;
      var dx = e.touches[0].clientX - x0;
      el.style.transform = "translateX(" + dx + "px) rotate(" + dx / 20 + "deg)";
    }, { passive: true });
    el.addEventListener("touchend", function (e) {
      if (!dragging) return;
      dragging = false;
      var dx = (e.changedTouches[0].clientX - x0);
      var w = el.getBoundingClientRect().width;
      if (Math.abs(dx) > w * 0.25) {
        if (dx > 0) doLike(); else doSkip();
      } else {
        el.style.transform = "";
      }
    });
  }

  window.openGreetFor = function (user) {
    greetTarget = user;
    qs("#greet-title").textContent = "给「" + user.nickname + "」打个招呼";
    var first = (user.common && user.common[0] && user.common[0].name) || "白酒";
    qs("#greet-text").value = "我也在看" + first + "，最近怎么看？";
    updateCount();
    openModal("greet-modal");
  };

  if (!stage.dataset.cold) load();
})();
