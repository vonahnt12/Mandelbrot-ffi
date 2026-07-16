# Mandelbrot — Integração Python + C via FFI (`ctypes`)

**Eduardo Alencastro von Ahnt** — Matrícula 20100405

Aplicação gráfica interativa do **conjunto de Mandelbrot** construída com **duas
linguagens de vocações distintas**, comunicando-se através de uma interface
binária (FFI):

| Linguagem  | Responsabilidade | Justificativa |
|------------|------------------|---------------|
| **C** (C99 + pthreads) | Serviço de cálculo: iteração `z ← z² + c`, coloração e paralelismo | Aritmética de ponto flutuante nativa, `-O3`, paralelismo real com threads |
| **Python** (Tkinter) | Interface com o usuário: janela, eventos de mouse, zoom, exibição e gravação da imagem | Prototipagem rápida de GUI e integração; nenhuma dependência externa |
| **Ponte** | `ctypes` (biblioteca padrão do Python) | Carrega a `.so` e chama as funções C diretamente, sem código de cola |

O ganho medido do kernel em C sobre o mesmo algoritmo em Python puro é de
aproximadamente **50×** (single-thread), antes mesmo do paralelismo — é
exatamente essa diferença que motiva a separação de responsabilidades.

---

## Arquivos do repositório

```
.
├── Makefile                  # compilação, execução, testes e benchmark
├── README.md                 # este arquivo
├── src/
│   ├── mandelbrot.h          # ABI pública: o "contrato" entre C e Python
│   └── mandelbrot.c          # kernel de cálculo (iteração, coloração, pthreads)
├── gui/
│   ├── mandelbrot_ffi.py     # A PONTE: carrega a .so e declara os protótipos
│   ├── main.py               # interface gráfica Tkinter (aplicação principal)
│   └── headless.py           # cliente de linha de comando (sem GUI) + benchmark
├── docs/
│   ├── documentacao.pdf      # documentação da implementação (entrega)
│   └── gerar_pdf.py          # fonte que gera o PDF acima (ReportLab)
├── build/                    # gerado por `make` (libmandelbrot.so)
└── out/                      # gerado por `make run-headless` (imagens .ppm)
```

Descrição dos três arquivos centrais:

- **`src/mandelbrot.c`** — todo o custo computacional do projeto. Implementa a
  iteração de escape com coloração contínua (*normalized iteration count*),
  testes analíticos do cardioide e do bulbo principal, e distribui as linhas da
  imagem entre threads POSIX. Não contém nenhuma linha de interface gráfica.
- **`gui/mandelbrot_ffi.py`** — o coração do trabalho. Carrega a biblioteca
  compartilhada, declara `argtypes`/`restype` de cada função e converte os tipos
  entre as linguagens.
- **`gui/main.py`** — toda a interação com o usuário. Não calcula nada do
  fractal; apenas traduz cliques em coordenadas complexas e delega ao C.

---

## Portabilidade

O projeto não depende de nenhuma plataforma específica: o código C é C99 com
pthreads, e a interface usa apenas a biblioteca padrão do Python. A adaptação ao
sistema operacional acontece em dois pontos que se espelham — o `Makefile`
detecta o SO com `uname` e o módulo `mandelbrot_ffi.py` faz a detecção
correspondente com `platform.system()`:

| Sistema | Biblioteca gerada | Flag de ligação | Situação |
|---------|-------------------|-----------------|----------|
| **Linux** | `libmandelbrot.so` | `-shared` | Compilado e testado |
| **macOS** | `libmandelbrot.dylib` | `-dynamiclib` | Compilado e testado (Apple Silicon, macOS 15) |
| **Windows** | `mandelbrot.dll` | `-shared` | Suportado **via MSYS2/MinGW-w64** (ver ressalva abaixo) |

Outras diferenças tratadas em tempo de execução ou de compilação:

- **Botões do mouse:** o Tk numera o botão direito como `3` em X11/Windows e
  como `2` no macOS. `_bind_events()` consulta o sistema de janelas e ajusta.
- **`-march=native`:** desativado automaticamente em Macs Apple Silicon (arm64),
  onde o Clang não aceita a flag.
- **Detecção de núcleos:** usa `sysconf(_SC_NPROCESSORS_ONLN)` onde disponível,
  com fallback para 4 threads caso contrário.

### Ressalva sobre o Windows

O Windows não traz `make` nem `gcc`, e este `Makefile` usa comandos de shell
Unix (`mkdir -p`, `rm -rf`). A compilação, portanto, requer um ambiente
**MSYS2/MinGW-w64** (ou WSL) — não funciona no `cmd.exe` puro. Além disso, o
MinGW não implementa `sysconf`, de modo que a detecção automática de núcleos
recai no fallback; recomenda-se passar o número explicitamente:

```bash
make run THREADS=8
```

> **Transparência:** a aplicação foi compilada e executada em Linux e em macOS
> (Apple Silicon). O caminho do Windows está implementado e revisado, mas não foi
> validado em execução.

---

## Requisitos

| Requisito | Versão | Observação |
|-----------|--------|------------|
| GCC (ou Clang) | qualquer com suporte a C99 | compilação da biblioteca |
| `make` | — | automação |
| Python | 3.8+ | `ctypes` já vem na biblioteca padrão |
| Tkinter | — | **único pacote extra possivelmente necessário** |

**Não são necessários NumPy, Pillow, SciPy ou qualquer pacote do PyPI.** O
projeto usa exclusivamente a biblioteca padrão do Python — a imagem é exibida
convertendo os bytes RGB em PPM, formato que o widget `PhotoImage` do Tk lê
nativamente.

### Instalação do Tkinter (se ausente)

```bash
# Debian / Ubuntu
sudo apt install python3-tk build-essential

# Fedora
sudo dnf install python3-tkinter gcc make

# Arch
sudo pacman -S tk gcc make

# macOS — compilador (Clang) e make:
xcode-select --install

# macOS — Tkinter: já acompanha o Python oficial do python.org e o do Xcode.
# Se você usa o Python do Homebrew, ele vem SEM Tkinter; instale à parte:
brew install python-tk
```

> **macOS:** o `Makefile` desativa `-march=native` automaticamente em Macs
> Apple Silicon (arm64), pois o Clang não aceita essa flag nessa arquitetura.
> Nada precisa ser feito manualmente.

Verificação: `python3 -c "import tkinter; print('ok')"`

---

## Como compilar

```bash
make
```

Isso gera `build/libmandelbrot.so` (ou `.dylib` no macOS, `.dll` no Windows).

Flags relevantes usadas: `-fPIC` (obrigatório para bibliotecas compartilhadas),
`-shared`, `-O3`, `-march=native` e `-fvisibility=hidden` (exporta apenas os
símbolos da ABI).

> Se for distribuir o binário para outra máquina, desative a otimização
> específica da CPU: `make NATIVE=0`

---

## Como executar

### Caso de estudo principal — aplicação gráfica

```bash
make run
```

Parâmetros opcionais:

```bash
make run WIDTH=1280 HEIGHT=720 ITER=1000 THREADS=8
```

**Controles:**

| Ação | Efeito |
|------|--------|
| Clique esquerdo | Zoom in no ponto |
| Clique direito (ou Control + clique, no macOS) | Zoom out |
| Roda do mouse / dois dedos no trackpad | Zoom contínuo |
| Arrastar com **Shift + botão esquerdo** | Deslocar a vista |
| `R` | Restaurar a vista inicial |
| `S` | Salvar a imagem |
| `Q` | Sair |

> O Tk numera os botões do mouse de forma invertida no macOS (o botão direito
> é o número 2, e não o 3, como em X11/Windows). A aplicação detecta o sistema
> de janelas em tempo de execução e ajusta as associações — ver `_bind_events()`
> em `gui/main.py`. O arraste com **Shift + botão esquerdo** funciona em
> qualquer plataforma e é a opção recomendada em trackpads.

A barra inferior mostra, em tempo real, a coordenada complexa sob o cursor e o
número de iterações daquele ponto — cada movimento do mouse dispara uma chamada
FFI escalar a `mb_iterations_at()`. A barra de status reporta o tempo gasto
dentro do C e a taxa em Mpixel/s.

### Caso de estudo sem interface gráfica (SSH, servidores, CI)

```bash
make run-headless
```

Gera `out/mandelbrot.ppm` (vista completa) e `out/mandelbrot_zoom.ppm` (zoom de
~5000× no Vale dos Cavalos-Marinhos) e imprime as métricas.

### Verificar apenas a ponte entre as linguagens

```bash
make test
```

Saída esperada:

```
Biblioteca C carregada de: .../build/libmandelbrot.so
Versao reportada pelo C : libmandelbrot 1.0 (C99 + pthreads)
Render 80x40 OK: 9600 bytes
Iteracoes em (0,0) : 500 (esperado: 500)
Iteracoes em (2,2) : 4 (esperado: baixo)
```

### Benchmark de paralelismo

```bash
make bench
```

O *speedup* só aparece em máquinas com mais de um núcleo; em um container de 1
vCPU o resultado é ~1.00× para qualquer número de threads.

### Limpeza

```bash
make clean
```

---

## Sobre a interface entre as linguagens

O detalhamento completo está em [`docs/documentacao.pdf`](docs/documentacao.pdf).
Em resumo, três decisões sustentam a integração:

1. **ABI mínima** — apenas tipos primitivos (`int`, `double`, `uint8_t*`)
   atravessam a fronteira. Nenhuma `struct` é compartilhada, evitando ter de
   replicar layouts de memória no lado Python.
2. **Memória alocada no Python, preenchida no C** — o buffer de pixels nasce em
   `ctypes.create_string_buffer()` e o C apenas escreve nele. O C nunca aloca
   memória que o Python precisaria liberar, eliminando a ambiguidade sobre a
   posse dos recursos entre o `malloc` e o coletor de lixo.
3. **Liberação do GIL** — durante uma chamada via `ctypes` o *Global Interpreter
   Lock* é liberado, de modo que as pthreads do C executam com paralelismo real
   e a interface Tk permanece responsiva.

## Solução de problemas

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| `FileNotFoundError: Biblioteca 'libmandelbrot.so' nao encontrada` | Biblioteca não compilada | Execute `make` |
| `ModuleNotFoundError: No module named '_tkinter'` | Python do Homebrew vem sem Tk (macOS) | `brew install python-tk@3.14` (ajuste a versão) |
| `ModuleNotFoundError: No module named 'tkinter'` | Tkinter ausente (Linux) | `sudo apt install python3-tk` |
| `macOS 15 (1507) or later required, have instead 15 (1506)` | Bug do Tk que acompanha o Python do sistema no macOS 15 | Use o Python do Homebrew com `python-tk` instalado |
| `_tkinter.TclError: no display name` | Ambiente sem servidor gráfico | Use `make run-headless` |
| `Illegal instruction` | Binário compilado com `-march=native` em outra CPU | `make clean && make NATIVE=0` |

Para apontar uma biblioteca em local não padrão:
`export MANDELBROT_LIB=/caminho/para/libmandelbrot.so`
