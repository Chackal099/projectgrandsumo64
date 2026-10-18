# Capturar no Windows — Project64

**Estas instruções ainda não foram executadas no Windows.** O adapter foi exercitado apenas com memória/eventos sintéticos, inclusive no Duktape do fonte consultado. Nenhuma cena ou overlay do jogo foi observado na nuvem.

## 1. Preparar ferramentas e isolamento

Use um clone deste repositório contendo os novos helpers, Python 3.10+ (`py -3`) e a ROM original já investigada em `baseroms/ozumo2.z64`. Não execute `make analyze`. O helper usa somente a biblioteca padrão Python; Splat, spimdisasm e N64Recomp não são dependências da captura. Node LTS é opcional para o harness sintético.

Use Project64 com debugger e **API `jsapi-2`**. A revisão de referência é `24376e868350792a181d2121fec20d37354559d6`. Prefira compilar exatamente esse fonte; um binário diferente exige registrar sua revisão real e conferir as APIs/ordem dos hooks. `--emulator-revision` é uma declaração do operador, não uma leitura automática do SHA Git do executável; seu hash binário é registrado separadamente.

Com Git e Visual Studio com a carga *Desktop development with C++* e Windows SDK:

```powershell
git clone https://github.com/project64/project64.git C:\n64tools\Project64-src
git -C C:\n64tools\Project64-src checkout --detach 24376e868350792a181d2121fec20d37354559d6
git -C C:\n64tools\Project64-src submodule update --init --recursive
```

Abra `Project64.sln` e compile o projeto Windows Project64 e suas dependências. O [guia upstream](https://github.com/project64/project64/blob/24376e868350792a181d2121fec20d37354559d6/Docs/BUILDING.md) cita VS 2015/2017/2019; `PropertySheets/Platform.props` seleciona o toolset instalado, com v142 ou posterior sem sufixo `_xp`. Compatibilidade/build no seu Visual Studio e disponibilidade dos plugins devem ser verificados no Windows. Não há binário Project64 produzido por esta tarefa. Saídas configuradas pelo fonte ficam sob `bin\PLATAFORMA\CONFIGURACAO\`; escolha um conjunto de executável/plugins da mesma arquitetura.

Mantenha uma instalação/configuração de captura separada, em um caminho simples como `C:\n64tools\Project64-capture`. O `fs` do debugger usa `fopen`; caminhos ASCII evitam diferenças de codificação do Windows. Configure saves e estados dentro de `local/` no clone. Copie os saves desejados para essa instalação; não sobrescreva saves pessoais. Se começar sem save, registre `--empty-save` e use uma pasta efetivamente vazia. Cada repetição precisa restaurar essa mesma condição inicial, em outra sessão/pasta.

Em Settings/Options, habilite as opções avançadas/debugger e **Always use interpreter** (ou selecione CPU Interpreter nas opções do jogo). Desabilite cheats, enhancements, patches, overclock e alterações de velocidade; use escala de tempo original. Configure explicitamente 4 ou 8 MiB conforme o experimento, sem concluir por isso qual RAM o hardware original exigia. Registre nomes, versões e configurações dos plugins de gráficos, áudio, RSP e controle. Comece sem savestate e desabilite auto-start ao abrir a ROM para armar o script antes da execução.

## 2. Criar sessão e armar o script

A partir da raiz do clone, ajuste caminhos e nomes dos backends aos **realmente usados**:

```powershell
$runId = "S0-boot-menu-luta-retorno-01"
$runDir = Join-Path (Get-Location) "local\traces\ozumo2\$runId"
$project64 = "C:\n64tools\Project64-capture\Project64.exe"
py -3 tools/dynamic/trace.py prepare --run-id $runId --emulator-exe $project64 --rdram-mib 4 --empty-save --backend "GFX: NOME E VERSAO" --backend "Audio: NOME E VERSAO" --backend "RSP: NOME E VERSAO" --backend "Input: NOME E VERSAO"
```

Substitua `--empty-save` por `--save "caminho\save.eep"` repetido para cada save inicial quando aplicável. Salve também uma cópia dos arquivos de configuração em `$runDir`; registre hashes deles antes da sessão, por exemplo com `Get-FileHash -Algorithm SHA256`. O helper não copia saves/configuração nem altera o perfil do emulador. Arquive esses arquivos locais para reproduzir a configuração, sem incluí-los no Git.

A preparação cria somente `session.json` e `capture.js`. IDs existentes são rejeitados. Abra a ROM correta com a CPU parada. Copie `capture.js` para a pasta **Scripts** da instalação usada e selecione-o no debugger **Scripts**. Use o botão da própria janela para abrir a pasta Scripts correta, se a configuração a tiver movido.

```powershell
Copy-Item (Join-Path $runDir "capture.js") "C:\n64tools\Project64-capture\Scripts\ozumo2-capture.js"
```

Execute o script uma única vez. Ele lê e calcula o SHA-256 completo da ROM carregada; aguarde `OZTRACE armed` no console. Divergência de ROM/RAM, API incompatível ou exigência do interpretador devem ser resolvidas antes da captura. Não edite o script gerado depois da preparação: seu hash é conferido no resumo. Não reinicie o script no mesmo ID, pois `events.jsonl` não será sobrescrito.

Com o script armado, faça um **hard reset**, sem savestate, e retome a CPU. Verifique `resident_visible`, `boot_checkpoint` e a passagem por `0x80093400` no trace antes de tratar a sessão como evidência do boot. Caso o reset encerre os scripts na sua build, a sessão fica incompleta: use autorun do debugger/pausa antes da primeira instrução e um novo ID. Registre essa diferença; não reaproveite o arquivo como boot confirmado.

## 3. Marcar e percorrer os cenários

O helper escreve `control.json` atomicamente. O adapter lê o comando a cada 4096 callbacks de CPU. Aguarde **`OZTRACE marker applied`** antes de fazer a ação; o contexto começa quando o evento é aplicado. Se a CPU estiver pausada, retome para que ela processe o comando.

```powershell
py -3 tools/dynamic/trace.py command --run-dir $runDir --marker boot --note "hard reset; condição inicial do save registrada"
py -3 tools/dynamic/trace.py command --run-dir $runDir --marker menus --note "anotar nomes reais das opções e sequência de seleção"
```

Os dois comandos acima devem ser enviados **separadamente**, esperando a confirmação do primeiro antes de enviar o segundo. A ferramenta recusa substituir um comando ainda não reconhecido. Registre as ações e a progressão observada:

1. Boot frio até título/menu.
2. Navegação e seleção de opções/participantes, anotando os nomes reais.
3. Marcador `inicio_luta` antes da transição, depois `luta` quando ela começar; permaneça um intervalo registrado e acompanhe a contagem de VI por um recurso adicional do debugger, se disponível/verificado.
4. Marcador `retorno_menu` antes de sair pelo fluxo normal; anote resultados/transições e marque `menu_retornado` quando alcançado.
5. Inicie outra luta e procure a sequência A→B→A após identificar os acionadores. Não force a troca escrevendo na RAM.

`input_poll` registra controles lidos do PIF, mas **não reproduz as entradas automaticamente**. Documente a navegação e use o log para confrontar repetições. Não trate número de polls/VI acknowledgements como frames ou ticks. O requisito anterior de 600 VIs permanece pendente se não houver medição real adicional. Não ajuste a velocidade de simulação.

## 4. Encerrar e validar

Envie stop com a CPU ainda executando e espere a confirmação:

```powershell
py -3 tools/dynamic/trace.py command --run-dir $runDir --stop
```

Depois de `OZTRACE stopped: operator`, pare o script pela janela Scripts. Os callbacks ainda registrados ficam inertes após stop; não continue a sessão como se ela estivesse capturando. Se o stop registrar operações pendentes, produza outra sessão com encerramento fora da transição. Atingir o limite padrão de 2 milhões de eventos produz `incomplete`, sem continuar silenciosamente.

```powershell
py -3 tools/dynamic/trace.py summarize --run-dir $runDir
```

A ferramenta valida os hashes, sequência, submissões e gerações e cria `summary-ID/` com `overlays.json`, `static-comparison.csv` e `observations.md`. Cada execução cria uma pasta nova. `closed` significa encerramento sem pendências, **não cobertura completa**. JSON truncado é rejeitado; preserve o arquivo original. Ausência do evento stop deixa uma captura de linhas válidas como incompleta.

Confira antes de extrair conclusões:

- SHA-256 da ROM e do script correspondentes à sessão, CPU Interpreter e configuração de RAM/plugin/save arquivada.
- Boot checkpoints, marcadores aplicados e entradas realmente observados; ausência de `identity_mismatch`, `event_limit` ou divergências não explicadas.
- Para cada código confirmado: `dma_visible` com hash válido → `exec` no intervalo ainda válido → sobrescritas/reset explícitos. Atribuição fora do mapa e tentativa de escrita são pendências.
- Retorno do wrapper após seu delay slot; contagem wrapper/SDK/PI sem somá-las como três cargas.
- Tarefas RSP com tamanhos/hash válidos; `ucodeSize=0` permanece sem hash, sem supor automaticamente 4 KiB.
- A/B/A com ROM A `[0x58EF0,0x8FC90)`, B `[0x3D15E0,0x434580)` e destino `0x8012C860`; compare também a cauda maior de B. Esses nomes continuam hipóteses até serem observados.

Repita em outro ID, restaurando as cópias iniciais de saves e usando os mesmos plugins/configuração. Diferenças de RNG/RTC/timing devem ser anotadas, sem adulterar hashes esperados.

## 5. Desempenho e armazenamento

Interpretador + hooks de PC/stores + hashes pode ser lento. Deduplicação reduz o arquivo, sem acelerar o jogo artificialmente. Se necessário, `--no-watch-writes` serve para diagnóstico de desempenho; nesse modo o analisador conserva as cargas, mas não confirma sua origem ROM na execução. Faça a confirmação com observação de stores habilitada. Não mude para dynarec mantendo a alegação de cobertura desses hooks.

Todos os outputs, saves e configurações de sessão permanecem em `local/`, ignorado pelo Git; `.jsonl`, saves e dumps também são bloqueados pela auditoria de publicação. `make check-publish`/`py -3 tools/check_publishable.py` confere o índice antes de um commit. Só resumos textuais revisados devem ser promovidos a `re/ozumo2/`; nenhum push é feito pelos helpers.
