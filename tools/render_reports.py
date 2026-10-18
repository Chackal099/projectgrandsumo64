#!/usr/bin/env python3
"""Write human-readable reports from evidence and explicit interpretations."""
from collections import Counter, defaultdict
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'


def hx(n):
    return f'0x{n:08X}'


def span(a, b):
    return f'`[{hx(a)}, {hx(b)})`'


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(str, r)) + ' |' for r in rows])


def game_report(game, spec, e, matches):
    core_end = spec['entry'] + spec['cpu_text_end'] - 0x1000
    ram_end = spec['bss_start'] + spec['bss_size']
    ram_groups = defaultdict(list)
    for load in e['dma_loads']:
        ram_groups[load['vram']].append(load)
    if game == 'ozumo1':
        init = ('O entrypoint `0x80000400` limpa a BSS em pares de palavras e estabelece '
                '`sp=0x8002DCC8`; salta para `0x80000450`. Essa rotina chama `0x8000CC50` '
                '(candidata a `osInitialize`), prepara uma thread com entrada `0x800004BC` '
                'e prioridade 10 pela rotina `0x8000CEE0`, e a inicia por `0x8000D030`. '
                'O reconhecimento de libultra se apoia no padrão CP0/FPU/PIF e nos argumentos '
                'e estruturas de threads; os nomes, exceto os dois pares TLB comparados, ainda são atribuições sem símbolos originais.\n\n'
                '`0x8000D8D0` e `0x8000D950` usam instruções `cache` para invalidar I/D-cache '
                'antes de carregamentos. `0x8000DA00` monta uma mensagem de DMA com origem, '
                'destino e tamanho; as rotinas chamadoras esperam a conclusão via `0x8000D3F0`. '
                '`0x8000E670` zera blocos de memória, inclusive áreas posteriores a alguns overlays. '
                'Essas sequências sustentam o carregamento direto ROM→RAM; não resolvem todos os caminhos de inicialização de cenas.')
        selected = [0x2C4D0, 0x2427A0, 0x6E14F0, 0x704090, 0x4810F0]
        examples = [0x136C08, 0x317408, 0x31F980, 0x468A20, 0x7F0288]
        overlay_note = ('ROM `0x6E14F0–0x6E1570` e `0x704090–0x704110` são stubs diferentes '
                        'carregados em `0x800A62E0`; as chamadas de DMA estão em ROM `0x1640` '
                        'e `0x1820`. A imagem maior em ROM `0x2C4D0–0x92DF0` usa a mesma base '
                        '(DMA em ROM `0x3D5C`). Há também chamadas residentes para essa área. '
                        'É evidência forte de overlays de código, além de buffers reutilizados de recursos.')
        feasibility = ('**Recompilação estática é uma linha de trabalho plausível, mas a imagem ainda não está pronta '
                       'para um recompilador automático.** O núcleo residente tem entrada/BSS/pilha bem definidos e '
                       'há código MIPS não comprimido e microcódigos gráficos identificáveis. O maior obstáculo é '
                       'a troca de imagens no mesmo endereço: um único mapa linear ou uma função por VRAM perderia contexto. '
                       'Os dois microcódigos gráficos encontrados dão um escopo inicial delimitado; seu uso efetivo e '
                       'compatibilidade com o runtime escolhido ainda precisam ser capturados.\n\n'
                       'É necessário resolver os overlays e as chamadas indiretas, separar dados embutidos, '
                       'recuperar jump tables, conferir BSS de cada imagem e criar metadados de seções/relocações. '
                       'As APIs libultra, interrupções, PI DMA, scheduler, áudio e controle precisam ser mapeados para '
                       'um runtime. Não foi gerado ELF, reconstrução byte a byte nem código N64Recomp. '
                       'A evidência não permite prometer um port completo, uma estimativa de prazo ou uma taxa de quadros.')
    else:
        init = ('O entrypoint `0x80080400` limpa a BSS, estabelece `sp=0x800FF280` e salta '
                'para `0x80093400` (ROM `0x14000`), pulando um grande bloco anterior de funções. '
                'A inicialização chama `0x800AB200` (candidata a `osInitialize`), prepara uma '
                'thread com entrada `0x80093464` via `0x800A2AF0` e a inicia por `0x800A2EF0`. '
                'A rotina seguinte cria outra thread com entrada `0x80081EE4`. Há dispatch '
                'indireto de um callback guardado em `0x80120898` (carregado em `0x80093508`, '
                '`jalr` em `0x80093510`). Nomes de SDK permanecem atribuições sem símbolos originais, '
                'exceto os dois pares TLB comparados.\n\n'
                '`0x80098640` é um wrapper síncrono de carregamento: recebe ROM/destino/tamanho '
                'em `a0/a1/a2`, cria fila, invalida D-cache, submete DMA pela rotina `0x800A4F70` '
                'e espera mensagem em `0x800A2BC0`. A preservação de `a0/a1/a2` em `s5/s2/s4` '
                'e seu uso como campos de DMA fundamentam a convenção adotada pelo scanner. '
                'Não se pressupõe que cada chamada desse wrapper transporte código.')
        selected = [0x4AF50, 0x58EF0, 0x3D15E0, 0x48D190, 0x61FE90]
        examples = [0x4FDA0, 0xA9D28, 0x21D798, 0x332270, 0x426D58, 0x48C728]
        overlay_note = ('ROM `0x58EF0–0x8FC90` e `0x3D15E0–0x434580` são imagens diferentes '
                        'carregadas em `0x8012C860`, por chamadas em ROM `0x5374` e `0x8EE4`. '
                        'Ambas começam com código CPU e são candidatas fortes a overlays. '
                        'Outras famílias reutilizam `0x801636E0`, `0x80179960` e `0x80180930`; '
                        'os numerosos blocos em `0x80366800` também incluem recursos e não devem ser todos chamados de executáveis.')
        feasibility = ('**Recompilação estática é plausível como projeto de investigação; os metadados atuais ainda são insuficientes '
                       'para iniciar uma tradução confiável de todo o jogo.** Entrypoint, BSS, pilha e o wrapper de DMA estão '
                       'bem caracterizados, e há vários prefixos de código acessíveis sem descompressão. '
                       'A reutilização de RAM exige identidade de overlay e tratamento de callbacks, não apenas símbolos por endereço.\n\n'
                       'O conjunto de microcódigos é mais variado do que no primeiro jogo: além de variantes F3DEX/F3DLX, '
                       'há F3DLP.Rej, L3DEX e S2DEX/S2DEXD. É preciso descobrir quais OSTasks os selecionam e quais variantes '
                       'o runtime escolhido suporta. As texturas paletizadas exigem resolver TLUTs e segmentos; identificá-las '
                       'não demonstra que o renderizador esteja pronto. Ainda faltam confirmação dinâmica dos overlays, '
                       'jump tables, BSS por imagem, seções/relocações, áudio, scheduler e I/O. Não foi produzido ELF, '
                       'build N64Recomp ou execução nativa. A variedade maior de recursos não prova maior custo total de port.')

    maps = [
        ['Cabeçalho', span(0, 0x40), '—', 'Confirmado'],
        ['IPL3', span(0x40, 0x1000), 'bootstrap separado', 'Idêntico entre os jogos'],
        ['CPU residente', span(0x1000, spec['cpu_text_end']), span(spec['entry'], core_end), 'Alto; fronteira RSP inspecionada'],
        ['RSP + dados residentes', span(spec['cpu_text_end'], spec['resident_rom_end']), span(core_end, spec['bss_start']), 'Misto; fronteiras internas pendentes'],
        ['BSS residente', 'sem bytes ROM', span(spec['bss_start'], ram_end), 'Confirmado pelo loop inicial'],
    ]
    dynamic_rows = []
    for r in e['regions']:
        if r['rom_start'] in selected:
            dynamic_rows.append([span(r['rom_start'], r['rom_end']), hx(r['vram']),
                                 span(r['rom_start'], r['text_end']), 'Médio: DMA + prefixo CPU'])
    graphics_rows = []
    for c in e['graphics_candidates']:
        if c['rom'] in examples and c['render_tiles']:
            t = c['render_tiles'][0]
            dim = c['tile_bounds'][0] if c['tile_bounds'] else None
            graphics_rows.append([hx(c['rom']), c['load_format'] + str(c['load_bits']),
                                  t['format'] + str(t['bits']),
                                  f"{dim['width']}×{dim['height']}" if dim else '—', hx(c['image_address'])])
    shared = []
    for m in matches:
        if m['method'] == 'sha256' and m['unique_pair']:
            pos = m[game][0]
            name = '__osProbeTLB' if m['size'] == 192 else 'osMapTLBRdb'
            shared.append([name, hx(pos['rom']), hx(pos['vram']), m['size'], 'Bytes iguais; nome por referência'])
    parts = [f'# {spec["title"]} — mapa e viabilidade',
             '**Resultado:** ambiente e análise estática funcionais; viabilidade de recompilação preliminar, com confirmação dinâmica pendente.',
             '## Identidade e integridade',
             f'ROM original big-endian de 16 MiB, SHA-256 `{spec["sha256"]}`. SHA-1 `{spec["sha1"]}`. '
             f'CRC CIC-6102 recalculado: `{e["crc6102"]["computed"][0]}` / `{e["crc6102"]["computed"][1]}`, ambos iguais ao cabeçalho. '
             'Os bytes originais foram preservados. Todos os intervalos terminam em endereço exclusivo.',
             '## Mapa principal de ROM e memória', table(['Região', 'ROM', 'VRAM/RAM', 'Confiança'], maps),
             f'[Mapa visual SVG]({game}-memory-map.svg) · [Mapa completo CSV](evidence/{game}-memory-map.csv) · [Evidências JSON](evidence/{game}.json)',
             '## Inicialização e rotinas residentes', init,
             '## Código e possíveis overlays',
             f'Foram recuperados **{len(e["dma_loads"])} mapeamentos DMA constantes**, '
             f'**{len(e["regions"])} regiões CPU candidatas, incluindo a residente**, e '
             f'**{e["function_count"]} funções inferidas por spimdisasm**. '
             f'Há {e["indirect_calls"]} instruções `jalr` e {e["indirect_jumps"]} `jr` que não retornam por `ra`, '
             'contadas no corpus de regiões, sem deduplicar possíveis sobreposições. Esses saltos incluem dispatch e jump tables; '
             'não são, isoladamente, falhas nem uma contagem de funções desconhecidas.',
             overlay_note, table(['Bloco completo ROM', 'Base VRAM', 'Prefixo CPU candidato na ROM', 'Confiança'], dynamic_rows),
             table(['Base de RAM reutilizada', 'Blocos ROM distintos mapeados'],
                   [[hx(v), len(ls)] for v, ls in sorted(ram_groups.items()) if len(ls) >= 3]),
             'A tabela acima inclui dados. As imagens sobrepostas são alternativas, não ocupações simultâneas. '
             'Os fins de prefixo CPU são hipóteses locais: um opcode inválido pode ser dado embutido, e não o fim real da seção. '
             f'O scanner independente deixou {len(e["uncovered_density_candidates"])} páginas de densidade CPU sem interseção com os prefixos mapeados; '
             'ver `uncovered_density_candidates` no JSON. Isso não prova cobertura completa: páginas com pouco código, streams comprimidos e caminhos indiretos podem escapar.',
             '## SDK e rotinas compartilhadas', table(['Nome atribuído', 'ROM', 'VRAM', 'Bytes', 'Evidência'], shared),
             'Os dois pares são idênticos byte a byte entre jogos e reaparecem no comparador normalizado. '
             'Não são quatro correspondências distintas. Sua função é gerenciamento de TLB da família libultra; '
             'não demonstram compartilhamento da lógica de sumô. Não se identificou uma biblioteca dinâmica ou engine inteira comum.',
             '## Gráficos e recursos',
             table(['Offset ROM da assinatura', 'Microcódigo presente'], [[hx(s['rom']), s['text']] for s in e['ucode_signatures']]),
             f'O scanner encontrou {len(e["graphics_candidates"])} cadeias candidatas de comandos de textura. '
             'Formatos de tiles de renderização recuperados: ' + ', '.join(f'**{k}** ({v} declarações)' for k, v in sorted(e['render_format_counts'].items())) + '. '
             'Contam-se declarações, não texturas únicas ou recursos efetivamente usados.',
             table(['ROM do SetTextureImage', 'Transferência', 'Tile render', 'Tile (não asset inteiro)', 'Endereço da imagem'], graphics_rows),
             'As sequências coerentes `FD/F5/E6/F3 ou F4/E7/F5/F2` sustentam a interpretação RDP. '
             'Formatos de transferência podem ser diferentes dos pixels renderizados. '
             'Ainda faltam bases de segmentos, TLUTs, uso em runtime e validação visual; nenhuma imagem foi extraída. '
             'As assinaturas confirmam presença das variantes, sem provar seleção de todas durante o jogo. '
             'O layout exato de modelos, fontes e containers de assets não foi resolvido.',
             f'Marcadores exatos de compressão encontrados: `{e["compression_markers"]}`. '
             'Contagem zero não exclui codecs próprios ou streams sem assinatura.',
             '## Viabilidade de recompilação', feasibility,
             '## Próxima validação recomendada',
             '1. Executar em emulador com trace de PC e DMA, cobrindo boot, menus, início e troca de lutas; '
             'comparar origens/destinos com os mapeamentos estáticos.\n'
             '2. Capturar OSTasks, microcódigos selecionados e display lists, resolvendo segmentos e paletas.\n'
             '3. Confirmar fronteiras CPU/dados, BSS, chamadas indiretas e jump tables em cada contexto de overlay.\n'
             '4. Só então preparar um ELF/metadados mínimos e avaliar uma prova limitada de recompilação, em tarefa separada.',
             '## Reprodução e limites',
             '`make setup && make analyze && make verify`. A análise foi executada com Splat 0.50.1, '
             'spimdisasm 1.42.4 e Rabbitizer 1.16.2. Logs e assembly estão em `generated/`, '
             'fora do Git. Não houve emulação, teste de gameplay, build/link MIPS ou recompilação. '
             'Veja [metodologia](../docs/metodologia.md), [comparação](comparacao.md) e '
             f'[inventário de funções](evidence/{game}-functions.csv).']
    (REPORTS / f'{game}.md').write_text('\n\n'.join(parts) + '\n')


def main():
    specs = json.loads((ROOT / 'config/roms.json').read_text())
    summary = json.loads((REPORTS / 'evidence/summary.json').read_text())
    matches = json.loads((REPORTS / 'evidence/shared-functions.json').read_text())
    evidence = {g: json.loads((REPORTS / 'evidence' / (g + '.json')).read_text()) for g in specs}
    for game, spec in specs.items():
        game_report(game, spec, evidence[game], matches)
    rows = []
    for label, key in [('Regiões CPU candidatas (inclui residente)', 'regions'),
                       ('Funções inferidas', 'functions'), ('Mapeamentos DMA constantes', 'dma_mappings'),
                       ('Cadeias gráficas candidatas', 'graphics_candidates'),
                       ('Assinaturas de microcódigo gráfico', 'ucode_signatures'),
                       ('Instruções jalr / jr não-ra', None)]:
        if key:
            rows.append([label, summary['games']['ozumo1'][key], summary['games']['ozumo2'][key]])
        else:
            rows.append([label] + [f"{evidence[g]['indirect_calls']} / {evidence[g]['indirect_jumps']}" for g in specs])
    parts = ['# Comparação técnica e viabilidade de recompilação',
             '**Os dois jogos oferecem uma base plausível para pesquisa de recompilação estática, mas nenhum está pronto para tradução automática completa.** '
             'A análise confirmou núcleos residentes MIPS, carregamentos que reutilizam endereços RAM, microcódigos gráficos e rotinas SDK compartilhadas. '
             'Persistem fronteiras inferidas, chamadas indiretas e ausência de validação dinâmica. O ambiente de análise está preparado; isso não é um port funcional.',
             table(['Métrica estática', '64 Oozumou', '64 Oozumou 2'], rows),
             'As contagens cobrem o corpus descoberto e não equivalem ao número real de funções ou overlays do jogo. '
             'Mais funções, mais cadeias gráficas ou mais mapeamentos não determinam maior dificuldade. '
             'Os gráficos usam candidatos por prefixo/declaração; não são contagens de assets únicos.',
             '## Mapas e evidências',
             '- [Jogo 1: relatório e viabilidade](ozumo1.md), [mapa SVG](ozumo1-memory-map.svg), [mapa CSV](evidence/ozumo1-memory-map.csv).\n'
             '- [Jogo 2: relatório e viabilidade](ozumo2.md), [mapa SVG](ozumo2-memory-map.svg), [mapa CSV](evidence/ozumo2-memory-map.csv).\n'
             '- [Manifesto de ROMs](../config/roms.json), [funções compartilhadas](evidence/shared-functions.json), [resumo verificável](evidence/summary.json).',
             '## Diferenças que afetam uma futura recompilação',
             table(['Aspecto', 'Jogo 1', 'Jogo 2'], [
                 ['Inicialização', '`0x80000400` → `0x80000450`', '`0x80080400` → `0x80093400`'],
                 ['BSS residente', '`0x8002B8D0–0x800A62E0`', '`0x800CA350–0x80125130`'],
                 ['Famílias de overlays exemplificadas', '`0x800A62E0`, `0x801D18C0`, `0x801D4400`', '`0x8012C860`, `0x801636E0`, `0x80179960`, `0x80180930`'],
                 ['Microcódigos presentes', 'F3DEX e L3DEX 1.21', 'Família F3DEX/F3DLX/F3DLP/L3DEX 1.23; S2DEX/S2DEXD 1.07'],
                 ['Tiles identificados', ', '.join(sorted(evidence['ozumo1']['render_format_counts'])), ', '.join(sorted(evidence['ozumo2']['render_format_counts']))],
                 ['Toolchain sugerido por Splat', 'IDO (hipótese)', 'KMC (hipótese)'],
                 ['Risco principal', 'Endereços reutilizados por imagens alternativas', 'Overlays e seleção de microcódigos variados'],
             ]),
             'O primeiro jogo apresenta um conjunto menor de assinaturas de microcódigo, o que delimita melhor uma investigação inicial de renderização. '
             'O segundo exige verificar mais variantes e paletas. Isso não permite afirmar qual port seria mais fácil: o uso real, os codecs, '
             'o áudio e a cobertura dos overlays ainda podem mudar a avaliação. Entrypoints diferentes, isoladamente, não justificam ranking.',
             '## O que os jogos compartilham',
             'O IPL3 é idêntico byte a byte. O comparador de funções encontrou dois pares únicos idênticos '
             '(192 e 96 bytes), compatíveis com `__osProbeTLB` e `osMapTLBRdb`. O mesmo conjunto reaparece após normalização de endereços. '
             'É evidência concreta de rotinas libultra ligadas estaticamente. Não se comprovou engine compartilhada, nem sua ausência. '
             'A comparação conserva registradores e constantes e pode perder correspondências entre compilações diferentes.',
             '## Validação realizada',
             f'Foram concluídos {summary["commands_completed"]} comandos de ferramentas com exit code zero: '
             'Splat para os dois residentes e spimdisasm em cada região CPU. A validação confere funções realmente emitidas, '
             'mapas SVG, hashes das ROMs e CRCs CIC-6102 de ambos os jogos. A suíte unitária exercita casos de instruções e fluxo, '
             'não apenas sintaxe. `generated/run-manifest.json` contém os comandos/logs da última execução completa. '
             'Os originais e as cópias locais mantêm os hashes fornecidos. Não houve testes de gameplay, build recompilado ou emulação.',
             '## Próxima decisão e pendências',
             'Antes de escolher um alvo de port, obter traces representativos de boot, menus e combate para ambos. '
             'Resolver mapeamentos de overlays e BSS, jump tables, microcódigos ativos e recursos segmentados. '
             'Depois, preparar seções e relocações de um ELF/metadados compatíveis com o recompilador escolhido e '
             'avaliar uma prova pequena, em escopo separado. Não se gerou um port nem se alteraram as ROMs. '
             '1080p, widescreen e 60 FPS permanecem fora desta análise.',
             '[Método e níveis de confiança](../docs/metodologia.md) · [Relatório inicial recebido](../docs/relatorio-inicial-fornecido.md) · [Como reproduzir](../README.md)']
    (REPORTS / 'comparacao.md').write_text('\n\n'.join(parts) + '\n')


if __name__ == '__main__':
    main()
