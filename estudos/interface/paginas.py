"""HTML das páginas internas no estilo "Mosaico colorido".

  estudos://inicio            -> página inicial
  (tela de bloqueio)          -> gerada na hora, quando um site é barrado
O visual fica em recursos/paginas/mosaico.css.
"""

import datetime
from html import escape
from ..nucleo.tempo import formatar
from ..nucleo.urls import analisar

CSS = '<link rel="stylesheet" href="estudos://recursos/paginas/mosaico.css">'

# Cor de cada categoria, na ordem em que aparecem na lista.
# (classe CSS, é escura?) — nas escuras o texto fica branco.
CORES = [("cor-lilas", True), ("cor-verde", False), ("cor-amarelo", False),
         ("cor-azul", True), ("cor-coral", False), ("cor-branco", False)]

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

DICAS = [
    "Explique o assunto em voz alta como se ensinasse alguém. Onde travar é o que falta estudar.",
    "Antes de reler, tente lembrar sozinho o que estudou ontem. Puxar da memória fixa mais.",
    "Peça para a IA criar 5 perguntas sobre o tema e responda sem consultar.",
    "Estude em blocos curtos com pausas: use o botão 🍅 lá em cima.",
    "Misture matérias no mesmo dia. Alternar ajuda o cérebro a diferenciar os assuntos.",
    "Use a IA para tirar dúvidas, mas confira a resposta na Wikipédia ou no livro.",
    "Resuma cada página em uma frase com suas palavras.",
    "Revise o que aprendeu em 1 dia, 1 semana e 1 mês: isso evita esquecer.",
]


def _data_por_extenso(hoje):
    return f"{DIAS[hoje.weekday()].capitalize()}, {hoje.day} de {MESES[hoje.month - 1]}"


def _saudacao(hora):
    if hora < 12:
        return "Bom dia"
    return "Boa tarde" if hora < 18 else "Boa noite"


def _bloco_categoria(categoria, indice, ordem):
    classe, escura = CORES[indice % len(CORES)]
    largo = len(categoria.atalhos) > 4
    itens = []
    for atalho in categoria.atalhos:
        host = escape(analisar(atalho.url).host)
        itens.append(f"""
        <li><a class="site" href="{escape(atalho.url)}">
          <span class="selo"><img src="https://{host}/favicon.ico" alt=""
                onerror="this.remove()">{escape(atalho.nome[:1].upper())}</span>
          <span><strong>{escape(atalho.nome)}</strong><small>{escape(atalho.dominio)}</small></span>
        </a></li>""")
    classes = f"bloco categoria {classe}{' escuro' if escura else ''}{' largo' if largo else ''}"
    return f"""
    <section class="{classes}" style="--ordem:{ordem}">
      <h2>{escape(categoria.nome)}</h2>
      <ul>{''.join(itens)}</ul>
    </section>"""


def pagina_inicial(lista, contador, preferencias):
    agora = datetime.datetime.now()
    total = contador.total()
    meta = max(1, int(preferencias.get("meta_minutos", 60))) * 60
    progresso = min(100, 100 * total / meta)
    falta = meta - total
    texto_meta = ("Meta de hoje batida! 🎉" if falta <= 0 else
                  f"Meta: {formatar(meta)} · faltam {formatar(falta)}")
    if total < 60:
        texto_total = "0 min"
    else:
        texto_total = formatar(total)

    dias = contador.dias_seguidos()
    texto_dias = "1 dia" if dias == 1 else f"{dias} dias"
    detalhe_dias = ("Estude 10 min hoje para começar sua sequência." if dias == 0 else
                    "Estude 10 min por dia para manter o fogo aceso.")

    ranking = contador.ranking(lista.nome_para_estatistica)[:5]
    linhas_uso = "".join(f"<li><span>{escape(site)}</span><span>{formatar(seg)}</span></li>"
                         for site, seg in ranking)
    uso = (f"<ol>{linhas_uso}</ol>" if ranking else
           '<p class="vazio">Nenhum site visitado ainda hoje. Escolha um atalho para começar.</p>')

    ordem = 3
    categorias = []
    for indice, categoria in enumerate(lista.categorias):
        if categoria.atalhos:
            categorias.append(_bloco_categoria(categoria, indice, ordem))
            ordem += 1

    dica = DICAS[agora.timetuple().tm_yday % len(DICAS)]

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Página inicial</title>{CSS}</head><body><main class="mosaico">

  <section class="bloco largo boas-vindas" style="--ordem:0">
    <div class="bolinha" aria-hidden="true"></div>
    <p class="data">{_data_por_extenso(agora.date())}</p>
    <h1>{_saudacao(agora.hour)}!<br>O que vamos aprender hoje?</h1>
    <form class="busca" action="https://pt.wikipedia.org/w/index.php" method="get" role="search">
      <input name="search" placeholder="Pesquisar na Wikipédia" aria-label="Pesquisar na Wikipédia"
             autocomplete="off">
      <button>Pesquisar</button>
    </form>
  </section>

  <section class="bloco numero hoje" style="--ordem:1">
    <p class="rotulo">Estudo de hoje</p>
    <div class="valor">{texto_total}</div>
    <div>
      <div class="meta" role="progressbar" aria-valuenow="{progresso:.0f}"
           aria-valuemin="0" aria-valuemax="100"><div style="width:{progresso:.0f}%"></div></div>
      <p class="detalhe">{texto_meta}</p>
    </div>
  </section>

  <section class="bloco numero sequencia" style="--ordem:2">
    <p class="rotulo">Sequência</p>
    <div class="valor">🔥 {texto_dias}</div>
    <p class="detalhe">{detalhe_dias}</p>
  </section>

  {''.join(categorias)}

  <section class="bloco uso" style="--ordem:{ordem}">
    <h2>Onde você estudou hoje</h2>
    {uso}
  </section>

  <section class="bloco dica" style="--ordem:{ordem + 1}">
    <h2>Dica de estudo</h2>
    <p>{escape(dica)}</p>
  </section>

</main></body></html>"""


MOTIVOS = {
    "fora_da_lista": ("Este site não está na lista de estudos",
                      "O Navegador de Estudos só abre sites aprovados pelo responsável."),
    "excluido": ("Esta parte do site não está liberada",
                 "O site é permitido, mas esta seção (fórum, chat ou rede social) foi barrada."),
    "redirecionamento": ("O site tentou levar você para fora da lista",
                         "A página permitida redirecionou para um endereço que não está aprovado."),
    "invalido": ("Este endereço é inválido ou está disfarçado",
                 "Ele usa um formato que pode enganar o filtro, por isso foi barrado."),
    "sem_criptografia": ("Este endereço não tem conexão segura",
                         "Só abrimos sites com “https”, que protegem o que você digita."),
}


def pagina_bloqueada(url, motivo="fora_da_lista"):
    # Usa o mesmo leitor rígido do filtro: endereços disfarçados (ex.: com
    # barra invertida) aparecem como texto, nunca como o site "de fachada".
    endereco = analisar(url)
    if endereco is None or not endereco.host:
        motivo = "invalido" if endereco is None else motivo
        host = escape(url if len(url) <= 80 else url[:77] + "…")
    else:
        host = escape(endereco.host)
    titulo, explicacao = MOTIVOS[motivo]
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Site bloqueado</title>{CSS}</head><body><main class="centro">
  <div class="bloqueio">
    <section class="bloco principal" style="--ordem:0">
      <div class="placa" aria-hidden="true">🚧</div>
      <h1>{titulo}</h1>
      <span class="endereco-bloqueado">{host}</span>
    </section>
    <section class="bloco lateral" style="--ordem:1">
      <p>{explicacao}</p>
      <p>Precisa dele para uma tarefa? Peça ao responsável para incluí-lo na lista.</p>
      <a class="botao" href="estudos://inicio">Voltar para a página inicial</a>
    </section>
  </div>
</main></body></html>"""


def pagina_aba_interrompida(url, pode_voltar):
    """Mostrada quando o motor de páginas encerra a aba (falha gráfica, memória...).

    pode_voltar: se o endereço é permitido, o botão "Tentar de novo" leva a ele;
    senão, só a página inicial é oferecida.
    """
    endereco = analisar(url) if url else None
    host = escape(endereco.host) if endereco and endereco.host else "esta página"
    tentar = (f'<a class="botao" href="{escape(url)}">Tentar de novo</a>' if pode_voltar else "")
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Aba interrompida</title>{CSS}</head><body><main class="centro">
  <div class="bloqueio">
    <section class="bloco principal cor-amarelo" style="--ordem:0">
      <div class="placa" aria-hidden="true">🔌</div>
      <h1>Esta aba parou de funcionar</h1>
      <span class="endereco-bloqueado">{host}</span>
    </section>
    <section class="bloco lateral" style="--ordem:1">
      <p>O motor de páginas encerrou esta aba. Isso pode acontecer com vídeos ou
         páginas muito pesadas. Seus dados e o tempo de estudo não foram afetados.</p>
      {tentar}
      <a class="botao" href="estudos://inicio">Página inicial</a>
    </section>
  </div>
</main></body></html>"""
