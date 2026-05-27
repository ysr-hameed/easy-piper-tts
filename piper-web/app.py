#!/usr/bin/env python3
import os, sys, subprocess, tempfile, uuid, json, urllib.parse, re, threading, time
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

PIPER_HOME = os.environ.get("PIPER_HOME", os.path.expanduser("~/Documents/library/piper"))
MODELS_DIR = os.environ.get("MODELS_DIR", os.path.join(PIPER_HOME, "models"))
HOST = "0.0.0.0"
PORT = 8765

PIPER_BIN = os.path.join(PIPER_HOME, "bin", "piper")
if not os.path.exists(PIPER_BIN):
    PIPER_BIN = os.path.join(PIPER_HOME, "piper")

MODELS = [
    {"id": "hi_IN-rohan-medium.onnx",    "name": "Rohan",      "gender": "♂ Male"},
    {"id": "hi_IN-pratham-medium.onnx",  "name": "Pratham",    "gender": "♂ Male"},
    {"id": "hi_IN-priyamvada-medium.onnx","name": "Priyamvada","gender": "♀ Female"},
]

_tasks = {}
_lock = threading.Lock()

def _task_status(task_id):
    with _lock:
        return _tasks.get(task_id)

def _set_task(task_id, status, progress=0, result=None, error=None):
    with _lock:
        _tasks[task_id] = {"status": status, "progress": progress, "result": result, "error": error}

def _gen_wav_thread(task_id, text, model_path, speed, noise, variation, gap):
    try:
        chars = len(text)
        _set_task(task_id, "processing", 0)

        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = f"{PIPER_HOME}/lib:" + env.get("LD_LIBRARY_PATH", "")
        env["ESPEAK_DATA_PATH"] = f"{PIPER_HOME}/lib/espeak-ng-data"
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()

        cmd = [
            PIPER_BIN,
            "--model", model_path,
            "--length-scale", speed,
            "--noise-scale", noise,
            "--noise-w", variation,
            "--sentence-silence", gap,
            "--output-file", tmp.name
        ]

        est_sec = max(2.0, chars * 0.035)
        start = time.time()

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()

        while proc.poll() is None:
            elapsed = time.time() - start
            pct = min(94, int(elapsed / est_sec * 100))
            _set_task(task_id, "processing", pct)
            time.sleep(0.3)

        _set_task(task_id, "processing", 95)
        proc.wait(timeout=10)

        with open(tmp.name, "rb") as f:
            wav_data = f.read()
        os.unlink(tmp.name)

        if proc.returncode != 0:
            _set_task(task_id, "error", 0, error="Piper failed")
            return

        _set_task(task_id, "done", 100, result=wav_data)

    except Exception as e:
        _set_task(task_id, "error", 0, error=str(e))

_C = {
    "ksh":"क्ष","gy":"ज्ञ","shra":"श्र","tr":"त्र","chh":"छ",
    "kh":"ख","gh":"घ","ch":"च","jh":"झ","th":"थ","dh":"ध",
    "ph":"फ","bh":"भ","sh":"श","Sh":"ष","ny":"ञ","ng":"ङ",
    "nk":"ङ्क","ndh":"न्ध","ndr":"न्द्र","ntr":"न्त्र",
    "str":"स्त्र","shr":"श्र","k":"क","g":"ग","n":"न","t":"त",
    "d":"द","p":"प","b":"ब","m":"म","y":"य","r":"र","l":"ल",
    "v":"व","w":"व","s":"स","h":"ह","j":"ज","c":"क","f":"फ़",
    "q":"क","x":"क्स","z":"ज़",
    "T":"ट","Th":"ठ","D":"ड","Dh":"ढ","N":"ण","R":"ड़","Rh":"ढ़",
}
_VS = {"aa":"ा","ae":"ा","i":"ि","ee":"ी","ii":"ी",
       "u":"ु","oo":"ू","uu":"ू","e":"े","ai":"ै",
       "o":"ो","au":"ौ","ri":"ृ","a":""}
_SV = {"aa":"आ","a":"अ","i":"इ","ee":"ई","ii":"ई",
       "u":"उ","oo":"ऊ","uu":"ऊ","e":"ए","ai":"ऐ",
       "o":"ओ","au":"औ","ri":"ऋ"}
_SP = {
    "recording":"रिकॉर्डिंग","battery":"बैटरी","focus":"फ़ोकस",
    "camera":"कैमरा","phone":"फ़ोन","table":"टेबल","number":"नंबर",
    "video":"वीडियो","photo":"फ़ोटो","room":"रूम","light":"लाइट",
    "door":"डोर","glass":"ग्लास","case":"केस","time":"टाइम",
    "doctor":"डॉक्टर","zero":"ज़ीरो","world":"वर्ल्ड","rules":"रूल्स",
    "page":"पेज","control":"कंट्रोल","click":"क्लिक",
    "pata":"पता","pataa":"पता",
    "kaha":"कहा","kahan":"कहाँ","kaho":"कहो",
    "mila":"मिला","mili":"मिली","khula":"खुला","khuli":"खुली",
    "utha":"उठा","uthi":"उठी","gira":"गिरा","giri":"गिरी",
    "chhupa":"छुपा","chhupi":"छुपी","daba":"दबा","dabi":"दबी",
    "mara":"मारा","mari":"मारी","pahuncha":"पहुँचा",
    "pade":"पड़े","pada":"पड़ा","padi":"पड़ी",
    "main":"मैं","nahi":"नहीं","hai":"है","hain":"हैं",
    "tha":"था","thi":"थी","the":"थे","hoon":"हूँ",
    "hua":"हुआ","hui":"हुई","hue":"हुए","kya":"क्या",
    "kyun":"क्यों","kaun":"कौन","kuch":"कुछ","kisi":"किसी",
    "kab":"कब","kaise":"कैसे",
    "yahan":"यहाँ","wahan":"वहाँ","idhar":"इधर","udhar":"उधर",
    "yeh":"ये","ye":"ये","yah":"ये","woh":"वो","wah":"वो",
    "jo":"जो","toh":"तो",
    "aur":"और","par":"पर","lekin":"लेकिन","magar":"मगर",
    "bahut":"बहुत","thoda":"थोड़ा","thodi":"थोड़ी",
    "sa":"सा","si":"सी","se":"से","ke":"के","ki":"की",
    "ko":"को","ka":"का","ne":"ने","mein":"में","mai":"मैं",
    "tum":"तुम","tumne":"तुमने","tumhe":"तुम्हें",
    "aap":"आप","aapne":"आपने","aapko":"आपको",
    "usne":"उसने","uska":"उसका","uski":"उसकी","usko":"उसको",
    "sab":"सब","har":"हर","ek":"एक","do":"दो","teen":"तीन",
    "ab":"अब","phir":"फिर","tab":"तब","jab":"जब",
    "haan":"हाँ","nahin":"नहीं","dono":"दोनों",
    "aisa":"ऐसा","aisi":"ऐसी","waisa":"वैसा","waisi":"वैसी",
    "sirf":"सिर्फ","bas":"बस","andhera":"अंधेरा","andheri":"अंधेरी",
    "andar":"अंदर","bahar":"बाहर","aage":"आगे","peeche":"पीछे",
    "neeche":"नीचे","upar":"ऊपर","saamne":"सामने","paas":"पास",
    "dur":"दूर","raat":"रात","din":"दिन","subah":"सुबह",
    "shaam":"शाम","aaj":"आज","kal":"कल","roshni":"रोशनी",
    "aaina":"आइना","aaine":"आइने","parchayi":"परछाई",
    "chhaya":"छाया","aadmi":"आदमी","aadmiyo":"आदमियों",
    "insaan":"इंसान","insaano":"इंसानों",
    "aankh":"आँख","aankhen":"आँखें","aankho":"आँखों",
    "chehra":"चेहरा","chehre":"चेहरे","dil":"दिल","rooh":"रूह",
    "dard":"दर्द","pyaar":"प्यार","darr":"डर",
    "waqt":"वक़्त","samay":"समय","baat":"बात","baatein":"बातें",
    "kahani":"कहानी","sach":"सच","sahi":"सही","galat":"गलत",
    "shukriya":"शुक्रिया","maaf":"माफ़","karo":"करो",
    "chalo":"चलो","aao":"आओ","jao":"जाओ",
    "dekho":"देखो","suno":"सुनो","bolo":"बोलो",
    "khatam":"खत्म","shuru":"शुरू",
    "aakhri":"आखिरी","waapas":"वापस",
    "beech":"बीच","bich":"बीच",
    "kahi":"कहीं","yaha":"यहाँ","waha":"वहाँ",
    "kyoki":"क्योंकि","kyonki":"क्योंकि",
    "agar":"अगर","kabhi":"कभी",
    "samajh":"समझ","samjha":"समझा",
    "raha":"रहा","rahi":"रही","rahe":"रहे",
    "kar":"कर","karta":"करता","karti":"करती","karte":"करते",
    "tha":"था","thi":"थी","the":"थे",
    "dekh":"देख","dekha":"देखा","dekhi":"देखी",
    "bol":"बोल","bola":"बोला","boli":"बोली",
    "sun":"सुन","suna":"सुना","suni":"सुनी","sune":"सुने",
    "aa":"आ","aaya":"आया","aayi":"आई",
    "ja":"जा","gaya":"गया","gayi":"गई","gaye":"गए",
    "chuka":"चुका","chuki":"चुकी",
    "hota":"होता","hoti":"होती","hote":"होते",
    "sakta":"सकता","sakti":"सकती","sakte":"सकते",
    "chahiye":"चाहिए","chahta":"चाहता","chahti":"चाहती",
    "jaanta":"जानता","jaanti":"जानती",
    "mujhe":"मुझे","maine":"मैंने","mera":"मेरा","meri":"मेरी",
    "tere":"तेरे","tera":"तेरा",
    "humein":"हमें","hum":"हम",
    "inke":"इनके","unke":"उनके",
    "unki":"उनकी","isliye":"इसलिए",
}

def roman_to_dev(text):
    text = re.sub(r'\s+', ' ', text.strip())
    words = text.split()
    out = []
    for word in words:
        punct_b = ""; punct_a = ""
        while word and not word[-1].isalpha():
            punct_a = word[-1] + punct_a; word = word[:-1]
        while word and not word[0].isalpha():
            punct_b = punct_b + word[0]; word = word[1:]
        if not word:
            out.append(punct_b + punct_a); continue
        lower = word.lower()
        if lower in _SP:
            out.append(punct_b + _SP[lower] + punct_a); continue
        out.append(punct_b + _tw(lower) + punct_a)
    return " ".join(out)

def _tw(w):
    i = 0; r = []
    while i < len(w):
        ch = w[i]
        if ch in "aeiou" and (i == 0 or w[i-1] in "aeiou"):
            for vl in range(4,0,-1):
                if i+vl <= len(w) and w[i:i+vl] in _SV:
                    r.append(_SV[w[i:i+vl]]); i += vl; break
            else:
                r.append(_SV.get(ch,ch)); i += 1
            continue
        hit = False
        for cl in range(4,0,-1):
            if i+cl <= len(w) and w[i:i+cl] in _C:
                c = _C[w[i:i+cl]]; i += cl
                if i < len(w) and w[i] in "aeiou":
                    for vl in range(4,0,-1):
                        if i+vl <= len(w) and w[i:i+vl] in _VS:
                            s = _VS[w[i:i+vl]]
                            if s: c += s
                            i += vl; break
                    else:
                        v = w[i]
                        if v in "aeiou":
                            c += _VS.get(v,""); i += 1
                elif cl <= 2 and w[i-cl:i] in ["k","g","t","d","p","b","m","n","l","r","h","s","j","ch"]:
                    pass
                else:
                    c += "्"
                r.append(c); hit = True; break
        if hit: continue
        if ch == 'n' and i+1 < len(w) and w[i+1] in "gklmnpst":
            r.append("ं"); i += 1; continue
        if ch == 'm' and i+1 < len(w) and w[i+1] in "pbmnv":
            r.append("ं"); i += 1; continue
        r.append(_SV.get(ch,ch) if ch in "aeiou" else ch); i += 1
    return "".join(r)

HTML_PAGE = """\
<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Piper TTS — Hindi Voice Studio</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;500;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:#0a0a0a;color:#e0e0e0;font-family:'Noto Sans Devanagari','Inter',system-ui,sans-serif;min-height:100vh;padding:20px;display:flex;align-items:center;justify-content:center}
  .card{background:#141416;border-radius:20px;padding:36px;max-width:780px;width:100%;box-shadow:0 30px 80px rgba(0,0,0,.7);border:1px solid #1e1e22}
  h1{font-size:24px;font-weight:600;margin-bottom:2px;letter-spacing:.3px}
  .sub{color:#666;font-size:13px;margin-bottom:20px}
  .voice-strip{display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap}
  .voice-btn{padding:6px 14px;border:1px solid #26262b;border-radius:8px;background:transparent;color:#888;font-size:12px;font-family:inherit;cursor:pointer;transition:all .2s;display:flex;align-items:center;gap:4px}
  .voice-btn:hover{border-color:#3a3a40;color:#ccc}
  .voice-btn.active{background:#dc262610;border-color:#dc2626;color:#dc2626}
  .voice-btn .sym{font-size:11px;opacity:.5}
  .two-col{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px}
  @media(max-width:600px){.two-col{grid-template-columns:1fr}}
  .ctrl label{font-size:11px;color:#777;display:flex;justify-content:space-between;margin-bottom:4px}
  .ctrl label span{color:#dc2626;font-weight:500}
  input[type=range]{width:100%;height:4px;-webkit-appearance:none;appearance:none;background:#26262b;border-radius:4px;outline:none}
  input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:14px;height:14px;border-radius:50%;background:#dc2626;cursor:pointer;border:2px solid #141416}
  .val{color:#dc2626;font-size:12px;font-weight:500}
  .info-bar{display:flex;align-items:center;gap:10px;padding:8px 14px;background:#0d0d0f;border-radius:10px;font-size:12px;color:#777;border:1px solid #1c1c20;margin-bottom:16px}
  .led{width:6px;height:6px;border-radius:50%;background:#dc2626;animation:pulse 2s infinite;flex-shrink:0}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
  label.txt-lbl{font-size:12px;font-weight:500;color:#777;margin-bottom:4px;display:block;letter-spacing:.2px}
  textarea{width:100%;padding:12px 14px;border:1px solid #26262b;border-radius:10px;background:#0d0d0f;color:#e0e0e0;font-size:14px;line-height:1.6;resize:vertical;min-height:150px;font-family:'Noto Sans Devanagari','Inter',system-ui,sans-serif;transition:border .2s}
  textarea:focus{outline:none;border-color:#dc2626}
  textarea::placeholder{color:#444}
  .row{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap}
  .btn{flex:1;padding:10px 20px;border:none;border-radius:10px;font-size:13px;font-weight:500;cursor:pointer;transition:all .2s;min-width:100px;font-family:inherit}
  .go{background:#dc2626;color:#fff}
  .go:hover{background:#b91c1c}
  .go:disabled{opacity:.35;cursor:not-allowed}
  .sec{background:#26262b;color:#aaa}
  .sec:hover{background:#303036}
  .file-wrap{position:relative;display:inline-block}
  .file-wrap input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%}
  .player{margin-top:16px;display:none}
  .player audio{width:100%;border-radius:8px}
  .progress-wrap{display:none;margin-top:12px;text-align:center}
  .progress-bar{width:100%;height:6px;background:#26262b;border-radius:4px;overflow:hidden;margin-bottom:4px}
  .progress-fill{height:100%;background:#dc2626;border-radius:4px;width:0%;transition:width .3s ease}
  .progress-label{font-size:11px;color:#888;letter-spacing:.3px}
  .toast{position:fixed;bottom:28px;left:50%;transform:translateX(-50%);background:#141416;border:1px solid #26262b;padding:10px 20px;border-radius:10px;font-size:12px;display:none;z-index:999;font-family:inherit}
  .toast.err{border-color:#ef444433;color:#ef4444}
  .toast.ok{border-color:#dc262633;color:#dc2626}
</style>
</head>
<body>
<div class="card">
  <h1>Piper <span style="color:#dc2626">TTS</span></h1>
  <div class="sub">Horror Story Mode · Slow · Atmospheric · Hindi</div>

  <div class="voice-strip" id="voiceStrip">
    <button class="voice-btn active" data-model="hi_IN-rohan-medium.onnx" onclick="pick(this)"><span class="sym">♂</span> Rohan</button>
    <button class="voice-btn" data-model="hi_IN-pratham-medium.onnx" onclick="pick(this)"><span class="sym">♂</span> Pratham</button>
    <button class="voice-btn" data-model="hi_IN-priyamvada-medium.onnx" onclick="pick(this)"><span class="sym">♀</span> Priyamvada</button>
  </div>

  <div class="two-col">
    <div class="ctrl">
      <label>Speed <span id="speedVal">0.85</span></label>
      <input type="range" id="speed" min="0.5" max="2.0" step="0.05" value="0.85" oninput="document.getElementById('speedVal').textContent=this.value;upd()">
    </div>
    <div class="ctrl">
      <label>Pitch / Expressiveness <span id="noiseVal">0.75</span></label>
      <input type="range" id="noise" min="0.0" max="1.0" step="0.01" value="0.75" oninput="document.getElementById('noiseVal').textContent=this.value">
    </div>
    <div class="ctrl">
      <label>Voice Variation <span id="variationVal">0.40</span></label>
      <input type="range" id="variation" min="0.0" max="1.0" step="0.01" value="0.40" oninput="document.getElementById('variationVal').textContent=this.value">
    </div>
    <div class="ctrl">
       <label>Sentence Gap (sec) <span id="gapVal">0.65</span></label>
      <input type="range" id="gap" min="0.0" max="2.0" step="0.05" value="0.65" oninput="document.getElementById('gapVal').textContent=this.value">
    </div>
  </div>

  <div class="info-bar">
    <span class="led"></span>
    <span id="infoText">Horror Mode · Rohan · 0.85x · gap 0.65s</span>
  </div>

  <label class="txt-lbl">Text — Roman Hindi ya Devanagari likhein</label>
  <textarea id="textBox" placeholder="Yahan likhein...&#10;&#10;Mera naam Kabir hai. Aur yeh meri aakhri recording hai."></textarea>

  <div class="row">
    <button class="btn go" id="goBtn" onclick="speak()">&#9654; Generate & Play</button>
    <div class="file-wrap"><button class="btn sec">&#128206; .txt</button><input type="file" accept=".txt" onchange="loadFile(event)"></div>
    <button class="btn sec" onclick="clr()">&#10005;</button>
  </div>

  <div class="progress-wrap" id="progressWrap">
    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
    <div class="progress-label" id="progressLabel">Generating...</div>
  </div>

  <div class="player" id="player"><audio id="aud" controls preload="auto"></audio></div>
</div>
<div class="toast" id="toast"></div>

<script>
var _model="hi_IN-rohan-medium.onnx"
var _pollTimer=null
function pick(b){document.querySelectorAll(".voice-btn").forEach(function(x){x.classList.remove("active")});b.classList.add("active");_model=b.getAttribute("data-model");upd()}
function upd(){var s=document.getElementById("speed").value,g=document.getElementById("gap").value;document.getElementById("infoText").textContent="Horror Mode · "+document.querySelector(".voice-btn.active").textContent.trim()+" · "+s+"x · gap "+g+"s"}
function speak(){
  var box=document.getElementById("textBox"),txt=box.value.trim();
  if(!txt){toast("Pehle text likhein","err");return}
  var btn=document.getElementById("goBtn"),pw=document.getElementById("progressWrap"),pf=document.getElementById("progressFill"),pl=document.getElementById("progressLabel"),au=document.getElementById("aud");
  btn.disabled=true;pw.style.display="block";pf.style.width="0%";pl.textContent="Starting...";document.getElementById("player").style.display="none";
  var f=new URLSearchParams;
  f.set("text",txt);f.set("model",_model);
  f.set("speed",document.getElementById("speed").value);
  f.set("noise",document.getElementById("noise").value);
  f.set("variation",document.getElementById("variation").value);
  f.set("gap",document.getElementById("gap").value);
  fetch("/speak",{method:"POST",body:f})
  .then(function(r){if(!r.ok)throw new Error("Server error");return r.json()})
  .then(function(d){if(d.task_id){_pollTask(d.task_id)}else{throw new Error("No task_id")}})
  .catch(function(e){pw.style.display="none";btn.disabled=false;toast("Error: "+e.message,"err")})
}
function _pollTask(id){
  var pw=document.getElementById("progressWrap"),pf=document.getElementById("progressFill"),pl=document.getElementById("progressLabel"),btn=document.getElementById("goBtn"),au=document.getElementById("aud");
  _pollTimer=setInterval(function(){
    fetch("/task/"+id+"/status")
    .then(function(r){return r.json()})
    .then(function(s){
      pf.style.width=s.progress+"%";
      if(s.status=="processing"){pl.textContent="Generating... "+s.progress+"%"}
      else if(s.status=="done"){
        clearInterval(_pollTimer);
        pl.textContent="Finalizing... 100%";
        fetch("/task/"+id+"/audio")
        .then(function(r){if(!r.ok)throw new Error("Audio fetch failed");return r.blob()})
        .then(function(b){var u=URL.createObjectURL(b);au.src=u;document.getElementById("player").style.display="block";au.play();pw.style.display="none";btn.disabled=false;toast("Audio ready!","ok")})
        .catch(function(e){pw.style.display="none";btn.disabled=false;toast("Error: "+e.message,"err")})
      }
      else if(s.status=="error"){
        clearInterval(_pollTimer);
        pw.style.display="none";btn.disabled=false;
        toast(s.error||"Generation failed","err");
      }
    })
    .catch(function(){clearInterval(_pollTimer);pw.style.display="none";btn.disabled=false;toast("Poll failed","err")})
  },400)
}
function loadFile(e){var f=e.target.files[0];if(!f)return;var r=new FileReader;r.onload=function(x){document.getElementById("textBox").value=x.target.result;toast("Loaded: "+f.name,"ok")};r.readAsText(f)}
function clr(){document.getElementById("textBox").value="";document.getElementById("player").style.display="none";document.getElementById("progressWrap").style.display="none"}
function toast(m,t){var d=document.getElementById("toast");d.textContent=m;d.className="toast "+(t||"");d.style.display="block";setTimeout(function(){d.style.display="none"},2800)}
</script>
</body>
</html>"""

class PiperHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        if self.path.startswith("/task/"):
            parts = self.path.split("/")
            if len(parts) == 4 and parts[3] == "status":
                task_id = parts[2]
                t = _task_status(task_id)
                if not t:
                    self._json(404, {"error": "Task not found"})
                    return
                self._json(200, {"status": t["status"], "progress": t["progress"]})
                return
            if len(parts) == 4 and parts[3] == "audio":
                task_id = parts[2]
                t = _task_status(task_id)
                if not t or t["status"] != "done" or t["result"] is None:
                    self._json(404, {"error": "Audio not ready"})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(t["result"])))
                self.end_headers()
                self.wfile.write(t["result"])
                return

        self.send_error(404)

    def do_POST(self):
        if self.path == "/speak":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            params = urllib.parse.parse_qs(body)
            text = params.get("text", [""])[0]
            model_id = params.get("model", [""])[0]
            speed = params.get("speed", ["0.85"])[0]
            noise = params.get("noise", ["0.75"])[0]
            variation = params.get("variation", ["0.40"])[0]
            gap = params.get("gap", ["0.65"])[0]

            if not text.strip():
                self._json(400, {"error": "No text"})
                return

            model_path = os.path.join(MODELS_DIR, model_id)
            if not os.path.exists(model_path):
                model_path = os.path.join(MODELS_DIR, "hi_IN-rohan-medium.onnx")

            has_devanagari = bool(re.search(r'[\u0900-\u097F]', text))
            if not has_devanagari:
                text = roman_to_dev(text)

            task_id = uuid.uuid4().hex[:12]
            _set_task(task_id, "queued", 0)

            t = threading.Thread(target=_gen_wav_thread, args=(task_id, text, model_path, speed, noise, variation, gap), daemon=True)
            t.start()

            self._json(200, {"task_id": task_id})
            return
        self.send_error(404)

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, fmt, *args):
        msg = fmt % args
        if "POST" in msg or "GET /" in msg or "/task/" in msg:
            print(f"  ⇄  {msg.split('] ')[-1] if '] ' in msg else msg}")

def start():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    host = sys.argv[2] if len(sys.argv) > 2 else HOST
    avail = [m for m in MODELS if os.path.exists(os.path.join(MODELS_DIR, m["id"]))]
    if not avail: print(f"  ✗ No models in {MODELS_DIR}"); sys.exit(1)
    if not os.path.exists(PIPER_BIN): print("  ✗ Piper missing"); sys.exit(1)
    print()
    print("  ┌──────────────────────────────────────┐")
    print("  │ Piper TTS │ HORROR STORY MODE       │")
    print("  ├──────────────────────────────────────┤")
    print(f"  │  http://localhost:{port}                   │")
    if host == "0.0.0.0": print(f"  │  http://0.0.0.0:{port}                   │")
    print(f"  │  Models: {len(avail)} loaded                   │")
    for m in avail:
        ck = "◆" if os.path.exists(os.path.join(MODELS_DIR, m["id"])) else "◇"
        print(f"  │   {ck} {m['name']:<12s} {m['gender']}           │")
    print("  │                                      │")
    print("  │  Ctrl+C to stop                      │")
    print("  └──────────────────────────────────────┘")
    print()
    srv = HTTPServer((host, port), PiperHandler)
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\n  Stopped."); srv.server_close()

if __name__ == "__main__":
    start()
