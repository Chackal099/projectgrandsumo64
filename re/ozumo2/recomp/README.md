# Preparação de uma unidade limitada

Não há configuração de recompilação comercial habilitada. Antes de criar um TOML ou ELF executável, confirmar os limites de uma unidade, suas chamadas externas, dados/jump tables, estado inicial e identidade de overlay.

A revisão fixada de N64Recomp aceita `elf_path` **ou** `symbols_file_path` com `rom_file_path`. Os símbolos TOML não são os símbolos Splat e os CSVs de spimdisasm não constituem esse formato. O exemplo executável atual está somente em `tools/development/smoke_recompiler.py` e usa 12 bytes sintéticos próprios.

Saídas futuras vão a `generated/ozumo2/recomp/`; entradas comerciais continuam em `baseroms/`. Não adicionar stubs para mascarar chamadas desconhecidas nem emitir todos os candidatos heurísticos de uma vez.
