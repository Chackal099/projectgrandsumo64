# Projeto Ozumo 64 — Comparação preliminar das ROMs

**Data:** 17/10/2026  
**Escopo:** Inspeção estática e preliminar, sem execução em emulador, desassemblagem completa, extração de assets ou recompilação.  
**Arquivos fornecidos:** `64 Oozumou (Japan).zip` e `64 Oozumou 2 (Japan).zip`; foi analisado somente o `.z64` contido em cada ZIP.

## Identificação dos binários

| Propriedade | 64 Oozumou | 64 Oozumou 2 |
|---|---|---|
| Arquivo da ROM | `64 Oozumou (Japan).z64` | `64 Oozumou 2 (Japan).z64` |
| Tamanho | 16.777.216 bytes (16 MiB) | 16.777.216 bytes (16 MiB) |
| Magic big-endian | `80 37 12 40` | `80 37 12 40` |
| Title do cabeçalho (bytes brutos) | `64 OHZUMOU` | `64 \xb5\xb5\xbd\xde\xd3\xb3 2` (codificação japonesa; exibição bruta) |
| Game ID | `NOSJ` | `NO2J` |
| Região | `J` (Japão) | `J` (Japão) |
| Revisão (byte) | `0` | `0` |
| Entrypoint do cabeçalho | `0x80000400` | `0x80080400` |
| Header CRC1 (lido, não validado) | `9C961069` | `85C18B16` |
| Header CRC2 (lido, não validado) | `F5EA488D` | `DF9622AF` |
| CRC32 do bootcode `0x40–0xFFF` | `90BB6CB5` | `90BB6CB5` |
| SHA-256 | `661420aa5a7b5c0f86aad0dad813a0c876b99267d9d92fed0f4507e8e2a37240` | `3ff701b4735c84b17f8d80a996db59801caa766ee7da4d3e5a3b88eb34d99a17` |
| MD5 | `2cf9edb51ada9de2ae7ad9fd5acc5580` | `f7c796371e77e0a6fbd02eb866341952` |
| Tamanho comprimido do `.z64` no ZIP | 10.928.952 bytes | 8.767.676 bytes |

## Indícios preliminares de organização interna

- O intervalo de bootcode `0x40–0xFFF` é **idêntico byte por byte**, não apenas no CRC32.
- As ROMs possuem endereços de entrada diferentes. Isso não prova, isoladamente, que sua arquitetura de software ou grau de dificuldade de port sejam diferentes.
- Pesquisa de assinaturas ASCII `F3DEX` encontrou ocorrências em `0x2B4CE` (jogo 1) e `0x4667E`/`0x46E7E` (jogo 2). Isso é uma **pista** de microcódigo gráfico, a validar por inspeção dos bytes e do disassembly.
- Não foram encontrados marcadores ASCII exatos `MIO0`, `Yay0` ou `Yaz0`. Isso **não** comprova ausência de compressão: podem existir codecs diferentes, headers alternativos ou streams sem assinatura.
- Contagem de blocos de 4096 bytes inteiramente preenchidos por `0xFF`: 83 (jogo 1) e 398 (jogo 2). Cauda final de `0xFF`: 342.176 bytes (jogo 1) e 1.630.480 bytes (jogo 2). Esses números não são medidas confiáveis do volume de código ou conteúdo jogável.
- Comparação exploratória de blocos **alinhados** ao mesmo tamanho, iniciando em `0x1000`, e excluindo sequências com até dois valores de byte distintos: foram encontrados somente **1 bloco de 256 bytes** não trivial comum e **0 blocos de 1024 bytes** comuns. O método não detecta blocos deslocados por offsets não múltiplos do tamanho, sequências parcialmente alteradas nem dados comprimidos. Portanto, **não indica ausência de reutilização de código**.

## O que NÃO foi determinado ainda

- Quais segmentos da ROM são código MIPS, dados, texturas, áudio, overlays ou áreas comprimidas.
- Se os jogos compartilham funções ou engine em posições diferentes.
- Como cada jogo implementa física, temporizadores, câmera, combate, savestates e carregamento de texto.
- Compatibilidade de seus microcódigos e rotinas com um runtime de PC específico.
- Se o jogo 2 é mais fácil ou mais difícil de recompilar que o primeiro.
- Viabilidade real de 1080p, widescreen correto e interpolação 60 FPS.

## Próximas tarefas recomendadas para Codex

1. Registrar hashes dos dois `.z64` em um manifesto, manter os binários fora do Git público (`.gitignore`) e impedir alteração dos originais.
2. Executar um pipeline reproduzível de extração e análise estática dos **dois** jogos (ex.: `splat`/`spimdisasm`) com versões fixas das ferramentas.
3. Identificar ranges de código e dados, VRAM, seções, assinaturas gráficas, rotinas de descompressão e possíveis overlays; produzir mapa de endereços com nível de confiança.
4. Comparar funções por fingerprints normalizados de MIPS em vez de simples comparação de blocos em offset fixo.
5. Identificar o carregamento das strings e os pontos onde o texto passa para renderização; avaliar hooks para `locales/` externos.
6. Investigar medição de tick de lógica versus quadro renderizado e listar dependências antes de propor 60 FPS.
7. Decidir o jogo-alvo com base na evidência, risco de runtime e valor da experiência, não somente na qualidade visual.
8. Preparar símbolos/metadados requeridos pelo N64Recomp e fazer uma **prova de conceito pequena**, nunca exigir 'decompilar o jogo inteiro' de uma vez.

## Recomendações de projeto

- Guardar um inventário técnico compartilhado (`docs/roms.md`, `docs/segments.md`, `docs/symbols.md`, `docs/unknowns.md`).
- Separar `generated/` (código recompilado e artefatos gerados) de `src/` (código legível criado manualmente).
- Planejar localização externa e suporte a mods como APIs do port; não presumir que esse suporte seja automático.
- Preserve o patch do jogo 1 e sua documentação, independentemente do jogo escolhido para o port nativo.

**Interpretação:** A inspeção de cabeçalhos valida que temos duas ROMs N64 japonesas distintas, mas não permite concluir qual oferece a melhor base para recompilação. O próximo passo decisivo é mapear código e assets com desassemblagem comparativa.
