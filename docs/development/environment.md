# Ambiente e ferramentas de recompilação

Revisões consultadas em **18/10/2026** pelos repositórios oficiais. São versões Git fixadas, não números de release inventados. As pontas `main` observadas nesta data foram:

| Componente | Revisão selecionada | Uso |
| --- | --- | --- |
| [N64Recomp](https://github.com/N64Recomp/N64Recomp/tree/ffb39cdad1da5de07eaaa48bd1db4a89a7986771) | `ffb39cdad1da5de07eaaa48bd1db4a89a7986771` | CLI de CPU e `RSPRecomp` |
| [N64ModernRuntime](https://github.com/N64Recomp/N64ModernRuntime/tree/cdf5abbd5026fef5c364c676e4667c45e42b6863) | `cdf5abbd5026fef5c364c676e4667c45e42b6863` | Bibliotecas estáticas `ultramodern` e `librecomp` |
| N64Recomp dentro do runtime | `81213c1831fab2521a6a5459c67b63437d67e253` | Dependência escolhida pelo upstream do runtime; não substituída pelo CLI mais novo |

O [lock](../../config/toolchain.lock.json) registra também **todos os submódulos recursivos**. Novas versões devem ser avaliadas explicitamente, em vez de atualizar `main` em cada build. Consultar o código/CMake/CI da revisão fixada é necessário: o README do recompilador ainda descreve funcionalidades atuais como futuras.

## Dependências verificadas

- CMake mínimo upstream: 3.20; escolhido e testado **3.31.10**. A série 3 atende o mínimo e evita introduzir mudanças de políticas da série 4 nesta base.
- Pacote Ninja **1.13.2**; o executável instalado identifica-se como `1.13.2.git.kitware.jobserver-pipe-1`.
- C++20; C17 para a saída do recompilador. Nesta máquina: GCC/G++ **14.2.0**, Python **3.12.14**, Debian 13 x86-64.
- Git HTTPS com TLS e autenticação já fornecidos pelo ambiente; nenhuma credencial adicional é necessária para clonar esses upstreams públicos.
- N64Recomp: Rabbitizer, ELFIO, fmt, tomlplusplus e sljit, como submódulos nas revisões do lock. Não confundir Rabbitizer C/C++ do upstream com o pacote Python da análise.
- N64ModernRuntime: N64Recomp e seus submódulos, miniz, xxHash e o1heap; concurrentqueue, JSON e sse2neon também fazem parte da árvore upstream. As bibliotecas não exigiram SDL/Vulkan/RT64 para esta compilação isolada.

N64Recomp é distribuído sob MIT; o runtime contém `COPYING` da GPL versão 3. Consultar os arquivos de licença e os termos das dependências ao preparar uma distribuição. Nenhum código de terceiros foi copiado para os arquivos rastreados deste projeto.

## Instalação Linux testada

Use o checkout existente, sem criar worktrees adicionais. Os ambientes de análise e desenvolvimento são separados:

```sh
# Análise anterior: mantém as versões já fixadas, sem executar make analyze.
make setup
make test
make verify

# Ferramentas nativas: CMake/Ninja em um segundo venv, com hashes de pacotes.
make setup-native
make upstream
make smoke-recompiler
```

`make upstream` usa dois jobs, compila apenas `N64RecompCLI`, `RSPRecomp`, `ultramodern` e `librecomp`, e preserva saídas válidas para builds incrementais. Não lê ROMs, não gera código do jogo e não abre emulador. A máquina tem cinco CPUs e aproximadamente 33 GiB de RAM; essa paralelização é suficiente para o escopo. Não é um build de aplicação ou de renderizador.

As fontes vão para `.tools/src/`, os builds para `.tools/build/` e os logs para `.tools/logs/`. Todos são ignorados. O script recusa revisão diferente, modificações locais, origem inesperada ou submódulos fora do lock; não executa reset sobre trabalho existente. Para mudar de compilador ou de árvore de fontes, usar um diretório de build novo para não misturar caches CMake. Se uma árvore existente não corresponder ao lock, preservá-la e usar uma instalação separada.

Repetir `make setup-native` e `make upstream` é suportado. `tools/setup.sh` continua cuidando somente da análise anterior. As fontes upstream podem ser obtidas novamente a partir do lock; nada depende de copiar os binários da máquina atual.

Logs locais:

```text
.tools/logs/N64Recomp-configure.log
.tools/logs/N64Recomp-build.log
.tools/logs/N64ModernRuntime-configure.log
.tools/logs/N64ModernRuntime-build.log
.tools/build-status.json
.tools/smoke/recompiler/result.json
```

`make verify` usa os artefatos estáticos **já existentes** e não reroda a análise. Em um clone sem ROMs/outputs locais, poderá falhar por falta dessas entradas; `make test` e o teste sintético upstream são independentes das ROMs. Uma cópia de CSV não substitui os artefatos exigidos pelo verificador anterior. Não rerodar as duas ROMs para contornar essa ausência sem uma tarefa que o autorize.

## Preparação Windows x64 — instruções não executadas nesta máquina

Instalar Git, Python 3.12 e Visual Studio 2022 com Desktop development with C++, Windows SDK e ferramentas LLVM/Clang. Abrir Developer PowerShell para x64. A CI do runtime usa `clang-cl`, Ninja e as flags de exceptions abaixo; não se afirma validação Windows local.

```powershell
py -3.12 -m venv .tools/venv
.tools/venv/Scripts/python.exe -m pip install --require-hashes -r tools/development/requirements.lock
.tools/venv/Scripts/python.exe tools/development/build_upstream.py --jobs 2 --c-compiler clang-cl --cxx-compiler clang-cl --cxx-flags="-Xclang -fexceptions -Xclang -fcxx-exceptions"
```

O script chama CMake/Ninja do mesmo venv. Os targets de ferramentas/bibliotecas são os mesmos do Linux. Para a futura aplicação, usar `add_subdirectory` de N64ModernRuntime, ligar `librecomp`/`ultramodern` e implementar os callbacks do host. A construção de uma aplicação Windows, o renderer, a camada de áudio/entrada e o empacotamento ainda não foram executados. Não há teste de gameplay ou compatibilidade gráfica nesta preparação.

## Uso real do CLI e formatos

`N64Recomp` sem argumentos mostra a sintaxe `N64Recomp <config file> [--dump-context]`; não existe uma versão semântica verificada por `--version`. A versão deste projeto é o SHA do lock.

O código da revisão fixada aceita **um ELF ou um arquivo de símbolos TOML**, não ambos. Ao usar símbolos, exige `rom_file_path`. `symbols_file_path`, `output_func_path` e os demais caminhos são relativos ao TOML de configuração. Um CSV de spimdisasm ou uma configuração Splat não pode ser passado diretamente como arquivo de símbolos.

O teste [smoke_recompiler.py](../../tools/development/smoke_recompiler.py) fornece uma entrada executável mínima:

```toml
[input]
symbols_file_path = "symbols.toml"
rom_file_path = "synthetic.bin"
output_func_path = "output"
functions_per_output_file = 1
```

O arquivo de símbolos usa `[[section]]` com `rom`, `vram`, `size`, `name` e uma lista `functions`, cujos elementos possuem `name`, `vram` e `size`. O default atual agrupa **50 funções por arquivo**, apesar de o README mencionar uma função por arquivo. O teste escolhe 1 explicitamente, compila o C com `recomp.h` upstream e espera `v0=43`, incluindo o delay slot do retorno. A entrada contém 12 bytes escritos para o teste, sem bytes dos jogos.

Uma futura prova do jogo deve começar pelos limites confirmados de uma unidade, preservar seções distintas para overlays sobrepostos e resolver alvos externos. O resultado de recompilar uma função sintética não demonstra que o jogo, os microcódigos, o loader ou a ABI completa do runtime estejam validados.

## Pontos de integração que exigem confirmação dinâmica

No runtime fixado:

- `librecomp` fornece PI DMA e APIs `load_overlays`/`unload_overlays`. **`do_rom_read` copia bytes, mas não chama automaticamente essas APIs para cada carga dinâmica.** O jogo precisará de integração baseada nos carregamentos confirmados.
- `unload_overlays` recusa descarregar parcialmente uma seção. Alternar uma imagem maior por outra menor no mesmo endereço requer conhecer o ciclo de vida da imagem inteira, não descarregar somente o tamanho da nova carga.
- O bootstrap genérico registra overlays e copia o primeiro MiB da ROM. Verificar que isso não registra imagens alternativas em endereços lineares que não correspondem às cargas reais do jogo.
- Há TODOs upstream para DMA assíncrono e desalinhado. O código atual exige origem par e destino RDRAM alinhado a 8 bytes; observar as chamadas reais antes de presumir compatibilidade.
- `osGetMemSize_recomp` retorna 8 MiB. A memória e o comportamento de boot do original precisam ser medidos; não assumir uso original de Expansion Pak ou alterar o perfil de memória sem avaliação de fidelidade.
- `ultramodern` fornece threads, filas, timers, VI, áudio, controle e gestão RSP; espera callbacks e renderer do projeto. A presença de APIs de overlays/mods não valida os metadados ou hooks específicos deste jogo.

Esses pontos vieram da leitura do upstream, não de nova investigação das ROMs. O [plano dinâmico](../../re/ozumo2/overlay-validation.md) transforma-os em critérios de aceitação.
