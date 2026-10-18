# 64 Oozumou 2 (Japan) — mapa e viabilidade

**Resultado:** ambiente e análise estática funcionais; viabilidade de recompilação preliminar, com confirmação dinâmica pendente.

## Identidade e integridade

ROM original big-endian de 16 MiB, SHA-256 `3ff701b4735c84b17f8d80a996db59801caa766ee7da4d3e5a3b88eb34d99a17`. SHA-1 `6d524e0d0dd610dfb0c3bccaa88ef1e7aeceab98`. CRC CIC-6102 recalculado: `0x85C18B16` / `0xDF9622AF`, ambos iguais ao cabeçalho. Os bytes originais foram preservados. Todos os intervalos terminam em endereço exclusivo.

## Mapa principal de ROM e memória

| Região | ROM | VRAM/RAM | Confiança |
| --- | --- | --- | --- |
| Cabeçalho | `[0x00000000, 0x00000040)` | — | Confirmado |
| IPL3 | `[0x00000040, 0x00001000)` | bootstrap separado | Idêntico entre os jogos |
| CPU residente | `[0x00001000, 0x00034420)` | `[0x80080400, 0x800B3820)` | Alto; fronteira RSP inspecionada |
| RSP + dados residentes | `[0x00034420, 0x0004AF50)` | `[0x800B3820, 0x800CA350)` | Misto; fronteiras internas pendentes |
| BSS residente | sem bytes ROM | `[0x800CA350, 0x80125130)` | Confirmado pelo loop inicial |

[Mapa visual SVG](ozumo2-memory-map.svg) · [Mapa completo CSV](evidence/ozumo2-memory-map.csv) · [Evidências JSON](evidence/ozumo2.json)

## Inicialização e rotinas residentes

O entrypoint `0x80080400` limpa a BSS, estabelece `sp=0x800FF280` e salta para `0x80093400` (ROM `0x14000`), pulando um grande bloco anterior de funções. A inicialização chama `0x800AB200` (candidata a `osInitialize`), prepara uma thread com entrada `0x80093464` via `0x800A2AF0` e a inicia por `0x800A2EF0`. A rotina seguinte cria outra thread com entrada `0x80081EE4`. Há dispatch indireto de um callback guardado em `0x80120898` (carregado em `0x80093508`, `jalr` em `0x80093510`). Nomes de SDK permanecem atribuições sem símbolos originais, exceto os dois pares TLB comparados.

`0x80098640` é um wrapper síncrono de carregamento: recebe ROM/destino/tamanho em `a0/a1/a2`, cria fila, invalida D-cache, submete DMA pela rotina `0x800A4F70` e espera mensagem em `0x800A2BC0`. A preservação de `a0/a1/a2` em `s5/s2/s4` e seu uso como campos de DMA fundamentam a convenção adotada pelo scanner. Não se pressupõe que cada chamada desse wrapper transporte código.

## Código e possíveis overlays

Foram recuperados **140 mapeamentos DMA constantes**, **67 regiões CPU candidatas, incluindo a residente**, e **2378 funções inferidas por spimdisasm**. Há 57 instruções `jalr` e 151 `jr` que não retornam por `ra`, contadas no corpus de regiões, sem deduplicar possíveis sobreposições. Esses saltos incluem dispatch e jump tables; não são, isoladamente, falhas nem uma contagem de funções desconhecidas.

ROM `0x58EF0–0x8FC90` e `0x3D15E0–0x434580` são imagens diferentes carregadas em `0x8012C860`, por chamadas em ROM `0x5374` e `0x8EE4`. Ambas começam com código CPU e são candidatas fortes a overlays. Outras famílias reutilizam `0x801636E0`, `0x80179960` e `0x80180930`; os numerosos blocos em `0x80366800` também incluem recursos e não devem ser todos chamados de executáveis.

| Bloco completo ROM | Base VRAM | Prefixo CPU candidato na ROM | Confiança |
| --- | --- | --- | --- |
| `[0x00058EF0, 0x0008FC90)` | 0x8012C860 | `[0x00058EF0, 0x0005DB00)` | Médio: DMA + prefixo CPU |
| `[0x0004AF50, 0x00052680)` | 0x80125130 | `[0x0004AF50, 0x0004F290)` | Médio: DMA + prefixo CPU |
| `[0x0061FE90, 0x00627290)` | 0x80179960 | `[0x0061FE90, 0x00626360)` | Médio: DMA + prefixo CPU |
| `[0x003D15E0, 0x00434580)` | 0x8012C860 | `[0x003D15E0, 0x00420C20)` | Médio: DMA + prefixo CPU |
| `[0x0048D190, 0x004E0680)` | 0x801636E0 | `[0x0048D190, 0x00496520)` | Médio: DMA + prefixo CPU |

| Base de RAM reutilizada | Blocos ROM distintos mapeados |
| --- | --- |
| 0x801636E0 | 16 |
| 0x80179960 | 9 |
| 0x80180930 | 11 |
| 0x801A5A40 | 6 |
| 0x801B6E30 | 11 |
| 0x80366800 | 72 |

A tabela acima inclui dados. As imagens sobrepostas são alternativas, não ocupações simultâneas. Os fins de prefixo CPU são hipóteses locais: um opcode inválido pode ser dado embutido, e não o fim real da seção. O scanner independente deixou 0 páginas de densidade CPU sem interseção com os prefixos mapeados; ver `uncovered_density_candidates` no JSON. Isso não prova cobertura completa: páginas com pouco código, streams comprimidos e caminhos indiretos podem escapar.

## SDK e rotinas compartilhadas

| Nome atribuído | ROM | VRAM | Bytes | Evidência |
| --- | --- | --- | --- | --- |
| __osProbeTLB | 0x0002C570 | 0x800AB970 | 192 | Bytes iguais; nome por referência |
| osMapTLBRdb | 0x0002C6A0 | 0x800ABAA0 | 96 | Bytes iguais; nome por referência |

Os dois pares são idênticos byte a byte entre jogos e reaparecem no comparador normalizado. Não são quatro correspondências distintas. Sua função é gerenciamento de TLB da família libultra; não demonstram compartilhamento da lógica de sumô. Não se identificou uma biblioteca dinâmica ou engine inteira comum.

## Gráficos e recursos

| Offset ROM da assinatura | Microcódigo presente |
| --- | --- |
| 0x00046670 | RSP Gfx ucode F3DEX         1.23 Yoshitaka Yasumoto Nintendo. |
| 0x00046E70 | RSP Gfx ucode F3DEX.NoN     1.23 Yoshitaka Yasumoto Nintendo. |
| 0x00047670 | RSP Gfx ucode F3DLX         1.23 Yoshitaka Yasumoto Nintendo. |
| 0x00047E70 | RSP Gfx ucode F3DLX.NoN     1.23 Yoshitaka Yasumoto Nintendo. |
| 0x00048670 | RSP Gfx ucode F3DLX.Rej     1.23 Yoshitaka Yasumoto Nintendo. |
| 0x00048E70 | RSP Gfx ucode F3DLP.Rej     1.23 Yoshitaka Yasumoto Nintendo. |
| 0x00049670 | RSP Gfx ucode L3DEX         1.23 Yoshitaka Yasumoto Nintendo. |
| 0x00049CF9 | RSP Gfx ucode S2DEX  1.07 Yoshitaka Yasumoto Nintendo. |
| 0x0004A0B9 | RSP Gfx ucode S2DEXD 1.07 Yoshitaka Yasumoto Nintendo. |

O scanner encontrou 1137 cadeias candidatas de comandos de textura. Formatos de tiles de renderização recuperados: **CI4** (1097 declarações), **CI8** (24 declarações), **I4** (2 declarações), **IA4** (4 declarações), **IA8** (2 declarações), **RGBA16** (9 declarações). Contam-se declarações, não texturas únicas ou recursos efetivamente usados.

| ROM do SetTextureImage | Transferência | Tile render | Tile (não asset inteiro) | Endereço da imagem |
| --- | --- | --- | --- | --- |
| 0x0004FDA0 | I16 | I4 | 128×32 | 0x801296D8 |
| 0x000A9D28 | CI16 | CI4 | 64×64 | 0x01000548 |
| 0x0021D798 | IA16 | IA8 | 32×32 | 0x803DA5A8 |
| 0x00332270 | RGBA16 | RGBA16 | 16×16 | 0x0F018F08 |
| 0x00426D58 | IA16 | IA4 | 64×64 | 0x0F00BCF8 |
| 0x0048C728 | CI8 | CI8 | 29×44 | 0x801AA130 |

As sequências coerentes `FD/F5/E6/F3 ou F4/E7/F5/F2` sustentam a interpretação RDP. Formatos de transferência podem ser diferentes dos pixels renderizados. Ainda faltam bases de segmentos, TLUTs, uso em runtime e validação visual; nenhuma imagem foi extraída. As assinaturas confirmam presença das variantes, sem provar seleção de todas durante o jogo. O layout exato de modelos, fontes e containers de assets não foi resolvido.

Marcadores exatos de compressão encontrados: `{'MIO0': 0, 'Yay0': 0, 'Yaz0': 0}`. Contagem zero não exclui codecs próprios ou streams sem assinatura.

## Viabilidade de recompilação

**Recompilação estática é plausível como projeto de investigação; os metadados atuais ainda são insuficientes para iniciar uma tradução confiável de todo o jogo.** Entrypoint, BSS, pilha e o wrapper de DMA estão bem caracterizados, e há vários prefixos de código acessíveis sem descompressão. A reutilização de RAM exige identidade de overlay e tratamento de callbacks, não apenas símbolos por endereço.

O conjunto de microcódigos é mais variado do que no primeiro jogo: além de variantes F3DEX/F3DLX, há F3DLP.Rej, L3DEX e S2DEX/S2DEXD. É preciso descobrir quais OSTasks os selecionam e quais variantes o runtime escolhido suporta. As texturas paletizadas exigem resolver TLUTs e segmentos; identificá-las não demonstra que o renderizador esteja pronto. Ainda faltam confirmação dinâmica dos overlays, jump tables, BSS por imagem, seções/relocações, áudio, scheduler e I/O. Não foi produzido ELF, build N64Recomp ou execução nativa. A variedade maior de recursos não prova maior custo total de port.

## Próxima validação recomendada

1. Executar em emulador com trace de PC e DMA, cobrindo boot, menus, início e troca de lutas; comparar origens/destinos com os mapeamentos estáticos.
2. Capturar OSTasks, microcódigos selecionados e display lists, resolvendo segmentos e paletas.
3. Confirmar fronteiras CPU/dados, BSS, chamadas indiretas e jump tables em cada contexto de overlay.
4. Só então preparar um ELF/metadados mínimos e avaliar uma prova limitada de recompilação, em tarefa separada.

## Reprodução e limites

`make setup && make analyze && make verify`. A análise foi executada com Splat 0.50.1, spimdisasm 1.42.4 e Rabbitizer 1.16.2. Logs e assembly estão em `generated/`, fora do Git. Não houve emulação, teste de gameplay, build/link MIPS ou recompilação. Veja [metodologia](../docs/metodologia.md), [comparação](comparacao.md) e [inventário de funções](evidence/ozumo2-functions.csv).
