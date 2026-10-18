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
.stage{position:fixed;inset:0;background:url(/static/megumi.jpg) center 20%/cover no-repeat;
animation:breathe 6s ease-in-out infinite}
@keyframes breathe{0%,100%{transform:scale(1)}50%{transform:scale(1.018)}}
.stage.speaking{animation:speak .5s ease-in-out infinite}
@keyframes speak{0%,100%{transform:scale(1.018) translateY(0)}50%{transform:scale(1.022) translateY(-4px)}}
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
<div class="stage" id="stage"></div><div class="scrim"></div>
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
      stage=document.getElementById('stage'), hint=document.getElementById('hint');
const STR={id:{ph:'Ketik pesan...',hello:'Dipa-kun, selamat datang kembali! Kamu bisa bicara langsung lewat mic atau ketik pesan di bawah ya.',title:'Megumi Kato \u00b7 Live2D AI'},
           jp:{ph:'\u30e1\u30c3\u30bb\u30fc\u30b8\u3092\u5165\u529b...',hello:'\u30c7\u30a3\u30d1\u541b\u3001\u304a\u304b\u3048\u308a! \u30de\u30a4\u30af\u3067\u8a71\u3057\u304b\u3051\u3066\u3082\u3001\u4e0b\u3067\u6253\u3063\u3066\u3082\u3044\u3044\u3088\u3002',title:'\u52a0\u85e4\u6075 \u00b7 Live2D AI'}};
function addMsg(who,text,me){const d=document.createElement('div');d.className='msg'+(me?' me':'');
d.innerHTML='<div class="who">'+who+'</div><div></div>';d.lastChild.textContent=text;
msgs.appendChild(d);msgs.scrollTop=msgs.scrollHeight;return d;}
function speak(t){if(!TTS)return;try{speechSynthesis.cancel();
const u=new SpeechSynthesisUtterance(t);u.lang=LANG==='id'?'id-ID':'ja-JP';u.rate=1;
const vs=speechSynthesis.getVoices().filter(v=>v.lang.startsWith(u.lang.slice(0,2)));
if(vs.length)u.voice=vs.find(v=>v.name.toLowerCase().includes('female'))||vs[0];
u.onstart=()=>stage.classList.add('speaking');u.onend=u.onerror=()=>stage.classList.remove('speaking');
speechSynthesis.speak(u);}catch(e){}}
async function send(text){text=(text||'').trim();if(!text||busy)return;busy=true;
document.getElementById('send').disabled=true;
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
addMsg('MEGUMI KATO',STR.id.hello,false);
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
