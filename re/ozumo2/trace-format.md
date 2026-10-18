# Contrato proposto dos traces

Formato proposto para a próxima captura: JSON Lines UTF-8 em `local/traces/ozumo2/RUN_ID/events.jsonl`, acompanhado de uma cópia preenchida de `session.template.json`. Não há capturador ou resultados de emulação nesta fase.

Cada registro terá `schema_version=1`, `run_id`, `sequence` inteiro estritamente crescente, `event`, `host_time_ns` monotônico e `vi_count` quando observável. O relógio host ordena a coleta, não define tempo da simulação. Campos desconhecidos devem ser `null`, não números fictícios. Endereços usam strings `0x` com oito dígitos hexadecimais; tamanhos e contadores usam inteiros.

| Evento | Campos específicos |
| --- | --- |
| `dma_submit` | `transfer_id`, `thread_id`, `pc`, `caller_ra`, registradores brutos, origem cart bruta, `rom_start`, `dest_vram`, `dest_physical`, `byte_count`, direção, fila e camada de observação (wrapper/SDK/PI) |
| `dma_complete` | `transfer_id`, origem da confirmação, `ram_sha256` em ordem lógica N64, `rom_slice_sha256`, status observado ou `null`, geração de carga |
| `exec` | `pc`, thread, imagem/geração ativa e origem do salto; vincular somente após carga confirmada |
| `bss_clear` | Intervalo RAM semiaberto, PC de escrita, thread e geração correlacionada quando conhecida |
| `overwrite` | Intervalo RAM escrito, PC/causa, imagens atingidas; não implica automaticamente invalidação integral |
| `rsp_task` | Ponteiro/tipo OSTask, endereços/tamanhos/hash dos microcódigos, VI e thread; payload comercial permanece local |
| `marker` | Nome do cenário/transição e referência à gravação de controle |

Uma chamada do wrapper pode resultar em mais de uma transação PI; correlacionar sem duplicar uma carga só por observá-la em três camadas. A mensagem de conclusão precisa pertencer à operação, não a outra thread ou fila. Execução anterior ao término deve ser registrada como divergência em vez de corrigida na gravação.

O arquivo de sessão registrará revisão exata do emulador, modo CPU, backends, bytes de RAM, saves iniciais e a gravação de inputs. O formato de eventos é um contrato para o futuro adaptador; não é um script baseado em uma API de emulador que ainda não foi verificada.

Metadados derivados podem ser versionados após revisão. RAM, savestates, texturas, áudio, display lists completos e quaisquer bytes extraídos da ROM não devem ser adicionados ao Git.
