#!/usr/bin/env python3
"""Renderiza um reel vertical (1080x1920) a partir de um roteiro de edição em JSON.

Estilo padrão = João Bueno (ver clientes/joao-bueno/ESTILO.md):
  - talking head com jump cuts secos, SEM zoom
  - SEMPRE abre com insert; B-roll numa faixa no topo (~31% da altura) com borda esfumada
  - legenda pequena, branca, Montserrat Bold, 1-3 palavras, no peito
  - 3 variações de gancho por vídeo (--gancho 1|2|3)

Uso:
  python3 tools/reel.py roteiro.json            # renderiza
  python3 tools/reel.py roteiro.json --preview  # 540x960 rápido
  python3 tools/reel.py roteiro.json --gancho 2 # usa o gancho 2 (padrão: 1)
  python3 tools/reel.py roteiro.json --todos    # renderiza uma versão por gancho

Formato do roteiro. Tempos de "captions"/"broll" são relativos ao início do próprio bloco
(o gancho começa em 0; o corpo também começa em 0 e é deslocado pela duração do gancho):
{
  "output": "saida.mp4",
  "ganchos": [
    {"clips": [...], "captions": [...], "broll": [...]},   # gancho 1
    {"clips": [...], "captions": [...], "broll": [...]}    # gancho 2 ...
  ],
  "clips":    [{"src": "bruto.mov", "in": 1.20, "out": 3.40}],
  "captions": [{"start": 0.0, "end": 0.6, "text": "Você acorda"}],
  "broll":    [{"src": "broll.mp4", "start": 0.0, "end": 3.0, "src_in": 0.0}],
  "music":    {"src": "trilha.mp3", "volume": 0.08}
}
Caminhos relativos são resolvidos a partir da pasta do roteiro.
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(ROOT, "fonts")

STYLE = {
    "W": 1080,
    "H": 1920,
    "fps": 30,
    "broll_band": 0.31,      # fração da altura ocupada pelo B-roll no topo
    "broll_feather": 70,     # px de degradê na borda inferior do B-roll
    "font": "Montserrat",
    "bold": 1,
    "font_size": 64,
    "caption_y": 0.80,       # posição vertical da legenda (fração da altura)
    "outline": 1.2,
    "shadow": 1.5,
    "zoom": 1.0,             # sem zoom (pedido do cliente); "zoom" por clip ainda funciona
    "lufs": -14,
}


def ass_time(t):
    t = max(t, 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_ass(captions, path, st):
    margin_v = int(st["H"] * (1 - st["caption_y"]))
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {st['W']}",
        f"PlayResY: {st['H']}",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{st['font']},{st['font_size']},&H00FFFFFF,&H00FFFFFF,&H64000000,&H78000000,"
        f"{-1 if st['bold'] else 0},0,0,0,100,100,0,0,1,{st['outline']},{st['shadow']},2,60,60,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for c in captions:
        text = c["text"].replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{ass_time(c['start'])},{ass_time(c['end'])},Default,,0,0,0,,{text}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def esc(p):
    """Escapa caminho para uso dentro de um filtergraph do ffmpeg."""
    return p.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def assemble(spec, gancho):
    """Junta gancho N + corpo numa linha do tempo única."""
    ganchos = spec.get("ganchos") or []
    blocks = []
    if ganchos:
        if not 1 <= gancho <= len(ganchos):
            sys.exit(f"gancho {gancho} não existe (roteiro tem {len(ganchos)})")
        blocks.append(ganchos[gancho - 1])
    blocks.append(spec)
    out = {"clips": [], "captions": [], "broll": []}
    t0 = 0.0
    for b in blocks:
        out["clips"] += b.get("clips", [])
        out["captions"] += [dict(c, start=c["start"] + t0, end=c["end"] + t0) for c in b.get("captions", [])]
        out["broll"] += [dict(r, start=r["start"] + t0, end=r["end"] + t0) for r in b.get("broll", [])]
        t0 += sum(c["out"] - c["in"] for c in b.get("clips", []))
    if not any(r["start"] <= 0.001 for r in out["broll"]):
        sys.exit("estilo João Bueno: o vídeo precisa ABRIR com um insert (broll com start=0)")
    covered = sum(r["end"] - r["start"] for r in out["broll"])
    print(f"duração {t0:.1f}s | inserts {len(out['broll'])} | cobertura B-roll {100 * covered / t0:.0f}%",
          file=sys.stderr)
    m = dict(spec, **out)
    m.pop("ganchos", None)
    return m


def build(spec, base, preview=False):
    st = dict(STYLE)
    st.update(spec.get("style", {}))
    W, H, fps = st["W"], st["H"], st["fps"]

    def P(p):
        return p if os.path.isabs(p) else os.path.join(base, p)

    inputs, fc = [], []
    clips = spec["clips"]
    for i, c in enumerate(clips):
        inputs += ["-ss", str(c["in"]), "-t", f"{c['out'] - c['in']:.3f}", "-i", P(c["src"])]
        z = c.get("zoom", st["zoom"])
        sw, sh = int(W * z) // 2 * 2, int(H * z) // 2 * 2
        fc.append(
            f"[{i}:v]setpts=PTS-STARTPTS,fps={fps},"
            f"scale={sw}:{sh}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,format=yuv420p[v{i}];"
            f"[{i}:a]asetpts=PTS-STARTPTS,aresample=48000,"
            f"aformat=channel_layouts=stereo,afade=t=in:d=0.01[a{i}]"
        )
    n = len(clips)
    fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[base][voice]")

    # B-roll na faixa superior com degradê de transparência embaixo
    band = int(H * st["broll_band"]) // 2 * 2
    feather = st["broll_feather"]
    cur = "base"
    for j, b in enumerate(spec.get("broll", [])):
        k = inputs.count("-i")
        dur = b["end"] - b["start"]
        inputs += ["-ss", str(b.get("src_in", 0)), "-t", f"{dur:.3f}", "-i", P(b["src"])]
        fc.append(
            f"[{k}:v]setpts=PTS-STARTPTS,fps={fps},scale={W}:{band}:force_original_aspect_ratio=increase,"
            f"crop={W}:{band},setsar=1,format=yuva420p,"
            f"geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':"
            f"a='if(lt(Y,H-{feather}),255,255*(H-Y)/{feather})',"
            f"setpts=PTS+{b['start']}/TB[b{j}];"
            f"[{cur}][b{j}]overlay=0:0:eof_action=pass:enable='between(t,{b['start']},{b['end']})'[o{j}]"
        )
        cur = f"o{j}"

    ass = os.path.join(base, ".captions.ass")
    write_ass(spec.get("captions", []), ass, st)
    vf_out = f"[{cur}]ass='{esc(ass)}':fontsdir='{esc(FONTS_DIR)}'"
    if preview:
        vf_out += ",scale=540:960"
    fc.append(vf_out + "[vout]")

    # Áudio: voz normalizada (+ trilha opcional baixa por baixo)
    fc.append(f"[voice]highpass=f=80,loudnorm=I={st['lufs']}:TP=-1.5:LRA=11[vo]")
    music = spec.get("music")
    if music:
        k = inputs.count("-i")
        inputs += ["-stream_loop", "-1", "-i", P(music["src"])]
        fc.append(
            f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume={music.get('volume', 0.08)}[mu];"
            f"[vo][mu]amix=inputs=2:duration=first:normalize=0[aout]"
        )
    else:
        fc.append("[vo]anull[aout]")

    out = P(spec.get("output", "saida.mp4"))
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats"] + inputs + [
        "-filter_complex", ";".join(fc),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast" if preview else "medium",
        "-crf", "26" if preview else "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", out,
    ]
    return cmd, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roteiro")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--print", action="store_true", help="só imprime o comando ffmpeg")
    ap.add_argument("--gancho", type=int, default=1)
    ap.add_argument("--todos", action="store_true", help="uma versão por gancho")
    a = ap.parse_args()
    with open(a.roteiro, encoding="utf-8") as f:
        spec = json.load(f)
    n = len(spec.get("ganchos") or [None])
    for g in range(1, n + 1) if a.todos else [a.gancho]:
        s = assemble(spec, g)
        if spec.get("ganchos"):
            root, ext = os.path.splitext(s.get("output", "saida.mp4"))
            s["output"] = f"{root}_gancho{g}{ext}"
        cmd, out = build(s, os.path.dirname(os.path.abspath(a.roteiro)), a.preview)
        if a.print:
            print(" ".join(cmd))
            continue
        r = subprocess.run(cmd)
        if r.returncode:
            sys.exit(r.returncode)
        print(out)


if __name__ == "__main__":
    main()
