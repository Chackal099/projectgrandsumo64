# Validação da preparação nativa — 18/10/2026

Escopo executado: inspeção dos scripts/configurações/documentos existentes, checagem da análise preservada, instalação/build de ferramentas upstream e organização para a próxima etapa. Não foi executado `make analyze`.

## Resultados observados

| Verificação | Resultado nesta máquina |
| --- | --- |
| `make test`, antes das alterações | 11 testes existentes aprovados |
| `make test`, com o verificador de publicação | 16 testes aprovados: 11 anteriores e 5 novos |
| `make verify` | Aprovado para ambas as ROMs e os artefatos existentes; confere o manifesto anterior de 118 comandos, sem executá-los novamente |
| Preservação da análise | SHA-256 idêntico em 999 arquivos preexistentes: relatórios, documentos, exportação, configurações Splat/ROMs, ROMs e outputs gerados |
| `make setup-native` | CMake 3.31.10 e pacote Ninja 1.13.2 instalados por lock com hashes; repetição aprovada |
| `make upstream` | `N64RecompCLI`, `RSPRecomp`, `ultramodern` e `librecomp` compilados com GCC/G++ 14.2.0 |
| Repetição do build upstream | Aprovada; Ninja informou `no work to do` para as duas árvores |
| Obtenção a partir de árvore vazia | Fetch do SHA de N64Recomp e inicialização recursiva dos submódulos aprovados pelo helper; versões conferidas com o lock |
| `make smoke-recompiler` | Uma função sintética traduzida, C17 compilado e executado; `v0=43`, incluindo o delay slot do retorno |
| Pontos do plano | `0x80093510`, `0x800986E8` e `0x800986EC` conferidos no assembly anterior já existente |

`make verify` confirmou novamente 2.925 funções inferidas/49 regiões do primeiro jogo e 2.378/67 do segundo, a partir dos artefatos anteriores. Essas quantidades continuam sendo heurísticas da análise estática, não novas confirmações dinâmicas.

As revisões são as do [lock de ferramentas](../../config/toolchain.lock.json). O ambiente de análise continua em `.venv/`; as novas ferramentas ficam em `.tools/venv/`. Os logs/recibos de build e o resultado do teste sintético estão em `.tools/`, conforme [a documentação do ambiente](environment.md).

## Limites do que foi validado

- Os builds e o teste sintético foram executados em Linux x86-64. Não houve build local ou execução Windows; as instruções Windows foram preparadas a partir do CMake/CI upstream.
- Compilar bibliotecas estáticas não valida callbacks, áudio, controle, renderer ou ligação de um executável de jogo.
- O teste sintético usa 12 bytes próprios. Não recompila uma função de nenhuma das ROMs e não valida toda a compatibilidade entre o CLI mais novo e o N64Recomp embutido no runtime.
- Não houve emulador, captura de DMA/PC, validação de overlays, extração nova de assets, nova investigação comparativa ou alteração de bytes das ROMs.
- O template de sessão permanece `not_captured`. As etapas e critérios seguintes estão no [plano de overlays](../../re/ozumo2/overlay-validation.md).

## Preparação Git

O pipeline Python, seus testes e as configurações Splat existentes estavam fora do versionamento; a preparação inclui esses arquivos sem regenerar seus resultados. A referência documental anterior permanece nos commits ancestrais `9304b0e5bffa` e `579871b67d76`.

`make check-publish` audita o índice Git real, não só a árvore de trabalho. Os cinco testes novos verificam preservação dos CSVs históricos, rejeição de assinatura de ROM renomeada, distinção entre conteúdo staged/unstaged e bloqueio de código gerado/capturas privadas. `.gitignore` também cobre dependências, builds, binários, ROMs, saves e dumps locais.

O novo commit deve conter somente fontes, configurações e documentação. Não inclui as árvores `.tools/`, `local/`, `baseroms/` ou `generated/`, nem as bibliotecas/executáveis compilados.
