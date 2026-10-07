"""
Painel de testes - versao web unica (acessivel por outros aparelhos na mesma rede Wi-Fi)
Uso pessoal, apenas no seu proprio computador (Windows).

Requisitos para rodar direto com Python: pip install flask
"""
import os
import sys
import json
import time
import socket
import ctypes
import random
import string
import secrets
import threading
import subprocess
import webbrowser

from flask import Flask, jsonify, request, session

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# ---------- onde salvar o PIN (do lado do exe, nao dentro dele) ----------

def pasta_base():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

ARQ_CONFIG = os.path.join(pasta_base(), "painel_config.json")


def carregar_pin():
    try:
        with open(ARQ_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f).get("pin")
    except Exception:
        return None


def salvar_pin(pin):
    try:
        with open(ARQ_CONFIG, "w", encoding="utf-8") as f:
            json.dump({"pin": pin}, f)
    except Exception:
        pass


ESTADO = {"pin": carregar_pin()}


def autenticado():
    return not ESTADO["pin"] or session.get("ok") is True


def exigir_auth():
    if not autenticado():
        return jsonify(erro="nao autenticado"), 401
    return None


def ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


# ---------- pagina ----------

PAGINA = """
<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Painel de Testes</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
:root{--bg:#0a0a0d;--panel:#101015;--line:#1d1d25;--fg:#e9e9f0;--mut:#8b8b99;--acc:#7c00f0;--acc2:#9a3cff;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif;padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}
.app{display:grid;grid-template-columns:190px 1fr;min-height:100vh}
aside{background:var(--panel);border-right:1px solid var(--line);padding:16px 12px;display:flex;flex-direction:column;gap:6px}
.logo{padding:2px 4px 16px;font-weight:800;font-size:20px;letter-spacing:1px}
.logo span{color:var(--acc2)}
aside h6{margin:10px 0 2px 4px;font-size:12px;color:var(--mut);font-weight:600}
.nav{border:0;background:none;color:var(--fg);text-align:left;padding:9px 12px;border-radius:8px;font:inherit;cursor:pointer}
.nav.on{background:var(--acc);font-weight:600}
main{padding:16px;display:grid;gap:14px;align-content:start}
.tabs{display:none;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:3px}
.tab{flex:1;border:0;background:none;color:var(--fg);padding:8px 10px;border-radius:8px;font:inherit;cursor:pointer}
.tab.on{background:var(--acc);font-weight:600}
.cards{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:12px}
.card h3{margin:0;font-size:14px}
.row{display:flex;justify-content:space-between;align-items:center;gap:10px}
.hint{color:var(--mut);font-size:12px}
input[type=text],input[type=password],input[type=number]{background:#1a1a20;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:9px;font:inherit;width:100%}
.btn{border:0;background:var(--acc);color:#fff;padding:10px 14px;border-radius:8px;font:inherit;font-weight:600;cursor:pointer;white-space:nowrap}
.btn:hover{background:var(--acc2)}
.btn.outline{background:none;border:1px solid var(--line)}
.btn.block{width:100%}
.grid-btns{display:grid;gap:8px;grid-template-columns:1fr 1fr}
#term{background:#000;color:#21ff5a;font:12px/1.5 ui-monospace,Consolas,monospace;border:1px solid var(--line);border-radius:12px;padding:10px;height:220px;overflow:auto;white-space:pre-wrap}
.cmdrow{display:flex;gap:8px}
.warn{background:#2a1a00;border:1px solid #7a4a00;color:#ffd08a;border-radius:8px;padding:10px;font-size:12px;line-height:1.5}
.ipbox{font:13px ui-monospace,Consolas,monospace;color:var(--acc2);background:#0b0b10;border-radius:8px;padding:8px 10px}
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);align-items:center;justify-content:center;z-index:10}
.modal{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:22px;width:280px;text-align:center}
.modal input{margin:10px 0;text-align:center}
.lock{position:fixed;inset:0;background:var(--bg);display:flex;align-items:center;justify-content:center;z-index:20}
.lockbox{width:260px;text-align:center}
@media(max-width:700px){.app{grid-template-columns:1fr}aside{display:none}main{padding:12px}.tabs{display:flex}}
.hid{display:none!important}
</style>
</head>
<body>
<div class="app">
  <aside>
    <div class="logo">PAINEL<span>_</span></div>
    <h6>Controle</h6>
    <button class="nav on" data-p="a">Comandos</button>
    <button class="nav" data-p="b">Terminal</button>
    <h6>Config</h6>
    <button class="nav" data-p="c">Sistema</button>
  </aside>
  <main>
    <div class="tabs">
      <button class="tab on" data-p="a">Comandos</button>
      <button class="tab" data-p="b">Terminal</button>
      <button class="tab" data-p="c">Sistema</button>
    </div>

    <div class="cards" id="pa">
      <div class="card">
        <h3>Acoes rapidas</h3>
        <div class="grid-btns">
          <button class="btn" onclick="rodar('terminal_hacker')">Terminal hacker</button>
          <button class="btn" onclick="abrirAbas()">Abrir abas</button>
          <button class="btn" onclick="rodar('monitor_off')">Desligar monitor</button>
        </div>
      </div>
      <div class="card">
        <h3>Energia</h3>
        <div class="grid-btns">
          <button class="btn" onclick="abrirModal('desligar')">Desligar PC</button>
          <button class="btn" onclick="abrirModal('reiniciar')">Reiniciar PC</button>
        </div>
        <button class="btn outline block" onclick="rodar('cancelar')">Cancelar desligamento</button>
      </div>
    </div>

    <div class="cards hid" id="pb">
      <div class="card" style="grid-column:1/-1">
        <h3>Terminal</h3>
        <div id="term">Aguardando comandos...\n</div>
        <div class="cmdrow">
          <input id="cmdInput" type="text" placeholder="Comando do Windows..." onkeydown="if(event.key==='Enter')rodarComando()">
          <button class="btn" onclick="rodarComando()">Executar</button>
        </div>
      </div>
    </div>

    <div class="cards hid" id="pc">
      <div class="card">
        <h3>Acesso de outros aparelhos</h3>
        <span class="hint">Use este endereco no navegador do celular (mesma rede Wi-Fi):</span>
        <div class="ipbox" id="ipShow">carregando...</div>
        <div class="warn" id="pinWarn">Sem PIN: qualquer aparelho nessa rede pode controlar este PC pelo painel.</div>
        <input id="pinIn" type="password" placeholder="Definir um PIN (4 a 32 caracteres)">
        <div class="grid-btns">
          <button class="btn" onclick="definirPin()">Definir PIN</button>
          <button class="btn outline" onclick="removerPin()">Remover PIN</button>
        </div>
      </div>
    </div>
  </main>
</div>

<div class="modal-bg" id="modalBg">
  <div class="modal">
    <div id="modalTitulo">Confirmar acao</div>
    <input type="number" id="segundos" value="30" min="5">
    <div class="hint">segundos</div>
    <button class="btn" onclick="confirmarAcao()">Confirmar</button>
    <button class="btn outline" onclick="fecharModal()">Cancelar</button>
  </div>
</div>

<div class="lock hid" id="lockScreen">
  <div class="lockbox">
    <div class="logo" style="justify-content:center;display:flex">PAINEL<span>_</span></div>
    <p class="hint">Este painel esta protegido por PIN.</p>
    <input type="password" id="lockPin" placeholder="PIN">
    <button class="btn block" onclick="entrarPin()">Entrar</button>
  </div>
</div>

<script>
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
function show(p){["a","b","c"].forEach(x=>$("#p"+x).classList.toggle("hid",x!==p));$$(".tab,.nav").forEach(b=>b.classList.toggle("on",b.dataset.p===p))}
$$(".tab,.nav").forEach(b=>b.onclick=()=>show(b.dataset.p));

const consoleDiv=$("#term");
function log(txt){consoleDiv.textContent+=txt+"\\n";consoleDiv.scrollTop=consoleDiv.scrollHeight}

async function rodar(acao,dados){
  log("> executando: "+acao);
  const r=await fetch('/api/'+acao,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dados||{})});
  if(r.status===401){mostrarLock();return}
  const j=await r.json();
  log(j.saida||j.erro||"ok");
}

function abrirAbas(){
  const links=prompt("Cole os links separados por espaco:","https://www.google.com https://www.wikipedia.org");
  if(links===null)return;
  rodar('abrir_abas',{links:links});
}

let acaoModal=null;
function abrirModal(acao){
  acaoModal=acao;
  $("#modalTitulo").textContent=acao==='desligar'?'Desligar PC em quantos segundos?':'Reiniciar PC em quantos segundos?';
  $("#modalBg").style.display='flex';
}
function fecharModal(){$("#modalBg").style.display='none'}
function confirmarAcao(){const seg=$("#segundos").value||30;fecharModal();rodar(acaoModal,{segundos:seg})}

function rodarComando(){
  const input=$("#cmdInput"),cmd=input.value.trim();
  if(!cmd)return;
  input.value='';
  rodar('shell',{comando:cmd});
}

async function definirPin(){
  const pin=$("#pinIn").value.trim();
  if(pin.length<4){alert("O PIN precisa ter pelo menos 4 caracteres.");return}
  const r=await fetch('/api/pin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin})});
  if(r.ok){$("#pinIn").value='';carregarEstado()}else alert((await r.json()).erro||"erro")
}
async function removerPin(){
  if(!confirm("Remover o PIN? Qualquer aparelho na rede podera controlar o PC."))return;
  await fetch('/api/pin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin:""})});
  carregarEstado();
}

function mostrarLock(){$("#lockScreen").classList.remove("hid")}
async function entrarPin(){
  const pin=$("#lockPin").value;
  const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin})});
  if(r.ok){$("#lockScreen").classList.add("hid");$("#lockPin").value='';carregarEstado()}
  else alert("PIN incorreto.");
}

async function carregarEstado(){
  const r=await fetch('/api/state');
  const j=await r.json();
  $("#ipShow").textContent="http://"+j.ip+":"+j.porta;
  $("#pinWarn").classList.toggle("hid",j.pin_set);
  if(j.pin_set && !j.autenticado){mostrarLock()}else{$("#lockScreen").classList.add("hid")}
}
carregarEstado();
</script>
</body>
</html>
"""


@app.route("/")
def home():
    return PAGINA


@app.route("/api/state")
def api_state():
    return jsonify(ip=ip_local(), porta=5000, pin_set=bool(ESTADO["pin"]), autenticado=autenticado())


@app.route("/api/login", methods=["POST"])
def api_login():
    pin = request.get_json(force=True).get("pin", "")
    if not ESTADO["pin"] or pin == ESTADO["pin"]:
        session["ok"] = True
        return jsonify(ok=True)
    return jsonify(erro="pin incorreto"), 401


@app.route("/api/pin", methods=["POST"])
def api_pin():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    pin = (request.get_json(force=True).get("pin") or "").strip()
    ESTADO["pin"] = pin or None
    salvar_pin(ESTADO["pin"])
    return jsonify(ok=True)


@app.route("/api/terminal_hacker", methods=["POST"])
def api_terminal_hacker():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    etapas = [
        "Escaneando portas", "Quebrando firewall", "Injetando payload",
        "Descriptografando hashes", "Contornando autenticacao", "Apagando rastros",
    ]
    linhas = []
    for etapa in etapas:
        lixo = "".join(random.choices(string.hexdigits.lower(), k=32))
        linhas.append(f"[+] {etapa}... {lixo} OK")
    linhas.append("ACESSO CONCEDIDO (brincadeira, nada foi hackeado)")
    return jsonify(saida="\n".join(linhas))


@app.route("/api/abrir_abas", methods=["POST"])
def api_abrir_abas():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    dados = request.get_json(force=True)
    links = (dados.get("links") or "").split()
    if not links:
        return jsonify(erro="nenhum link informado")
    for link in links[:15]:
        if not link.startswith("http"):
            link = "https://" + link
        webbrowser.open_new_tab(link)
    return jsonify(saida=f"{len(links[:15])} aba(s) aberta(s).")


@app.route("/api/monitor_off", methods=["POST"])
def api_monitor_off():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio

    def desligar():
        time.sleep(0.5)
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)

    threading.Thread(target=desligar, daemon=True).start()
    return jsonify(saida="Monitor vai apagar em instantes. Mexa o mouse para acordar.")


@app.route("/api/desligar", methods=["POST"])
def api_desligar():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    seg = int(request.get_json(force=True).get("segundos", 30))
    subprocess.run(["shutdown", "/s", "/t", str(seg)])
    return jsonify(saida=f"PC vai desligar em {seg}s. Use 'Cancelar' para abortar.")


@app.route("/api/reiniciar", methods=["POST"])
def api_reiniciar():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    seg = int(request.get_json(force=True).get("segundos", 30))
    subprocess.run(["shutdown", "/r", "/t", str(seg)])
    return jsonify(saida=f"PC vai reiniciar em {seg}s. Use 'Cancelar' para abortar.")


@app.route("/api/cancelar", methods=["POST"])
def api_cancelar():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    subprocess.run(["shutdown", "/a"])
    return jsonify(saida="Desligamento/reinicio cancelado (se havia algum agendado).")


@app.route("/api/shell", methods=["POST"])
def api_shell():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    cmd = request.get_json(force=True).get("comando", "")
    if not cmd:
        return jsonify(erro="comando vazio")
    try:
        resultado = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
        saida = (resultado.stdout or "") + (resultado.stderr or "")
        return jsonify(saida=saida.strip() or "(sem saida)")
    except subprocess.TimeoutExpired:
        return jsonify(erro="comando demorou demais e foi cancelado")


def abrir_navegador():
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    if os.name != "nt":
        print("Feito para Windows.")
        sys.exit(1)
    print(f"Painel disponivel neste PC em:        http://127.0.0.1:5000")
    print(f"Painel disponivel para outros aparelhos na mesma rede Wi-Fi em: http://{ip_local()}:5000")
    threading.Thread(target=abrir_navegador, daemon=True).start()
    # host 0.0.0.0 = acessivel por outros aparelhos na mesma rede (use PIN no painel!)
    app.run(host="0.0.0.0", port=5000, debug=False)
