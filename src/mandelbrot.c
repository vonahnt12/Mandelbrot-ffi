/* ============================================================================
 * mandelbrot.c — Serviço de cálculo do conjunto de Mandelbrot.
 * ----------------------------------------------------------------------------
 * Papel desta linguagem no trabalho: C é a linguagem "de vocação numérica"
 * do projeto. Aqui concentra-se todo o custo computacional (a iteração
 * z <- z^2 + c por pixel), explorando aritmética de ponto flutuante nativa e
 * paralelismo com threads POSIX. Nenhuma linha de interface gráfica existe
 * neste arquivo — a imagem é apenas um vetor de bytes.
 *
 * Compilação (ver Makefile):
 *   gcc -O3 -march=native -fPIC -shared mandelbrot.c -o libmandelbrot.so -lpthread -lm
 * ==========================================================================*/

#include "mandelbrot.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>

/* Raio de escape. Usa-se 2 (i.e. |z|^2 > 4) como critério clássico: se o
 * módulo de z ultrapassa 2, a órbita diverge necessariamente. Um raio maior
 * (aqui 2^8) melhora a qualidade da coloração contínua, ao custo de poucas
 * iterações extras. */
#define ESCAPE_RADIUS      256.0
#define ESCAPE_RADIUS_SQ   (ESCAPE_RADIUS * ESCAPE_RADIUS)

/* ---------------------------------------------------------------------------
 * Estrutura de trabalho passada a cada thread. É INTERNA à biblioteca: não
 * atravessa a fronteira FFI, justamente para manter a ABI simples.
 * -------------------------------------------------------------------------*/
typedef struct {
    uint8_t *rgb;          /* buffer de saída compartilhado (fornecido pelo Python) */
    int      width;
    int      height;
    double   x_min;        /* canto do retângulo no plano complexo */
    double   y_min;
    double   step;         /* tamanho do pixel em unidades do plano complexo */
    int      max_iter;
    int      y_start;      /* faixa horizontal [y_start, y_end) desta thread */
    int      y_end;
} mb_task_t;

/* ---------------------------------------------------------------------------
 * mb_escape_smooth
 * ---------------------------------------------------------------------------
 * Núcleo matemático. Itera z_{n+1} = z_n^2 + c com z_0 = 0 e conta quantas
 * iterações são necessárias para que |z| escape do raio de escape.
 *
 * Retorna uma contagem CONTÍNUA (real) de iterações, obtida pela fórmula do
 * "normalized iteration count":
 *
 *     nu = n + 1 - log2( log(|z|) / log(R) )
 *
 * Isso elimina as faixas de cor abruptas que apareceriam com a contagem
 * inteira. Se o ponto não escapar dentro de max_iter, retorna-se -1.0 como
 * marcador de "pertence ao conjunto".
 *
 * Otimizações aplicadas:
 *   - Teste de cardioide e do bulbo principal: descarta analiticamente os dois
 *     maiores componentes do conjunto sem iterar, o que economiza a maior
 *     parte do tempo na visualização inicial.
 *   - Aritmética com zx2/zy2 reutilizados, evitando multiplicações redundantes
 *     e o cálculo de raiz quadrada dentro do laço.
 * -------------------------------------------------------------------------*/
static double mb_escape_smooth(double cx, double cy, int max_iter)
{
    /* --- Teste do cardioide principal: |1 - sqrt(1-4c)| <= 1 (forma otimizada) */
    double x_m = cx - 0.25;
    double q   = x_m * x_m + cy * cy;
    if (q * (q + x_m) <= 0.25 * cy * cy)
        return -1.0;                       /* interior: pertence ao conjunto */

    /* --- Teste do bulbo de período 2, centrado em (-1, 0) com raio 1/4 --- */
    double x_p = cx + 1.0;
    if (x_p * x_p + cy * cy <= 0.0625)
        return -1.0;

    /* --- Iteração principal ------------------------------------------------ */
    double zx = 0.0, zy = 0.0;             /* z = zx + i*zy */
    double zx2 = 0.0, zy2 = 0.0;           /* zx^2 e zy^2, reaproveitados */
    int n;

    for (n = 0; n < max_iter && (zx2 + zy2) <= ESCAPE_RADIUS_SQ; ++n) {
        zy  = 2.0 * zx * zy + cy;          /* parte imaginária de z^2 + c */
        zx  = zx2 - zy2 + cx;              /* parte real de z^2 + c */
        zx2 = zx * zx;
        zy2 = zy * zy;
    }

    if (n >= max_iter)
        return -1.0;                       /* não escapou: dentro do conjunto */

    /* Suavização: converte a contagem inteira em um valor real contínuo. */
    double mod   = sqrt(zx2 + zy2);
    double nu    = log(log(mod) / log(ESCAPE_RADIUS)) / log(2.0);
    double value = (double)(n + 1) - nu;

    return value < 0.0 ? 0.0 : value;
}

/* ---------------------------------------------------------------------------
 * mb_colorize
 * ---------------------------------------------------------------------------
 * Mapeia a contagem contínua de iterações para uma cor RGB usando uma paleta
 * trigonométrica ("cosine palette"): barata de calcular, periódica e sem
 * necessidade de tabela em memória. Pontos internos ao conjunto ficam pretos.
 * -------------------------------------------------------------------------*/
static void mb_colorize(double iter, uint8_t *out)
{
    if (iter < 0.0) {                      /* interior do conjunto */
        out[0] = out[1] = out[2] = 0;
        return;
    }

    /* t controla a velocidade de variação das cores ao longo das faixas. */
    double t = 0.16 * iter;

    /* cor = 0.5 + 0.5*cos(t + fase), com fases distintas por canal. */
    double r = 0.5 + 0.5 * cos(t + 0.0);
    double g = 0.5 + 0.5 * cos(t + 0.6);
    double b = 0.5 + 0.5 * cos(t + 1.0);

    out[0] = (uint8_t)(255.0 * r);
    out[1] = (uint8_t)(255.0 * g);
    out[2] = (uint8_t)(255.0 * b);
}

/* ---------------------------------------------------------------------------
 * mb_worker
 * ---------------------------------------------------------------------------
 * Corpo de cada thread: percorre uma faixa de linhas da imagem. Como as faixas
 * são disjuntas, não há escrita concorrente na mesma posição do buffer e,
 * portanto, nenhum mutex é necessário.
 * -------------------------------------------------------------------------*/
static void *mb_worker(void *arg)
{
    mb_task_t *t = (mb_task_t *)arg;

    for (int py = t->y_start; py < t->y_end; ++py) {
        /* Eixo y invertido: linha 0 da imagem = topo = maior parte imaginária. */
        double cy = t->y_min + (t->height - 1 - py) * t->step;
        uint8_t *row = t->rgb + (size_t)py * t->width * 3;

        for (int px = 0; px < t->width; ++px) {
            double cx   = t->x_min + px * t->step;
            double iter = mb_escape_smooth(cx, cy, t->max_iter);
            mb_colorize(iter, row + (size_t)px * 3);
        }
    }
    return NULL;
}

/* ---------------------------------------------------------------------------
 * mb_default_threads — detecta o número de núcleos de forma portável.
 * -------------------------------------------------------------------------*/
static int mb_default_threads(void)
{
#if defined(_SC_NPROCESSORS_ONLN)
    long n = sysconf(_SC_NPROCESSORS_ONLN);
    return (n > 0) ? (int)n : 1;
#else
    return 4;
#endif
}

/* =====================  FUNÇÕES EXPORTADAS PELA ABI  ===================== */

const char *mb_version(void)
{
    /* String estática: vive por toda a execução, logo pode ser lida pelo
     * Python sem risco de dangling pointer e sem transferir posse. */
    return "libmandelbrot 1.0 (C99 + pthreads)";
}

int mb_iterations_at(double cx, double cy, int max_iter)
{
    if (max_iter <= 0) return -1;
    double v = mb_escape_smooth(cx, cy, max_iter);
    return (v < 0.0) ? max_iter : (int)v;
}

int mb_render(uint8_t *rgb,
              int width, int height,
              double center_x, double center_y,
              double scale,
              int max_iter,
              int n_threads)
{
    /* Validação defensiva: a fronteira FFI não oferece nenhuma checagem de
     * tipo em tempo de execução, então a biblioteca não confia no chamador. */
    if (!rgb || width <= 0 || height <= 0 || max_iter <= 0 || scale <= 0.0)
        return -1;

    if (n_threads <= 0)
        n_threads = mb_default_threads();
    if (n_threads > height)
        n_threads = height;                /* não faz sentido mais threads que linhas */

    /* Conversão do sistema de coordenadas: pixels -> plano complexo.
     * `scale` é a ALTURA da janela; a largura é derivada da proporção, de modo
     * que o fractal nunca apareça distorcido ao redimensionar a janela. */
    double step  = scale / (double)height;
    double x_min = center_x - (width  * step) / 2.0;
    double y_min = center_y - (height * step) / 2.0;

    pthread_t *tids  = (pthread_t *)malloc(sizeof(pthread_t) * n_threads);
    mb_task_t *tasks = (mb_task_t *)malloc(sizeof(mb_task_t) * n_threads);
    if (!tids || !tasks) {                 /* fallback: executa em série */
        free(tids); free(tasks);
        mb_task_t solo = { rgb, width, height, x_min, y_min, step,
                           max_iter, 0, height };
        mb_worker(&solo);
        return 1;
    }

    /* Particionamento em faixas horizontais contíguas. O resto da divisão é
     * distribuído entre as primeiras threads para balancear a carga. */
    int base = height / n_threads;
    int rest = height % n_threads;
    int y    = 0;
    int launched = 0;

    for (int i = 0; i < n_threads; ++i) {
        int rows = base + (i < rest ? 1 : 0);
        tasks[i] = (mb_task_t){ rgb, width, height, x_min, y_min, step,
                                max_iter, y, y + rows };
        y += rows;

        if (pthread_create(&tids[i], NULL, mb_worker, &tasks[i]) == 0)
            launched++;
        else
            mb_worker(&tasks[i]);          /* se falhar, o chamador faz o trabalho */
    }

    for (int i = 0; i < launched; ++i)
        pthread_join(tids[i], NULL);

    free(tids);
    free(tasks);
    return n_threads;
}
