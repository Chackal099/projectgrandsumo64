# Validação dinâmica — estado e método

**Instrumentação implementada; nenhuma captura real realizada nesta tarefa.** Não foi executado emulador ou jogo no ambiente Linux da nuvem. O inventário [observed-overlays.json](observed-overlays.json) tem zero sessões e zero overlays observados. Os 140 itens de [static-candidates.csv](static-candidates.csv) vieram exclusivamente da investigação anterior e permanecem `not_seen`.

Este diretório complementa o [plano anterior](../overlay-validation.md), preservado como documento histórico. O contrato implementado é a [versão 2](trace-v2.md); o esboço `../trace-format.md` não descreve um capturador existente naquela etapa.

## Ferramentas avaliadas e escolha

Foram lidos os fontes oficiais nas revisões registradas em [emulator-sources.json](emulator-sources.json). São revisões de desenvolvimento consultadas, sem afirmação sobre a versão estável mais recente.

| Ferramenta | Evidência verificada no fonte | Adequação e limite |
| --- | --- | --- |
| Project64 `24376e868350792a181d2121fec20d37354559d6`, Windows, `jsapi-2` | `events.onexec`, `onopcode`, `onwrite`, `onpidma`, `onsptask`, `onpifread`; acesso a GPRs, memória e arquivos | Escolhido: scripting no debugger, sem patch da ROM ou do emulador. Hooks de CPU exigem interpretador. Fonte Win32/Windows do debugger não é executável Linux. |
| Mupen64Plus core `ba95bab92a76744753bfe61470823a4937850ab0` | `DebugSetCallbacks`, stepping, breakpoints, `DebugMemRead*`, registradores/memória; PI em `src/device/rcp/pi/pi_controller.c` | Alternativa para automação Linux: exige frontend próprio, build `DEBUGGER=1`, SDL2 e plugins. A API pública consultada não oferece um hook PI/OSTask equivalente; rastreamento completo precisaria combinar stepping/watchpoints ou adicionar hooks no core. Não foi compilado ou executado. |

Nesta máquina não foram encontrados `mupen64plus`, `retroarch`, `wine`, `Xvfb`, `xvfb-run` ou `sdl2-config`; `DISPLAY` não está configurado e não há `/dev/dri`. Esses fatos impedem executar diretamente o método Windows escolhido nesta sessão. Não demonstram impossibilidade de preparar futuramente um emulador Linux com renderização por software. A alternativa autorizada pelo usuário foi aplicada: ferramentas testáveis aqui e instruções para a captura Windows.

## O que a instrumentação registra

O helper [trace.py](../../../tools/dynamic/trace.py) prepara uma sessão nova, confere a ROM por SHA-256 e registra hash do executável, revisão declarada, plugins/backends, RAM e hashes dos saves iniciais. O JavaScript confere novamente a ROM **carregada no emulador**, usando bytes lógicos N64. Uma ROM/RAM diferente encerra a captura. Nenhum byte de memória ou ROM é escrito pelo capturador.

- PI: direção, endereço de cart, destino, tamanho da API e registradores brutos. `PIEvent.length` já contém `registro+1`; o script não soma novamente. Cart→RAM corresponde a `direction=0`.
- Materialização: no próximo callback de CPU após o evento PI, calcula hashes da RAM e do trecho ROM. No fonte fixado a cópia acontece sincronicamente dentro de `PI_DMA_WRITE`, **depois** do hook PI e **antes** do próximo passo da CPU. Isso confirma disponibilidade dos bytes no emulador, sem afirmar término do timer/IRQ de PI.
- Wrapper `0x80098640`: ROM/destino/tamanho em `a0/a1/a2`, `ra` e `sp`. Retorno somente no `ra` capturado com a pilha restaurada, depois de `0x800986E8` e seu delay slot `0x800986EC`. Chamadas em `0x800A4F70`/`0x800A2BC0` são registradas como candidatas SDK quando existe wrapper pendente.
- PC: primeira observação de cada PC físico/geração/contexto; também reconhece KSEG1. Cada marcador reinicia essa deduplicação. Não é uma listagem de todas as instruções nem uma contagem de frequência.
- `jalr`/`jr` não-retorno: primeira combinação origem/geração/destino/contexto. Destino amostrado antes do delay slot; um evento separado verifica o PC após os dois passos seguintes. Exceções/interrupts podem impedir a confirmação. Retornos `jr ra` comuns são omitidos.
- Escritas da CPU: intervalos que atingem imagens com origem ROM confirmada e o BSS residente anterior. São tentativas antes da instrução; stores condicionais/unalinhados invalidam conservadoramente. Escrita no slot `0x80120898` tem evento próprio.
- RSP: `onsptask` registra o descritor recebido em DMEM `0xA4000FC0`, tipo, flags, ponteiros e tamanhos dos microcódigos; calcula hashes quando o intervalo é válido e o tamanho declarado é positivo. Uma submissão SP DMA para esse descritor pode fornecer `task_ptr`; a função CPU que criou a tarefa continua desconhecida.
- Contexto: sequência, passos de CPU, marcadores aplicados, relógio civil do host, confirmações de VI e leituras PIF. São medidas diferentes. `vi_count`, tempo monotônico e identidade da thread permanecem `null`.
- Controle: respostas reais de leitura de botões/analógicos do PIF, após `ControlRead()` no fonte consultado. Não exporta EEPROM, controller pak, display lists, imagens ou payloads binários. O log de entradas ajuda a comparar repetições; não há replay automático implementado.

## Comparação e classificação

O analisador de traces usa somente `reports/evidence/ozumo2.json`, o CSV de funções de spimdisasm e os mapas anteriores. Registra também os hashes do CSV de memória e de `config/splat/ozumo2.yaml`. Não chama Splat, spimdisasm ou `make analyze`.

Cada PI materializado cria uma identidade própria `(ROM, tamanho, destino, transfer_id)`. Um PC só recebe essa identidade se os hashes corresponderem à ROM original e todos os quatro bytes da instrução ainda pertencerem a um intervalo válido. O analisador reconstrói as invalidações independentemente do ID declarado no trace. Tentativas de escrita e novas cargas retiram apenas os intervalos afetados; há uma margem conservadora para alinhamento PI.

Na troca B→A em `0x8012C860`, o trecho final de B pode continuar contendo bytes antigos. O relatório distingue esses intervalos residuais, marca `partial_overwrite_unresolved` e **não comprova que o módulo B ainda esteja semanticamente ativo**. Não usar essa sobra para gerar automaticamente seções ou chamadas de N64ModernRuntime.

| Estado | Significado |
| --- | --- |
| `not_seen` | Nenhuma transferência compatível vista; não exclui a hipótese estática. |
| `loaded_not_executed` | Hash válido, sem PC correlacionado no período observado. Pode ser código ainda não usado, dados ou imagem mista. |
| `executed` | Pelo menos um PC observado dentro de bytes válidos dessa origem. Não confirma todas as funções ou a fronteira integral do módulo. |
| `mismatch` | Hash de RAM/ROM divergente; a imagem não pode fundamentar atribuição de código. |
| `data_only` | Reservado para classificação manual com consumidores e cobertura suficientes; o analisador nunca o infere da ausência de PC. |

Uma transferência PI em partes pode coincidir com parte de um mapeamento estático, desde que a transformação ROM→RAM seja a mesma. `visible_transfers`/`executed_transfers` contam transferências, não módulos nem cobertura de todos os bytes. A correlação wrapper↔PI usa intervalo temporal e mapeamento; permanece candidata sem identidade de thread/fila. Camadas wrapper/SDK/PI não são somadas como cargas independentes.

Os microcódigos são comparados por hash do componente ativo e offset ROM. Assinaturas das nove variantes anteriores só são associadas se estiverem dentro do intervalo efetivamente referenciado. Seleção de um microcódigo não demonstra que HLE o implementa corretamente.

## Reproduzir e próximos critérios

Siga [windows.md](windows.md) para boot frio → menus → início de luta → retorno, com entradas e saves controlados. Preserve todos os arquivos em `local/traces/ozumo2/`; o resumo cria um diretório novo a cada execução. O [contrato JSONL](trace-v2.md) define eventos e limites de interpretação.

Antes de uma prova limitada de recompilação ainda faltam:

1. Capturas reais em dois boots frios, com os quatro contextos mínimos e identificação dos seus acionadores.
2. Encontrar o fluxo normal A→B→A e conferir origem, hashes, PCs e sobrescritas nas três gerações.
3. Separar funções efetivamente executadas, BSS/relocações e recursos consumidos. Nenhum dos 140 candidatos está validado dinamicamente nesta entrega.
4. Resolver thread/fila, término real de PI, TLB e escritas iniciadas pelo RSP; os hooks de CPU não cobrem todos esses casos.
5. Identificar as funções de criação de OSTask e microcódigos realmente usados, confrontando HLE com RSP LLE quando necessário.
6. Medir VIs reais por outro hook verificado; `vi_ack_count` não substitui o critério anterior de 600 VIs. A simulação permanece na velocidade original.

O teste sintético possui bytes próprios e não gera um arquivo de captura real. Consulte [validation.md](validation.md) para os checks executados.
