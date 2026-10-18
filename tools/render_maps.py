#!/usr/bin/env python3
"""Render measured ROM/RAM spans as standalone SVG, without extra dependencies."""
from collections import defaultdict
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(game, spec, evidence):
    groups = defaultdict(list)
    for load in evidence['dma_loads']:
        groups[load['vram']].append(load)
    width = 1180
    height = 340 + 24 * len(groups)
    left, axis_width = 250, 880
    pieces = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
              '<style>text{font:13px monospace;fill:#172033}.title{font:bold 20px sans-serif}.small{font:11px sans-serif}rect:hover{stroke:#111;stroke-width:2}</style>',
              f'<rect width="{width}" height="{height}" fill="#f8fafc"/>',
              f'<text x="24" y="34" class="title">{escape(spec["title"])} — mapa estático</text>',
              '<text x="24" y="57" class="small">Azul: prefixos CPU candidatos; roxo: RSP/dados residentes; laranja: DMA; cinza: BSS. Pontas direitas exclusivas.</text>',
              '<text x="24" y="76" class="small">Sobreposição indica reutilização de RAM, sem demonstrar a sequência de execução. Passe o mouse nos blocos para ver os intervalos.</text>']

    def text(x, y, label, cls=''):
        pieces.append(f'<text x="{x}" y="{y}" class="{cls}">{escape(str(label))}</text>')

    def rect(start, end, limit, y, fill, tooltip):
        x = left + start / limit * axis_width
        span = max(1.5, (end - start) / limit * axis_width)
        pieces.append(f'<rect x="{x:.2f}" y="{y}" width="{span:.2f}" height="15" rx="2" fill="{fill}" fill-opacity="0.65"><title>{escape(tooltip)}</title></rect>')

    text(24, 108, 'ROM [0, 16 MiB)')
    for mb in range(0, 17, 2):
        text(left + mb / 16 * axis_width, 108, f'{mb}M', 'small')
    text(24, 137, 'CPU: por offsets na ROM')
    for r in evidence['regions']:
        rect(r['rom_start'], r['text_end'], spec['size'], 123, '#2563eb',
             f'{r["id"]}: ROM {r["rom_start"]:#x}..{r["text_end"]:#x}; VRAM {r["vram"]:#x}; {r["confidence"]}')
    text(24, 163, 'Outros bytes DMA')
    for r in evidence['dma_loads']:
        rect(r['rom_start'], r['rom_end'], spec['size'], 149, '#d97706',
             f'ROM {r["rom_start"]:#x}..{r["rom_end"]:#x} -> {r["vram"]:#x}')
    text(24, 189, 'RSP + dados residentes')
    rect(spec['cpu_text_end'], spec['resident_rom_end'], spec['size'], 175, '#9333ea', 'Mistura de código RSP e dados; limites internos não recuperados')
    text(24, 221, 'KSEG0 RAM [80000000, 80400000)')
    for mb in range(5):
        text(left + mb / 4 * axis_width, 240, f'{0x80000000 + mb * 0x100000:08X}', 'small')
    text(24, 265, 'Residente / BSS')
    rect(spec['entry'] - 0x80000000, spec['bss_start'] - 0x80000000, 0x400000, 251, '#2563eb', 'Imagem residente; VRAM não é memória de vídeo separada')
    rect(spec['bss_start'] - 0x80000000, spec['bss_start'] + spec['bss_size'] - 0x80000000, 0x400000, 251, '#64748b', f'BSS {spec["bss_start"]:#x} + {spec["bss_size"]:#x}')
    for idx, (vram, loads) in enumerate(sorted(groups.items())):
        y = 281 + idx * 24
        text(24, y + 13, f'{vram:08X}: {len(loads)} bloco(s)')
        for load in sorted(loads, key=lambda x: -x['size']):
            rect(vram - 0x80000000, vram + load['size'] - 0x80000000, 0x400000, y,
                 '#d97706', f'ROM {load["rom_start"]:#x}..{load["rom_end"]:#x} -> RAM {vram:#x}..{vram+load["size"]:#x}')
    text(24, height - 24, 'Fonte: reports/evidence/' + game + '.json. Candidatos estáticos; uso efetivo depende de trace.', 'small')
    pieces.append('</svg>')
    (ROOT / 'reports' / f'{game}-memory-map.svg').write_text('\n'.join(pieces) + '\n')


if __name__ == '__main__':
    specs = json.loads((ROOT / 'config/roms.json').read_text())
    for game, spec in specs.items():
        render(game, spec, json.loads((ROOT / 'reports/evidence' / (game + '.json')).read_text()))
