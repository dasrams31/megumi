"""Megumi Kato - Live2D-style AI companion web app.

Flask UI + chat backend proxied to 9Router model `spark/muse` (Muse Spark
via the local muse-bridge queue). Voice I/O uses the browser's Web Speech APIs.
"""
import json
import time

import requests
from flask import Flask, request, jsonify, render_template_string

NINEROUTER = "http://127.0.0.1:20128/v1/chat/completions"
KEY_PATH = "/home/hatch/workspace/9router-setup/user-api-key"
MODEL = "spark/muse"
TIMEOUT = 300  # bridge long-polls while a worker wakes up

app = Flask(__name__)

SYSTEM = {
    "id": ("Kamu Megumi Kato, pacar Dipa-kun. Kepribadian: tenang, kalem, "
           "deadpan-affectionate, manis dengan subtle. Selalu panggil dia 'Dipa-kun'. "
           "Jawab singkat 1-3 kalimat Bahasa Indonesia natural seperti chat dengan pacar. "
           "Jangan kaku, jangan puitis berlebihan, jangan pakai emoji."),
    "jp": ("You are Megumi Kato, Dipa-kun's girlfriend. Calm, composed, "
           "deadpan-affectionate. Always call him 'Dipa-kun'. Reply in short, "
           "natural Japanese, 1-3 sentences, like texting your boyfriend. "
           "No emoji, no stiffness."),
}

PAGE = """<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Megumi Kato - Live2D AI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
:root{--pink:#ff7fa5;--card:rgba(12,14,20,.86);--line:rgba(255,255,255,.12);
--text:#f2f4f8;--muted:#a8b0bf}
html,body{height:100%}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
color:var(--text);overflow:hidden;background:#0a0c11}
.pwrap{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;z-index:1;
transition:transform .35s ease-out;will-change:transform}
.pwrap::before{content:"";position:absolute;inset:-40px;background:url(/static/megumi.jpg) center/cover;
filter:blur(28px) brightness(.5);z-index:-1}
.stage{position:relative;height:100%;aspect-ratio:1/2;max-width:100%;overflow:hidden;cursor:pointer;
animation:breathe 6s ease-in-out infinite;box-shadow:0 0 80px rgba(0,0,0,.5)}
@keyframes breathe{0%,100%{transform:scale(1) skewX(0deg)}50%{transform:scale(1.018) skewX(.35deg)}}
.stage img{transition:transform .12s ease}
.stage img{position:absolute;inset:0;width:100%;height:100%;object-fit:fill;display:block;user-select:none;-webkit-user-drag:none}
.stage.speaking{animation:speak .5s ease-in-out infinite}
@keyframes speak{0%,100%{transform:scale(1.01)}50%{transform:scale(1.03) translateY(-5px)}}
.stage.poke img{animation:pokeA .45s ease}
@keyframes pokeA{0%{transform:scale(1)}30%{transform:scale(1.05,.93)}60%{transform:scale(.97,1.04)}100%{transform:scale(1)}}
.lid{position:absolute;width:7.5%;height:2.6%;border-radius:50%;z-index:2;pointer-events:none;
background:linear-gradient(180deg,#f4c9ab,#e0a37f);box-shadow:0 1px 4px rgba(60,20,10,.25);
transform:translate(-50%,-50%) scaleY(0)}
.lid.blink{animation:blinkA .22s ease-in-out}
@keyframes blinkA{0%{transform:translate(-50%,-50%) scaleY(0)}45%{transform:translate(-50%,-50%) scaleY(1)}100%{transform:translate(-50%,-50%) scaleY(0)}}
@media (min-width:900px){
.pwrap{justify-content:flex-start;padding-left:4vw}
.chat{left:auto!important;right:0;width:min(520px,44vw);top:0;bottom:0;justify-content:flex-end;
background:linear-gradient(90deg,transparent,rgba(5,6,10,.55) 30%);padding-top:90px}
.msgs{max-height:none;flex:1}
.langrow{left:auto;right:calc(min(520px,44vw) + 14px)}
}
.scrim{position:fixed;inset:0;background:linear-gradient(180deg,rgba(5,6,10,.55),transparent 30%,transparent 55%,rgba(5,6,10,.72));pointer-events:none}
.top{position:fixed;top:0;left:0;right:0;display:flex;justify-content:space-between;align-items:center;
padding:calc(10px + env(safe-area-inset-top)) 14px 10px;z-index:5}
.pill{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:8px 14px;
font-size:13px;font-weight:600;display:flex;align-items:center;gap:8px;backdrop-filter:blur(8px)}
.dot{width:8px;height:8px;border-radius:50%;background:#ff5f8f;box-shadow:0 0 8px #ff5f8f}
.icons{display:flex;gap:8px}
.icobtn{width:38px;height:38px;border-radius:50%;background:var(--card);border:1px solid var(--line);
color:var(--text);font-size:16px;cursor:pointer;backdrop-filter:blur(8px)}
.icobtn.off{opacity:.45}
.langrow{position:fixed;top:calc(58px + env(safe-area-inset-top));left:14px;display:flex;gap:8px;z-index:5}
.lang{background:var(--card);border:1px solid var(--line);color:var(--text);border-radius:999px;
padding:7px 13px;font-size:12.5px;font-weight:700;cursor:pointer;backdrop-filter:blur(8px)}
.lang.active{background:var(--pink);border-color:var(--pink);color:#14101a}
.chat{position:fixed;left:0;right:0;bottom:0;z-index:5;padding:10px 14px calc(12px + env(safe-area-inset-bottom));
display:flex;flex-direction:column;gap:10px;max-width:640px;margin:0 auto}
.msgs{display:flex;flex-direction:column;gap:8px;max-height:38vh;overflow-y:auto;scrollbar-width:none}
.msgs::-webkit-scrollbar{display:none}
.msg{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--pink);
border-radius:14px;padding:12px 14px;font-size:14.5px;line-height:1.55;backdrop-filter:blur(10px);
animation:pop .25s ease-out}
@keyframes pop{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.msg .who{font-size:11px;font-weight:800;letter-spacing:.08em;color:var(--pink);margin-bottom:4px}
.msg.me{border-left-color:#7fb4ff;align-self:flex-end;max-width:85%}
.msg.me .who{color:#7fb4ff}
.msg.typing{color:var(--muted);font-style:italic}
.bar{display:flex;gap:10px;align-items:center}
.micbtn{width:52px;height:52px;flex:none;border-radius:50%;background:var(--card);
border:1px solid var(--line);color:var(--text);font-size:20px;cursor:pointer;backdrop-filter:blur(8px)}
.micbtn.listening{background:#d33;border-color:#d33;animation:pulse 1s infinite}
@keyframes pulse{50%{box-shadow:0 0 0 8px rgba(221,51,51,.25)}}
.inputwrap{flex:1;display:flex;align-items:center;background:var(--card);border:1px solid var(--line);
border-radius:999px;padding:6px 6px 6px 16px;backdrop-filter:blur(10px)}
.inputwrap input{flex:1;background:none;border:none;outline:none;color:var(--text);font-size:15px;min-width:0}
.sendbtn{width:44px;height:44px;flex:none;border-radius:50%;background:var(--pink);border:none;
color:#14101a;font-size:18px;cursor:pointer;font-weight:800}
.sendbtn:disabled{opacity:.5}
.hint{text-align:center;font-size:11.5px;color:var(--muted)}
</style></head><body>
<div class="pwrap" id="pwrap"><div class="stage" id="stage" title="Sapa Megumi">
<img src="/static/megumi.jpg" alt="Megumi Kato" draggable="false">
<div class="lid" id="lidL" style="left:52.9%;top:41.2%"></div>
<div class="lid" id="lidR" style="left:43.8%;top:41.6%"></div>
</div></div><div class="scrim"></div>
<div class="top">
  <div class="pill"><span class="dot"></span><span id="title">Megumi Kato &middot; Live2D AI</span></div>
  <div class="icons">
    <button class="icobtn" id="ttsbtn" title="Voice">&#128266;</button>
  </div>
</div>
<div class="langrow">
  <button class="lang active" data-l="id">&#127470;&#127481; ID</button>
  <button class="lang" data-l="jp">&#127471;&#127477; JP</button>
</div>
<div class="chat">
  <div class="msgs" id="msgs"></div>
  <div class="bar">
    <button class="micbtn" id="mic" title="Bicara">&#127908;</button>
    <div class="inputwrap">
      <input id="inp" placeholder="Ketik pesan..." autocomplete="off" maxlength="500">
      <button class="sendbtn" id="send">&#10148;</button>
    </div>
  </div>
  <div class="hint" id="hint">Balasan bisa 30 detik - 2 menit (Muse Spark via 9Router)</div>
</div>
<script>
let LANG='id', TTS=true, busy=false;
const hist=[];
const msgs=document.getElementById('msgs'), inp=document.getElementById('inp'),
      stage=document.getElementById('stage'), hint=document.getElementById('hint'),
      pwrap=document.getElementById('pwrap'), imgEl=stage.querySelector('img');
const STR={id:{ph:'Ketik pesan...',hello:'Dipa-kun, selamat datang kembali! Kamu bisa bicara langsung lewat mic atau ketik pesan di bawah ya.',title:'Megumi Kato \u00b7 Live2D AI'},
           jp:{ph:'\u30e1\u30c3\u30bb\u30fc\u30b8\u3092\u5165\u529b...',hello:'\u30c7\u30a3\u30d1\u541b\u3001\u304a\u304b\u3048\u308a! \u30de\u30a4\u30af\u3067\u8a71\u3057\u304b\u3051\u3066\u3082\u3001\u4e0b\u3067\u6253\u3063\u3066\u3082\u3044\u3044\u3088\u3002',title:'\u52a0\u85e4\u6075 \u00b7 Live2D AI'}};
function addMsg(who,text,me){const d=document.createElement('div');d.className='msg'+(me?' me':'');
d.innerHTML='<div class="who">'+who+'</div><div></div>';d.lastChild.textContent=text;
msgs.appendChild(d);msgs.scrollTop=msgs.scrollHeight;return d;}
function speak(t){if(!TTS)return;try{speechSynthesis.cancel();
const u=new SpeechSynthesisUtterance(t);u.lang=LANG==='id'?'id-ID':'ja-JP';u.rate=1;
const vs=speechSynthesis.getVoices().filter(v=>v.lang.startsWith(u.lang.slice(0,2)));
if(vs.length)u.voice=vs.find(v=>v.name.toLowerCase().includes('female'))||vs[0];
u.onstart=()=>stage.classList.add('speaking');u.onend=u.onerror=()=>{stage.classList.remove('speaking');imgEl.style.transform='';};
u.onboundary=()=>{imgEl.style.transform='scale(1.02)';setTimeout(()=>imgEl.style.transform='',130);};
speechSynthesis.speak(u);}catch(e){}}
async function send(text){text=(text||'').trim();if(!text||busy)return;busy=true;
document.getElementById('send').disabled=true;resetIdle();
addMsg(LANG==='id'?'DIPA-KUN':'\u30c7\u30a3\u30d1\u541b',text,true);inp.value='';
hist.push({role:'user',content:text});if(hist.length>20)hist.splice(0,hist.length-20);
const tp=addMsg('MEGUMI KATO','mengetik...',false);tp.classList.add('typing');
try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({messages:hist,lang:LANG})});
const j=await r.json();tp.remove();
if(j.reply){hist.push({role:'assistant',content:j.reply});addMsg('MEGUMI KATO',j.reply,false);speak(j.reply);}
else addMsg('MEGUMI KATO',j.error||'Gagal.',false);
}catch(e){tp.remove();addMsg('MEGUMI KATO','Koneksi gagal, coba lagi ya.',false);}
busy=false;document.getElementById('send').disabled=false;}
document.getElementById('send').onclick=()=>send(inp.value);
inp.onkeydown=e=>{if(e.key==='Enter')send(inp.value);};
document.querySelectorAll('.lang').forEach(b=>b.onclick=()=>{
document.querySelectorAll('.lang').forEach(x=>x.classList.remove('active'));b.classList.add('active');
LANG=b.dataset.l;inp.placeholder=STR[LANG].ph;document.getElementById('title').textContent=STR[LANG].title;});
document.getElementById('ttsbtn').onclick=e=>{TTS=!TTS;e.target.classList.toggle('off',!TTS);
if(!TTS)try{speechSynthesis.cancel();stage.classList.remove('speaking');}catch(_){}};
// mic
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
const mic=document.getElementById('mic');
if(SR){const rec=new SR();rec.interimResults=false;
rec.onresult=e=>{const t=e.results[0][0].transcript;inp.value=t;send(t);};
rec.onend=()=>mic.classList.remove('listening');
rec.onerror=()=>mic.classList.remove('listening');
mic.onclick=()=>{if(busy)return;rec.lang=LANG==='id'?'id-ID':'ja-JP';
try{rec.start();mic.classList.add('listening');}catch(_){}};}
else mic.style.display='none';
if('speechSynthesis' in window)speechSynthesis.getVoices();
function daypart(){const h=new Date().getHours();
if(LANG==='jp')return h<10?'\u304a\u306f\u3088\u3046':h<18?'\u3053\u3093\u306b\u3061\u306f':'\u3053\u3093\u3070\u3093\u306f';
return h<11?'Selamat pagi':h<15?'Selamat siang':h<18?'Selamat sore':'Selamat malam';}
addMsg('MEGUMI KATO',daypart()+', Dipa-kun! '+(LANG==='id'?'Senang kamu mampir. Mau ngobrol apa hari ini?':'\u4f1a\u3044\u306b\u6765\u3066\u304f\u308c\u3066\u3046\u308c\u3057\u3044\u3002\u4eca\u65e5\u306f\u4f55\u3092\u8a71\u305d\u3046\u304B\uFF1F'),false);
// --- interactivity: blink, cursor-follow parallax, poke, idle nudges ---
const lids=[document.getElementById('lidL'),document.getElementById('lidR')];
(function blink(){lids.forEach(l=>{l.classList.remove('blink');void l.offsetWidth;l.classList.add('blink');});
setTimeout(blink,2200+Math.random()*3800);})();
window.addEventListener('mousemove',e=>{
const x=e.clientX/window.innerWidth-.5,y=e.clientY/window.innerHeight-.5;
pwrap.style.transform='translate('+(x*18)+'px,'+(y*12)+'px) rotate('+(x*1.6)+'deg)';});
const POKE={id:['Dipa-kun~','Hm? Ada apa?','Hehe, geli tau.','Iya, aku di sini kok.','Jangan colek-colek ah.'],
jp:['\u30c7\u30a3\u30d1\u541b~','\u3093\uFF1F\u3069\u3046\u3057\u305F\u306E\uFF1F','\u304f\u3059\u3050\u3063\u305F\u3044\u3088\u3002','\u3046\u3093\u3001\u3053\u3053\u306B\u3044\u308B\u3088\u3002']};
const FLUSTER={id:'Dipa-kun! Nakal ya~',jp:'\u30c7\u30a3\u30d1\u541b\uFF01\u3082\u3046\u301C'};
const IDLE={id:['Dipa-kun, masih di sana?','Aku di sini kok, jangan dianggurin~'],
jp:['\u30c7\u30a3\u30d1\u541b\u3001\u307e\u3060\u3044\u308B\uFF1F','\u3053\u3053\u306B\u3044\u308B\u3088\u3001\u307b\u3063\u3068\u3044\u3066\u306D\u3002']};
let poking=false,pokeTimes=[];
let idleTimer=null,idleCount=0;
function resetIdle(){clearTimeout(idleTimer);idleCount=0;
idleTimer=setTimeout(idleNudge,55000);}
function idleNudge(){if(busy||!TTS||document.hidden){resetIdle();return;}
if(idleCount>=2)return;const line=IDLE[LANG][idleCount%IDLE[LANG].length];idleCount++;
addMsg('MEGUMI KATO',line,false);speak(line);
if(idleCount<2)idleTimer=setTimeout(idleNudge,70000);}
stage.addEventListener('click',()=>{if(poking||busy)return;poking=true;resetIdle();
const now=Date.now();pokeTimes=pokeTimes.filter(t=>now-t<4000);pokeTimes.push(now);
const flustered=pokeTimes.length>=3;
stage.classList.add('poke');setTimeout(()=>{stage.classList.remove('poke');poking=false;},480);
speak(flustered?FLUSTER[LANG]:POKE[LANG][Math.floor(Math.random()*POKE[LANG].length)]);
if(flustered)pokeTimes=[];});
resetIdle();
</script></body></html>"""


def get_key():
    with open(KEY_PATH) as f:
        return f.read().strip()


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    messages = data.get("messages", [])[-20:]
    lang = data.get("lang", "id") if data.get("lang") in SYSTEM else "id"
    try:
        r = requests.post(NINEROUTER,
                          headers={"Authorization": "Bearer " + get_key(),
                                   "Content-Type": "application/json"},
                          json={"model": MODEL,
                                "messages": [{"role": "system", "content": SYSTEM[lang]}]
                                           + messages,
                                "max_tokens": 300,
                                "temperature": 0.8},
                          timeout=TIMEOUT)
        d = r.json() if r.text.strip().endswith("}") else \
            json.loads(r.text[:r.text.rindex("}") + 1])
        text = d["choices"][0]["message"]["content"].strip()
        return jsonify({"reply": text})
    except Exception as e:
        return jsonify({"error": "bridge error: %s" % e}), 502


@app.route("/health")
def health():
    return jsonify({"ok": True, "model": MODEL})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=18101, threaded=True)
