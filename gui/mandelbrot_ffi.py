"""
mandelbrot_ffi.py — A PONTE entre Python e C.

Este é o arquivo central do trabalho: é aqui que as duas linguagens se
encontram. Ele não desenha nada e não calcula nada; sua única função é
apresentar a biblioteca compartilhada em C (`libmandelbrot.so`) ao Python
como se fosse um módulo Python comum.

Mecanismo utilizado: ctypes (biblioteca padrão do Python)
---------------------------------------------------------
O `ctypes` é uma FFI (Foreign Function Interface) que:

  1. Carrega a biblioteca compartilhada no espaço de endereçamento do
     processo Python (via dlopen/LoadLibrary);
  2. Localiza os símbolos exportados pelo nome (ex.: "mb_render");
  3. Marshalla (converte) os argumentos Python para os tipos da ABI C e
     realiza a chamada respeitando a convenção de chamada da plataforma.

Vantagem sobre alternativas (Python/C API, Cython, SWIG, pybind11): não é
preciso escrever nenhum código de cola em C nem compilar um módulo de
extensão específico para a versão do interpretador. A .so gerada aqui é uma
biblioteca C comum, utilizável por qualquer outra linguagem com FFI.

Ponto crítico — GERÊNCIA DE MEMÓRIA:
    O buffer de pixels é criado do lado Python com `ctypes.create_string_buffer`
    e passado ao C como ponteiro. O C apenas ESCREVE nesse bloco; nunca aloca
    memória que o Python teria de liberar. Assim, o coletor de lixo do Python
    continua sendo o dono exclusivo da memória, e não há vazamento nem
    "double free" atravessando a fronteira.

Ponto crítico — CONCORRÊNCIA (GIL):
    `ctypes` libera automaticamente o GIL (Global Interpreter Lock) durante a
    execução de uma função C carregada com CDLL. Por isso as pthreads criadas
    dentro de mb_render() rodam com paralelismo real, e a interface Tk continua
    responsiva se a chamada for feita a partir de uma thread Python auxiliar.
"""

import ctypes
import os
import platform
import sys

# ---------------------------------------------------------------------------
# Localização da biblioteca compartilhada
# ---------------------------------------------------------------------------

def _library_name() -> str:
    """Nome do arquivo da biblioteca conforme o sistema operacional."""
    system = platform.system()
    if system == "Windows":
        return "mandelbrot.dll"
    if system == "Darwin":
        return "libmandelbrot.dylib"
    return "libmandelbrot.so"


def _find_library() -> str:
    """
    Procura a biblioteca compilada. A busca cobre o layout do repositório
    (build/ na raiz do projeto) e o diretório corrente, além de permitir
    sobrescrita explícita pela variável de ambiente MANDELBROT_LIB.
    """
    override = os.environ.get("MANDELBROT_LIB")
    if override:
        return override

    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)  # raiz do repositório
    name = _library_name()

    candidates = [
        os.path.join(root, "build", name),
        os.path.join(root, name),
        os.path.join(here, name),
        os.path.join(os.getcwd(), name),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path

    raise FileNotFoundError(
        f"Biblioteca '{name}' nao encontrada.\n"
        f"Procurei em:\n  " + "\n  ".join(candidates) + "\n\n"
        "Compile antes de executar:  make"
    )


# ---------------------------------------------------------------------------
# Carregamento e declaração dos protótipos
# ---------------------------------------------------------------------------

_lib = ctypes.CDLL(_find_library())

# Declarar argtypes/restype NAO é opcional: sem isso o ctypes assume que todo
# argumento é int e que o retorno é int, o que corromperia silenciosamente os
# doubles (que trafegam em registradores de ponto flutuante, não nos inteiros).
# Esta é a fonte de erro mais comum ao usar ctypes.

_lib.mb_version.argtypes = []
_lib.mb_version.restype = ctypes.c_char_p          # string estática: não liberar

_lib.mb_render.argtypes = [
    ctypes.POINTER(ctypes.c_uint8),  # rgb (buffer de saída, alocado no Python)
    ctypes.c_int,                    # width
    ctypes.c_int,                    # height
    ctypes.c_double,                 # center_x
    ctypes.c_double,                 # center_y
    ctypes.c_double,                 # scale
    ctypes.c_int,                    # max_iter
    ctypes.c_int,                    # n_threads
]
_lib.mb_render.restype = ctypes.c_int

_lib.mb_iterations_at.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_int]
_lib.mb_iterations_at.restype = ctypes.c_int


# ---------------------------------------------------------------------------
# Camada "pythônica" sobre a ABI em C
# ---------------------------------------------------------------------------

def version() -> str:
    """Retorna a identificação da biblioteca C (teste de sanidade da FFI)."""
    return _lib.mb_version().decode("ascii")


def render(width: int, height: int, center_x: float, center_y: float,
           scale: float, max_iter: int, threads: int = 0) -> bytes:
    """
    Chama o kernel em C e devolve os pixels como `bytes` no formato RGB.

    O buffer é alocado aqui (Python) e preenchido lá (C) — ver nota sobre
    gerência de memória no topo do módulo.

    Retorna: bytes de tamanho width*height*3.
    Levanta ValueError se o C reportar argumentos inválidos.
    """
    n_bytes = width * height * 3
    buf = ctypes.create_string_buffer(n_bytes)

    # Reinterpreta o buffer como ponteiro para uint8, tipo esperado pela ABI.
    ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint8))

    used = _lib.mb_render(ptr, width, height,
                          ctypes.c_double(center_x), ctypes.c_double(center_y),
                          ctypes.c_double(scale),
                          max_iter, threads)
    if used < 0:
        raise ValueError("mb_render: argumentos invalidos")

    return buf.raw[:n_bytes]


def iterations_at(cx: float, cy: float, max_iter: int) -> int:
    """Contagem de iterações de um único ponto (chamada FFI escalar)."""
    return _lib.mb_iterations_at(ctypes.c_double(cx), ctypes.c_double(cy), max_iter)


def to_ppm(rgb: bytes, width: int, height: int) -> bytes:
    """
    Empacota os bytes RGB em um arquivo PPM binário (P6) em memória.

    Motivo: o widget PhotoImage do Tk lê PPM nativamente, o que permite exibir
    a imagem sem depender de Pillow/NumPy — o projeto usa apenas a biblioteca
    padrão do Python, mantendo o foco na integração entre as linguagens.
    """
    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    return header + rgb


if __name__ == "__main__":
    # Auto-teste rápido da ponte: python3 gui/mandelbrot_ffi.py
    print("Biblioteca C carregada de:", _find_library())
    print("Versao reportada pelo C :", version())
    px = render(80, 40, -0.5, 0.0, 2.0, 200, 0)
    print(f"Render 80x40 OK: {len(px)} bytes")
    print("Iteracoes em (0,0) :", iterations_at(0.0, 0.0, 500), "(esperado: 500)")
    print("Iteracoes em (2,2) :", iterations_at(2.0, 2.0, 500), "(esperado: baixo)")
    sys.exit(0)
