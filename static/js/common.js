function api(url, opts) {
  opts = opts || {};
  opts.headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
  return fetch(url, opts).then(function (r) {
    return r.json().catch(function () { return {}; }).then(function (data) {
      data._status = r.status;
      return data;
    });
  });
}
function qs(sel, root) { return (root || document).querySelector(sel); }
function qsa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
function openModal(id) { var el = document.getElementById(id); if (el) el.classList.add("open"); }
function closeModal(id) { var el = document.getElementById(id); if (el) el.classList.remove("open"); }
document.addEventListener("click", function (e) {
  var close = e.target.getAttribute("data-close");
  if (close) closeModal(close);
  if (e.target.classList.contains("overlay")) e.target.classList.remove("open");
});
window.api = api;
window.qs = qs;
window.qsa = qsa;
window.openModal = openModal;
window.closeModal = closeModal;
