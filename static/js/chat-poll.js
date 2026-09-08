(function () {
  var box = qs("#chat-stream");
  if (!box) return;
  var convId = box.dataset.conv;
  var lastId = parseInt(box.dataset.last || "0", 10);
  var fails = 0;
  var draftKey = "draft-" + convId;
  var input = qs("#chat-input");
  var sending = false;
  var atBottom = true;

  function scrollBottom(force) {
    if (force || atBottom) box.scrollTop = box.scrollHeight;
  }
  box.addEventListener("scroll", function () {
    atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    if (atBottom) qs("#new-msg-fab").style.display = "none";
  });
  qs("#new-msg-fab").addEventListener("click", function () {
    qs("#new-msg-fab").style.display = "none";
    scrollBottom(true);
  });

  if (localStorage.getItem(draftKey)) input.value = localStorage.getItem(draftKey);
  input.addEventListener("input", function () {
    localStorage.setItem(draftKey, input.value);
    qs("#chat-send").disabled = !input.value.trim();
  });
  qs("#chat-send").disabled = !input.value.trim();

  function append(m, pending) {
    if (m.sep) {
      var sep = document.createElement("div");
      sep.className = "time-sep";
      sep.textContent = m.sep;
      box.appendChild(sep);
    }
    var row = document.createElement("div");
    row.className = "bubble-row " + (m.mine ? "mine" : "theirs");
    row.dataset.id = m.id || "";
    var av = "";
    if (m.show_meta !== false) {
      var who = m.mine ? box.dataset.meAv : box.dataset.peerAv;
      var ch = m.mine ? box.dataset.meCh : box.dataset.peerCh;
      av = '<div class="avatar sm av-' + who + '">' + ch + "</div>";
    }
    row.innerHTML = av + '<div class="bubble ' + (pending ? "pending" : "") + '"></div>' + (m.fail ? '<span class="fail-mark" title="重发">!</span>' : "");
    row.querySelector(".bubble").textContent = m.content;
    box.appendChild(row);
    if (m.fail) {
      row.querySelector(".fail-mark").addEventListener("click", function () {
        if (confirm("重发这条消息？取消则删除。")) resend(m.content, row);
        else row.remove();
      });
    }
    if (m.id) lastId = Math.max(lastId, m.id);
    if (!atBottom && !m.mine) {
      qs("#new-msg-fab").style.display = "block";
      qs("#new-msg-fab").textContent = "新消息 ↓";
    } else {
      scrollBottom(!!m.mine || pending);
    }
  }

  function send(text) {
    if (!text.trim() || sending) return;
    if (text.length > 500) text = text.slice(0, 500);
    sending = true;
    qs("#chat-send").disabled = true;
    var temp = { mine: true, content: text, show_meta: true };
    append(temp, true);
    var row = box.lastElementChild;
    api("/api/chat/" + convId + "/send", { method: "POST", body: JSON.stringify({ content: text }) }).then(function (data) {
      sending = false;
      if (!data.ok) {
        row.querySelector(".bubble").classList.remove("pending");
        failRow(row, text);
        return;
      }
      row.remove();
      append(data.message);
      localStorage.removeItem(draftKey);
      input.value = "";
      qs("#chat-send").disabled = true;
    }).catch(function () {
      sending = false;
      failRow(row, text);
    });
  }

  function failRow(row, text) {
    row.querySelector(".bubble").classList.remove("pending");
    var mark = document.createElement("span");
    mark.className = "fail-mark";
    mark.textContent = "!";
    mark.addEventListener("click", function () {
      if (confirm("重发这条消息？取消则删除。")) { row.remove(); send(text); }
      else row.remove();
    });
    row.appendChild(mark);
  }

  function resend(text, row) { row.remove(); send(text); }

  qs("#chat-send").addEventListener("click", function () { send(input.value); });
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey && window.innerWidth >= 768) {
      e.preventDefault();
      send(input.value);
    }
  });
  qsa("[data-quick]").forEach(function (b) {
    b.addEventListener("click", function () { input.value = b.getAttribute("data-quick"); qs("#chat-send").disabled = false; input.focus(); });
  });

  function poll() {
    api("/api/chat/" + convId + "/poll?after=" + lastId).then(function (data) {
      fails = 0;
      qs("#chat-warn").style.display = "none";
      (data.messages || []).forEach(function (m) {
        if (m.mine) return;
        if (qs('[data-id="' + m.id + '"]')) return;
        append(m);
      });
      if (data.messages && data.messages.length) {
        lastId = Math.max.apply(null, [lastId].concat(data.messages.map(function (m) { return m.id; })));
      }
    }).catch(function () {
      fails += 1;
      if (fails > 3) qs("#chat-warn").style.display = "block";
    });
  }
  setInterval(poll, 3000);
  scrollBottom(true);

  var addBtn = qs("#add-friend-btn");
  if (addBtn) {
    addBtn.addEventListener("click", function () {
      addBtn.disabled = true;
      api("/api/chat/" + box.dataset.peer + "/add-friend", { method: "POST" }).then(function (data) {
        if (data.friends) { qs("#friend-bar").style.display = "none"; showToast("已添加为好友", "ok"); }
        else { addBtn.textContent = "请求已发送，等待对方同意"; }
      });
    });
  }
})();
