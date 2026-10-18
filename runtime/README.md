# Integração nativa planejada

Este diretório é reservado ao código C/C++ manual do port de 64 Ōzumō 2. Nenhuma função do jogo foi recompilada nesta etapa.

- `game/`: vinculação específica do jogo com librecomp/ultramodern e os metadados de overlays confirmados.
- `platform/`: callbacks de Windows, áudio, controle, apresentação e persistência.
- `patches/`: substituições manuais pequenas, com comportamento original como referência.
- `localization/` e `mods/`: interfaces futuras, sem implementação prematura.

O futuro código gerado vai para `generated/ozumo2/recomp/`, sem ser misturado a estes módulos. As fontes upstream ficam em `.tools/src/`, fixadas por revisão. A biblioteca de tradução de funções e a aplicação têm responsabilidades diferentes.

Consulte a [arquitetura e a sequência de desenvolvimento](../docs/development/structure.md) e o [ambiente](../docs/development/environment.md). Uma futura aplicação CMake usará `add_subdirectory` de N64ModernRuntime e os targets `librecomp`/`ultramodern`; a aplicação fornecerá os callbacks e o renderizador. O build desses targets já pode ser validado isoladamente com `make upstream`.
