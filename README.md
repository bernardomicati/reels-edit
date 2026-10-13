# reels-edit

Pipeline de edição de Reels com ffmpeg, parametrizado por estilo de cliente.

## Clientes
- [João Bueno](clientes/joao-bueno/ESTILO.md): talking head com jump cuts, B-roll em faixa no topo e legenda pequena branca.

## Fluxo
1. **Cortar silêncios** do bruto e gerar o esqueleto do roteiro:
   ```bash
   python3 tools/cortes.py brutos/take1.mov > clientes/joao-bueno/projetos/video01.json
   ```
2. **Editar o roteiro** (`clips`, `captions`, `broll`); veja `clientes/joao-bueno/projetos/exemplo.json`.
   Os tempos de `captions` e `broll` são na linha do tempo final.
3. **Renderizar:**
   ```bash
   python3 tools/reel.py clientes/joao-bueno/projetos/video01.json --preview   # rápido, 540x960
   python3 tools/reel.py clientes/joao-bueno/projetos/video01.json             # final, 1080x1920
   ```

Requisitos: `ffmpeg` com libass. As fontes Montserrat (OFL) estão em `fonts/`.
Vídeos (`*.mp4`, `*.mov`) ficam fora do git.
