# Integração do jogo

Reservado ao registro de 64 Ōzumō 2, validação da ROM esperada, escolha de save confirmado e conexão de seções/overlays com librecomp. O entrypoint investigado é `0x80080400`; ver `reports/ozumo2.md` a partir da raiz.

Não preencher `GameEntry.rom_hash` com o SHA-256 do manifesto: esse campo upstream é `uint64_t` e deve seguir o algoritmo do próprio runtime. O SHA-256 existente continua identificando a entrada da investigação. O tipo de save deve ser confirmado em execução, sem selecionar EEPROM/SRAM por adivinhação.

Overlays precisam de identidade por seção e geração de carga, não apenas por endereço. A integração deve respeitar os registros de DMA/ciclo de vida antes de registrar destinos indiretos.
