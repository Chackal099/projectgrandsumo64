# Adaptadores Windows

Reservado aos callbacks de janela/renderização, entrada, reprodução de áudio, diretórios de saves/configuração e notificações ao usuário. Não duplicar scheduler, filas e timers já fornecidos por ultramodern sem evidência de incompatibilidade.

O relógio de apresentação e as preferências de resolução não comandam a simulação. Formatos dos arquivos e interfaces públicas devem evitar tipos específicos de Win32 fora desta camada. A construção de uma aplicação Windows e seus testes permanecem para a etapa de integração.
