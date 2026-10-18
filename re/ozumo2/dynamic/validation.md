# Verificação da instrumentação — 18/10/2026

**Nenhum emulador ou jogo foi executado. Não existem traces reais desta tarefa.** A validação abaixo demonstra o funcionamento dos helpers com dados sintéticos próprios e a conservação da investigação anterior. A execução Windows permanece por realizar.

| Check executado | Resultado |
| --- | --- |
| `make test` antes da implementação | 16 testes anteriores aprovados |
| `make test` com a instrumentação | 37 aprovados: 11 da análise anterior, 20 da captura/correlação sintética, 6 da auditoria Git |
| `make test-dynamic` | 20 testes sintéticos aprovados, sem ROM comercial ou emulador |
| `make verify` | Aprovado para as duas ROMs/artefatos retidos. Verifica o manifesto histórico de 118 comandos, sem executá-los novamente |
| Harness JavaScript em Node `v24.19.0` | Aprovado, 22 assertions; `real_emulator_executed=false` |
| Mesmo harness em Duktape 2.6.0 do fonte Project64 fixado | Aprovado, 22 assertions; memória e callbacks continuam sendo mocks |
| Preservação dos originais | SHA-256 idêntico em 996 arquivos preexistentes de `reports/`, `export/`, `config/splat/`, `baseroms/`, `generated/`; metodologia, relatório fornecido e `config/roms.json` também idênticos ao Git anterior |
| Auditoria do índice Git | `make check-publish` aprovado; fontes/documentos permitidos, sem ROMs, assets, captures brutas ou binários |

A suíte cobre PI submetido sem dados visíveis, hash divergente, aliases KSEG, A→B→A, substituição parcial com cauda residual, alterações em código, reset, gerações incompatíveis, retorno RA/SP, correspondência de funções por ROM/RAM e consumo RSP. Confere também fronteiras de padding de SHA-256 contra `hashlib`, callbacks antes/depois de delay slots, Unicode, encerramento, preparação idempotente por rejeição de IDs existentes e resumos em diretórios novos sem modificar o trace de entrada.

`capture_status=synthetic_test` não pode ser promovido a captura real mudando somente o manifesto: o início do trace precisa ter a mesma proveniência. Os eventos do harness JavaScript permanecem em memória e somente seu resultado resumido é emitido. Fixtures Python ficam em diretórios temporários de teste e são identificadas como sintéticas.

## Reproduzir os checks

No ambiente de análise preparado:

```sh
make test
make verify
make test-dynamic
.venv/bin/python tools/dynamic/check_adapter.py
make check-publish
```

Os dois testes que executam JavaScript usam Node quando disponível; sua ausência gera `skipped`, sem converter isso em aprovação da compatibilidade JS. Os testes de correlação Python não dependem de Node ou das ROMs. No Windows, os helpers usam `py -3`; a auditoria precisa de Git instalado.

O check adicional do Duktape foi feito com o próprio engine da revisão oficial consultada, sem modificar seu fonte:

```sh
git clone https://github.com/project64/project64.git .tools/src/Project64
# Se o clone já existir, reutilizá-lo após conferir o estado; não sobrescrever trabalho local.
git -C .tools/src/Project64 checkout --detach 24376e868350792a181d2121fec20d37354559d6
g++ -O2 -fPIC -shared .tools/src/Project64/Source/3rdParty/duktape/duktape.cpp tools/dynamic/duktape_timeout.cpp -o .tools/liboztrace-duktape.so -lm
.venv/bin/python tools/dynamic/check_adapter.py --duktape-library .tools/liboztrace-duktape.so
```

O build usou GCC/G++ 14.2.0 no Linux. O fonte do engine usa `DukTimeoutCheck`, fornecido pelo host Project64; o pequeno callback próprio acima limita apenas o harness standalone a 30 segundos. Isso **não compila o emulador**, não testa plugins e não executa instruções do jogo. A biblioteca e o clone ficam ignorados em `.tools/`.

A etapa de resumo também foi exercitada de ponta a ponta com fixtures próprias, produzindo JSON/CSV/Markdown em diretório temporário, sempre como `synthetic_test`. Nenhum desses resultados foi adicionado ao inventário de overlays reais.

## Limites que continuam abertos

- Build e execução do Project64 no Windows, integração real dos callbacks e custo de captura.
- Módulos efetivamente carregados/executados em cada cena; todos os 140 mapeamentos continuam `not_seen` no inventário entregue.
- Função de criação de OSTask, seleção real de microcódigos, queue/thread e término de PI por mensagem/IRQ.
- Stores com êxito arquitetural, BSS por overlay, TLB, escritas iniciadas pelo RSP, contador VI real e replay de entradas.
- Compatibilidade de um futuro port/recompilação; esta tarefa não compila o jogo nem altera as ROMs.

Nenhum resultado estático anterior foi regenerado, renomeado ou substituído. O índice Git inclui somente a instrumentação própria, documentação/inventário textual e alterações de proteção contra publicação acidental. O commit desta etapa é local; não há push automático.
