# 64 Oozumou (Japan) — mapa e viabilidade

**Resultado:** ambiente e análise estática funcionais; viabilidade de recompilação preliminar, com confirmação dinâmica pendente.

## Identidade e integridade

ROM original big-endian de 16 MiB, SHA-256 `661420aa5a7b5c0f86aad0dad813a0c876b99267d9d92fed0f4507e8e2a37240`. SHA-1 `e77fe9f2c32870eb7acbcf6a13d26dd022bafe5d`. CRC CIC-6102 recalculado: `0x9C961069` / `0xF5EA488D`, ambos iguais ao cabeçalho. Os bytes originais foram preservados. Todos os intervalos terminam em endereço exclusivo.

## Mapa principal de ROM e memória

| Região | ROM | VRAM/RAM | Confiança |
| --- | --- | --- | --- |
| Cabeçalho | `[0x00000000, 0x00000040)` | — | Confirmado |
| IPL3 | `[0x00000040, 0x00001000)` | bootstrap separado | Idêntico entre os jogos |
| CPU residente | `[0x00001000, 0x00024720)` | `[0x80000400, 0x80023B20)` | Alto; fronteira RSP inspecionada |
| RSP + dados residentes | `[0x00024720, 0x0002C4D0)` | `[0x80023B20, 0x8002B8D0)` | Misto; fronteiras internas pendentes |
| BSS residente | sem bytes ROM | `[0x8002B8D0, 0x800A62E0)` | Confirmado pelo loop inicial |

[Mapa visual SVG](ozumo1-memory-map.svg) · [Mapa completo CSV](evidence/ozumo1-memory-map.csv) · [Evidências JSON](evidence/ozumo1.json)

## Inicialização e rotinas residentes

O entrypoint `0x80000400` limpa a BSS em pares de palavras e estabelece `sp=0x8002DCC8`; salta para `0x80000450`. Essa rotina chama `0x8000CC50` (candidata a `osInitialize`), prepara uma thread com entrada `0x800004BC` e prioridade 10 pela rotina `0x8000CEE0`, e a inicia por `0x8000D030`. O reconhecimento de libultra se apoia no padrão CP0/FPU/PIF e nos argumentos e estruturas de threads; os nomes, exceto os dois pares TLB comparados, ainda são atribuições sem símbolos originais.

`0x8000D8D0` e `0x8000D950` usam instruções `cache` para invalidar I/D-cache antes de carregamentos. `0x8000DA00` monta uma mensagem de DMA com origem, destino e tamanho; as rotinas chamadoras esperam a conclusão via `0x8000D3F0`. `0x8000E670` zera blocos de memória, inclusive áreas posteriores a alguns overlays. Essas sequências sustentam o carregamento direto ROM→RAM; não resolvem todos os caminhos de inicialização de cenas.

## Código e possíveis overlays

Foram recuperados **62 mapeamentos DMA constantes**, **49 regiões CPU candidatas, incluindo a residente**, e **2925 funções inferidas por spimdisasm**. Há 54 instruções `jalr` e 365 `jr` que não retornam por `ra`, contadas no corpus de regiões, sem deduplicar possíveis sobreposições. Esses saltos incluem dispatch e jump tables; não são, isoladamente, falhas nem uma contagem de funções desconhecidas.

ROM `0x6E14F0–0x6E1570` e `0x704090–0x704110` são stubs diferentes carregados em `0x800A62E0`; as chamadas de DMA estão em ROM `0x1640` e `0x1820`. A imagem maior em ROM `0x2C4D0–0x92DF0` usa a mesma base (DMA em ROM `0x3D5C`). Há também chamadas residentes para essa área. É evidência forte de overlays de código, além de buffers reutilizados de recursos.

| Bloco completo ROM | Base VRAM | Prefixo CPU candidato na ROM | Confiança |
| --- | --- | --- | --- |
| `[0x002427A0, 0x002823E0)` | 0x800B2400 | `[0x002427A0, 0x0024A430)` | Médio: DMA + prefixo CPU |
| `[0x006E14F0, 0x006E1570)` | 0x800A62E0 | `[0x006E14F0, 0x006E1570)` | Médio: DMA + prefixo CPU |
| `[0x00704090, 0x00704110)` | 0x800A62E0 | `[0x00704090, 0x00704110)` | Médio: DMA + prefixo CPU |
| `[0x004810F0, 0x004D59B0)` | 0x80120000 | `[0x004810F0, 0x004ADF20)` | Médio: DMA + prefixo CPU |
| `[0x0002C4D0, 0x00092DF0)` | 0x800A62E0 | `[0x0002C4D0, 0x0007C1B0)` | Médio: DMA + prefixo CPU |

| Base de RAM reutilizada | Blocos ROM distintos mapeados |
| --- | --- |
| 0x800A62E0 | 24 |
| 0x801D18C0 | 13 |
| 0x801D4400 | 7 |
| 0x8034B000 | 12 |

A tabela acima inclui dados. As imagens sobrepostas são alternativas, não ocupações simultâneas. Os fins de prefixo CPU são hipóteses locais: um opcode inválido pode ser dado embutido, e não o fim real da seção. O scanner independente deixou 0 páginas de densidade CPU sem interseção com os prefixos mapeados; ver `uncovered_density_candidates` no JSON. Isso não prova cobertura completa: páginas com pouco código, streams comprimidos e caminhos indiretos podem escapar.

## SDK e rotinas compartilhadas

| Nome atribuído | ROM | VRAM | Bytes | Evidência |
| --- | --- | --- | --- | --- |
| __osProbeTLB | 0x0001C2A0 | 0x8001B6A0 | 192 | Bytes iguais; nome por referência |
| osMapTLBRdb | 0x0001A5A0 | 0x800199A0 | 96 | Bytes iguais; nome por referência |

Os dois pares são idênticos byte a byte entre jogos e reaparecem no comparador normalizado. Não são quatro correspondências distintas. Sua função é gerenciamento de TLB da família libultra; não demonstram compartilhamento da lógica de sumô. Não se identificou uma biblioteca dinâmica ou engine inteira comum.

## Gráficos e recursos

| Offset ROM da assinatura | Microcódigo presente |
| --- | --- |
| 0x0002B4C0 | RSP Gfx ucode F3DEX         1.21 Yoshitaka Yasumoto Nintendo. |
| 0x0002BCC0 | RSP Gfx ucode L3DEX         1.21 Yoshitaka Yasumoto Nintendo. |

O scanner encontrou 544 cadeias candidatas de comandos de textura. Formatos de tiles de renderização recuperados: **I4** (1 declarações), **IA16** (1 declarações), **IA4** (9 declarações), **RGBA16** (527 declarações), **RGBA32** (6 declarações). Contam-se declarações, não texturas únicas ou recursos efetivamente usados.

| ROM do SetTextureImage | Transferência | Tile render | Tile (não asset inteiro) | Endereço da imagem |
| --- | --- | --- | --- | --- |
| 0x00136C08 | RGBA16 | RGBA16 | 32×32 | 0x010046A0 |
| 0x00317408 | I8 | I4 | 32×32 | 0x01031268 |
| 0x0031F980 | RGBA32 | RGBA32 | 32×32 | 0x01032550 |
| 0x00468A20 | IA16 | IA16 | 32×32 | 0x0103FE50 |
| 0x007F0288 | IA8 | IA4 | 128×64 | 0x01004290 |

As sequências coerentes `FD/F5/E6/F3 ou F4/E7/F5/F2` sustentam a interpretação RDP. Formatos de transferência podem ser diferentes dos pixels renderizados. Ainda faltam bases de segmentos, TLUTs, uso em runtime e validação visual; nenhuma imagem foi extraída. As assinaturas confirmam presença das variantes, sem provar seleção de todas durante o jogo. O layout exato de modelos, fontes e containers de assets não foi resolvido.

Marcadores exatos de compressão encontrados: `{'MIO0': 0, 'Yay0': 0, 'Yaz0': 0}`. Contagem zero não exclui codecs próprios ou streams sem assinatura.

## Viabilidade de recompilação

**Recompilação estática é uma linha de trabalho plausível, mas a imagem ainda não está pronta para um recompilador automático.** O núcleo residente tem entrada/BSS/pilha bem definidos e há código MIPS não comprimido e microcódigos gráficos identificáveis. O maior obstáculo é a troca de imagens no mesmo endereço: um único mapa linear ou uma função por VRAM perderia contexto. Os dois microcódigos gráficos encontrados dão um escopo inicial delimitado; seu uso efetivo e compatibilidade com o runtime escolhido ainda precisam ser capturados.

É necessário resolver os overlays e as chamadas indiretas, separar dados embutidos, recuperar jump tables, conferir BSS de cada imagem e criar metadados de seções/relocações. As APIs libultra, interrupções, PI DMA, scheduler, áudio e controle precisam ser mapeados para um runtime. Não foi gerado ELF, reconstrução byte a byte nem código N64Recomp. A evidência não permite prometer um port completo, uma estimativa de prazo ou uma taxa de quadros.

## Próxima validação recomendada

1. Executar em emulador com trace de PC e DMA, cobrindo boot, menus, início e troca de lutas; comparar origens/destinos com os mapeamentos estáticos.
2. Capturar OSTasks, microcódigos selecionados e display lists, resolvendo segmentos e paletas.
3. Confirmar fronteiras CPU/dados, BSS, chamadas indiretas e jump tables em cada contexto de overlay.
4. Só então preparar um ELF/metadados mínimos e avaliar uma prova limitada de recompilação, em tarefa separada.

## Reprodução e limites

`make setup && make analyze && make verify`. A análise foi executada com Splat 0.50.1, spimdisasm 1.42.4 e Rabbitizer 1.16.2. Logs e assembly estão em `generated/`, fora do Git. Não houve emulação, teste de gameplay, build/link MIPS ou recompilação. Veja [metodologia](../docs/metodologia.md), [comparação](comparacao.md) e [inventário de funções](evidence/ozumo1-functions.csv).
