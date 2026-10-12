"""A lista de sites permitidos e a decisão "pode abrir ou não?".

Este arquivo não depende da parte gráfica, então dá para testá-lo sozinho
(veja a pasta testes/).

Tipos de destino (função ListaDeSites.classificar):
  interno            páginas do próprio navegador (estudos://, about:blank)
  site               site da lista, pode abrir como página ou iframe
  login              página de entrar (Google, Microsoft...): abre, mas não
                     conta como tempo de estudo
  embutido           só pode aparecer DENTRO de uma página (iframe): vídeos,
                     "não sou robô", imagens geradas pela página (data:, blob:)
  excluido           subdomínio barrado mesmo com o domínio liberado
  sem_criptografia   "http://" de um site liberado (só "https://" abre)
  bloqueado          todo o resto
  invalido           endereço ambíguo ou malformado (veja nucleo/urls.py)

Requisições auxiliares (imagens, scripts, vídeos, fontes, conexões das IAs)
NÃO passam por esta lista: elas carregam de qualquer lugar para que YouTube
e IAs funcionem. O filtro controla as PÁGINAS que podem ser abertas.
"""

import hashlib
import os
import re
import sys
from dataclasses import dataclass, field

from . import caminhos, dominios
from .arquivos import PoliticaDeCopias, gravar_atomico, gravar_com_copia, ler_com_recuperacao
from .urls import analisar


@dataclass
class Atalho:
    """Um site que aparece na página inicial."""
    nome: str
    url: str
    dominio: str


@dataclass
class Categoria:
    nome: str
    atalhos: list = field(default_factory=list)


# "Impressões digitais" (SHA-256) das listas padrão de versões antigas.
# Se a lista do usuário for idêntica a uma delas (ou seja, ninguém a mudou),
# ela é trocada pela lista padrão nova automaticamente.
PADROES_ANTIGOS = {
    "0a9a7c48a137afbbb515dd0ef47fcf705bdf94de4a38c745c88db963b845989d",  # v1.0
    "7249f35beaf3d1f86b6ec7b326afcf9b1f1c394f607b91a192e051e30673ed0d",  # v2.0
    "6dc31f237dbe31c452b09f75f8837c4329c0d77e8966ae5cdaa13ac3a3544924",  # v2.1.1 sem o Sora
    "bf6379f5b74981249902fed8bacfa0e689e8e62c9452108d86b22321cc91de5d",  # v2.1.1
}

# Endereços internos do próprio navegador (página inicial, fonte, estilos).
ESQUEMA_INTERNO = "estudos"

# Conteúdo que os sites de estudo colocam DENTRO das páginas (iframes):
# vídeos e verificações "não sou robô". Podem aparecer embutidos, mas não
# abrem como página inteira (a não ser que o domínio esteja na lista).
#   (domínio, começo do caminho exigido)
EMBUTIDOS_PERMITIDOS = [
    ("youtube.com", "/embed/"),
    ("youtube-nocookie.com", "/embed/"),
    ("player.vimeo.com", "/"),
    ("google.com", "/recaptcha/"),
    ("recaptcha.net", "/recaptcha/"),
    ("challenges.cloudflare.com", "/"),   # verificação usada pelo ChatGPT e outros
]

# Esquemas que só podem aparecer dentro de páginas já permitidas
# (imagens geradas pela própria página, PDFs etc.), nunca como página.
ESQUEMAS_SO_EMBUTIDOS = ("data", "blob", "about")

# Páginas de login conhecidas. Só abrem se estiverem na lista; quando abrem,
# não contam como tempo de estudo.
DOMINIOS_DE_LOGIN = ("accounts.google.com", "login.live.com", "login.microsoftonline.com",
                     "auth.openai.com", "appleid.apple.com")

PERMITIDOS_COMO_PAGINA = ("interno", "site", "login")


def _lista_valida(dados):
    """Uma lista "boa" para virar cópia: texto UTF-8 com ao menos um site."""
    return bool(ListaDeSites.de_texto(dados.decode("utf-8")).dominios)


POLITICA_DE_COPIAS = PoliticaDeCopias(validar=_lista_valida)
PERMITIDOS_EM_IFRAME = PERMITIDOS_COMO_PAGINA + ("embutido",)


def limpar_dominio(texto):
    """'https://www.Exemplo.com/a' ou 'www.exemplo.com' -> 'exemplo.com'."""
    texto = texto.strip().lower()
    if "://" in texto:
        endereco = analisar(texto)
        texto = endereco.host if endereco else ""
    else:
        texto = texto.split("/")[0]
        if texto.endswith("."):
            texto = texto[:-1]
    if texto.startswith("www."):
        texto = texto[4:]
    return texto


def dominio_bate(host, dominio):
    """True se o host é o próprio domínio ou um subdomínio dele.

    Ex.: 'pt.wikipedia.org' bate com 'wikipedia.org', mas
    'wikipedia.org.golpe.com' e 'falsawikipedia.org' NÃO batem.
    """
    return host == dominio or host.endswith("." + dominio)


def _montar(esquema, endereco):
    porta = f":{endereco.porta}" if endereco.porta is not None else ""
    return f"{esquema}://{endereco.host}{porta}{endereco.resto}"


def para_https(url):
    """'http://site.com/x' -> 'https://site.com/x' (outros endereços não mudam)."""
    endereco = analisar(url)
    if endereco is None or endereco.esquema != "http":
        return url
    return _montar("https", endereco)


def _regex_do_dominio(dominio):
    """Trecho de expressão regular que casa o domínio e seus subdomínios.

    Ex.: 'wikipedia.org' -> '([^/:@?#]+\\.)?wikipedia\\.org(:[0-9]+)?/'
    O "/" no final garante que 'wikipedia.org.golpe.com' NÃO casa, e a
    classe [^/:@?#] impede truques com "usuario@" antes do domínio.
    """
    return r"([^/:@?#]+\.)?" + dominio.replace(".", r"\.") + r"(:[0-9]+)?/"


class ListaDeSites:
    """Lê o arquivo sites.txt e responde se um endereço é permitido."""

    def __init__(self, somente_https=True, embutidos=None):
        self.categorias = []
        self.dominios = set()
        self.excluidos = set()
        self.apelidos = {}      # domínio extra -> nome nas estatísticas
        self.nao_conta = set()  # "~ dominio": liberado, mas não conta como estudo
        self.erros = []
        # Com somente_https, endereços "http://" (sem criptografia) não abrem.
        # Os testes automáticos desligam isso para usar um servidor local.
        self.somente_https = somente_https
        self.embutidos = list(EMBUTIDOS_PERMITIDOS if embutidos is None else embutidos)

    # ---------- leitura ----------

    @classmethod
    def carregar(cls):
        """Lê ~/.config/navegador-estudos/sites.txt (cria a partir do padrão)."""
        padrao = (caminhos.PASTA_RECURSOS / "sites_padrao.txt").read_bytes()
        arquivo = caminhos.ARQUIVO_SITES
        if caminhos.MODO_PROTEGIDO:
            # Lista do administrador (/etc): só leitura. Nunca tentamos gravar
            # nem "consertar" — se estiver ilegível, usa a padrão na memória.
            try:
                dados = arquivo.read_bytes()
                if _lista_valida(dados):
                    return cls.de_texto(dados.decode("utf-8"))
            except (OSError, UnicodeDecodeError):
                pass
            print("Navegador de Estudos: lista do administrador ilegível; usando a lista padrão",
                  file=sys.stderr)
            return cls.de_texto(padrao.decode("utf-8"))
        # Lista corrompida: é guardada com outro nome e a última cópia válida volta.
        dados = ler_com_recuperacao(arquivo, POLITICA_DE_COPIAS)
        if dados is None:
            # Sem lista (primeira vez) ou corrompida/ilegível sem cópia (o arquivo
            # ruim já foi guardado com outro nome): usa a padrão. Se o arquivo
            # ainda existir (não deu para movê-lo), não é sobrescrito.
            if not arquivo.exists():
                gravar_atomico(arquivo, padrao)
            dados = padrao
        elif hashlib.sha256(dados).hexdigest() in PADROES_ANTIGOS:
            # Lista nunca editada: guarda a antiga e atualiza para a nova.
            gravar_atomico(arquivo.with_suffix(".txt.anterior"), dados)
            gravar_com_copia(arquivo, padrao, POLITICA_DE_COPIAS)
            dados = padrao
        try:
            os.chmod(arquivo, 0o600)   # só o próprio usuário lê e altera
        except OSError:
            pass
        return cls.de_texto(dados.decode("utf-8"))

    @staticmethod
    def salvar_texto(conteudo):
        """Grava a lista editada pelo responsável (atômico, com cópia da anterior)."""
        gravar_com_copia(caminhos.ARQUIVO_SITES, conteudo, POLITICA_DE_COPIAS)

    @classmethod
    def de_texto(cls, texto, somente_https=True, embutidos=None):
        lista = cls(somente_https, embutidos)
        atual = None
        for numero, linha in enumerate(texto.splitlines(), start=1):
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            if linha.startswith("[") and linha.endswith("]") and "|" not in linha:
                atual = Categoria(linha[1:-1].strip())
                lista.categorias.append(atual)
            elif linha.startswith("~"):
                # "~ spotify.com": não conta como tempo de estudo (música, lazer).
                # Não libera nada sozinho: o site precisa estar liberado por "+" ou atalho.
                dominio = limpar_dominio(linha[1:])
                erro = dominios.validar(dominio)
                if erro:
                    lista.erros.append(f"Linha {numero}: {erro} “{linha}”")
                else:
                    lista.nao_conta.add(dominio)
            elif linha.startswith(("+", "-")):
                # "+ scielo.org = SciELO": o "= Nome" (opcional) dá nome ao domínio
                # nas estatísticas, juntando-o com o atalho de mesmo nome.
                texto_dominio, _, apelido = linha[1:].partition("=")
                dominio = limpar_dominio(texto_dominio)
                apelido = apelido.strip()
                erro = dominios.validar(dominio)
                if erro:
                    lista.erros.append(f"Linha {numero}: {erro} “{linha}”")
                elif linha.startswith("-") and apelido:
                    lista.erros.append(f"Linha {numero}: “= Nome” só vale em linhas com + “{linha}”")
                elif linha.startswith("+"):
                    lista.dominios.add(dominio)
                    if apelido:
                        lista.apelidos[dominio] = apelido
                else:
                    lista.excluidos.add(dominio)
            elif "|" in linha:
                nome, url = (parte.strip() for parte in linha.split("|", 1))
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                endereco = analisar(url)
                if not nome or "[" in nome or "]" in nome or endereco is None:
                    lista.erros.append(f"Linha {numero}: atalho inválido “{linha}”")
                    continue
                dominio = limpar_dominio(endereco.host)
                erro = dominios.validar(dominio)
                if erro:
                    lista.erros.append(f"Linha {numero}: {erro} “{linha}”")
                    continue
                if atual is None:
                    atual = Categoria("Sites")
                    lista.categorias.append(atual)
                atual.atalhos.append(Atalho(nome, para_https(url) if somente_https else url,
                                            dominio))
                lista.dominios.add(dominio)
            else:
                lista.erros.append(f"Linha {numero}: não entendi “{linha}”")
        return lista

    # ---------- decisões ----------

    def classificar(self, url, quadro="principal"):
        """Diz que tipo de destino é este endereço (veja o topo do arquivo).

        quadro: "principal" (a página da aba) ou "iframe" (dentro de uma página).
        """
        endereco = analisar(url)
        if endereco is None:
            return "invalido"
        if endereco.esquema == ESQUEMA_INTERNO or url.strip() == "about:blank":
            return "interno"
        if endereco.esquema in ESQUEMAS_SO_EMBUTIDOS:
            return "embutido" if quadro == "iframe" else "bloqueado"
        if endereco.esquema not in ("http", "https"):
            return "bloqueado"     # file:, ftp:, javascript:, view-source:...
        host = endereco.host
        if any(dominio_bate(host, d) for d in self.excluidos):
            return "excluido"
        liberado = any(dominio_bate(host, d) for d in self.dominios)
        if liberado and self.somente_https and endereco.esquema == "http":
            return "sem_criptografia"
        if liberado:
            return "login" if host in DOMINIOS_DE_LOGIN else "site"
        seguro = endereco.esquema == "https" or not self.somente_https
        if quadro == "iframe" and seguro and any(
                dominio_bate(host, d) and endereco.resto.startswith(caminho)
                for d, caminho in self.embutidos):
            return "embutido"
        return "bloqueado"

    def permite(self, url):
        """Pode abrir este endereço como página principal?"""
        return self.classificar(url) in PERMITIDOS_COMO_PAGINA

    def permite_embutido(self, url):
        """Pode aparecer DENTRO de uma página permitida (iframe)?"""
        return self.classificar(url, "iframe") in PERMITIDOS_EM_IFRAME

    def https_disponivel(self, url):
        """Se for 'http://' de um site liberado, devolve a versão 'https://'."""
        endereco = analisar(url)
        if self.somente_https and endereco is not None and endereco.esquema == "http":
            seguro = _montar("https", endereco)
            if self.permite(seguro):
                return seguro
        return None

    def nome_do_site(self, url):
        """Nome amigável para o relatório de tempo ('Wikipédia', 'MDN'...).

        Páginas de login e endereços fora da lista devolvem None (não contam).
        """
        if self.classificar(url) != "site":
            return None
        host = analisar(url).host
        if any(dominio_bate(host, d) for d in self.nao_conta):
            return None      # liberado, mas não é estudo (ex.: música)
        # Atalhos e apelidos ("+ dominio = Nome"): vence o domínio mais específico.
        candidatos = [(a.dominio, a.nome) for c in self.categorias for a in c.atalhos]
        candidatos += list(self.apelidos.items())
        batem = [(dominio, nome) for dominio, nome in candidatos if dominio_bate(host, dominio)]
        if batem:
            return max(batem, key=lambda par: len(par[0]))[1]
        for dominio in sorted(self.dominios, key=len, reverse=True):
            if dominio_bate(host, dominio):
                # 'en.wikipedia.org' cai em '+ wikipedia.org'; se algum atalho
                # é desse mesmo domínio (pt.wikipedia.org), usamos o nome dele.
                for categoria in self.categorias:
                    for atalho in categoria.atalhos:
                        if dominio_bate(atalho.dominio, dominio):
                            return atalho.nome
                return dominio
        return None

    def nome_para_estatistica(self, chave):
        """Nome com que uma chave já gravada nas estatísticas deve aparecer.

        Versões antigas gravavam domínios ("youtube.com", "scielo.org") quando
        não havia atalho; aqui eles são juntados ao nome atual do site. Os
        arquivos não são alterados — é só na hora de mostrar.
        """
        if " " in chave or "." not in chave or dominios.validar(chave):
            return chave            # já é um nome amigável (registros antigos ficam visíveis)
        return self.nome_do_site(f"https://{chave}/") or chave

    # ---------- regras para o WebKit ----------

    def regras_de_conteudo(self):
        """Regras no formato dos "bloqueadores de conteúdo" do WebKit.

        Elas barram páginas e iframes ANTES de o pedido sair do computador,
        inclusive redirecionamentos — então um site bloqueado nem fica sabendo
        da tentativa (e não consegue gravar cookies).

        Ordem importa: o WebKit aplica as regras de cima para baixo, e
        "ignore-previous-rules" anula os bloqueios anteriores.
          1. bloqueia toda página/iframe/pop-up
          2. libera páginas internas e os domínios da lista
          3. libera, só em iframes, os embutidos e data:/blob:
          4. volta a bloquear subdomínios excluídos e endereços com "usuario@"
        """
        documentos = ["document", "popup"]
        esquemas = "https" if self.somente_https else "https?"

        def regra(filtro, acao, tipos=documentos, contexto=None):
            gatilho = {"url-filter": filtro, "resource-type": list(tipos)}
            if contexto:
                gatilho["load-context"] = [contexto]
            return {"trigger": gatilho, "action": {"type": acao}}

        regras = [regra(".*", "block"),
                  regra(f"^{ESQUEMA_INTERNO}:", "ignore-previous-rules"),
                  regra("^about:", "ignore-previous-rules")]
        for dominio in sorted(self.dominios):
            regras.append(regra(f"^{esquemas}://{_regex_do_dominio(dominio)}",
                                "ignore-previous-rules"))
        for dominio, caminho in self.embutidos:
            caminho_re = re.escape(caminho).replace(r"\/", "/")
            regras.append(regra(f"^{esquemas}://" + _regex_do_dominio(dominio)[:-1] + caminho_re,
                                "ignore-previous-rules", ["document"], "child-frame"))
        for esquema in ("data", "blob"):
            regras.append(regra(f"^{esquema}:", "ignore-previous-rules",
                                ["document"], "child-frame"))
        for dominio in sorted(self.excluidos):
            regras.append(regra(f"^https?://{_regex_do_dominio(dominio)}", "block"))
        regras.append(regra("^[a-z][a-z0-9+.-]*://[^/?#]*@", "block"))
        return regras
