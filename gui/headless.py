#!/usr/bin/env python3
"""
headless.py — Cliente de linha de comando (sem interface gráfica).

Serve a dois propósitos:

  1. Permitir executar o caso de estudo em ambientes sem servidor gráfico
     (servidores, CI, acesso via SSH), onde o Tkinter não pode abrir janela.
  2. Medir o ganho de desempenho do kernel em C conforme o número de threads,
     evidenciando por que o cálculo foi delegado a C em vez de escrito em
     Python puro.

Uso:
    python3 gui/headless.py --out saida.ppm
    python3 gui/headless.py --bench
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mandelbrot_ffi as core  # noqa: E402


def salvar(caminho, width, height, cx, cy, scale, it, threads):
    """Renderiza uma imagem via C e grava em disco no formato PPM (P6)."""
    t0 = time.perf_counter()
    pixels = core.render(width, height, cx, cy, scale, it, threads)
    dt = time.perf_counter() - t0

    with open(caminho, "wb") as f:
        f.write(core.to_ppm(pixels, width, height))

    mpix = (width * height) / 1e6
    print(f"  {width}x{height}, iter={it}  ->  {caminho}")
    print(f"  tempo no C: {dt * 1000:.1f} ms  ({mpix / dt:.1f} Mpixel/s)")


def bench(width, height, it):
    """Compara o tempo de cálculo variando o número de threads no lado C."""
    print(f"\nBenchmark — {width}x{height}, iter={it}")
    print("  threads |   tempo (ms) |  speedup")
    print("  --------+--------------+---------")
    base = None
    for n in (1, 2, 4, 8):
        t0 = time.perf_counter()
        core.render(width, height, -0.65, 0.0, 2.6, it, n)
        dt = (time.perf_counter() - t0) * 1000
        base = base or dt
        print(f"  {n:7d} | {dt:12.1f} | {base / dt:6.2f}x")


def main():
    ap = argparse.ArgumentParser(description="Mandelbrot headless (kernel C)")
    ap.add_argument("--out", default="mandelbrot.ppm", help="arquivo de saída")
    ap.add_argument("--width", type=int, default=1200)
    ap.add_argument("--height", type=int, default=800)
    ap.add_argument("--cx", type=float, default=-0.65)
    ap.add_argument("--cy", type=float, default=0.0)
    ap.add_argument("--scale", type=float, default=2.6)
    ap.add_argument("--iter", type=int, default=800)
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--bench", action="store_true", help="apenas o benchmark")
    args = ap.parse_args()

    print("Ponte Python <-> C estabelecida via ctypes.")
    print("  Biblioteca:", core.version())

    if args.bench:
        bench(args.width, args.height, args.iter)
        return

    print("\nVista completa do conjunto:")
    salvar(args.out, args.width, args.height, args.cx, args.cy,
           args.scale, args.iter, args.threads)

    # Segunda imagem: mergulho no "Vale dos Cavalos-Marinhos" (zoom ~5000x),
    # região que exige muitas iterações e evidencia o custo do cálculo.
    zoom_out = os.path.splitext(args.out)[0] + "_zoom.ppm"
    print("\nZoom no Vale dos Cavalos-Marinhos (~5000x):")
    salvar(zoom_out, args.width, args.height,
           -0.743643887037151, 0.131825904205330, 5.0e-4,
           max(args.iter, 1500), args.threads)

    bench(args.width // 2, args.height // 2, args.iter)


if __name__ == "__main__":
    main()
