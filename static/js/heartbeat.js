(function () {
  function beat() {
    fetch("/api/heartbeat", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).catch(function () {});
  }
  beat();
  setInterval(beat, 60000);
})();
