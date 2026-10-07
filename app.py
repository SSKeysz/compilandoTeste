"""
Painel de testes - versao web (localhost)
Sobe um site local em http://127.0.0.1:5000 com botoes para controlar o PC.
Uso pessoal, apenas no seu proprio computador (Windows).

Requisitos: pip install flask
"""
import os
import sys
import time
import ctypes
import random
import string
import threading
import subprocess
import webbrowser

from flask import Flask, jsonify, request, Response

app = Flask(__name__)

# ---------- paginas ----------

PAGINA = """
<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Painel de Testes</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root { --verde: #39ff14; --fundo: #0a0a0a; --painel: #111; }
  * { box-sizing: border-box; }
  body {
    background: var(--fundo); color: var(--verde);
    font-family: 'Consolas', 'Courier New', monospace;
    margin: 0; padding: 24px; min-height: 100vh;
  }
  h1 { text-align: center; text-shadow: 0 0 8px var(--verde); letter-spacing: 2px; }
  .grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 14px; max-width: 900px; margin: 30px auto;
  }
  button {
    background: var(--painel); color: var(--verde);
    border: 1px solid var(--verde); border-radius: 6px;
    padding: 16px; font-family: inherit; font-size: 15px;
    cursor: pointer; transition: 0.15s;
  }
  button:hover { background: var(--verde); color: #000; box-shadow: 0 0 12px var(--verde); }
  #console {
    max-width: 900px; margin: 20px auto; background: #000;
    border: 1px solid var(--verde); border-radius: 6px;
    padding: 14px; height: 300px; overflow-y: auto;
    white-space: pre-wrap; font-size: 13px;
  }
  .linha-cmd { max-width: 900px; margin: 0 auto; display: flex; gap: 8px; }
  .linha-cmd input {
    flex: 1; background: #000; color: var(--verde); border: 1px solid var(--verde);
    padding: 10px; font-family: inherit; border-radius: 6px;
  }
  .modal-bg {
    display: none; position: fixed; inset: 0; background: rgba(0,0,0,.7);
    align-items: center; justify-content: center;
  }
  .modal {
    background: var(--painel); border: 1px solid var(--verde); border-radius: 8px;
    padding: 24px; width: 300px; text-align: center;
  }
  .modal input { width: 80px; text-align: center; margin: 10px 0; background:#000;
    color: var(--verde); border: 1px solid var(--verde); padding: 6px; border-radius: 4px; }
  .modal button { margin: 4px; }
  small { opacity: .6; display:block; text-align:center; margin-top:30px; }
</style>
</head>
<body>
  <h1>&gt; PAINEL DE TESTES_</h1>

  <div class="grid">
    <button onclick="rodar('terminal_hacker')">Terminal hacker (fake)</button>
    <button onclick="abrirAbas()">Abrir varias abas</button>
    <button onclick="rodar('monitor_off')">Desligar monitor</button>
    <button onclick="abrirModal('desligar')">Desligar PC</button>
    <button onclick="abrirModal('reiniciar')">Reiniciar PC</button>
    <button onclick="rodar('cancelar')">Cancelar desligamento</button>
  </div>

  <div id="console">Aguardando comandos...\n</div>
  <div class="linha-cmd">
    <input id="cmdInput" placeholder="Digite um comando do Windows e Enter..." onkeydown="if(event.key==='Enter')rodarComando()">
    <button onclick="rodarComando()">Executar</button>
  </div>

  <div class="modal-bg" id="modalBg">
    <div class="modal">
      <div id="modalTitulo">Confirmar acao</div>
      <input type="number" id="segundos" value="30" min="5">
      <div>segundos</div>
      <button onclick="confirmarAcao()">Confirmar</button>
      <button onclick="fecharModal()">Cancelar</button>
    </div>
  </div>

  <small>Use apenas no seu proprio PC. Projeto de teste.</small>

<script>
const consoleDiv = document.getElementById('console');
function log(txt) {
  consoleDiv.textContent += txt + "\\n";
  consoleDiv.scrollTop = consoleDiv.scrollHeight;
}

async function rodar(acao, dados) {
  log("> executando: " + acao);
  const r = await fetch('/api/' + acao, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(dados || {})
  });
  const j = await r.json();
  log(j.saida || j.erro || "ok");
}

function abrirAbas() {
  const links = prompt("Cole os links separados por espaco:", "https://www.google.com https://www.wikipedia.org");
  if (links === null) return;
  rodar('abrir_abas', {links: links});
}

let acaoModal = null;
function abrirModal(acao) {
  acaoModal = acao;
  document.getElementById('modalTitulo').textContent =
    acao === 'desligar' ? 'Desligar PC em quantos segundos?' : 'Reiniciar PC em quantos segundos?';
  document.getElementById('modalBg').style.display = 'flex';
}
function fecharModal() { document.getElementById('modalBg').style.display = 'none'; }
function confirmarAcao() {
  const seg = document.getElementById('segundos').value || 30;
  fecharModal();
  rodar(acaoModal, {segundos: seg});
}

function rodarComando() {
  const input = document.getElementById('cmdInput');
  const cmd = input.value.trim();
  if (!cmd) return;
  input.value = '';
  rodar('shell', {comando: cmd});
}
</script>
</body>
</html>
"""


@app.route("/")
def home():
    return PAGINA


# ---------- api ----------

@app.route("/api/terminal_hacker", methods=["POST"])
def api_terminal_hacker():
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
    dados = request.get_json(force=True)
    links = (dados.get("links") or "").split()
    if not links:
        return jsonify(erro="nenhum link informado")
    for link in links[:15]:  # limite de seguranca
        if not link.startswith("http"):
            link = "https://" + link
        webbrowser.open_new_tab(link)
    return jsonify(saida=f"{len(links[:15])} aba(s) aberta(s).")


@app.route("/api/monitor_off", methods=["POST"])
def api_monitor_off():
    def desligar():
        time.sleep(0.5)
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
    threading.Thread(target=desligar, daemon=True).start()
    return jsonify(saida="Monitor vai apagar em instantes. Mexa o mouse para acordar.")


@app.route("/api/desligar", methods=["POST"])
def api_desligar():
    seg = int(request.get_json(force=True).get("segundos", 30))
    subprocess.run(["shutdown", "/s", "/t", str(seg)])
    return jsonify(saida=f"PC vai desligar em {seg}s. Use 'Cancelar' para abortar.")


@app.route("/api/reiniciar", methods=["POST"])
def api_reiniciar():
    seg = int(request.get_json(force=True).get("segundos", 30))
    subprocess.run(["shutdown", "/r", "/t", str(seg)])
    return jsonify(saida=f"PC vai reiniciar em {seg}s. Use 'Cancelar' para abortar.")


@app.route("/api/cancelar", methods=["POST"])
def api_cancelar():
    subprocess.run(["shutdown", "/a"])
    return jsonify(saida="Desligamento/reinicio cancelado (se havia algum agendado).")


@app.route("/api/shell", methods=["POST"])
def api_shell():
    cmd = request.get_json(force=True).get("comando", "")
    if not cmd:
        return jsonify(erro="comando vazio")
    try:
        resultado = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=20
        )
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
    threading.Thread(target=abrir_navegador, daemon=True).start()
    # host 127.0.0.1 = so acessivel no proprio PC, nao expoe na rede
    app.run(host="127.0.0.1", port=5000, debug=False)
