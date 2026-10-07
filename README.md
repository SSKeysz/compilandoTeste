# Painel de Testes - gerar o .exe sem instalar nada no seu PC

Este repositorio compila os dois programas (`hacker_tool.py` e `app.py`)
em arquivos `.exe` automaticamente, usando um computador Windows na nuvem
do GitHub. Voce nao precisa instalar Python, Flask nem Pyinstaller na sua
maquina - so precisa de uma conta gratuita no GitHub.

## Passo a passo

1. Crie uma conta gratuita em https://github.com (se ainda nao tiver).
2. Crie um repositorio novo (pode ser privado): botao verde "New".
3. Nessa pagina do repositorio, clique em "Add file" > "Upload files" e
   suba estes 3 arquivos (mantendo a pasta `.github/workflows/build.yml`
   exatamente nesse caminho):
   - `hacker_tool.py`
   - `app.py`
   - `.github/workflows/build.yml`
4. Clique em "Commit changes" para salvar.
5. Va na aba **Actions** do repositorio. Um processo chamado "Build EXE"
   vai comecar sozinho (leva uns 2 a 4 minutos).
6. Quando terminar (bolinha verde), clique nesse processo e role ate
   "Artifacts". Vai ter dois arquivos para baixar:
   - `hacker_tool-exe` (o painel de menu no terminal)
   - `app-exe` (o painel com site local em http://127.0.0.1:5000)
7. Baixe o `.zip`, extraia, e dentro vem o `.exe` prontinho. Copie para
   o pendrive.

Pronto - o Windows compilou o programa, nao a sua maquina. Voce so baixa
o resultado final.

## Observacoes

- Os `.exe` nao sao assinados digitalmente, entao o Windows SmartScreen ou
  o antivirus podem avisar "editor desconhecido" na primeira vez que abrir.
  Isso e normal para programas caseiros; basta clicar em "Mais informacoes"
  > "Executar assim mesmo".
- Se quiser recompilar depois de editar o codigo, basta subir os arquivos
  atualizados de novo (ou editar direto pelo site do GitHub) - o Actions
  roda automaticamente a cada mudanca.
- Tudo isso roda so no seu PC: nao expoe nada na internet.
