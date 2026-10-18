# Comparação técnica e viabilidade de recompilação

**Os dois jogos oferecem uma base plausível para pesquisa de recompilação estática, mas nenhum está pronto para tradução automática completa.** A análise confirmou núcleos residentes MIPS, carregamentos que reutilizam endereços RAM, microcódigos gráficos e rotinas SDK compartilhadas. Persistem fronteiras inferidas, chamadas indiretas e ausência de validação dinâmica. O ambiente de análise está preparado; isso não é um port funcional.

| Métrica estática | 64 Oozumou | 64 Oozumou 2 |
| --- | --- | --- |
| Regiões CPU candidatas (inclui residente) | 49 | 67 |
| Funções inferidas | 2925 | 2378 |
| Mapeamentos DMA constantes | 62 | 140 |
| Cadeias gráficas candidatas | 544 | 1137 |
| Assinaturas de microcódigo gráfico | 2 | 9 |
| Instruções jalr / jr não-ra | 54 / 365 | 57 / 151 |

As contagens cobrem o corpus descoberto e não equivalem ao número real de funções ou overlays do jogo. Mais funções, mais cadeias gráficas ou mais mapeamentos não determinam maior dificuldade. Os gráficos usam candidatos por prefixo/declaração; não são contagens de assets únicos.

## Mapas e evidências

- [Jogo 1: relatório e viabilidade](ozumo1.md), [mapa SVG](ozumo1-memory-map.svg), [mapa CSV](evidence/ozumo1-memory-map.csv).
- [Jogo 2: relatório e viabilidade](ozumo2.md), [mapa SVG](ozumo2-memory-map.svg), [mapa CSV](evidence/ozumo2-memory-map.csv).
- [Manifesto de ROMs](../config/roms.json), [funções compartilhadas](evidence/shared-functions.json), [resumo verificável](evidence/summary.json).

## Diferenças que afetam uma futura recompilação

| Aspecto | Jogo 1 | Jogo 2 |
| --- | --- | --- |
| Inicialização | `0x80000400` → `0x80000450` | `0x80080400` → `0x80093400` |
| BSS residente | `0x8002B8D0–0x800A62E0` | `0x800CA350–0x80125130` |
| Famílias de overlays exemplificadas | `0x800A62E0`, `0x801D18C0`, `0x801D4400` | `0x8012C860`, `0x801636E0`, `0x80179960`, `0x80180930` |
| Microcódigos presentes | F3DEX e L3DEX 1.21 | Família F3DEX/F3DLX/F3DLP/L3DEX 1.23; S2DEX/S2DEXD 1.07 |
| Tiles identificados | I4, IA16, IA4, RGBA16, RGBA32 | CI4, CI8, I4, IA4, IA8, RGBA16 |
| Toolchain sugerido por Splat | IDO (hipótese) | KMC (hipótese) |
| Risco principal | Endereços reutilizados por imagens alternativas | Overlays e seleção de microcódigos variados |

O primeiro jogo apresenta um conjunto menor de assinaturas de microcódigo, o que delimita melhor uma investigação inicial de renderização. O segundo exige verificar mais variantes e paletas. Isso não permite afirmar qual port seria mais fácil: o uso real, os codecs, o áudio e a cobertura dos overlays ainda podem mudar a avaliação. Entrypoints diferentes, isoladamente, não justificam ranking.

## O que os jogos compartilham

O IPL3 é idêntico byte a byte. O comparador de funções encontrou dois pares únicos idênticos (192 e 96 bytes), compatíveis com `__osProbeTLB` e `osMapTLBRdb`. O mesmo conjunto reaparece após normalização de endereços. É evidência concreta de rotinas libultra ligadas estaticamente. Não se comprovou engine compartilhada, nem sua ausência. A comparação conserva registradores e constantes e pode perder correspondências entre compilações diferentes.

## Validação realizada

Foram concluídos 118 comandos de ferramentas com exit code zero: Splat para os dois residentes e spimdisasm em cada região CPU. A validação confere funções realmente emitidas, mapas SVG, hashes das ROMs e CRCs CIC-6102 de ambos os jogos. A suíte unitária exercita casos de instruções e fluxo, não apenas sintaxe. `generated/run-manifest.json` contém os comandos/logs da última execução completa. Os originais e as cópias locais mantêm os hashes fornecidos. Não houve testes de gameplay, build recompilado ou emulação.

## Próxima decisão e pendências

Antes de escolher um alvo de port, obter traces representativos de boot, menus e combate para ambos. Resolver mapeamentos de overlays e BSS, jump tables, microcódigos ativos e recursos segmentados. Depois, preparar seções e relocações de um ELF/metadados compatíveis com o recompilador escolhido e avaliar uma prova pequena, em escopo separado. Não se gerou um port nem se alteraram as ROMs. 1080p, widescreen e 60 FPS permanecem fora desta análise.

[Método e níveis de confiança](../docs/metodologia.md) · [Relatório inicial recebido](../docs/relatorio-inicial-fornecido.md) · [Como reproduzir](../README.md)
