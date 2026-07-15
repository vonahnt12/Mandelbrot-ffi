# ============================================================================
# Makefile — Mandelbrot: interface em Python + kernel de cálculo em C
# ----------------------------------------------------------------------------
# Alvos principais:
#   make            (ou make all)  -> compila a biblioteca compartilhada em C
#   make run                       -> executa a aplicação gráfica (caso de estudo)
#   make run-headless              -> caso de estudo sem interface gráfica
#   make test                      -> testa a ponte FFI (Python <-> C)
#   make bench                     -> mede o desempenho variando as threads
#   make clean                     -> remove artefatos gerados
# ============================================================================

# ----- Ferramentas ----------------------------------------------------------
CC      := gcc
PYTHON  := python3

# ----- Diretórios e arquivos ------------------------------------------------
SRC_DIR   := src
GUI_DIR   := gui
BUILD_DIR := build
OUT_DIR   := out

SOURCES := $(SRC_DIR)/mandelbrot.c
HEADERS := $(SRC_DIR)/mandelbrot.h
OBJECTS := $(BUILD_DIR)/mandelbrot.o

# ----- Detecção de plataforma (nome da biblioteca compartilhada) ------------
UNAME_S := $(shell uname -s)
ifeq ($(OS),Windows_NT)
    LIBNAME := mandelbrot.dll
else ifeq ($(UNAME_S),Darwin)
    LIBNAME := libmandelbrot.dylib
else
    LIBNAME := libmandelbrot.so
endif
LIB := $(BUILD_DIR)/$(LIBNAME)

# ----- Flags de compilação --------------------------------------------------
# -fPIC      : código independente de posição — OBRIGATÓRIO para bibliotecas
#              compartilhadas, que são mapeadas em endereços arbitrários.
# -shared    : produz a .so em vez de um executável.
# -O3        : otimização agressiva; é o motivo de o cálculo estar em C.
# -fvisibility=hidden : oculta todos os símbolos exceto os marcados com
#              MB_EXPORT no cabeçalho, deixando a ABI enxuta e explícita.
CFLAGS  := -std=c99 -O3 -Wall -Wextra -fPIC -fvisibility=hidden
LDFLAGS := -shared
LDLIBS  := -lpthread -lm

# -march=native acelera bastante, mas gera binário não portável entre CPUs.
# Desative manualmente com:  make NATIVE=0
#
# Exceção automática: o Clang dos Macs com Apple Silicon (arm64) NÃO aceita
# -march=native e aborta a compilação. Nessas máquinas o padrão passa a ser 0,
# sem perda relevante — o Clang já otimiza para a CPU nativa por padrão no arm64.
UNAME_M := $(shell uname -m)
ifeq ($(UNAME_S)-$(UNAME_M),Darwin-arm64)
    NATIVE ?= 0
else
    NATIVE ?= 1
endif

ifeq ($(NATIVE),1)
    CFLAGS += -march=native
endif

# No macOS a flag de biblioteca dinâmica difere.
ifeq ($(UNAME_S),Darwin)
    LDFLAGS := -dynamiclib
endif

# ----- Parâmetros do caso de estudo (sobrescrevíveis na linha de comando) ---
WIDTH   ?= 900
HEIGHT  ?= 600
ITER    ?= 500
THREADS ?= 0

.PHONY: all run run-headless test bench clean help
.DEFAULT_GOAL := all

# ---------------------------------------------------------------------------
# Compilação
# ---------------------------------------------------------------------------
all: $(LIB)
	@echo ""
	@echo "  Biblioteca gerada: $(LIB)"
	@echo "  Execute a aplicacao com:  make run"

$(LIB): $(OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $^ $(LDLIBS)

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c $(HEADERS) | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR)

$(OUT_DIR):
	@mkdir -p $(OUT_DIR)

# ---------------------------------------------------------------------------
# Execução — CASO DE ESTUDO PRINCIPAL
# Abre a interface gráfica em Python, que calcula o fractal chamando o C.
# ---------------------------------------------------------------------------
run: $(LIB)
	$(PYTHON) $(GUI_DIR)/main.py --width $(WIDTH) --height $(HEIGHT) \
	                             --iter $(ITER) --threads $(THREADS)

# ---------------------------------------------------------------------------
# Caso de estudo alternativo, sem servidor gráfico (SSH, CI, servidores).
# Gera duas imagens em out/ e imprime as métricas de desempenho.
# ---------------------------------------------------------------------------
run-headless: $(LIB) | $(OUT_DIR)
	$(PYTHON) $(GUI_DIR)/headless.py --out $(OUT_DIR)/mandelbrot.ppm \
	          --width 1200 --height 800 --iter 800 --threads $(THREADS)
	@echo ""
	@echo "  Imagens geradas no diretorio $(OUT_DIR)/"

# ---------------------------------------------------------------------------
# Verificação da ponte entre as linguagens
# ---------------------------------------------------------------------------
test: $(LIB)
	$(PYTHON) $(GUI_DIR)/mandelbrot_ffi.py

bench: $(LIB)
	$(PYTHON) $(GUI_DIR)/headless.py --bench --width 800 --height 600 --iter 1000

# ---------------------------------------------------------------------------
clean:
	rm -rf $(BUILD_DIR) $(OUT_DIR)
	rm -rf $(GUI_DIR)/__pycache__
	@echo "  Artefatos removidos."

help:
	@echo "Alvos disponiveis:"
	@echo "  make               compila a biblioteca C ($(LIBNAME))"
	@echo "  make run           executa a aplicacao grafica (caso de estudo)"
	@echo "  make run-headless  caso de estudo sem interface grafica"
	@echo "  make test          verifica a ponte Python <-> C"
	@echo "  make bench         benchmark de threads"
	@echo "  make clean         remove os artefatos"
	@echo ""
	@echo "Variaveis: WIDTH HEIGHT ITER THREADS NATIVE"
	@echo "Exemplo:   make run WIDTH=1280 HEIGHT=720 ITER=1000"
