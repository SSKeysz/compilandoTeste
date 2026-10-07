"""
Painel de testes - estilo "terminal hacker" (so para uso no seu proprio PC, Windows)
Funcoes: terminal falso de hacker, abrir varias abas, desligar monitor,
desligar/reiniciar PC com contagem e cancelamento, executar comandos.
"""
import os
import sys
import time
import random
import string
import ctypes
import subprocess
import webbrowser

# Ativa cores ANSI no terminal do Windows
os.system("")
VERDE = "\033[92m"
VERMELHO = "\033[91m"
AMARELO = "\033[93m"
RESET = "\033[0m"


def limpar():
    os.system("cls" if os.name == "nt" else "clear")


def digitar(texto, atraso=0.02, cor=VERDE):
    for c in texto:
        sys.stdout.write(cor + c + RESET)
        sys.stdout.flush()
        time.sleep(atraso)
    print()


def banner():
    limpar()
    print(VERDE + r"""
  _   _    _    ____ _  _____ _   _  ____
 | | | |  / \  / ___| |/ /_ _| \ | |/ ___|
 | |_| | / _ \| |   | ' / | ||  \| | |  _
 |  _  |/ ___ \ |___| . \ | || |\  | |_| |
 |_| |_/_/   \_\____|_|\_\___|_| \_|\____|
        [ painel de testes v1.0 ]
""" + RESET)


def terminal_hacker():
    limpar()
    digitar("Iniciando conexao segura...", 0.03)
    time.sleep(0.5)
    alvos = ["192.168.0.1", "10.0.0.42", "172.16.8.5", "servidor.local"]
    etapas = [
        "Escaneando portas",
        "Quebrando firewall",
        "Injetando payload",
        "Descriptografando hashes",
        "Contornando autenticacao",
        "Baixando banco de dados",
        "Apagando rastros",
    ]
    for etapa in etapas:
        alvo = random.choice(alvos)
        print(f"{VERDE}[+] {etapa} em {alvo}...{RESET}")
        for _ in range(random.randint(4, 9)):
            lixo = "".join(random.choices(string.hexdigits.lower(), k=64))
            print(f"{VERDE}{lixo}{RESET}")
            time.sleep(0.05)
        for p in range(0, 101, 10):
            sys.stdout.write(f"\r{AMARELO}    progresso: {p}%{RESET}")
            sys.stdout.flush()
            time.sleep(0.08)
        print(f"  {VERDE}OK{RESET}")
    print()
    digitar("ACESSO CONCEDIDO", 0.08)
    digitar("(brincadeira, nada foi hackeado :)", 0.03, AMARELO)
    input("\nEnter para voltar ao menu...")


def abrir_abas():
    print("Cole os links separados por espaco (Enter vazio = exemplo).")
    entrada = input("> ").strip()
    links = entrada.split() if entrada else [
        "https://www.google.com",
        "https://www.wikipedia.org",
        "https://www.youtube.com",
    ]
    try:
        vezes = int(input("Quantas vezes repetir cada link? [1]: ") or 1)
    except ValueError:
        vezes = 1
    vezes = max(1, min(vezes, 10))  # limite de seguranca
    for link in links:
        if not link.startswith("http"):
            link = "https://" + link
        for _ in range(vezes):
            webbrowser.open_new_tab(link)
            time.sleep(0.3)
    print(VERDE + "Abas abertas." + RESET)
    time.sleep(1)


def desligar_monitor():
    print("O monitor vai apagar. Mexa o mouse ou aperte uma tecla para acordar.")
    time.sleep(2)
    # WM_SYSCOMMAND=0x0112, SC_MONITORPOWER=0xF170, 2 = desligar
    ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)


def desligar_pc(reiniciar=False):
    acao = "reiniciar" if reiniciar else "desligar"
    try:
        seg = int(input(f"Em quantos segundos {acao}? [30]: ") or 30)
    except ValueError:
        seg = 30
    if input(f"Confirma {acao} o PC em {seg}s? (s/n): ").lower() != "s":
        print("Cancelado.")
        time.sleep(1)
        return
    flag = "/r" if reiniciar else "/s"
    subprocess.run(["shutdown", flag, "/t", str(seg)])
    print(AMARELO + "Agendado! Use a opcao 'Cancelar' no menu para abortar." + RESET)
    time.sleep(2)


def cancelar_desligamento():
    subprocess.run(["shutdown", "/a"])
    time.sleep(1.5)


def shell_livre():
    print("Terminal livre. Digite comandos do Windows. 'sair' volta ao menu.\n")
    while True:
        try:
            cmd = input(f"{VERDE}root@pc:~# {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd.lower() in ("sair", "exit", "quit"):
            break
        if cmd:
            os.system(cmd)


MENU = {
    "1": ("Terminal hacker (fake)", terminal_hacker),
    "2": ("Abrir varias abas", abrir_abas),
    "3": ("Desligar monitor", desligar_monitor),
    "4": ("Desligar PC (com contagem)", lambda: desligar_pc(False)),
    "5": ("Reiniciar PC (com contagem)", lambda: desligar_pc(True)),
    "6": ("Cancelar desligamento/reinicio", cancelar_desligamento),
    "7": ("Terminal livre (rodar comandos)", shell_livre),
    "0": ("Sair", None),
}


def main():
    if os.name != "nt":
        print("Este programa foi feito para Windows.")
        return
    os.system("title Painel de Testes")
    while True:
        banner()
        for k, (nome, _) in MENU.items():
            print(f"  {VERDE}[{k}]{RESET} {nome}")
        op = input(f"\n{VERDE}> {RESET}").strip()
        if op == "0":
            break
        if op in MENU:
            MENU[op][1]()


if __name__ == "__main__":
    main()
