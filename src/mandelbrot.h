/* ============================================================================
 * mandelbrot.h — Interface pública (ABI) da biblioteca de cálculo em C.
 * ----------------------------------------------------------------------------
 * Este cabeçalho define o "contrato" entre as duas linguagens do projeto:
 *
 *   - C      : implementa o SERVIÇO DE CÁLCULO (kernel numérico do fractal).
 *   - Python : implementa a INTERFACE COM O USUÁRIO e a exibição da imagem.
 *
 * A ponte entre elas é feita via FFI (Foreign Function Interface) usando o
 * módulo `ctypes` da biblioteca padrão do Python, que carrega este código
 * compilado como biblioteca compartilhada (libmandelbrot.so / .dll / .dylib)
 * e invoca as funções abaixo diretamente.
 *
 * REGRAS DE PROJETO DA ABI (importantes para a interoperabilidade):
 *   1. Somente tipos primitivos de C atravessam a fronteira (int, double,
 *      ponteiro para byte). Nada de structs complexas ou tipos do C++, pois
 *      isso exigiria replicar layouts de memória do lado Python.
 *   2. `extern "C"` + ausência de "name mangling": os símbolos são exportados
 *      com nome literal, permitindo que o ctypes os encontre por string.
 *   3. GERÊNCIA DE MEMÓRIA: o buffer de pixels é ALOCADO PELO PYTHON e apenas
 *      PREENCHIDO pelo C. Assim evita-se o problema clássico de "quem libera
 *      a memória?" através da fronteira entre linguagens (o alocador do C e o
 *      garbage collector do Python não conversam entre si).
 * ==========================================================================*/

#ifndef MANDELBROT_H
#define MANDELBROT_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Marcação de exportação de símbolo (portabilidade Windows/POSIX). */
#if defined(_WIN32) || defined(_WIN64)
#  define MB_EXPORT __declspec(dllexport)
#else
#  define MB_EXPORT __attribute__((visibility("default")))
#endif

/* --------------------------------------------------------------------------
 * mb_version
 * --------------------------------------------------------------------------
 * Retorna uma string estática identificando a biblioteca. Serve como
 * "handshake" simples: se o Python consegue ler esta string, o carregamento
 * da .so e a convenção de chamada estão corretos.
 *
 * Retorno: ponteiro para string constante (NÃO deve ser liberada pelo Python).
 * ------------------------------------------------------------------------*/
MB_EXPORT const char *mb_version(void);

/* --------------------------------------------------------------------------
 * mb_render
 * --------------------------------------------------------------------------
 * Calcula o conjunto de Mandelbrot para a janela do plano complexo indicada e
 * escreve o resultado, já colorido, no buffer RGB fornecido pelo chamador.
 *
 * Parâmetros:
 *   rgb       [out] Buffer de saída com width*height*3 bytes, no formato
 *                   RGB entrelaçado (R,G,B,R,G,B,...), linhas de cima para
 *                   baixo. ALOCADO PELO PYTHON.
 *   width     [in]  Largura da imagem em pixels (> 0).
 *   height    [in]  Altura da imagem em pixels (> 0).
 *   center_x  [in]  Parte real do centro da janela de visualização.
 *   center_y  [in]  Parte imaginária do centro da janela de visualização.
 *   scale     [in]  Altura da janela no plano complexo (unidades). A largura
 *                   é derivada preservando a proporção da imagem.
 *   max_iter  [in]  Número máximo de iterações por pixel (> 0).
 *   n_threads [in]  Número de threads POSIX a utilizar. Se <= 0, a biblioteca
 *                   detecta automaticamente o número de núcleos disponíveis.
 *
 * Retorno: número de threads efetivamente utilizadas, ou -1 em caso de
 *          argumento inválido.
 *
 * Observação: a função é reentrante e não mantém estado global.
 * ------------------------------------------------------------------------*/
MB_EXPORT int mb_render(uint8_t *rgb,
                        int width, int height,
                        double center_x, double center_y,
                        double scale,
                        int max_iter,
                        int n_threads);

/* --------------------------------------------------------------------------
 * mb_iterations_at
 * --------------------------------------------------------------------------
 * Calcula apenas a contagem de iterações de um único ponto do plano complexo.
 * Usada pela interface para exibir informação de diagnóstico sob o cursor,
 * demonstrando uma chamada FFI de granularidade fina (escalar -> escalar).
 *
 * Retorno: número de iterações até o escape, ou max_iter se o ponto pertence
 *          (provavelmente) ao conjunto.
 * ------------------------------------------------------------------------*/
MB_EXPORT int mb_iterations_at(double cx, double cy, int max_iter);

#ifdef __cplusplus
}
#endif

#endif /* MANDELBROT_H */
