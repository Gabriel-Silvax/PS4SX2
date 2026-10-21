# PS4SX2 Performance Lab (Python)

Ferramenta **somente de leitura** para medir e comparar o desempenho real do PS4SX2. Usa Python 3.10+ sem dependências adicionais. Não altera jogos, BIOS, clocks, firmware nem configurações do PS4. Não é um desbloqueador de FPS.

## Uso no Debian

Conecte PS4 e PC à mesma rede e inicie o FTP do GoldHEN. Substitua `192.168.1.50` pelo IP real do PS4 e ajuste `--port` caso o servidor use outra porta.

```bash
python3 tools/optimization/ps4_perf_lab.py fetch \
  --host 192.168.1.50 --port 2121 --output logs/budokai3-v2.log
python3 tools/optimization/ps4_perf_lab.py analyze logs/budokai3-v2.log \
  --warmup 30 --json reports/budokai3-v2.json
```

Depois de instalar uma versão diferente do emulador e executar a **mesma cena**:

```bash
python3 tools/optimization/ps4_perf_lab.py fetch \
  --host 192.168.1.50 --port 2121 --output logs/budokai3-v3.log
python3 tools/optimization/ps4_perf_lab.py compare \
  logs/budokai3-v2.log logs/budokai3-v3.log \
  --warmup 30 --json reports/comparacao.json
```

O caminho FTP padrão é `/data/PS4SX2/logs/PCSX2-vm-boot.log`. Se o servidor publicar uma raiz diferente, use `--remote-path`. O programa não sobrescreve arquivos locais existentes. Sempre reinicie o aplicativo para criar uma nova sessão de log antes de capturar outra versão.

## Experimento válido

1. Teste a mesma ISO/região e um trecho reproduzível de cutscene por ao menos 90 segundos.
2. Use resolução interna 1× e condições equivalentes em todas as medições.
3. Faça três repetições, compare mediana e p10 de `Speed_pct` e as medianas `EE_ms`, `GS_ms`, `VU1_ms`.
4. Não some EE, GS e VU1: são tempos de threads que podem se sobrepor e incluir esperas.
5. `PS2_Hz` é a cadência virtual do PS2. `Game_FPS` é heurística do PCSX2, não taxa interna garantida.

O PS4SX2 dispõe de marcadores para comparar clock EE e afinidade de threads em `/data/PS4SX2`, mas este script nunca os modifica. A medição e a escolha do próximo experimento são automatizadas; as alterações de C++ e os testes de compatibilidade continuam deliberados.

## Testes Python

```bash
python3 -m unittest discover -s tools/optimization -p 'test*.py' -v
```
