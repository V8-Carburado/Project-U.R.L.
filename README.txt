PROJECT U.R.L. - HUB de emuladores
===================================

Uma biblioteca de jogos para vários emuladores, tudo num lugar só.
Feito 100% com IA, porque eu não consegui usar RetroArch nem EmulationStation
e não sei programar.

O QUE ELE FAZ
- Encontra os emuladores instalados no seu PC (PCSX2, DuckStation, Dolphin,
  PPSSPP, RPCS3, Ryujinx, Cemu, mGBA, Snes9x, RetroArch e outros).
- Escaneia suas pastas de ROMs toda vez que abre e descobre o console de cada jogo.
- Baixa as capas automaticamente.
- Favoritos, contador de vezes jogadas e botão Jogar que abre o emulador certo.

COMO USAR (para quem só quer jogar)
1. Vá na aba "Releases" deste repositório e baixe o "Project U.R.L.exe".
2. Coloque o arquivo numa pasta só dele (ele cria arquivos ao lado de si).
3. Abra e use à vontade.

Ao abrir pela primeira vez, o Windows pode mostrar um aviso do SmartScreen ou
do antivírus, comum em programas pequenos sem assinatura digital. Se você
confia no programa, clique em "Mais informações" e depois em "Executar assim mesmo".

ONDE FICAM OS DADOS
Ao lado do .exe:
- hub_config.json : suas configurações, lista de jogos e favoritos
- covers          : as capas baixadas (precisa de internet para baixar)

PARA QUEM QUISER GERAR O .EXE (opcional)
Aqui sim precisa de Python, só para gerar o arquivo.
1. Instale o Python em python.org e marque "Add to PATH".
2. Deixe o "build_exe.bat" e o "emu_hub.py" na mesma pasta.
3. Dê dois cliques no "build_exe.bat".
4. O programa pronto aparece em: dist\Project U.R.L.exe

LICENÇA
MIT (veja o arquivo LICENSE).
