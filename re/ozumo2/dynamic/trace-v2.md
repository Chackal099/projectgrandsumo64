# Contrato implementado de captura — versão 2

Este contrato sucede o esboço de versão 1 de `../trace-format.md`, sem converter ou reescrever capturas antigas. Nesta entrega não existem capturas reais para converter.

Uma sessão preparada contém `session.json`, `capture.js` e, quando o emulador for executado, `events.jsonl`. O manifesto inicialmente tem `state=prepared_not_captured`. Preparação não demonstra execução. O script gerado e o executável possuem SHA-256 no manifesto. Só a execução do script cria `events.jsonl`; ele se recusa a reutilizar um caminho existente.

## Campos comuns

JSONL ASCII válido como UTF-8, uma linha por evento. Strings Unicode são escapadas. Endereços são strings `0x` com oito dígitos; tamanhos são inteiros em bytes; intervalos são semiabertos.

- `schema_version=2`, `run_id`, `sequence`: sequência contígua desde 1.
- `event`, `context`: tipo e último marcador aplicado.
- `cpu_step`: contador de callbacks de CPU, sem reiniciar durante resets. Não é ciclo R4300, tick de jogo ou quantidade de instruções retiradas.
- `host_wall_ms`: `Date.now()`, sujeito a ajustes de relógio. `host_time_ns=null`: a API usada não fornece relógio monotônico verificado.
- `vi_count=null`, `vi_ack_count`: tentativas de escrita em VI_CURRENT, separadas de uma contagem real de VIs.
- `pif_read_count`: leituras PIF observadas; não é frame.
- `thread_id=null`: pilha/RA não fornecem identidade de OSThread.

## Eventos

| Evento | Campos relevantes / semântica |
| --- | --- |
| `capture_start` | `source_kind=emulator`, ROM carregada/hash/tamanho, RAM, API/revisão declarada, modo interpretador, observação de stores habilitada. Primeiro evento obrigatório. |
| `dma_submit` | `transfer_id`, `layer=PI`, `direction`, `cart_address`, `dest_vram`, `byte_count`, `pc`, `caller_ra`, três registradores PI brutos. `byte_count` da API já é registro+1. |
| `overwrite` | Intervalo físico e causa: margem de alinhamento de PI ou SI→RAM. Retira proveniência anterior antes de atribuir nova imagem. |
| `dma_visible` | Mesmo ID de PI, `rom_start`, destino/tamanho, hashes RAM/ROM; `completion_source=next_cpu_step_after_pi_callback`, `hardware_completion=false`. Não é confirmação de IRQ. |
| `resident_visible` | Snapshot da imagem inicial `[ROM 0x1000,0x4AF50)` em `0x80080400`, na primeira entrada após armar/resetar. Mesma verificação de hashes; não inventa uma transferência PI anterior ao início da captura. |
| `wrapper_submit` / `wrapper_return` | ID da invocação, argumentos originais, RA/SP; retorno no RA com SP correspondente, `v0` bruto sem significado de status presumido. |
| `sdk_call` | PC e nome candidato de rotina SDK, `a0..a3`, RA/SP quando há wrapper pendente; não identifica thread/fila. |
| `exec` | `pc`, `image_id` ou `null`. Primeiro dispatch por PC/geração/contexto; código ainda não foi retirado pela CPU no momento do hook. |
| `indirect` | `branch_id`, PC, alvo antes do slot, registrador, `jalr`/`jr`, `target_observed=false`, `delay_slot_pending=true`. Deduplicado por origem/alvo/gerações/contexto. |
| `indirect_outcome` | ID anterior, PC observado dois passos depois, `target_observed`; sem afirmar sucesso quando interrupt/exception desviou o fluxo. |
| `write_attempt` | PC, intervalo físico, valor zero ou não, candidato BSS, conservador ou não, `committed=false`. Não confirma limpeza de BSS ou êxito de SC. |
| `callback_write` | Store tentado em `0x80120898`, alvo bruto e escritor. |
| `rsp_task_upload` | Ponteiro RDRAM derivado de SP_DRAM_ADDR ao submeter DMA para DMEM 0xFC0, tipo, PC. `creation_observed=false`. |
| `rsp_task` | Descritor recebido pelo RSP, tipo/flags, ponteiros/tamanhos de boot/texto/dados, hashes dos dois últimos quando válidos. `task_ptr=null`: o evento RSP não fornece o ponteiro CPU original. |
| `input_poll` | Controle, flags de erro, máscara de botões e eixos com sinal, lidos de respostas PIF após `ControlRead`. Não é gravação/replay de todos os dispositivos. |
| `marker` | Nome, nota opcional, ID do comando **aplicado**; contexto só muda aqui, não no instante de escrever `control.json`. |
| `emulator_state` | Estado numérico da API, `memory_reset`; reset invalida todas as identidades. Abrir outra ROM/savestate encerra o capturador. |
| `boot_checkpoint` | PC de entrada `0x80080400` ou inicialização `0x80093400`. |
| `capture_stop` | Motivo, PI e wrappers pendentes. `operator` sem pendências permite `capture_status=closed`; limite de eventos, ausência do encerramento e outros motivos dão `incomplete`. |

`closed` descreve a integridade do encerramento do arquivo. Não significa cobertura de cenários, ciclo de vida de módulos ou compatibilidade do jogo. Sessões de teste sintético permanecem `source_kind=synthetic_test`, `capture_status=synthetic_test`; o harness não salva seus eventos como capturas.

O validador rejeita identidade ROM incompatível, IDs duplicados, submissões inconsistentes, sequência incorreta, geração alegada divergente, eventos após encerramento e JSON truncado. Um arquivo interrompido em linha completa pode ser analisado como incompleto. Não o conserta ou reescreve automaticamente.

## Resultados derivados

`summary-ID/overlays.json` contém gerações com ROM/RAM/tamanho, hashes conferidos, primeiras/últimas **observações** de execução por sequência, funções inferidas anteriores atingidas, contextos, invalidações, intervalos remanescentes, tarefas RSP e chamadas indiretas. Não contém bytes comerciais. Inclui hashes das fontes estáticas e do trace.

`static-comparison.csv` conserva os 140 mapeamentos como hipóteses e acrescenta contadores/status; `observations.md` lista apenas gerações com PC e hash válidos. Imagens carregadas podem misturar CPU, RSP e recursos. A ferramenta não transforma uma função inferida pelo spimdisasm em nome/função confirmado por mera proximidade de endereço.
