#!/usr/bin/env python3
"""Gera docs/documentacao.pdf a partir do conteúdo estruturado abaixo."""

import os
import struct
import zlib

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, PageBreak, KeepTogether)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# --------------------------------------------------------------------------
# Utilitário: PPM -> PNG (sem dependências externas)
# --------------------------------------------------------------------------
def ppm_to_png(src, dst, downscale=2):
    with open(src, "rb") as f:
        data = f.read()
    parts = data.split(b"\n", 3)
    w, h = map(int, parts[1].split())
    px = parts[3]

    nw, nh = w // downscale, h // downscale
    rows = []
    for y in range(nh):
        sy = y * downscale
        row = bytearray(b"\x00")
        base = sy * w * 3
        for x in range(nw):
            o = base + x * downscale * 3
            row += px[o:o + 3]
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag, payload):
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", nw, nh, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(dst, "wb") as f:
        f.write(png)
    return nw, nh


# --------------------------------------------------------------------------
# Estilos
# --------------------------------------------------------------------------
ss = getSampleStyleSheet()
BODY = ParagraphStyle("Body", parent=ss["BodyText"], fontSize=10, leading=14.5,
                      alignment=TA_JUSTIFY, spaceAfter=7)
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=14.5, spaceBefore=14,
                    spaceAfter=8, textColor=colors.HexColor("#1a3a5c"))
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=11.5, spaceBefore=10,
                    spaceAfter=5, textColor=colors.HexColor("#2c5f8a"))
TITLE = ParagraphStyle("T", parent=ss["Title"], fontSize=20, spaceAfter=4,
                       textColor=colors.HexColor("#12283d"))
SUB = ParagraphStyle("Sub", parent=ss["Normal"], fontSize=11.5, alignment=TA_CENTER,
                     textColor=colors.HexColor("#4a5a6a"), spaceAfter=3)
CODE = ParagraphStyle("Code", parent=ss["Code"], fontSize=7.9, leading=10.2,
                      leftIndent=8, backColor=colors.HexColor("#f4f6f8"),
                      borderPadding=5, spaceBefore=4, spaceAfter=8,
                      textColor=colors.HexColor("#1c2b3a"))
CAP = ParagraphStyle("Cap", parent=ss["Normal"], fontSize=8.5, alignment=TA_CENTER,
                     textColor=colors.HexColor("#666"), spaceBefore=3, spaceAfter=10)
CELL = ParagraphStyle("Cell", parent=ss["Normal"], fontSize=8.6, leading=11.5)
CELLB = ParagraphStyle("CellB", parent=CELL, fontName="Helvetica-Bold")
CELLC = ParagraphStyle("CellC", parent=ss["Code"], fontSize=8, leading=11)


def tabela(dados, larguras, header=True):
    linhas = []
    for i, linha in enumerate(dados):
        linhas.append([c if isinstance(c, Paragraph) else
                       Paragraph(str(c), CELLB if (header and i == 0) else CELL)
                       for c in linha])
    t = Table(linhas, colWidths=larguras, repeatRows=1 if header else 0)
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d2dc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        estilo += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde5ed")),
                   ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                    [colors.white, colors.HexColor("#f7f9fb")])]
    t.setStyle(TableStyle(estilo))
    return t


def cod(texto):
    txt = (texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
           .replace(" ", "&nbsp;").replace("\n", "<br/>"))
    return Paragraph(txt, CODE)


def rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#8a97a4"))
    canvas.drawString(2.2 * cm, 1.2 * cm,
                      "Mandelbrot — Integração Python + C via FFI (ctypes)")
    canvas.drawRightString(A4[0] - 2.2 * cm, 1.2 * cm, f"pág. {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#d5dde5"))
    canvas.line(2.2 * cm, 1.5 * cm, A4[0] - 2.2 * cm, 1.5 * cm)
    canvas.restoreState()


# ==========================================================================
# Conteúdo
# ==========================================================================
S = []

S.append(Paragraph("Uso Conjunto de Duas Linguagens de Programação", TITLE))
S.append(Paragraph("Fractal de Mandelbrot: interface em Python, "
                   "cálculo em C, integração via FFI", SUB))
S.append(Spacer(1, 6))
S.append(tabela([
    ["Aplicação gráfica", "Conjunto de Mandelbrot, interativo (zoom e pan)"],
    ["Linguagem da interface", "Python 3 com Tkinter (biblioteca padrão)"],
    ["Linguagem do cálculo", "C (C99) compilada como biblioteca compartilhada, com pthreads"],
    ["Método de integração", "FFI — Foreign Function Interface — pelo módulo ctypes"],
    ["Dependências externas", "Nenhuma (nem NumPy, nem Pillow)"],
], [4.2 * cm, 11.3 * cm], header=False))
S.append(Spacer(1, 10))

# ---------------- 1
S.append(Paragraph("1. A aplicação escolhida", H1))
S.append(Paragraph(
    "O conjunto de Mandelbrot é o conjunto dos números complexos <i>c</i> para os "
    "quais a sequência definida por z<sub>0</sub> = 0 e z<sub>n+1</sub> = z<sub>n</sub><super>2</super> + c "
    "permanece limitada. Na prática, itera-se cada ponto até que |z| ultrapasse um "
    "raio de escape ou até um limite máximo de iterações; a contagem de iterações "
    "até o escape define a cor do pixel.", BODY))
S.append(Paragraph(
    "A escolha é conveniente para o propósito do trabalho por três razões. "
    "Primeiro, o algoritmo é <b>trivialmente paralelizável</b>: cada pixel é "
    "independente dos demais, o que permite explorar threads no lado C sem "
    "qualquer sincronização. Segundo, o custo é <b>concentrado e mensurável</b> — "
    "um laço aritmético apertado, exatamente o cenário em que uma linguagem "
    "compilada se distancia de uma interpretada. Terceiro, a aplicação é "
    "<b>naturalmente interativa</b>: o zoom exige recalcular a imagem a cada "
    "clique, tornando a latência do cálculo perceptível ao usuário e a "
    "qualidade da integração diretamente observável.", BODY))
S.append(Paragraph(
    "Conforme o enunciado, a aplicação gráfica em si não é o objeto de "
    "apreciação; ela é o pretexto para o problema real, tratado nas seções 3 e 4: "
    "fazer duas ferramentas de vocações distintas cooperarem.", BODY))

# ---------------- 2
S.append(Paragraph("2. Divisão de responsabilidades entre as linguagens", H1))
S.append(Paragraph(
    "A fronteira entre as linguagens foi traçada de modo que cada uma execute "
    "aquilo em que é boa, sem sobreposição. Não há uma única iteração do fractal "
    "escrita em Python, nem uma única linha de interface gráfica escrita em C.", BODY))

S.append(tabela([
    ["Arquivo", "Ling.", "Responsabilidade"],
    [Paragraph("src/mandelbrot.h", CELLC), "C",
     "Define a ABI pública — o contrato entre as duas linguagens. É o único "
     "arquivo que ambos os lados precisam conhecer."],
    [Paragraph("src/mandelbrot.c", CELLC), "C",
     "<b>Serviço de cálculo.</b> Iteração de escape, coloração contínua, testes "
     "analíticos do cardioide e do bulbo, particionamento entre pthreads."],
    [Paragraph("gui/mandelbrot_ffi.py", CELLC), "Python",
     "<b>A ponte.</b> Carrega a biblioteca, declara os protótipos, converte "
     "tipos e gerencia o buffer de pixels."],
    [Paragraph("gui/main.py", CELLC), "Python",
     "<b>Interface com o usuário.</b> Janela Tkinter, eventos de mouse e "
     "teclado, zoom/pan, exibição da imagem, gravação em disco."],
    [Paragraph("gui/headless.py", CELLC), "Python",
     "Cliente alternativo sem GUI, para ambientes sem servidor gráfico, e "
     "benchmark de escalabilidade."],
], [3.5 * cm, 1.3 * cm, 10.7 * cm]))
S.append(Spacer(1, 8))

S.append(Paragraph("2.1 Por que esta divisão e não outra", H2))
S.append(Paragraph(
    "A justificativa é quantitativa. O mesmo kernel de escape foi implementado "
    "em Python puro e medido contra a versão em C, ambos em uma única thread e "
    "sobre a mesma região do plano:", BODY))
S.append(tabela([
    ["Implementação (200×150 px, 200 iterações)", "Tempo", "Relação"],
    ["Python puro (laço interpretado)", "210 ms", "1×"],
    ["C, compilado com -O3, 1 thread", "4,1 ms", "≈ 51× mais rápido"],
], [9.0 * cm, 3.0 * cm, 3.5 * cm]))
S.append(Spacer(1, 6))
S.append(Paragraph(
    "A diferença de aproximadamente cinquenta vezes existe <i>antes</i> de "
    "qualquer paralelismo, e decorre da natureza das ferramentas: cada iteração "
    "em Python envolve despacho dinâmico de tipos e alocação de objetos "
    "<font face='Courier'>float</font>, enquanto em C a mesma operação é um punhado de "
    "instruções de ponto flutuante em registradores. Com as pthreads, o ganho "
    "escala adicionalmente com o número de núcleos.", BODY))
S.append(Paragraph(
    "A recíproca também vale: construir a mesma interface — janela, tratamento "
    "de eventos, diálogo de gravação — em C exigiria GTK ou Win32 e um volume de "
    "código desproporcional, enquanto em Python cabe em algumas dezenas de linhas "
    "com a biblioteca padrão. Cada linguagem foi empregada em sua vocação.", BODY))

S.append(PageBreak())

# ---------------- 3
S.append(Paragraph("3. O método de interface entre as duas linguagens", H1))
S.append(Paragraph(
    "Esta é a seção central do trabalho. A integração é feita por <b>FFI "
    "(Foreign Function Interface)</b> através do módulo <font face='Courier'>ctypes</font>, "
    "da biblioteca padrão do Python.", BODY))

S.append(Paragraph("3.1 Alternativas consideradas", H2))
S.append(tabela([
    ["Mecanismo", "Avaliação"],
    ["<b>ctypes</b> (adotado)",
     "Na biblioteca padrão; nenhum código de cola em C; a .so gerada é uma "
     "biblioteca C comum, reutilizável por qualquer linguagem com FFI. Custo por "
     "chamada é maior, mas irrelevante aqui — poucas chamadas de longa duração."],
    ["Python/C API",
     "Máximo desempenho, mas obriga a escrever código de cola acoplado ao "
     "interpretador (PyObject, contagem de referências), e o resultado só serve "
     "ao Python."],
    ["Cython / pybind11 / SWIG",
     "Geram o binding automaticamente, porém adicionam dependência de "
     "ferramenta e uma etapa de compilação extra, obscurecendo justamente o "
     "mecanismo que este trabalho pretende explicitar."],
    ["Subprocesso / socket / arquivo",
     "Integração por troca de dados, não por chamada de função. Custo de "
     "serialização e cópia a cada quadro, inviável para interação em tempo real."],
], [3.6 * cm, 11.9 * cm]))
S.append(Spacer(1, 6))
S.append(Paragraph(
    "O <font face='Courier'>ctypes</font> foi escolhido por ser o mecanismo que torna a "
    "fronteira <i>visível</i>: cada conversão de tipo é declarada explicitamente no "
    "código, o que serve ao propósito didático do exercício.", BODY))

S.append(Paragraph("3.2 Como o ctypes funciona", H2))
S.append(Paragraph(
    "O <font face='Courier'>ctypes</font> executa três operações:", BODY))
S.append(Paragraph(
    "<b>1. Carregamento.</b> <font face='Courier'>CDLL(caminho)</font> chama "
    "<font face='Courier'>dlopen()</font> (POSIX) ou <font face='Courier'>LoadLibrary()</font> "
    "(Windows), mapeando a biblioteca no espaço de endereçamento do próprio "
    "processo Python. Não há outro processo: o código C passa a executar dentro "
    "do interpretador.", BODY))
S.append(Paragraph(
    "<b>2. Resolução de símbolos.</b> As funções são localizadas pelo nome, como "
    "strings. Isso só funciona porque C não faz <i>name mangling</i> — o símbolo "
    "<font face='Courier'>mb_render</font> existe literalmente com esse nome na tabela da "
    "biblioteca. (Se o cálculo fosse escrito em C++, seria obrigatório envolver "
    "as declarações em <font face='Courier'>extern \"C\"</font>; o cabeçalho do projeto já "
    "prevê isso.)", BODY))
S.append(Paragraph(
    "<b>3. Marshalling e chamada.</b> Os argumentos Python são convertidos para a "
    "representação binária esperada pelo C e colocados nos registradores/pilha "
    "conforme a convenção de chamada da plataforma (System V AMD64 no Linux).", BODY))

S.append(Paragraph("3.3 O contrato: a ABI", H2))
S.append(Paragraph(
    "A fronteira foi projetada para ser a mais estreita possível. Apenas três "
    "funções são exportadas, e por elas trafegam <b>somente tipos primitivos</b>:", BODY))
S.append(cod(
    "const char *mb_version(void);\n\n"
    "int  mb_render(uint8_t *rgb, int width, int height,\n"
    "               double center_x, double center_y, double scale,\n"
    "               int max_iter, int n_threads);\n\n"
    "int  mb_iterations_at(double cx, double cy, int max_iter);"))
S.append(Paragraph(
    "Nenhuma <font face='Courier'>struct</font> atravessa a fronteira. Essa restrição é "
    "deliberada: compartilhar uma struct exigiria replicar seu layout de memória "
    "no lado Python com <font face='Courier'>ctypes.Structure</font>, incluindo o "
    "<i>padding</i> inserido pelo compilador — uma fonte clássica de erros "
    "silenciosos, pois um desalinhamento não gera erro, apenas dados corrompidos. "
    "As structs internas do C (<font face='Courier'>mb_task_t</font>) permanecem "
    "invisíveis ao Python.", BODY))
S.append(Paragraph(
    "A compilação com <font face='Courier'>-fvisibility=hidden</font> reforça o contrato: "
    "apenas os símbolos marcados no cabeçalho são exportados; todo o restante "
    "(funções <font face='Courier'>static</font> como o kernel de escape) fica oculto.", BODY))

S.append(Paragraph("3.4 Declaração dos protótipos", H2))
S.append(Paragraph(
    "Este é o passo mais crítico da integração. O <font face='Courier'>ctypes</font> não "
    "consegue ler o arquivo <font face='Courier'>.h</font>: a biblioteca compilada não "
    "carrega informação de tipos. Portanto a assinatura precisa ser "
    "<b>redeclarada manualmente</b> no lado Python:", BODY))
S.append(cod(
    "_lib.mb_render.argtypes = [\n"
    "    ctypes.POINTER(ctypes.c_uint8),  # rgb (buffer de saída)\n"
    "    ctypes.c_int, ctypes.c_int,      # width, height\n"
    "    ctypes.c_double, ctypes.c_double,# center_x, center_y\n"
    "    ctypes.c_double,                 # scale\n"
    "    ctypes.c_int, ctypes.c_int,      # max_iter, n_threads\n"
    "]\n"
    "_lib.mb_render.restype = ctypes.c_int"))
S.append(Paragraph(
    "Omitir <font face='Courier'>argtypes</font> não é uma otimização de conveniência: o "
    "ctypes assumiria que todo argumento é <font face='Courier'>int</font>. Os "
    "<font face='Courier'>double</font> seriam então passados pelos registradores de "
    "inteiros em vez dos de ponto flutuante (XMM0–XMM7 na convenção System V), e "
    "o C leria lixo — <b>sem qualquer mensagem de erro</b>, apenas uma imagem "
    "incorreta. É a armadilha mais comum ao usar ctypes, e a razão pela qual a "
    "declaração explícita é o coração do módulo-ponte.", BODY))
S.append(Paragraph(
    "Declarar <font face='Courier'>restype = c_char_p</font> em "
    "<font face='Courier'>mb_version</font> instrui o ctypes a converter o "
    "<font face='Courier'>char*</font> retornado em <font face='Courier'>bytes</font> Python. "
    "Como a string é estática no C, ela vive por toda a execução e pode ser lida "
    "sem risco de ponteiro pendente.", BODY))

S.append(PageBreak())

S.append(Paragraph("3.5 Gerência de memória através da fronteira", H2))
S.append(Paragraph(
    "Este é o ponto onde integrações entre linguagens costumam falhar. O C usa "
    "<font face='Courier'>malloc/free</font> explícitos; o Python usa contagem de "
    "referências e coletor de lixo. <b>Os dois sistemas não se comunicam.</b> Se o "
    "C alocasse o buffer da imagem e devolvesse o ponteiro, surgiria a pergunta "
    "insolúvel: quem o libera? O Python não pode chamar <font face='Courier'>free()</font> "
    "sobre memória que ele não conhece, e o coletor de lixo jamais recuperaria "
    "esse bloco — vazamento a cada quadro renderizado.", BODY))
S.append(Paragraph(
    "A solução adotada inverte a responsabilidade: <b>o buffer é alocado pelo "
    "Python e apenas preenchido pelo C.</b>", BODY))
S.append(cod(
    "n_bytes = width * height * 3\n"
    "buf = ctypes.create_string_buffer(n_bytes)   # alocado pelo Python\n"
    "ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint8))\n"
    "\n"
    "used = _lib.mb_render(ptr, width, height, ...)  # C apenas ESCREVE\n"
    "\n"
    "return buf.raw[:n_bytes]   # bytes gerenciados normalmente pelo GC"))
S.append(Paragraph(
    "Assim o Python permanece dono exclusivo da memória do início ao fim. Não há "
    "vazamento nem <i>double free</i>, e o objeto é coletado normalmente quando "
    "sai de escopo. O C, por sua vez, aloca apenas seus vetores internos de "
    "threads e os libera na mesma função — nenhuma alocação sua sobrevive ao "
    "retorno.", BODY))
S.append(Paragraph(
    "Como contrapartida dessa escolha, o C não pode confiar no chamador: um "
    "buffer de tamanho errado causaria corrupção de heap. Por isso "
    "<font face='Courier'>mb_render()</font> valida defensivamente todos os argumentos e "
    "retorna −1 em caso de inconsistência, valor que o lado Python converte em "
    "uma exceção <font face='Courier'>ValueError</font> — traduzindo o idioma de erros do "
    "C (códigos de retorno) para o do Python (exceções).", BODY))

S.append(Paragraph("3.6 Concorrência: o GIL e as pthreads", H2))
S.append(Paragraph(
    "O <i>Global Interpreter Lock</i> impede que dois <i>bytecodes</i> Python "
    "executem simultaneamente, o que normalmente inviabiliza paralelismo real com "
    "threads em Python. A integração contorna isso por uma propriedade do "
    "mecanismo escolhido: <b>o ctypes libera o GIL automaticamente antes de "
    "chamar uma função de uma <font face='Courier'>CDLL</font> e o readquire ao "
    "retornar.</b>", BODY))
S.append(Paragraph("Duas consequências se somam:", BODY))
S.append(Paragraph(
    "• As pthreads criadas dentro de <font face='Courier'>mb_render()</font> executam com "
    "paralelismo real, pois o GIL não está retido durante a chamada. O "
    "paralelismo acontece integralmente abaixo da fronteira, invisível ao Python.", BODY))
S.append(Paragraph(
    "• A interface permanece responsiva. A GUI dispara o cálculo em uma thread "
    "Python auxiliar; como essa thread solta o GIL ao entrar no C, o laço de "
    "eventos do Tk continua girando na thread principal e a janela não congela.", BODY))
S.append(Paragraph(
    "Há uma restrição a respeitar: o Tk não é <i>thread-safe</i>. A imagem, "
    "portanto, não é publicada na tela pela thread de trabalho; o resultado é "
    "reagendado para a thread principal com <font face='Courier'>root.after(0, ...)</font>. "
    "A regra resultante é: <i>calcular em qualquer thread, desenhar somente na "
    "principal</i>.", BODY))

S.append(Paragraph("3.7 Transporte da imagem até a tela", H2))
S.append(Paragraph(
    "O C devolve um vetor de bytes RGB entrelaçado. Para exibi-lo sem recorrer a "
    "Pillow ou NumPy, o Python antepõe um cabeçalho PPM (formato P6) aos bytes — "
    "um cabeçalho de texto de três linhas seguido dos pixels crus — e entrega o "
    "resultado ao widget <font face='Courier'>PhotoImage</font>, que lê PPM nativamente:", BODY))
S.append(cod(
    "header = f\"P6\\n{width} {height}\\n255\\n\".encode(\"ascii\")\n"
    "ppm = header + rgb          # nenhuma conversão dos pixels\n"
    "photo = tk.PhotoImage(data=ppm)"))
S.append(Paragraph(
    "A escolha do formato RGB entrelaçado na ABI não foi arbitrária: é "
    "exatamente o layout que o PPM exige, de modo que os bytes produzidos pelo C "
    "chegam à tela <b>sem nenhuma transformação intermediária</b>. O projeto "
    "assim permanece restrito à biblioteca padrão do Python.", BODY))

S.append(PageBreak())

# ---------------- 4
S.append(Paragraph("4. Fluxo completo de uma interação", H1))
S.append(Paragraph(
    "O trajeto de um clique do usuário até o pixel na tela, atravessando a "
    "fronteira duas vezes:", BODY))

S.append(tabela([
    ["#", "Lado", "Ação"],
    ["1", "Python", "O usuário clica no canvas. O Tk entrega o evento com as coordenadas (px, py) em pixels."],
    ["2", "Python", "<font face='Courier'>pixel_to_complex()</font> converte o pixel em um ponto do plano complexo e atualiza centro e escala da vista."],
    ["3", "Python", "Uma thread auxiliar é criada; <font face='Courier'>create_string_buffer()</font> aloca width×height×3 bytes."],
    ["4", "<b>ponte</b>", "<b>O ctypes converte os argumentos, libera o GIL e chama mb_render().</b>"],
    ["5", "C", "A janela é convertida de pixels para o plano complexo; as linhas são particionadas entre N pthreads."],
    ["6", "C", "Cada thread itera z ← z² + c por pixel, aplica a coloração contínua e escreve direto no buffer do Python."],
    ["7", "<b>ponte</b>", "<b>mb_render() retorna; o ctypes readquire o GIL.</b>"],
    ["8", "Python", "Os bytes recebem o cabeçalho PPM e o resultado é reagendado para a thread principal via <font face='Courier'>after(0, ...)</font>."],
    ["9", "Python", "<font face='Courier'>PhotoImage</font> exibe a imagem; a barra de status reporta o tempo gasto dentro do C."],
], [0.9 * cm, 1.9 * cm, 12.7 * cm]))
S.append(Spacer(1, 8))
S.append(Paragraph(
    "Note que os passos 5 e 6 desconhecem completamente a existência do Python, e "
    "os passos 1, 2, 8 e 9 desconhecem completamente a existência do C. O "
    "acoplamento está inteiramente confinado aos passos 4 e 7 — ou seja, ao "
    "arquivo <font face='Courier'>mandelbrot_ffi.py</font> e ao cabeçalho "
    "<font face='Courier'>mandelbrot.h</font>.", BODY))
S.append(Paragraph(
    "A aplicação também exercita uma chamada FFI de granularidade oposta: a cada "
    "movimento do mouse, <font face='Courier'>mb_iterations_at()</font> é invocada para um "
    "único ponto (dois <font face='Courier'>double</font> → um <font face='Courier'>int</font>) e "
    "o resultado aparece na barra inferior. O contraste entre as duas — uma "
    "chamada longa devolvendo um megabyte e uma chamada curtíssima devolvendo um "
    "inteiro — evidencia que o custo fixo por travessia da fronteira só importa "
    "quando as chamadas são muito frequentes e muito baratas.", BODY))

# ---------------- 5
S.append(Paragraph("5. Compilação e execução", H1))
S.append(Paragraph(
    "A compilação usa três flags essenciais à interoperabilidade: "
    "<font face='Courier'>-fPIC</font>, que gera código independente de posição (obrigatório, "
    "pois a biblioteca é mapeada em endereço arbitrário no processo do "
    "interpretador); <font face='Courier'>-shared</font>, que produz a biblioteca em vez de um "
    "executável; e <font face='Courier'>-fvisibility=hidden</font>, que restringe a "
    "exportação aos símbolos da ABI.", BODY))
S.append(cod(
    "gcc -std=c99 -O3 -march=native -fPIC -fvisibility=hidden \\\n"
    "    -c src/mandelbrot.c -o build/mandelbrot.o\n"
    "gcc -shared -o build/libmandelbrot.so build/mandelbrot.o -lpthread -lm"))
S.append(tabela([
    ["Comando", "Efeito"],
    [Paragraph("make", CELLC), "Compila a biblioteca compartilhada."],
    [Paragraph("make run", CELLC), "<b>Caso de estudo:</b> abre a aplicação gráfica."],
    [Paragraph("make run-headless", CELLC), "Caso de estudo sem servidor gráfico; gera as imagens em out/."],
    [Paragraph("make test", CELLC), "Verifica a ponte: carrega a .so e valida as três funções."],
    [Paragraph("make bench", CELLC), "Mede a escalabilidade com o número de threads."],
    [Paragraph("make clean", CELLC), "Remove os artefatos gerados."],
], [4.3 * cm, 11.2 * cm]))
S.append(Spacer(1, 5))
S.append(Paragraph(
    "O Makefile detecta o sistema operacional e ajusta o nome da biblioteca "
    "(<font face='Courier'>.so</font>, <font face='Courier'>.dylib</font> ou <font face='Courier'>.dll</font>) e as "
    "flags de ligação; o lado Python faz a detecção correspondente ao procurar o "
    "arquivo. O único requisito além do compilador e do Python é o Tkinter.", BODY))

# ---------------- 6 (imagens)
S.append(PageBreak())
S.append(Paragraph("6. Resultados", H1))

img1 = os.path.join(HERE, "_fig_full.png")
img2 = os.path.join(HERE, "_fig_zoom.png")
w1, h1 = ppm_to_png(os.path.join(ROOT, "out", "mandelbrot.ppm"), img1, 2)
w2, h2 = ppm_to_png(os.path.join(ROOT, "out", "mandelbrot_zoom.ppm"), img2, 2)

LARG = 13.2 * cm
S.append(KeepTogether([
    Image(img1, LARG, LARG * h1 / w1),
    Paragraph("Figura 1 — Vista completa do conjunto, 1200×800, 800 iterações. "
              "Calculada em C em 186 ms e exibida pela interface em Python.", CAP),
]))
S.append(KeepTogether([
    Image(img2, LARG, LARG * h2 / w2),
    Paragraph("Figura 2 — Vale dos Cavalos-Marinhos, zoom de aproximadamente "
              "5000× em c ≈ −0,743644 + 0,131826i, com 1500 iterações (600 ms). "
              "O aumento do custo com a profundidade do zoom é o que torna a "
              "delegação do cálculo ao C perceptível na interação.", CAP),
]))

S.append(Paragraph("6.1 Verificação da ponte", H2))
S.append(cod(
    "$ make test\n"
    "Biblioteca C carregada de: .../build/libmandelbrot.so\n"
    "Versao reportada pelo C : libmandelbrot 1.0 (C99 + pthreads)\n"
    "Render 80x40 OK: 9600 bytes\n"
    "Iteracoes em (0,0) : 500 (esperado: 500)\n"
    "Iteracoes em (2,2) : 4 (esperado: baixo)"))
S.append(Paragraph(
    "O teste valida os três aspectos da integração: a leitura da string estática "
    "confirma o marshalling de <font face='Courier'>char*</font>; o buffer de 9600 bytes "
    "confirma a escrita do C na memória do Python; e os pontos de controle "
    "confirmam que os <font face='Courier'>double</font> chegaram corretamente ao C — a "
    "origem pertence ao conjunto (atinge o teto de iterações) e o ponto (2,2) "
    "escapa em poucas iterações. Se os <font face='Courier'>argtypes</font> estivessem "
    "ausentes, este último teste falharia.", BODY))

S.append(Paragraph("6.2 Escalabilidade", H2))
S.append(Paragraph(
    "O <font face='Courier'>make bench</font> repete o cálculo variando o número de threads "
    "solicitado ao C. Em máquinas multicore o tempo cai de forma aproximadamente "
    "linear até o número de núcleos físicos, resultado esperado para um problema "
    "sem dependência entre pixels e sem sincronização — as faixas de linhas "
    "atribuídas às threads são disjuntas, dispensando qualquer mutex. No ambiente "
    "de validação utilizado, com uma única vCPU disponível, o <i>speedup</i> "
    "medido foi de 1,00× para qualquer número de threads, como seria de se "
    "esperar.", BODY))

# ---------------- 7
S.append(Paragraph("7. Considerações finais", H1))
S.append(Paragraph(
    "O exercício confirma que o trabalho real de uma integração entre linguagens "
    "não está em nenhuma das duas, mas na costura entre elas. O fractal e a "
    "janela Tk são código convencional; as decisões que sustentam o projeto são "
    "todas de fronteira: manter a ABI restrita a tipos primitivos, atribuir a "
    "posse da memória a um único lado, declarar os tipos explicitamente onde o "
    "compilador não pode mais verificá-los, e escolher um formato de dados "
    "(RGB entrelaçado) que sirva aos dois lados sem conversão.", BODY))
S.append(Paragraph(
    "O padrão resultante — <i>núcleo compilado, casca interpretada</i> — não é "
    "particular a este projeto. É a mesma arquitetura de NumPy, TensorFlow e "
    "boa parte do ecossistema científico do Python: um kernel em C ou Fortran "
    "para o custo computacional, e uma camada em linguagem de alto nível para a "
    "expressividade e a interação. Cada ferramenta na sua vocação, com uma "
    "fronteira estreita e explícita entre elas.", BODY))

# --------------------------------------------------------------------------
doc = SimpleDocTemplate(os.path.join(HERE, "documentacao.pdf"), pagesize=A4,
                        leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                        topMargin=1.9 * cm, bottomMargin=1.9 * cm,
                        title="Mandelbrot — Integração Python + C via FFI",
                        author="Documentação da implementação")
doc.build(S, onFirstPage=rodape, onLaterPages=rodape)

os.remove(img1)
os.remove(img2)
print("documentacao.pdf gerado")
