# Plano de validação dinâmica dos overlays — 64 Ōzumō 2

**Estado: planejado; nenhuma captura dinâmica foi realizada nesta tarefa.** O objetivo da próxima etapa é produzir um mapa de cargas e execuções que possa orientar uma prova limitada de recompilação. Não é refazer a comparação dos dois jogos ou afirmar cobertura integral.

## 1. Preparar uma sessão identificável

Usar somente `baseroms/ozumo2.z64` com SHA-256 `3ff701b4735c84b17f8d80a996db59801caa766ee7da4d3e5a3b88eb34d99a17`. O cabeçalho identifica a revisão japonesa investigada; o entrypoint é `0x80080400`.

Selecionar um emulador N64 com debugger capaz de breakpoints de execução, observação de registradores, watchpoints de memória e captura de PI DMA/PC. Project64 com debugger em Windows é uma opção a avaliar; versão e suporte de scripting devem ser confirmados antes de escolher uma API de automação. Não há script de captura de emulador supostamente pronto nesta entrega.

Começar em modo interpretador ou outro modo cujo debugger cubra todas as instruções relevantes. Documentar diferenças se migrar para um recompilador dinâmico, que pode ocultar watchpoints ou blocos já traduzidos. Fixar revisão do emulador, backends, perfil de RAM, controle, estado de saves e configuração de relógio. Copiar saves para uma sessão separada; não sobrescrever os do usuário.

Criar um `RUN_ID` em `local/traces/ozumo2/RUN_ID/` e preencher uma cópia de [session.template.json](session.template.json). Registrar boot frio, sem savestate, como referência. Savestates posteriores precisam declarar sua origem e não substituem a captura inicial. O plano não instala emulador ou muda o perfil de memória da ROM.

## 2. Instrumentar os pontos já conhecidos

| Ponto | Captura mínima | Fonte da hipótese |
| --- | --- | --- |
| `0x80080400` | Primeira entrada, RAM configurada, registradores e sequência de limpeza de BSS | Entrypoint e relatório existente |
| `0x80093400` | Entrada da inicialização após o bootstrap | `reports/ozumo2.md` |
| `0x80098640` | Entrada do wrapper: `a0`=offset ROM, `a1`=destino RAM, `a2`=bytes, `ra`, thread e VI | Convenção já inspecionada |
| `0x800986E8` / retorno ao `ra` capturado | O `jr ra` ainda tem delay slot em `0x800986EC`; observar o retorno efetivo após esse slot | Disassembly anterior do wrapper |
| `0x800A4F70` | Submissão ao SDK, campos reais do pedido, fila e identificador da operação | Chamada já identificada no wrapper |
| `0x800A2BC0` chamado pelo wrapper | Espera e recebimento da mensagem PI correspondente, sem assumir que toda mensagem significa sucesso | Relatório e fluxo do wrapper |
| Store em `0x80120898`; execução em `0x80093510` | Valor do callback, origem e contexto ativo no momento do `jalr` | Dispatch indireto já documentado |
| Registradores PI `0xA4600000–0xA4600010` | DRAM, cart, comprimento/direção e término de DMA | Verificação independente de cargas que não usem o wrapper |

Valores do wrapper devem ser lidos na entrada, antes de o prólogo reaproveitar registradores. Registrar `ra` e tratar chamadas aninhadas por thread/pilha; não colocar um breakpoint global único de retorno que confunda invocações simultâneas. `v0` no retorno pode ser registrado, mas sua semântica de status não será presumida.

No PI, `PI_WR_LEN` em `0xA460000C` inicia cart→RDRAM; `PI_RD_LEN` em `0xA4600008` cobre a direção inversa. Comprimento de registrador é bytes menos 1, sujeito às regras do hardware/emulador. Confirmar o evento de término e a interrupção/mensagem, sem confundir submissão com bytes já disponíveis.

Normalizar endereços de cart apenas quando pertencem à janela ROM esperada: `offset_ROM = cart_físico - 0x10000000`. Destinos KSEG0/KSEG1 são aliases de RAM; registrar também o endereço físico correspondente. Não aplicar cegamente a máscara de KSEG a código mapeado por TLB. Cada evento deve preservar os valores brutos além da forma normalizada.

## 3. Confirmar carga, uso e invalidação

Para cada transferência, registrar origem, destino, tamanho, contexto da chamada e IDs de submissão/conclusão. Depois de concluída e antes de modificações posteriores, calcular SHA-256 dos bytes lógicos N64 da RAM e compará-los ao trecho ROM correspondente. Dumps em ordem de palavras trocada precisam ser normalizados antes do hash; a ROM original permanece intocada.

Se houver diferença, manter a observação como divergente e investigar alinhamento, transferências em partes, descompressão, relocação, escrita posterior ou erro de captura. Não ajustar o hash esperado nem promover a carga a confirmada por semelhança visual.

Uma carga que contém instruções não é automaticamente um overlay executado. Acompanhar PC real entrando no intervalo, o offset dentro da imagem e o contexto ativo. Reutilização de um mesmo endereço por imagens distintas deve gerar épocas/generations de carga diferentes. Identidade mínima: `(origem ROM, tamanho carregado, base RAM, geração)`, com intervalos semiabertos.

Observar escritas de zero após a carga para delimitar BSS e sua relação com as outras imagens. Registrar invalidadores de cache e escritas sobre código já carregado. Se somente uma parte de uma imagem antiga for sobrescrita, não presumir que as funções restantes continuam válidas nem que a imagem antiga terminou por inteiro; isso exige evidência de ciclo de vida.

### Primeiro caso controlado A/B/A

| Imagem candidata | ROM | RAM prevista pelo mapa estático |
| --- | --- | --- |
| Bloco próximo ao residente | `[0x0004AF50, 0x00052680)` | `[0x80125130, 0x8012C860)` |
| A | `[0x00058EF0, 0x0008FC90)` | `[0x8012C860, 0x80163600)` |
| B | `[0x003D15E0, 0x00434580)` | `[0x8012C860, 0x8018F800)` |

As chamadas residentes previstas de A/B estão em ROM `0x5374`/`0x8EE4`. Encontrar nos traces quais estados reais disparam cada chamada e construir uma sequência A→B→A, se alcançável pelo fluxo normal do jogo. Registrar a primeira execução e o fim de validade dos alvos em cada geração. Não inventar nomes de cenas associados a A/B antes da observação.

B ocupa uma faixa maior. Sua substituição por A é um teste essencial de invalidação: descarregar apenas o tamanho de A pode deixar destinos antigos de B ou disparar a restrição de descarga parcial de N64ModernRuntime. A granularidade das futuras seções e a estratégia de retirada devem decorrer do trace, antes de chamar `load_overlays`/`unload_overlays`.

## 4. Matriz mínima de cenários

| Sessão | Ações e evidência esperada |
| --- | --- |
| S0: boot frio | Reset completo, estado inicial do save registrado, título/menu, DMA inicial, BSS e threads |
| S1: menus | Navegação com entradas registradas; seleção de participantes/opções realmente disponíveis |
| S2: entrada em luta | Transição, início e pelo menos 600 VIs de execução; observar cargas, callbacks e tarefas RSP |
| S3: saída e retorno | Encerrar uma luta pelo fluxo normal, observar resultado/próxima transição, voltar ao menu e iniciar outra |
| S4: cobertura adicional | Cobrir os outros modos/estados que forem encontrados; registrar seus nomes reais, sem presumir modos inexistentes |
| S5: repetição | Dois boots frios e reprodução das entradas; repetir o caso A/B/A quando os acionadores forem conhecidos |

Os VIs são uma medida da captura, não uma afirmação da taxa de simulação. Anotar diferenças de RNG, RTC, save ou plugins antes de interpretar divergências entre sessões. Não usar alterações de memória para forçar cenas no teste de fidelidade inicial.

## 5. Chamadas indiretas e gráficos

Para cada `jalr` e `jr` não-retorno observado nas imagens-alvo, registrar endereço de origem, destino, registrador e identidade ativa da imagem. Classificar retorno, dispatch e jump table por evidência; a contagem estática de 57/151 instruções não define quantos destinos precisam existir em runtime. Um alvo fora do mapa é uma pendência, não deve virar stub silencioso.

Capturar submissões de OSTask e hashes de seus microcódigos de texto/dados, tamanhos e tipo. Comparar os microcódigos usados com as nove assinaturas presentes já documentadas, sem assumir que todas são ativadas. Registrar display lists, bases de segmentos e TLUTs somente em armazenamento local quando incluírem dados do jogo.

Observar VI, timers e eventos que comandam a lógica. Não alterar o número de ticks para atingir 60 FPS. Não concluir compatibilidade gráfica de F3DEX/F3DLX/L3DEX/S2DEX somente pela existência das assinaturas na ROM.

## 6. Produtos e critérios de saída

Manter o material bruto em `local/`. Em tarefa posterior, produzir um resumo textual revisado em `re/ozumo2/` contendo:

1. Manifesto de sessões com ROM/save/emulador/configuração e entradas reproduzíveis.
2. Comparação dos **140 candidatos DMA anteriores** com os eventos observados, usando estados distintos: `not_seen`, `loaded_not_executed`, `executed`, `data_only`, `mismatch`. Não reclassificar `not_seen` como inexistente.
3. Tabela de imagens com ROM, RAM, tamanho, primeira/última execução, invalidação, BSS confirmada e estado das relocações.
4. Registro A/B/A com hashes e destinos indiretos correspondentes a cada geração; nenhum destino antigo resolvido para a imagem errada.
5. Lista de tarefas/microcódigos efetivamente usados e pendências de alinhamento, DMA assíncrono, RAM/Expansion Pak e callbacks.

Critério para **uma prova limitada**, não para declarar o jogo validado: uma unidade de código com fronteiras justificadas, dados/chamadas externas conhecidos, inicialização identificada, trace repetível e ciclo de vida de overlay confirmado nos cenários escolhidos. Depois preparar símbolos TOML ou ELF somente dessa unidade, testar o resultado e ampliar a cobertura em passos pequenos.

Os relatórios comparativos anteriores permanecem imutáveis. Observações novas devem ter arquivo próprio e apontar para a hipótese original, inclusive quando a contradisserem. Nenhuma captura planejada nesta página é apresentada como resultado executado.
