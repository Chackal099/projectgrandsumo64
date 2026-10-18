# Método e limites da análise

O pedido é iniciar uma análise comparativa estática. O relatório fornecido pelo usuário foi usado como referência de hashes e hipóteses; suas sugestões de port, localização e prova de conceito não ampliam o escopo. Não se executou um jogo, não se compilou um port e não se alteraram os ZIPs ou os bytes das ROMs.

## Entradas e preservação

`config/roms.json` registra tamanho, SHA-256, SHA-1 e SHA-256 dos ZIPs recebidos. O importador lê apenas o membro `.z64`, verifica o CRC do ZIP e o hash do conteúdo e não extrai caminhos arbitrários. Reimportar uma ROM válida é idempotente; um arquivo diferente já existente causa falha. Os originais recebidos permanecem fora do checkout. `baseroms/`, `.venv/` e `generated/` estão ignorados pelo Git. As ferramentas abrem as ROMs somente para leitura; hashes são conferidos antes e depois.

## Código e endereçamento

- CPU: VR4300, MIPS big-endian, convenção O32. Em cada imagem carregada, `VRAM = base_vram + offset_ROM - inicio_ROM`. Essa relação vale dentro daquele mapeamento e não para a ROM inteira.
- O cabeçalho fornece o ponto de entrada. As instruções em ROM `0x1000` constroem endereço/tamanho da BSS, endereço inicial da pilha e destino do salto de inicialização.
- Os limites residentes CPU/RSP foram inspecionados manualmente: ROM `0x24720` e `0x34420` começam com o mesmo bootstrap RSP `09000419 20010FC0`, seguido de acesso aos registradores DMA do RSP. A parte CPU anterior termina em código válido. O detector genérico de Splat sugeria `0x24950`/`0x34650`, já dentro do microcódigo: esses palpites foram corrigidos. Assim o inventário CPU não conta o RSP como funções VR4300.
- Os fins das imagens residentes decorrem do início da BSS menos a base VRAM, somado a `0x1000`. A mistura seguinte contém código RSP, tabelas, dados e strings. Ainda não existe separação exata `.data`/`.rodata` nem mapa completo dos microcódigos.
- `compiler_hint` registra a hipótese de Splat (IDO/KMC), usada nas ferramentas. Não é prova de uma única versão de compilador para todos os objetos.

A porcentagem de ROM que Splat diz ter dividido inclui o segmento `bin` não classificado. Ela não mede cobertura de código identificado nem progresso de decompilação.

## Carregamentos e overlays

Foram inspecionadas as rotinas `0x8000DA00` (API compatível com `osPiStartDma`, jogo 1) e `0x80098640` (wrapper bloqueante de DMA, jogo 2). A primeira recebe origem em `a3`, destino/tamanho na pilha e direção `OS_READ=0`. A segunda recebe origem, destino e tamanho em `a0/a1/a2`, invalida cache, submete a operação e espera uma mensagem. O mapeamento não pressupõe um descompressor intermediário.

O analisador propaga constantes em trechos lineares, processa delay slots e invalida registradores voláteis e argumentos de pilha após chamadas. Reseta o estado em transferências e destinos de branches. Não inventa valores para registradores desconhecidos, acessos à memória, joins de fluxo ou tabelas. Itera sobre os novos prefixos de código até um ponto fixo. Cada mapeamento guarda o PC ROM, PC VRAM e contexto de overlay da chamada que o fundamenta.

Um prefixo adicional é **candidato** a código se decodifica como instruções CPU, contém retorno `jr ra`, não é predominantemente zeros e não entra em saltos característicos do RSP. Interromper no primeiro opcode não implementado e alinhar o último retorno é heurística: dados embutidos podem encurtar o intervalo; dados que parecem instruções podem estendê-lo. Spimdisasm também infere limites de funções. Nenhuma contagem é uma medida de progresso de decompilação ou uma lista completa de alvos recompiláveis.

Blocos ROM distintos destinados a faixas RAM sobrepostas demonstram reutilização estática de endereços. Quando há código e chamadas ao destino, são fortes candidatos a overlays executáveis. Dados e texturas também reutilizam buffers; colisão isolada não prova execução. Sem trace não se conhece a ordem, o tempo de vida ou todas as BSS dos overlays. Não se assume que overlays sobrepostos coexistam.

Um scanner independente percorre páginas de 4 KiB de toda a ROM procurando decrementos de pilha e retornos. Páginas sem interseção com código mapeado ficam em `uncovered_density_candidates`: são alvos de investigação, com falsos positivos possíveis. Tabelas de DMA, descompressão, relocação e código alcançado apenas por ponteiros podem escapar ao pipeline.

## Bibliotecas e comparação de funções

Compara-se o conteúdo delimitado por spimdisasm, incluindo padding. Há dois passes: SHA-256 exato e fingerprint que remove endereços de chamadas externas e pares HI/LO de referências RAM reconhecidas. Preserva registradores, constantes comuns e branches locais. Exige ao menos 64 bytes, 12 palavras não nulas e retorno; separa correspondências únicas de grupos ambíguos. Os mesmos dois pares aparecem em ambos os passes e não devem ser somados.

Esse método não é equivalência semântica: mudanças de compilador, alocação de registradores, inlining e limites inferidos podem esconder funções compartilhadas. Encontrar poucos pares não demonstra ausência de uma engine comum. Aqui, as duas funções iguais têm comportamento de TLB compatível com `__osProbeTLB` e `osMapTLBRdb` da libultra. A igualdade binária é comprovada; os nomes foram atribuídos por comparação de instruções com a referência comunitária libreultra. Não há evidência de bibliotecas dinâmicas no sentido de `.so`; trata-se de rotinas SDK ligadas estaticamente.

Referências de nomenclatura, inspecionadas com TLS verificado no commit `1aca5c13ca041cef86f8dc194b727361dad9c09b` de [n64decomp/libreultra](https://github.com/n64decomp/libreultra/tree/1aca5c13ca041cef86f8dc194b727361dad9c09b):

- [probetlb.s](https://github.com/n64decomp/libreultra/blob/1aca5c13ca041cef86f8dc194b727361dad9c09b/src/os/probetlb.s)
- [maptlbrdb.s](https://github.com/n64decomp/libreultra/blob/1aca5c13ca041cef86f8dc194b727361dad9c09b/src/os/maptlbrdb.s)

## Gráficos e compressão

Assinaturas ASCII completas e legíveis identificam variantes de microcódigo presentes no arquivo; não provam que todas sejam selecionadas pelo jogo. São dados de identificação do RSP, não nomes de funções CPU.

O scanner de display lists exige comandos alinhados de 8 bytes com `SetTextureImage` (`FD`), `SetTile` (`F5`) e `LoadBlock`/`LoadTile` (`F3`/`F4`) próximos, além de uma cadeia predominantemente reconhecível. Registra formato de **transferência** e os tiles de **renderização**, além de limites de tile quando disponíveis. Por exemplo, transferir como CI16 é comum ao carregar uma textura CI4; não prova existência de pixels CI16. Os tamanhos de tile não comprovam o tamanho total do recurso, que pode usar atlas, múltiplos tiles e paletas.

Os endereços podem ser segmentados (por exemplo segmento `0x01`) ou KSEG0. Sem resolver `gSPSegment`, o contexto do DMA e a TLUT, não se convertem automaticamente em offsets ROM nem se extraem imagens. Candidatos podem estar inativos ou ser falsos positivos. Não foram identificados com segurança modelos completos, layouts de vértices de cada asset, fontes ou um container proprietário. A ausência dos marcadores `MIO0`, `Yay0`, `Yaz0` não exclui compressão sem cabeçalho ou outros codecs.

## Validação e próximos limites

Testes unitários verificam delay slots, sinal de imediatos, clobbers, joins, fingerprints, separação de RSP, rejeição de conteúdo corrompido e a diferença entre carga e renderização. A validação funcional usa as duas ROMs: Splat, spimdisasm para cada região, funções realmente emitidas, artefatos SVG parseáveis, checksums CIC-6102 e hashes intactos. `generated/run-manifest.json` preserva comandos, logs e exit codes da última execução completa. `tools/verify.py` verifica os artefatos reais.

Não foram executados emulador, trace de DMA/PI, captura de OSTask/display lists, reconstrução binária via assembler, ELF linker ou N64Recomp. Esses são os próximos meios de confirmar cobertura de código, endereços indiretos, overlays, timing e compatibilidade de runtime. Não há promessa de widescreen, 1080p ou 60 FPS.
