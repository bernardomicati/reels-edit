#!/usr/bin/env python3
"""Renderiza um reel vertical (1080x1920) a partir de um roteiro de edição em JSON.

Estilo padrão = João Bueno (ver clientes/joao-bueno/ESTILO.md):
  - talking head com jump cuts secos e punch-in alternado
  - B-roll numa faixa no topo (~31% da altura) com borda inferior esfumada
  - legenda pequena, branca, Montserrat Medium, 1-3 palavras, no peito

Uso:
  python3 tools/reel.py roteiro.json            # renderiza
  python3 tools/reel.py roteiro.json --preview  # 540x960 rápido

Formato do roteiro (tempos de "captions" e "broll" são na linha do tempo FINAL):
{
  "output": "saida.mp4",
  "clips":    [{"src": "bruto.mov", "in": 1.20, "out": 3.40, "zoom": 1.0}],
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
    "font": "Montserrat Medium",
    "font_size": 64,
    "caption_y": 0.80,       # posição vertical da legenda (fração da altura)
    "outline": 1.2,
    "shadow": 1.5,
    "zoom_alt": 1.12,        # punch-in usado em cortes alternados quando zoom não é dado
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
        f"0,0,0,0,100,100,0,0,1,{st['outline']},{st['shadow']},2,60,60,{margin_v},1",
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
        z = c.get("zoom", 1.0 if i % 2 == 0 else st["zoom_alt"])
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
    a = ap.parse_args()
    with open(a.roteiro, encoding="utf-8") as f:
        spec = json.load(f)
    cmd, out = build(spec, os.path.dirname(os.path.abspath(a.roteiro)), a.preview)
    if a.print:
        print(" ".join(cmd))
        return
    r = subprocess.run(cmd)
    if r.returncode:
        sys.exit(r.returncode)
    print(out)


if __name__ == "__main__":
    main()
