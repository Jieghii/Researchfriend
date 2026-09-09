/* 玻璃球点评：打分、匿名评价、点赞 / 点踩 */
(function () {
  // 星级选择
  qsa(".star-picker").forEach(function (picker) {
    var dim = picker.getAttribute("data-dim");
    var saved = qsa(".star-btn.on", picker).length;
    picker.setAttribute("data-value", saved || 0);
    qsa(".star-btn", picker).forEach(function (btn) {
      btn.addEventListener("click", function () {
        var v = parseInt(btn.getAttribute("data-star"), 10);
        picker.setAttribute("data-value", v);
        qsa(".star-btn", picker).forEach(function (b) {
          var bv = parseInt(b.getAttribute("data-star"), 10);
          b.classList.toggle("on", bv <= v);
        });
      });
    });
  });

  var rateBtn = qs("[data-submit-rate]");
  if (rateBtn) {
    rateBtn.addEventListener("click", function () {
      var teamId = rateBtn.getAttribute("data-team");
      var payload = {};
      var ok = true;
      qsa(".star-picker").forEach(function (p) {
        var v = parseInt(p.getAttribute("data-value") || "0", 10);
        if (!v) ok = false;
        payload[p.getAttribute("data-dim")] = v;
      });
      if (!ok) return showToast("三个维度都要打分哦");
      api("/api/glass/team/" + teamId + "/rate", {
        method: "POST",
        body: JSON.stringify(payload),
      }).then(function (r) {
        if (r.ok) {
          showToast("打分已提交", "success");
          setTimeout(function () { location.reload(); }, 800);
        } else {
          showToast(r.error || "提交失败", "error");
        }
      });
    });
  }

  // 卖家点击评价按钮
  qsa("[data-seller-deny]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      showToast("仅买方用户可以评价");
    });
  });

  // 评价弹窗
  var openBtn = qs("[data-open-review]");
  if (openBtn) openBtn.addEventListener("click", function () { openModal("review-modal"); });
  qsa("[data-close-review]").forEach(function (b) {
    b.addEventListener("click", function () { closeModal("review-modal"); });
  });

  var submitBtn = qs("[data-submit-review]");
  if (submitBtn) {
    submitBtn.addEventListener("click", function () {
      var input = qs("#review-input");
      var content = (input.value || "").trim();
      if (!content) return showToast("先写点什么再发布");
      api("/api/glass/review", {
        method: "POST",
        body: JSON.stringify({
          target_type: submitBtn.getAttribute("data-target-type"),
          target_id: parseInt(submitBtn.getAttribute("data-target-id"), 10),
          content: content,
        }),
      }).then(function (r) {
        if (r.ok) {
          closeModal("review-modal");
          showToast("评价已发布", "success");
          setTimeout(function () { location.reload(); }, 700);
        } else {
          showToast(r.error || "发布失败", "error");
        }
      });
    });
  }

  // 点赞 / 点踩
  qsa(".review-card").forEach(function (card) {
    var rid = card.getAttribute("data-review");
    qsa("[data-vote]", card).forEach(function (btn) {
      btn.addEventListener("click", function () {
        var value = parseInt(btn.getAttribute("data-vote"), 10);
        api("/api/glass/review/" + rid + "/vote", {
          method: "POST",
          body: JSON.stringify({ value: value }),
        }).then(function (r) {
          if (!r.ok) return showToast(r.error || "操作失败", "error");
          qsa("[data-vote]", card).forEach(function (b) {
            b.classList.toggle("on", parseInt(b.getAttribute("data-vote"), 10) === r.my_vote && r.my_vote !== 0);
          });
          if (r.ups !== undefined) {
            var u = qs("[data-ups]", card);
            var d = qs("[data-downs]", card);
            if (u) u.textContent = r.ups;
            if (d) d.textContent = r.downs;
          } else {
            var su = qs("[data-ups]", card);
            var sd = qs("[data-downs]", card);
            if (su) su.textContent = Math.max(0, parseInt(su.textContent, 10) + (r.my_vote === 0 ? -1 : 1));
            if (sd) sd.textContent = Math.max(0, parseInt(sd.textContent, 10) + (r.my_vote === 0 ? -1 : 0));
            if (r.my_vote === 0) location.reload();
          }
        });
      });
    });
  });
})();
