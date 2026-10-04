/* Bailey's Next Step board. Vacancy data comes from data/*.json (rebuilt every Saturday).
   Bailey's own statuses, notes and added jobs live only in this browser (localStorage). */
(function () {
  "use strict";
  var KEY = "bns.v1";
  var STAGES = { saved: "Saved", preparing: "Preparing", applied: "Applied", interview: "Interview", offer: "Offer", not_for_me: "Not for me", unsuccessful: "Unsuccessful" };
  var STAGE_ORDER = ["offer", "interview", "applied", "preparing", "saved", "unsuccessful", "not_for_me"];
  var INTRO = {
    job: "Jobs to get you out of food service now. <b>Electrical starter roles</b> come first, then trade counter and practical roles, then warehouse, production, retail and admin as stopgaps.",
    apprenticeship: "<b>Electrical apprenticeships</b> come first, then wider engineering and trade. Your Level 3 college qualification counts for a lot, but check each advert's entry requirements.",
    mine: "Everything you've saved, applied for or ruled out. This list stays on this device; use <b>Back up</b> to keep a copy."
  };

  var data = { items: [] }, run = null, site = {};
  var ui = { tab: "job", show: "best", q: "" };
  var store = load();

  // ---------- storage ----------
  function blank() { return { version: 1, statuses: {}, manual: [] }; }
  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      var s = raw ? JSON.parse(raw) : blank();
      if (!s || s.version !== 1 || typeof s.statuses !== "object") return blank();
      s.manual = Array.isArray(s.manual) ? s.manual : [];
      return s;
    } catch (e) { return blank(); }
  }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(store)); } catch (e) { /* private mode */ } }
  function rec(id) { return store.statuses[id] || null; }
  function setRec(v, patch) {
    var r = store.statuses[v.id] || { ready: {} };
    Object.keys(patch).forEach(function (k) { r[k] = patch[k]; });
    r.updated = new Date().toISOString().slice(0, 10);
    r.snap = { title: v.title, employer: v.employer, location: v.location, url: v.url, lane: v.lane };
    store.statuses[v.id] = r;
    save();
  }

  // ---------- helpers ----------
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function today() { var d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); }
  function daysUntil(iso) { return Math.round((new Date(iso + "T12:00:00") - new Date(today() + "T12:00:00")) / 86400000); }
  function niceDate(iso, withDay) {
    if (!iso) return "";
    var d = new Date(iso.slice(0, 10) + "T12:00:00");
    return d.toLocaleDateString("en-GB", withDay ? { weekday: "long", day: "numeric", month: "long" } : { day: "numeric", month: "short" });
  }
  function bandClass(v) { if (v.blocked) return "blocked"; if (v.score >= 75) return "strong"; if (v.score >= 60) return "good"; return ""; }
  function isActive(v) { var r = rec(v.id); return v.live !== "closed" && !v.blocked && !v.folded_into && !(r && (r.stage === "not_for_me" || r.stage === "unsuccessful")); }

  // ---------- rendering ----------
  function render() {
    document.querySelectorAll(".tabs button").forEach(function (b) { b.setAttribute("aria-selected", String(b.dataset.tab === ui.tab)); });
    document.querySelectorAll(".chip").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.show === ui.show)); });
    document.getElementById("controls").hidden = ui.tab === "mine";
    document.getElementById("intro").innerHTML = INTRO[ui.tab];
    ["job", "apprenticeship"].forEach(function (lane) {
      document.getElementById("count-" + lane).textContent = data.items.filter(function (v) { return v.lane === lane && isActive(v); }).length;
    });
    document.getElementById("count-mine").textContent = mine().length;

    var list = document.getElementById("list");
    list.innerHTML = "";
    var rows = ui.tab === "mine" ? mine() : visible();
    if (!rows.length) {
      list.appendChild(el("div", "empty", ui.tab === "mine"
        ? "Nothing here yet. Use Save or Already applied on any job, or add one you found elsewhere."
        : (ui.q ? "No matches for that search." : (ui.show === "best" ? "No active matches right now. Try Everything, or check back after Saturday's update." : "Nothing in this view."))));
      return;
    }
    rows.forEach(function (v) { list.appendChild(card(v)); });
  }

  function visible() {
    var q = ui.q.trim().toLowerCase();
    return data.items.filter(function (v) {
      if (v.lane !== ui.tab) return false;
      if (q && (v.title + " " + v.employer + " " + v.location).toLowerCase().indexOf(q) < 0) return false;
      if (ui.show === "all") return true;
      if (!isActive(v)) return false;
      if (ui.show === "new") return v.is_new;
      if (ui.show === "closing") return v.closes && daysUntil(v.closes) >= 0 && daysUntil(v.closes) <= 14;
      return true;
    });
  }

  function mine() {
    var byId = {};
    data.items.forEach(function (v) { byId[v.id] = v; });
    var out = Object.keys(store.statuses).filter(function (id) { return store.statuses[id].stage; }).map(function (id) {
      if (byId[id]) return byId[id];
      var s = store.statuses[id].snap || {};
      var manual = store.manual.filter(function (m) { return m.id === id; })[0];
      return Object.assign({ id: id, lane: s.lane || "job", title: s.title || "Saved job", employer: s.employer || "", location: s.location || "", url: s.url || "", gone: !manual, manual: !!manual }, manual || {});
    });
    out.sort(function (a, b) { return STAGE_ORDER.indexOf(rec(a.id).stage) - STAGE_ORDER.indexOf(rec(b.id).stage); });
    return out;
  }

  function card(v) {
    var c = document.getElementById("card-tpl").content.firstElementChild.cloneNode(true);
    var r = rec(v.id) || {};
    var scoreBox = c.querySelector(".score");
    if (v.manual || v.gone) {
      scoreBox.querySelector(".score-num").textContent = "–";
      scoreBox.querySelector(".score-band").textContent = v.manual ? "Added by you" : "No longer listed";
    } else {
      scoreBox.classList.add(bandClass(v));
      scoreBox.querySelector(".score-num").textContent = v.blocked ? "✕" : v.score;
      scoreBox.querySelector(".score-band").textContent = v.blocked ? "Not yet eligible" : v.band;
    }
    if (v.live === "closed" || v.blocked || v.gone) c.classList.add("dim");

    var a = c.querySelector(".title-link");
    a.textContent = v.title;
    if (v.url) a.href = v.url; else a.removeAttribute("href");
    var meta = [v.employer, v.location].filter(Boolean);
    if (v.distance_miles != null) var mi = Math.round(v.distance_miles); meta.push(mi < 1 ? "under a mile from home" : "about " + mi + (mi === 1 ? " mile" : " miles") + " from home");
    if (v.other_locations && v.other_locations.length) meta.push("also at " + v.other_locations.length + " other branch" + (v.other_locations.length > 1 ? "es" : ""));
    c.querySelector(".meta").textContent = meta.join(" · ");

    var tags = c.querySelector(".tags");
    function tag(text, cls) { tags.appendChild(el("span", "tag " + (cls || ""), text)); }
    if (r.stage) tag(STAGES[r.stage], "mine");
    if (v.is_new && v.live !== "closed") tag("New", "new");
    if (v.live === "closed") tag("Closed", "closed");
    else if (v.live === "unverified") tag("Not re-checked", "unverified");
    if (v.closes && v.live !== "closed") {
      var d = daysUntil(v.closes);
      tag(d === 0 ? "Closes today" : d === 1 ? "Closes tomorrow" : "Closes " + niceDate(v.closes), d <= 7 ? "soon" : "");
    }
    if (!v.manual && !v.gone) {
      tag(v.pay_text ? (v.pay_text.length > 48 ? v.pay_text.slice(0, 46) + "…" : v.pay_text) : "Pay not stated", v.pay_text ? "pay" : "unknown");
      if (v.hours_text) tag(v.hours_text.length > 40 ? v.hours_text.slice(0, 38) + "…" : v.hours_text);
      if (v.contract && v.contract !== "Permanent") tag(v.contract);
      if (v.training) tag(v.training);
      if (v.category && v.lane === "job") tag(v.category);
    }

    var why = c.querySelector(".why"), gaps = c.querySelector(".gaps");
    (v.why || []).forEach(function (t) { why.appendChild(el("li", "", t)); });
    (v.checks || []).filter(function (ch) { return ch.result === "not_met"; }).forEach(function (ch) { gaps.appendChild(el("li", "stop", ch.note)); });
    (v.gaps || []).filter(function (t) { return !(v.checks || []).some(function (ch) { return ch.result === "not_met" && ch.note === t; }); })
      .slice(0, 3).forEach(function (t) { gaps.appendChild(el("li", "", t)); });

    var more = c.querySelector(".more");
    if (v.manual || v.gone) more.remove(); else buildMore(c.querySelector(".more-body"), v);

    var open = c.querySelector(".open");
    if (v.url) open.href = v.url; else open.remove();
    var stage = c.querySelector(".stage");
    stage.value = r.stage || "";
    var track = c.querySelector(".track");
    var appliedOn = c.querySelector(".applied-on");
    track.hidden = !r.stage;
    appliedOn.hidden = ["applied", "interview", "offer", "unsuccessful"].indexOf(r.stage) < 0;
    stage.addEventListener("change", function () { setRec(v, { stage: stage.value || null }); render(); });
    var appliedBtn = c.querySelector(".applied-btn");
    if (["applied", "interview", "offer"].indexOf(r.stage) >= 0) appliedBtn.remove();
    else appliedBtn.addEventListener("click", function () { setRec(v, { stage: "applied" }); render(); });
    var date = c.querySelector(".applied-date");
    date.value = r.applied_on || "";
    date.addEventListener("change", function () { setRec(v, { applied_on: date.value || null }); });
    var note = c.querySelector(".note");
    note.value = r.note || "";
    note.addEventListener("change", function () { setRec(v, { note: note.value.slice(0, 2000) }); });
    c.querySelectorAll("[data-ready]").forEach(function (box) {
      box.checked = !!(r.ready && r.ready[box.dataset.ready]);
      box.addEventListener("change", function () {
        var ready = Object.assign({}, (rec(v.id) || {}).ready); ready[box.dataset.ready] = box.checked;
        setRec(v, { ready: ready });
      });
    });
    return c;
  }

  function buildMore(body, v) {
    var range = el("p", "muted small");
    range.textContent = v.score_low === v.score_high
      ? "Score " + v.score + " out of 100."
      : "Score " + v.score + " out of 100. Unknowns count as half marks, so it could be anywhere from " + v.score_low + " to " + v.score_high + " once they're checked.";
    if (v.blocked) range.textContent = "Not scored for now: at least one entry requirement isn't met yet (marked ✕ below).";
    body.appendChild(range);
    var t = el("table", "factors");
    (v.factors || []).forEach(function (f) {
      if (!f.note && f.value == null) return;
      var tr = el("tr");
      tr.appendChild(el("td", "pts", f.value == null ? "? / " + f.weight : f.points + " / " + f.weight));
      var td = el("td"); var b = el("b", "", f.label + ": "); td.appendChild(b); td.appendChild(document.createTextNode(f.note || "Not known."));
      tr.appendChild(td); t.appendChild(tr);
    });
    body.appendChild(t);
    if (v.checks && v.checks.length) {
      body.appendChild(el("p", "small", "Entry requirements"));
      var ul = el("ul", "checks small");
      v.checks.forEach(function (ch) {
        var li = el("li"); li.appendChild(el("span", "res " + ch.result, ch.result === "not_met" ? "Not met" : ch.result === "met" ? "Met" : "Check"));
        li.appendChild(document.createTextNode(" " + ch.label + ": " + ch.note)); ul.appendChild(li);
      });
      body.appendChild(ul);
    }
    var src = el("p", "muted small");
    src.textContent = "Found on " + v.source + (v.first_seen ? " on " + niceDate(v.first_seen) : "") + ". " + (v.live_note || "") + " " + (v.apply_route ? v.apply_route + "." : "");
    body.appendChild(src);
    if (v.more_roles && v.more_roles.length) {
      body.appendChild(el("p", "small", "More roles at " + v.employer + ":"));
      var ml = el("ul", "checks small");
      v.more_roles.forEach(function (m) {
        var li = el("li"); var l = el("a", "", m.title); l.href = m.url; l.target = "_blank"; l.rel = "noopener";
        li.appendChild(l); li.appendChild(document.createTextNode(" (" + m.score + ")")); ml.appendChild(li);
      });
      body.appendChild(ml);
    }
    if (v.other_locations && v.other_locations.length) body.appendChild(el("p", "muted small", "Also advertised at: " + v.other_locations.join("; ")));
    (v.other_links || []).forEach(function (u) {
      var p = el("p", "small"); var l = el("a", "", "Also listed here"); l.href = u; l.target = "_blank"; l.rel = "noopener"; p.appendChild(l); body.appendChild(p);
    });
  }

  function statusLine() {
    var s = document.getElementById("status-line");
    if (!run) { s.textContent = "Couldn't load the latest update. Check your connection and refresh."; return; }
    var sum = run.summary || {}, parts = [];
    parts.push("Updated <b>" + niceDate(run.today, true) + "</b>");
    var newCount = (sum.job ? sum.job.new : 0) + (sum.apprenticeship ? sum.apprenticeship.new : 0);
    if (newCount) parts.push("<b>" + newCount + "</b> new");
    var soon = (sum.job ? sum.job.closing_soon : 0) + (sum.apprenticeship ? sum.apprenticeship.closing_soon : 0);
    if (soon) parts.push("<b>" + soon + "</b> closing in the next 7 days");
    var stale = daysUntil(run.today) < -8;
    var html = parts.join(" · ");
    if (stale) html += ' · <span class="warn">This hasn\'t updated for over a week. Let Dad know.</span>';
    if (sum.sources_failed && sum.sources_failed.length) html += ' · <span class="warn">Couldn\'t check: ' + sum.sources_failed.join(", ") + "</span>";
    s.innerHTML = html;
    var ok = (run.sources || []).filter(function (x) { return x.ok; }).map(function (x) { return x.name; });
    document.getElementById("sources-line").textContent = "Searched this week: " + ok.join(", ") + ".";
  }

  // ---------- backup / restore ----------
  function backup() {
    var blob = new Blob([JSON.stringify({ format: "bailey-next-step-backup", saved: new Date().toISOString(), data: store }, null, 1)], { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "next-step-backup-" + today() + ".json";
    document.body.appendChild(a); a.click(); a.remove();
  }
  function restore(file) {
    var reader = new FileReader();
    reader.onload = function () {
      try {
        var doc = JSON.parse(reader.result);
        var d = doc && doc.format === "bailey-next-step-backup" ? doc.data : null;
        if (!d || d.version !== 1 || typeof d.statuses !== "object") throw new Error("bad");
        var n = Object.keys(d.statuses).length;
        if (!window.confirm("Restore " + n + " saved job(s) from " + (doc.saved || "").slice(0, 10) + "? This replaces what's saved on this device now.")) return;
        store = { version: 1, statuses: d.statuses, manual: Array.isArray(d.manual) ? d.manual : [] };
        save(); render();
      } catch (e) { window.alert("That file isn't a Next Step backup, so nothing was changed."); }
    };
    reader.readAsText(file);
  }

  // ---------- wiring ----------
  document.querySelectorAll(".tabs button").forEach(function (b) { b.addEventListener("click", function () { ui.tab = b.dataset.tab; try { localStorage.setItem("bns.tab", ui.tab); } catch (e) {} render(); }); });
  document.querySelectorAll(".chip").forEach(function (b) { b.addEventListener("click", function () { ui.show = b.dataset.show; render(); }); });
  document.getElementById("q").addEventListener("input", function (e) { ui.q = e.target.value; render(); });
  document.getElementById("backup").addEventListener("click", backup);
  document.getElementById("restore").addEventListener("change", function (e) { if (e.target.files[0]) restore(e.target.files[0]); e.target.value = ""; });
  var addPanel = document.getElementById("add-panel");
  document.getElementById("add-open").addEventListener("click", function () { addPanel.hidden = false; addPanel.scrollIntoView({ behavior: "smooth" }); });
  document.getElementById("add-cancel").addEventListener("click", function () { addPanel.hidden = true; });
  document.getElementById("add-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var f = e.target.elements, form = e.target, id = "manual:" + Date.now();
    var m = { id: id, title: f.title.value.trim(), employer: f.employer.value.trim(), url: f.url.value.trim(), lane: f.lane.value, location: "", added: today() };
    store.manual.push(m);
    setRec(m, { stage: f.stage.value });
    form.reset(); addPanel.hidden = true; ui.tab = "mine"; render();
  });

  try { var t = localStorage.getItem("bns.tab"); if (t && INTRO[t]) ui.tab = t; } catch (e) {}

  function getJSON(path) { return fetch(path + "?v=" + Date.now(), { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error(path); return r.json(); }); }
  Promise.all([getJSON("data/vacancies.json"), getJSON("data/run.json"), getJSON("data/site.json").catch(function () { return {}; })])
    .then(function (res) {
      data = res[0]; run = res[1]; site = res[2] || {};
      if (site.docs_folder) { var dl = document.getElementById("docs-link"); dl.href = site.docs_folder; dl.hidden = false; }
      statusLine(); render();
    })
    .catch(function () { statusLine(); render(); });
})();
