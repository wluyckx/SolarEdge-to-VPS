"""
Built-in operator page for the battery control API.

A single self-contained HTML page served at ``/`` — no external assets, no
build step, works on LAN/Tailscale from desktop or phone. The shell itself
is public (contains no data or secrets); every data call from the page goes
through the bearer-token API. The token is pasted once and kept in the
browser's localStorage only.

Design: operator instrument panel. The hero is the control state — who is
in charge (inverter logic vs forced command) and the deadman countdown.
Color is semantic: green = charge (energy into battery), orange = discharge,
amber = dry-run, red = live writes. The SOC gauge draws the 12% floor and
95% ceiling guardrails as tick marks. All numerals are tabular monospace.

CHANGELOG:
- 2026-07-18: Initial creation -- operator page for Phase 2 supervised tests

TODO:
- None
"""

from __future__ import annotations

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Battery control — Sungrow SH4.0RS</title>
<style>
:root{
  --bg:#14171a; --panel:#1d2126; --line:#2a3037; --ink:#e8eaed;
  --muted:#8b949e; --charge:#4cc38a; --discharge:#f0883e;
  --warn:#e5b567; --live:#e5534b;
  --mono:ui-monospace,"SF Mono","JetBrains Mono","Cascadia Mono",Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans",sans-serif;
}
*{box-sizing:border-box;margin:0}
html{color-scheme:dark}
body{background:var(--bg);color:var(--ink);font:15px/1.5 var(--sans);
  display:flex;justify-content:center;min-height:100vh;padding:20px 14px 48px}
main{width:100%;max-width:560px}
a{color:inherit}
h1{font-size:15px;font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.sub{color:var(--muted);font-size:12.5px;margin-top:2px}
header{display:flex;justify-content:space-between;align-items:flex-start;
  gap:12px;padding-bottom:14px}
.badge{font:600 11px/1 var(--mono);letter-spacing:.08em;padding:6px 9px;
  border-radius:4px;white-space:nowrap;margin-top:2px}
.badge.dry{color:#14171a;background:var(--warn)}
.badge.live{color:#fff;background:var(--live);animation:pulse 1.6s ease-in-out infinite}
@keyframes pulse{50%{opacity:.55}}
@media (prefers-reduced-motion:reduce){.badge.live{animation:none}}
section{background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:16px;margin-bottom:12px}
.eyebrow{font:600 10.5px/1 var(--mono);letter-spacing:.14em;color:var(--muted);
  text-transform:uppercase;margin-bottom:12px}
/* state */
.who{font-size:16px;font-weight:600}
.who .quiet{color:var(--muted);font-weight:400}
.cmd{border:1px solid var(--line);border-radius:6px;padding:12px;margin-top:10px}
.cmd .row{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.chip{font:600 12px/1 var(--mono);letter-spacing:.06em;padding:4px 8px;
  border-radius:4px;text-transform:uppercase}
.chip.charge{color:#14171a;background:var(--charge)}
.chip.discharge{color:#14171a;background:var(--discharge)}
.chip.hold{color:var(--ink);background:#39414b}
.count{font:600 34px/1.1 var(--mono);font-variant-numeric:tabular-nums;margin-top:10px}
.count small{font-size:12px;font-weight:400;color:var(--muted);display:block;
  letter-spacing:.08em;text-transform:uppercase;margin-bottom:4px}
.deplete{height:4px;background:var(--line);border-radius:2px;margin-top:10px;overflow:hidden}
.deplete i{display:block;height:100%;background:var(--warn);border-radius:2px;
  transition:width .5s linear}
.meta{color:var(--muted);font-size:12.5px;margin-top:8px}
/* gauge */
.socline{display:flex;justify-content:space-between;align-items:baseline}
.socnum{font:600 26px/1 var(--mono);font-variant-numeric:tabular-nums}
.socnum em{font-style:normal;font-size:13px;color:var(--muted)}
.gauge{position:relative;display:flex;gap:3px;margin-top:12px;padding-bottom:16px}
.seg{flex:1;height:18px;border-radius:2px;background:var(--line)}
.seg.on{background:var(--charge)}
.seg.low{background:var(--discharge)}
.tick{position:absolute;top:-4px;bottom:12px;width:2px;background:var(--ink);opacity:.85}
.tick span{position:absolute;top:100%;left:50%;transform:translateX(-50%);
  font:600 9.5px/1.6 var(--mono);color:var(--muted);letter-spacing:.05em;white-space:nowrap}
/* command form */
.modes{display:flex;gap:8px;margin-bottom:12px}
.modes button{flex:1;background:none;border:1px solid var(--line);color:var(--muted);
  border-radius:6px;padding:9px 4px;font:600 12.5px var(--sans);cursor:pointer}
.modes button.sel{color:var(--ink);border-color:var(--ink)}
.modes button.sel.m-charge{color:var(--charge);border-color:var(--charge)}
.modes button.sel.m-discharge{color:var(--discharge);border-color:var(--discharge)}
.fields{display:flex;gap:8px;margin-bottom:12px}
.fields label{flex:1;font-size:11.5px;color:var(--muted)}
.fields input{width:100%;margin-top:4px;background:var(--bg);color:var(--ink);
  border:1px solid var(--line);border-radius:6px;padding:8px 10px;
  font:14px var(--mono)}
.actions{display:flex;gap:8px}
button.primary{flex:2;background:var(--ink);color:var(--bg);border:0;border-radius:6px;
  padding:10px;font:600 13.5px var(--sans);cursor:pointer}
button.ghost{flex:1;background:none;color:var(--ink);border:1px solid var(--line);
  border-radius:6px;padding:10px;font:600 13.5px var(--sans);cursor:pointer}
button:focus-visible,input:focus-visible{outline:2px solid var(--warn);outline-offset:2px}
button:disabled{opacity:.45;cursor:default}
#msg{margin-top:10px;font-size:13px;min-height:1.2em}
#msg.err{color:var(--live)} #msg.ok{color:var(--charge)}
/* audit */
.audit{font:12px/1.7 var(--mono);color:var(--muted);overflow-x:auto;white-space:nowrap}
.audit b{color:var(--ink);font-weight:600}
.audit .e-revert b{color:var(--warn)}
.audit .e-write b{color:var(--live)}
.audit .e-command_rejected b{color:var(--discharge)}
/* token gate */
#gate section{margin-top:10vh}
#gate p{color:var(--muted);font-size:13px;margin:8px 0 14px}
.hidden{display:none}
footer{color:var(--muted);font-size:11.5px;text-align:center;margin-top:6px}
</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Battery control</h1>
      <div class="sub">Sungrow SH4.0RS · SBR096 · WiNet-S Modbus</div>
    </div>
    <span id="badge" class="badge hidden"></span>
  </header>

  <div id="gate" class="hidden">
    <section>
      <div class="eyebrow">Access</div>
      <p>Paste the control API token. It is stored only in this browser.</p>
      <div class="fields"><label>API token
        <input id="tok" type="password" autocomplete="off"></label></div>
      <div class="actions"><button class="primary" id="tokgo">Connect</button></div>
      <div id="gatemsg" class="err" style="color:var(--live);font-size:13px;margin-top:8px"></div>
    </section>
  </div>

  <div id="app" class="hidden">
    <section>
      <div class="eyebrow">State</div>
      <div class="who" id="who"></div>
      <div id="active" class="hidden">
        <div class="cmd">
          <div class="row"><span id="acmode" class="chip"></span>
            <span style="font:600 16px var(--mono)" id="acpower"></span></div>
          <div class="count"><small>Deadman reverts in</small><span id="countdown">–</span></div>
          <div class="deplete"><i id="bar" style="width:100%"></i></div>
          <div class="meta" id="acmeta"></div>
        </div>
      </div>
    </section>

    <section>
      <div class="eyebrow">Battery</div>
      <div class="socline"><span class="socnum" id="soc">–</span>
        <span class="sub" id="limits"></span></div>
      <div class="gauge" id="gauge"></div>
    </section>

    <section>
      <div class="eyebrow">Command</div>
      <div class="modes" id="modes">
        <button data-m="hold">Hold</button>
        <button data-m="charge" class="m-charge">Charge</button>
        <button data-m="discharge" class="m-discharge">Discharge</button>
      </div>
      <div class="fields">
        <label>Power (W)<input id="power" type="number" value="2000" step="100" min="100"></label>
        <label>Duration (min)<input id="ttl" type="number" value="15" min="1" max="360"></label>
      </div>
      <div class="actions">
        <button class="primary" id="send">Send command</button>
        <button class="ghost" id="auto">Return to auto</button>
      </div>
      <div id="msg" aria-live="polite"></div>
    </section>

    <section>
      <div class="eyebrow">Audit — last 15 events</div>
      <div class="audit" id="audit">–</div>
    </section>
    <footer id="foot"></footer>
  </div>
</main>
<script>
"use strict";
var $=function(id){return document.getElementById(id)};
var token=localStorage.getItem("sgc_token")||"";
var st=null, mode="hold";

function gate(m){$("gate").classList.remove("hidden");$("app").classList.add("hidden");
  $("badge").classList.add("hidden");if(m)$("gatemsg").textContent=m;}
function app(){$("gate").classList.add("hidden");$("app").classList.remove("hidden");}

function api(path,opts){opts=opts||{};opts.headers=Object.assign(
  {"Authorization":"Bearer "+token,"Content-Type":"application/json"},opts.headers||{});
  return fetch(path,opts).then(function(r){
    if(r.status===401){localStorage.removeItem("sgc_token");gate("Token rejected.");
      throw new Error("unauthorized");}
    return r.json().then(function(d){
      if(!r.ok)throw new Error(d.detail||("HTTP "+r.status));return d;});});}

function fmtClock(ms){if(ms<0)ms=0;var s=Math.floor(ms/1000);
  var h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;
  var p=function(n){return String(n).padStart(2,"0")};
  return (h?h+":"+p(m):m)+":"+p(x);}

function renderStatus(d){st=d;
  var b=$("badge");b.classList.remove("hidden","dry","live");
  b.classList.add(d.dry_run?"dry":"live");
  b.textContent=d.dry_run?"DRY RUN":"LIVE";
  var lim=d.limits;
  $("limits").textContent="floor "+lim.min_soc_pct+"% · ceiling "+lim.max_soc_pct+"%";
  var soc=d.last_soc_pct;
  $("soc").innerHTML=(soc==null?"–":soc.toFixed(1))+"<em> % SOC</em>";
  var g=$("gauge");g.innerHTML="";
  for(var i=0;i<20;i++){var seg=document.createElement("i");seg.className="seg";
    if(soc!=null&&soc>=(i+1)*5)seg.className+=(soc<=lim.min_soc_pct+3?" on low":" on");
    g.appendChild(seg);}
  [[lim.min_soc_pct,"floor"],[lim.max_soc_pct,"ceil"]].forEach(function(t){
    var el=document.createElement("div");el.className="tick";el.style.left=t[0]+"%";
    el.innerHTML="<span>"+t[0]+"</span>";g.appendChild(el);});
  if(d.active){
    $("active").classList.remove("hidden");
    $("who").innerHTML="Forced command active";
    $("acmode").textContent=d.active.mode;
    $("acmode").className="chip "+d.active.mode;
    $("acpower").textContent=d.active.mode==="hold"?"0 W":d.active.power_w+" W";
    $("acmeta").textContent="issued by "+d.active.issuer+" · expires "+
      new Date(d.active.expires_at).toLocaleTimeString();
  }else{
    $("active").classList.add("hidden");
    $("who").innerHTML="Self-consumption <span class=quiet>— inverter logic in control</span>";
  }
  $("foot").textContent=(d.dry_run?
    "Dry run: commands are recorded and expire normally, but are never written to the inverter.":
    "Live: commands write to the inverter. The deadman reverts to self-consumption on expiry.");
}

function tick(){if(!st||!st.active){return;}
  var end=Date.parse(st.active.expires_at),start=Date.parse(st.active.issued_at);
  var now=Date.now(),left=end-now;
  $("countdown").textContent=left<=0?"expiring…":fmtClock(left);
  var pct=Math.max(0,Math.min(100,(end-now)/(end-start)*100));
  $("bar").style.width=pct+"%";}

function renderAudit(d){var rows=d.events.slice().reverse().map(function(e){
    var t=new Date(e.ts).toLocaleTimeString();
    var extra=[];
    if(e.mode)extra.push(e.mode+(e.power_w?" "+e.power_w+"W":""));
    if(e.reason)extra.push(e.reason);
    if(e.address!=null)extra.push("reg "+e.address+"="+e.value);
    if(e.issuer)extra.push("by "+e.issuer);
    if(e.note)extra.push(e.note);
    return "<div class='e-"+e.event+"'>"+t+"  <b>"+e.event+"</b>  "+
      extra.join(" · ")+"</div>";});
  $("audit").innerHTML=rows.join("")||"no events yet";}

function refresh(){api("/control/status").then(renderStatus).catch(function(){});
  api("/control/audit?limit=15").then(renderAudit).catch(function(){});}

function msg(text,cls){var m=$("msg");m.textContent=text;m.className=cls||"";}

function selectMode(m){mode=m;
  Array.prototype.forEach.call($("modes").children,function(b){
    b.classList.toggle("sel",b.dataset.m===m);});
  $("power").disabled=(m==="hold");}

$("modes").addEventListener("click",function(ev){
  var b=ev.target.closest("button");if(b)selectMode(b.dataset.m);});

$("send").addEventListener("click",function(){
  var body={mode:mode,power_w:parseInt($("power").value||"0",10),
    ttl_s:parseInt($("ttl").value||"0",10)*60,issuer:"web-ui"};
  if(st&&!st.dry_run&&!confirm("LIVE MODE — this will write to the inverter. Proceed?"))return;
  msg("Sending…");
  api("/control/force",{method:"POST",body:JSON.stringify(body)})
    .then(function(r){msg((r.dry_run?"Recorded (dry run): ":"Active: ")+r.mode+
      (r.mode==="hold"?"":" "+r.power_w+" W")+" until "+
      new Date(r.expires_at).toLocaleTimeString(),"ok");refresh();})
    .catch(function(e){if(e.message!=="unauthorized")msg(e.message,"err");});});

$("auto").addEventListener("click",function(){
  if(st&&!st.dry_run&&!confirm("Return the inverter to self-consumption?"))return;
  api("/control/auto",{method:"POST",body:JSON.stringify({issuer:"web-ui"})})
    .then(function(){msg("Returned to self-consumption.","ok");refresh();})
    .catch(function(e){if(e.message!=="unauthorized")msg(e.message,"err");});});

$("tokgo").addEventListener("click",function(){
  token=$("tok").value.trim();
  if(!token)return;
  api("/control/status").then(function(d){
    localStorage.setItem("sgc_token",token);app();renderStatus(d);refresh();})
    .catch(function(){});});
$("tok").addEventListener("keydown",function(e){if(e.key==="Enter")$("tokgo").click();});

selectMode("hold");
if(token){app();refresh();}else{gate("");}
setInterval(function(){if(token&&!$("app").classList.contains("hidden"))refresh();},5000);
setInterval(tick,500);
</script>
</body>
</html>
"""
