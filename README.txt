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
- TUDO abre na mesma janela. O botão “⚙ Configurações” (embaixo, à esquerda) reúne: Histórico, Conquistas,
  Baixar consoles, Ajustes dos emuladores, Emuladores e Pastas de ROMs, além de Adicionar ROMs, Detectar
  emuladores, Buscar capas e o tema claro/escuro.
- Configurações > “⬇ Baixar consoles”: baixa o RetroArch + cores (um programa só para vários consoles) ou
  emuladores avulsos, direto dos sites oficiais, para a pasta “emuladores”. Não baixa jogos nem BIOS.
- Configurações > “🏆 Conquistas”: entre com seu usuário e sua Web API Key do RetroAchievements para ver pontos,
  jogos platinados/completos/zerados e as conquistas de cada jogo. Só lê a sua conta.
  Depois de entrar, a lista de jogos ganha a coluna “🏆 RA” com o progresso de cada jogo da sua biblioteca
  (clique direito > “Vincular ao RetroAchievements…” se o programa não achar um jogo sozinho).
- Configurações > “📚 Histórico”: tudo que você já jogou (horas, dias, vezes, conquistas, % e anotações), mesmo sem a ROM
  neste PC. Fica fora da pasta do programa, então reinstalar não apaga. Para trocar de PC: use a
  “☁ Sincronização” (uma pasta do OneDrive/Google Drive/Dropbox), “Exportar/Importar”, ou entre no
  RetroAchievements (os jogos com conquistas voltam sozinhos).
- Configurações > “🎛 Ajustes dos emuladores”: gráficos (Original / Melhorado / Ultra), tela larga e mapeamento automático do controle
  direto no arquivo de configuração do emulador, sem abrir o emulador. Funciona com PCSX2, DuckStation, PPSSPP,
  Dolphin e RetroArch (que cobre NES, SNES, Game Boy, GBA, N64, Mega Drive, Saturn, Dreamcast, PS1 e outros).
  Guarda uma cópia de segurança antes e tem o botão “Desfazer”. O emulador precisa estar fechado.
- Favoritos, contador de vezes jogadas e botão Jogar que abre o emulador certo.
- Botão “📖 Guias” (ao lado do Jogar, e no clique direito do jogo): abre um menu com sites de guias e
  passo a passo daquele jogo específico (GameFAQs, StrategyWiki, YouTube em português e inglês, Google).

COMO USAR (para quem só quer jogar)
NÃO precisa instalar Python nem nada.
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
- emuladores      : emuladores e cores baixados pelo botão “Baixar consoles”
- ra_cache         : ícones e badges do RetroAchievements

O histórico de jogos fica em %APPDATA%\ProjectURL (histórico, cópias de segurança diárias e escolhas de sincronização).

PARA QUEM QUISER GERAR O .EXE (opcional)
Aqui sim precisa de Python, só para gerar o arquivo.
1. Instale o Python em python.org e marque "Add to PATH".
2. Deixe o "build_exe.bat", o "emu_hub.py" e o "p_url_downloads.py", o "p_url_ra.py", o "p_url_history.py", o "p_url_emucfg.py", o "URL_ICON.ico" e o "URL_ICON.png" na mesma pasta.
3. Dê dois cliques no "build_exe.bat".
4. O programa pronto aparece em: dist\Project U.R.L.exe

LICENÇA
MIT (veja o arquivo LICENSE).
