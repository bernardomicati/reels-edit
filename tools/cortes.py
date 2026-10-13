#!/usr/bin/env python3
"""Gera o esqueleto de um roteiro (clips) cortando os silêncios do vídeo bruto.

Uso:
  python3 tools/cortes.py bruto.mov > roteiro.json
  python3 tools/cortes.py bruto.mov --db -32 --min-silence 0.30 --pad 0.06

Depois edite o roteiro: apague takes errados/repetidos, preencha "captions" e "broll".
"""
import argparse
import json
import re
import subprocess


def duration(src):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out.strip())


def silences(src, db, min_sil):
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", src, "-af", f"silencedetect=n={db}dB:d={min_sil}", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    return list(zip(starts, ends + [None] * (len(starts) - len(ends))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--db", type=float, default=-32)
    ap.add_argument("--min-silence", type=float, default=0.30)
    ap.add_argument("--pad", type=float, default=0.06, help="respiro mantido antes/depois da fala")
    ap.add_argument("--min-clip", type=float, default=0.35)
    a = ap.parse_args()

    total = duration(a.src)
    cur, clips = 0.0, []
    for s, e in silences(a.src, a.db, a.min_silence):
        if s - cur >= a.min_clip:
            clips.append((max(cur - a.pad, 0), min(s + a.pad, total)))
        cur = e if e is not None else total
    if total - cur >= a.min_clip:
        clips.append((max(cur - a.pad, 0), total))

    spec = {
        "output": "saida.mp4",
        "clips": [{"src": a.src, "in": round(i, 3), "out": round(o, 3)} for i, o in clips],
        "captions": [],
        "broll": [],
    }
    print(json.dumps(spec, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
