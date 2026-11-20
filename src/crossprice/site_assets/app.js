// Dashboard interactions: search, brand filter, sort and "show more" for the
// comparison table, and the "your store" picker of the demo. No dependencies.
(function () {
  "use strict";
  var el = document.getElementById("data");
  if (!el) return;
  var data = JSON.parse(el.textContent);
  var rows = data.rows, names = data.names;
  var tbody = document.querySelector("#cmp tbody");
  var q = document.getElementById("q"), brand = document.getElementById("brand");
  var sort = document.getElementById("sort"), count = document.getElementById("count");
  var more = document.getElementById("more");
  var shown = 40, STEP = 40;

  function money(v) {
    return v == null ? "" : "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function pct(v) { return v == null ? "–" : v.toFixed(1) + "%"; }
  function text(tag, cls, value) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (value != null) n.textContent = value;
    return n;
  }
  function filtered() {
    var term = (q.value || "").trim().toLowerCase(), b = brand.value;
    var out = rows.filter(function (r) {
      if (b && r.b !== b) return false;
      return !term || (r.b + " " + r.n).toLowerCase().indexOf(term) !== -1;
    });
    var key = sort.value;
    out.sort(function (x, y) {
      if (key === "name") return (x.b + x.n).localeCompare(y.b + y.n);
      if (key === "price") return (x.lo || 0) - (y.lo || 0);
      return (y.sp == null ? -1 : y.sp) - (x.sp == null ? -1 : x.sp);
    });
    return out;
  }
  function render() {
    var list = filtered();
    count.textContent = list.length + (list.length === 1 ? " product" : " products");
    tbody.textContent = "";
    list.slice(0, shown).forEach(function (r) {
      var tr = document.createElement("tr");
      var td = text("td"); td.setAttribute("data-label", "");
      var prod = text("div", "prod"); prod.appendChild(text("small", null, r.b));
      prod.appendChild(document.createTextNode(r.n)); td.appendChild(prod); tr.appendChild(td);
      var lo = text("td", "num", money(r.lo)); lo.setAttribute("data-label", "Lowest"); tr.appendChild(lo);
      var sp = text("td", "num", pct(r.sp)); sp.setAttribute("data-label", "Gap"); tr.appendChild(sp);
      var cell = text("td"), chips = text("div", "chips");
      r.o.forEach(function (o) {
        var a = text("a", "chip" + (!o.s ? " out" : (r.lr.indexOf(o.r) !== -1 ? " low" : "")));
        a.href = o.u; a.rel = "nofollow noopener";
        a.appendChild(document.createTextNode((names[o.r] || o.r) + " "));
        a.appendChild(text("b", null, money(o.p)));
        chips.appendChild(a);
      });
      cell.appendChild(chips); tr.appendChild(cell);
      tbody.appendChild(tr);
    });
    if (!list.length) {
      var e = text("tr"), c = text("td", "empty", "No product matches this search.");
      c.colSpan = 4; e.appendChild(c); tbody.appendChild(e);
    }
    if (more) more.hidden = list.length <= shown;
  }
  [q, brand, sort].forEach(function (n) {
    n.addEventListener("input", function () { shown = STEP; render(); });
  });
  if (more) more.addEventListener("click", function () { shown += STEP; render(); });

  var you = document.getElementById("you");
  if (you) {
    you.addEventListener("change", function () {
      document.querySelectorAll(".demo").forEach(function (d) {
        d.hidden = d.getAttribute("data-retailer") !== you.value;
      });
    });
  }
})();
