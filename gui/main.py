#!/usr/bin/env python3
"""
main.py — Interface com o usuário (Tkinter).

Papel desta linguagem no trabalho: Python é a linguagem "de vocação de
integração e interface". Este arquivo cuida exclusivamente de:

  - construir a janela, os controles e tratar eventos de mouse/teclado;
  - converter cliques em coordenadas do plano complexo;
  - exibir os pixels devolvidos pelo C;
  - salvar a imagem em disco.

Nenhuma iteração do fractal é calculada aqui. Todo o cálculo é delegado ao
módulo `mandelbrot_ffi`, que por sua vez chama a biblioteca em C.

Controles:
  - Clique esquerdo  : aproxima (zoom in) no ponto clicado
  - Clique direito   : afasta (zoom out)
  - Roda do mouse    : zoom contínuo
  - Arrastar (botão do meio ou esquerdo com Shift): deslocar a vista
  - R                : restaura a vista inicial
  - S                : salva a imagem atual em PPM

Uso:
    python3 gui/main.py [--width 900] [--height 600] [--iter 500] [--threads 0]
"""

import argparse
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

# Garante que o módulo da ponte seja encontrado mesmo se executado de outro
# diretório (ex.: via `make run` a partir da raiz do repositório).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mandelbrot_ffi as core  # noqa: E402  (import após ajuste de sys.path)


# Vista inicial: enquadra o conjunto inteiro.
VIEW_INICIAL = dict(cx=-0.65, cy=0.0, scale=2.6)


class MandelbrotApp:
    """Janela principal. Mantém o estado da vista e orquestra os redesenhos."""

    def __init__(self, root, width, height, max_iter, threads):
        self.root = root
        self.width = width
        self.height = height
        self.max_iter = max_iter
        self.threads = threads

        # Estado da vista (janela do plano complexo atualmente exibida).
        self.cx = VIEW_INICIAL["cx"]
        self.cy = VIEW_INICIAL["cy"]
        self.scale = VIEW_INICIAL["scale"]

        self.rendering = False       # evita renderizações sobrepostas
        self.drag_origin = None      # estado do arraste (pan)
        self.photo = None            # referência forte à PhotoImage (Tk exige)

        root.title("Mandelbrot — GUI em Python + kernel em C (ctypes/FFI)")
        root.resizable(False, False)

        self._build_widgets()
        self._bind_events()

        self.status.set(f"Ponte FFI ativa | {core.version()}")
        self.root.after(50, self.render_async)

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------
    def _build_widgets(self):
        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height,
                                highlightthickness=0, bg="black", cursor="crosshair")
        self.canvas.pack()
        self.image_id = self.canvas.create_image(0, 0, anchor=tk.NW)

        bar = tk.Frame(self.root, padx=6, pady=4)
        bar.pack(fill=tk.X)

        tk.Label(bar, text="Iterações:").pack(side=tk.LEFT)
        self.iter_var = tk.IntVar(value=self.max_iter)
        tk.Spinbox(bar, from_=50, to=20000, increment=50, width=7,
                   textvariable=self.iter_var,
                   command=self.render_async).pack(side=tk.LEFT, padx=(2, 12))

        tk.Button(bar, text="Redesenhar",
                  command=self.render_async).pack(side=tk.LEFT)
        tk.Button(bar, text="Vista inicial (R)",
                  command=self.reset_view).pack(side=tk.LEFT, padx=4)
        tk.Button(bar, text="Salvar (S)",
                  command=self.save_image).pack(side=tk.LEFT)

        self.status = tk.StringVar(value="iniciando…")
        tk.Label(self.root, textvariable=self.status, anchor="w",
                 relief=tk.SUNKEN, padx=6).pack(fill=tk.X)

        self.info = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.info, anchor="w",
                 padx=6, fg="#555").pack(fill=tk.X)

    def _bind_events(self):
        # ------------------------------------------------------------------
        # Portabilidade dos botões do mouse.
        #
        # O Tk numera os botões de forma DIFERENTE conforme o sistema de
        # janelas: em X11 (Linux) e Windows, o botão direito é o 3 e o do meio
        # é o 2; no macOS (windowingsystem "aqua"), essa ordem é INVERTIDA —
        # o direito é o 2 e o do meio é o 3. Sem este ajuste, o clique direito
        # no macOS dispararia o arraste em vez do zoom out.
        # ------------------------------------------------------------------
        aqua = self.root.tk.call("tk", "windowingsystem") == "aqua"
        btn_direito, btn_meio = (2, 3) if aqua else (3, 2)

        self.canvas.bind("<Button-1>", self.on_zoom_in)
        self.canvas.bind(f"<Button-{btn_direito}>", self.on_zoom_out)
        self.canvas.bind("<Button-4>", self.on_wheel)    # X11: roda para cima
        self.canvas.bind("<Button-5>", self.on_wheel)    # X11: roda para baixo
        self.canvas.bind("<MouseWheel>", self.on_wheel)  # Windows/macOS
        self.canvas.bind("<Motion>", self.on_motion)

        # Arraste (pan) com o botão do meio, quando existir.
        self.canvas.bind(f"<ButtonPress-{btn_meio}>", self.on_drag_start)
        self.canvas.bind(f"<B{btn_meio}-Motion>", self.on_drag_move)
        self.canvas.bind(f"<ButtonRelease-{btn_meio}>", self.on_drag_end)

        # Alternativa universal (essencial em trackpads sem botão do meio):
        # Shift + botão esquerdo.
        self.canvas.bind("<Shift-ButtonPress-1>", self.on_drag_start)
        self.canvas.bind("<Shift-B1-Motion>", self.on_drag_move)
        self.canvas.bind("<Shift-ButtonRelease-1>", self.on_drag_end)

        # No macOS, Control + clique esquerdo também equivale ao clique direito.
        if aqua:
            self.canvas.bind("<Control-Button-1>", self.on_zoom_out)

        self.root.bind("<KeyPress-r>", lambda e: self.reset_view())
        self.root.bind("<KeyPress-s>", lambda e: self.save_image())
        self.root.bind("<KeyPress-q>", lambda e: self.root.destroy())

    # ------------------------------------------------------------------
    # Conversão de coordenadas: tela (pixels) <-> plano complexo
    # ------------------------------------------------------------------
    def pixel_to_complex(self, px, py):
        """Espelha exatamente a transformação feita dentro de mb_render()."""
        step = self.scale / self.height
        x_min = self.cx - (self.width * step) / 2.0
        y_min = self.cy - (self.height * step) / 2.0
        return (x_min + px * step,
                y_min + (self.height - 1 - py) * step)

    # ------------------------------------------------------------------
    # Renderização
    # ------------------------------------------------------------------
    def render_async(self):
        """
        Dispara o cálculo em uma thread Python auxiliar.

        Detalhe relevante da integração: durante uma chamada via ctypes o GIL é
        liberado, então esta thread não bloqueia o laço de eventos do Tk — a
        janela continua respondendo enquanto as pthreads do C trabalham. A
        atualização da tela, porém, é reagendada para a thread principal com
        `after()`, pois o Tk não é thread-safe.
        """
        if self.rendering:
            return
        self.rendering = True
        self.max_iter = int(self.iter_var.get())
        self.status.set("calculando em C…")

        params = (self.width, self.height, self.cx, self.cy,
                  self.scale, self.max_iter, self.threads)

        def work():
            t0 = time.perf_counter()
            pixels = core.render(*params)
            dt = time.perf_counter() - t0
            self.root.after(0, self._on_render_done, pixels, dt)

        threading.Thread(target=work, daemon=True).start()

    def _on_render_done(self, pixels, dt):
        """Executado de volta na thread do Tk: publica a imagem na tela."""
        ppm = core.to_ppm(pixels, self.width, self.height)

        # PhotoImage lê PPM binário diretamente. Em versões de Tk que não
        # aceitam `data=` com bytes, recorre-se a um arquivo temporário.
        try:
            self.photo = tk.PhotoImage(data=ppm)
        except tk.TclError:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".ppm", delete=False) as f:
                f.write(ppm)
                tmp = f.name
            self.photo = tk.PhotoImage(file=tmp)
            os.unlink(tmp)

        self.canvas.itemconfig(self.image_id, image=self.photo)

        zoom = VIEW_INICIAL["scale"] / self.scale
        mpix = (self.width * self.height) / 1e6
        self.status.set(
            f"{self.width}x{self.height} | iter={self.max_iter} | "
            f"zoom={zoom:.3g}x | C: {dt * 1000:.0f} ms ({mpix / dt:.1f} Mpixel/s)"
        )
        self.rendering = False

    # ------------------------------------------------------------------
    # Manipuladores de eventos
    # ------------------------------------------------------------------
    def _zoom(self, px, py, fator):
        """Aplica zoom mantendo fixo o ponto complexo sob o cursor."""
        alvo_x, alvo_y = self.pixel_to_complex(px, py)
        self.scale *= fator
        # Interpola o centro em direção ao alvo, dando a sensação de mergulho.
        self.cx = alvo_x + (self.cx - alvo_x) * fator
        self.cy = alvo_y + (self.cy - alvo_y) * fator
        self.render_async()

    def on_zoom_in(self, ev):
        if self.drag_origin is None:
            self._zoom(ev.x, ev.y, 0.5)

    def on_zoom_out(self, ev):
        self._zoom(ev.x, ev.y, 2.0)

    def on_wheel(self, ev):
        subiu = getattr(ev, "delta", 0) > 0 or getattr(ev, "num", 0) == 4
        self._zoom(ev.x, ev.y, 0.8 if subiu else 1.25)

    def on_drag_start(self, ev):
        self.drag_origin = (ev.x, ev.y, self.cx, self.cy)

    def on_drag_move(self, ev):
        if not self.drag_origin:
            return
        x0, y0, cx0, cy0 = self.drag_origin
        step = self.scale / self.height
        self.cx = cx0 - (ev.x - x0) * step
        self.cy = cy0 + (ev.y - y0) * step
        self.render_async()

    def on_drag_end(self, ev):
        self.drag_origin = None

    def on_motion(self, ev):
        """
        Exibe as coordenadas sob o cursor e as iterações daquele ponto.
        Esta é uma chamada FFI de granularidade fina (um double -> um int),
        contrastando com mb_render(), que devolve um buffer inteiro.
        """
        zx, zy = self.pixel_to_complex(ev.x, ev.y)
        it = core.iterations_at(zx, zy, self.max_iter)
        dentro = " (no conjunto)" if it >= self.max_iter else ""
        self.info.set(f"c = {zx:+.10f} {zy:+.10f}i   |   iterações = {it}{dentro}")

    def reset_view(self):
        self.cx = VIEW_INICIAL["cx"]
        self.cy = VIEW_INICIAL["cy"]
        self.scale = VIEW_INICIAL["scale"]
        self.render_async()

    def save_image(self):
        caminho = filedialog.asksaveasfilename(
            defaultextension=".ppm",
            filetypes=[("Imagem PPM", "*.ppm")],
            initialfile="mandelbrot.ppm")
        if not caminho:
            return
        pixels = core.render(self.width, self.height, self.cx, self.cy,
                             self.scale, self.max_iter, self.threads)
        with open(caminho, "wb") as f:
            f.write(core.to_ppm(pixels, self.width, self.height))
        messagebox.showinfo("Salvo", f"Imagem gravada em:\n{caminho}")


def main():
    ap = argparse.ArgumentParser(description="Mandelbrot: GUI Python + kernel C")
    ap.add_argument("--width", type=int, default=900, help="largura em pixels")
    ap.add_argument("--height", type=int, default=600, help="altura em pixels")
    ap.add_argument("--iter", type=int, default=500, help="iterações máximas")
    ap.add_argument("--threads", type=int, default=0,
                    help="threads no C (0 = detectar núcleos)")
    args = ap.parse_args()

    root = tk.Tk()
    MandelbrotApp(root, args.width, args.height, args.iter, args.threads)
    root.mainloop()


if __name__ == "__main__":
    main()
