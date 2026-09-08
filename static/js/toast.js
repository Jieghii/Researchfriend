function showToast(msg, kind) {
  var el = document.getElementById("toast");
  if (!el) return;
  el.className = "toast show " + (kind || "neutral");
  el.textContent = msg;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(function () {
    el.classList.remove("show");
    el.classList.add("hide");
  }, 2500);
}
window.showToast = showToast;
