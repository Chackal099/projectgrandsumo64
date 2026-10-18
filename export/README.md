# Project Grand Sumo 64 — análise comparativa

Projeto de investigação estática de **64 Oozumou** e **64 Oozumou 2** para Nintendo 64, usando **Splat 0.50.1**, **spimdisasm 1.42.4** e Rabbitizer. Inclui mapas ROM/VRAM, inicialização, candidatos a overlays, comparação de funções, indícios gráficos e avaliação de recompilação por jogo. Não contém um port nem patches de ROM.

## Ler os resultados

- [Comparação e viabilidade](reports/comparacao.md)
- [64 Oozumou](reports/ozumo1.md) e [64 Oozumou 2](reports/ozumo2.md)
- [Mapa visual do jogo 1](reports/ozumo1-memory-map.svg) e [mapa do jogo 2](reports/ozumo2-memory-map.svg)
- [Método, confiança e limitações](docs/metodologia.md)
- [Metadados das ROMs](config/roms.json) e [evidências JSON/CSV](reports/evidence/)

Os números são produtos de análise estática, com limites de função e alguns limites de código inferidos. Evidências de reutilização de RAM não fornecem uma sequência de execução. As avaliações de recompilação são preliminares; não houve execução em emulador nem compilação via N64Recomp.

## Preparar e executar

Requisitos: Linux, Python 3.12 e `uv` no PATH. Use o checkout existente; tarefas na nuvem já são isoladas e não precisam de outro worktree. Não são necessários serviço web, banco de dados ou credenciais de aplicação.

```sh
cd /workspace/projectgrandsumo64
make setup
# Forneça os seus próprios arquivos; não são baixados por este projeto.
.venv/bin/python tools/import_roms.py ozumo1 '/caminho/64 Oozumou (Japan).zip'
.venv/bin/python tools/import_roms.py ozumo2 '/caminho/64 Oozumou 2 (Japan).zip'
make analyze
make verify
```

O importador também aceita `.z64` original. Os hashes esperados em `config/roms.json` são obrigatórios. Binários de outras revisões são rejeitados; não são convertidos, corrigidos ou alterados. Arquivos que já existem são validados antes de qualquer ação. Dependências estão fixadas com hashes em `requirements.lock`; `make setup` mantém a verificação TLS e de artefatos.

Na máquina preparada, as duas ROMs já foram importadas e a análise executada. Em outro clone sem os binários, o usuário precisa fornecê-los antes de `make analyze`. A publicação do ambiente preserva arquivos preparados, mas a restauração em uma nova tarefa ainda precisa ser verificada.

`make test` executa os testes do analisador sem precisar das ROMs. `make analyze` roda Splat para as imagens residentes e spimdisasm em contextos independentes para todos os prefixos de código descobertos, gera os mapas e relatórios. `make verify` verifica hashes, CRCs, contagem de funções efetivamente emitidas, resultados das ferramentas e os SVGs. Uma execução completa leva cerca de dois minutos nesta máquina; não exige compilação MIPS.

## Organização e manutenção

| Caminho | Conteúdo |
|---|---|
| `config/` | Manifesto e configurações Splat reproduzíveis |
| `tools/` | Importação, análise, relatórios, mapas e validação |
| `tests/` | Casos de MIPS/delay slots, fluxo e formatos gráficos |
| `docs/` | Método e relatório inicial recebido, preservado como referência |
| `reports/` | Relatórios e metadados derivados, sem ROMs ou assets extraídos |
| `baseroms/` | Cópias dos bytes originais, ignoradas pelo Git |
| `generated/` | Assembly, contextos, logs e manifestos de execução, ignorados pelo Git |
| `.venv/` | Ferramentas instaladas, ignoradas pelo Git |

Os mapas completos em CSV distinguem offsets ROM e endereços RAM. Todos os intervalos usam final exclusivo. Em N64, o termo VRAM aqui significa endereço virtual de execução, não uma área de vídeo dedicada. `0x80000000–0x80400000` cobre KSEG0 da RAM de 4 MiB; o alias não cacheado correspondente começa em `0xA0000000`. O mapa não comprova uso do Expansion Pak nem exige 8 MiB.

Para refinar um limite, primeiro registre a evidência, ajuste a configuração do analisador e reexecute os checks. Não acrescente nomes adivinhados ao disassembler como fatos. Qualquer port, prova de conceito de recompilação, localização ou mudança de taxa de quadros é trabalho posterior.
