"""Gravação segura de arquivos e cópias de segurança.

O problema que isto resolve:
  Gravar com write_text() APAGA o arquivo e escreve por cima. Se o programa
  for interrompido no meio (travou, faltou energia, disco cheio), sobra um
  arquivo pela metade — e uma lista de sites ou senha corrompida.

Gravação atômica ("tudo ou nada"):
  1. escreve num arquivo temporário NA MESMA PASTA (".sites.txt.xxxx.tmp");
  2. força os dados para o disco (fsync);
  3. troca o temporário pelo definitivo com os.replace — essa troca é
     atômica: quem lê o arquivo vê a versão antiga OU a nova, nunca metade;
  4. força a pasta para o disco, para a troca sobreviver a um desligamento.
  Se algo falhar antes da troca, o temporário é apagado e o arquivo antigo
  continua intacto.

Cópias de segurança (pasta "copias/" ao lado do arquivo):
  Antes de substituir um arquivo, a versão atual é copiada; depois da
  gravação, a versão nova também — assim a cópia mais recente é sempre o
  último estado bom (recuperar a senha traz a senha ATUAL, não a antiga).
  Só versões VÁLIDAS viram cópia (cópia de arquivo corrompido não ajuda
  ninguém), sem repetir a última. Ficam no máximo 3 cópias por arquivo.
"""

import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MODO_PRIVADO = 0o600          # só o próprio usuário lê e escreve
MODO_PASTA_PRIVADA = 0o700
PASTA_DE_COPIAS = "copias"
TEMPORARIO_ABANDONADO = 10 * 60   # segundos: .tmp mais velho que isso é lixo


def _avisar(mensagem):
    """Aviso no terminal. NUNCA inclui o conteúdo dos arquivos (pode ser senha)."""
    print(f"Navegador de Estudos: {mensagem}", file=sys.stderr)


@dataclass(frozen=True)
class PoliticaDeCopias:
    """Como guardar cópias de um tipo de arquivo.

    validar: função(bytes) -> bool. Só conteúdo válido vira cópia ou é
             restaurado.
    manter: quantas cópias guardar deste arquivo.
    intervalo_minimo: segundos entre duas cópias (o tempo de estudo é salvo
             a cada 15 s; não faz sentido copiar com essa frequência).
    """
    validar: object
    manter: int = 3
    intervalo_minimo: int = 0


# ---------------------------------------------------------------------------
#  Gravação atômica
# ---------------------------------------------------------------------------

def _sincronizar_pasta(pasta):
    """Grava no disco a "troca de nomes" feita pelo os.replace."""
    try:
        descritor = os.open(pasta, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descritor)
    except OSError:
        pass     # alguns sistemas de arquivos não suportam; a troca já foi feita
    finally:
        os.close(descritor)


def limpar_temporarios(pasta, nome):
    """Apaga temporários abandonados (ex.: o programa foi morto no meio)."""
    agora = time.time()
    for sobra in Path(pasta).glob(f".{nome}.*.tmp"):
        try:
            if agora - sobra.stat().st_mtime > TEMPORARIO_ABANDONADO:
                sobra.unlink()
        except OSError:
            pass


def gravar_atomico(caminho, conteudo, modo=MODO_PRIVADO):
    """Grava `conteudo` (texto ou bytes) em `caminho` no esquema tudo-ou-nada.

    Lança OSError se não conseguir; nesse caso o arquivo antigo fica intacto
    e nenhum temporário é deixado para trás.
    """
    caminho = Path(caminho)
    dados = conteudo.encode("utf-8") if isinstance(conteudo, str) else bytes(conteudo)
    pasta = caminho.parent
    limpar_temporarios(pasta, caminho.name)
    descritor, temporario = tempfile.mkstemp(dir=pasta, prefix=f".{caminho.name}.",
                                             suffix=".tmp")
    try:
        os.fchmod(descritor, modo)
        with os.fdopen(descritor, "wb") as arquivo:
            descritor = None          # agora quem fecha é o "with"
            arquivo.write(dados)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    except BaseException:
        if descritor is not None:
            os.close(descritor)
        try:
            os.unlink(temporario)
        except OSError:
            pass
        raise
    _sincronizar_pasta(pasta)


# ---------------------------------------------------------------------------
#  Cópias de segurança
# ---------------------------------------------------------------------------

def pasta_de_copias(caminho):
    return Path(caminho).parent / PASTA_DE_COPIAS


def listar_copias(caminho):
    """Cópias deste arquivo, da mais nova para a mais antiga."""
    caminho = Path(caminho)
    pasta = pasta_de_copias(caminho)
    if not pasta.is_dir():
        return []
    return sorted(pasta.glob(f"{caminho.name}.*"), reverse=True)


def _validar(politica, dados):
    try:
        return bool(politica.validar(dados))
    except Exception:          # um validador com defeito nunca derruba a gravação
        return False


def copiar_versao_atual(caminho, politica):
    """Guarda a versão atual do arquivo, se for válida. Nunca lança exceção.

    Devolve o caminho da cópia criada, ou None se não copiou.
    """
    caminho = Path(caminho)
    try:
        if not caminho.is_file():
            return None
        atual = caminho.read_bytes()
        if not _validar(politica, atual):
            return None          # não deixa um arquivo ruim "empurrar" uma cópia boa
        copias = listar_copias(caminho)
        if copias:
            if copias[0].read_bytes() == atual:
                return None      # igual à última cópia: nada a fazer
            if time.time() - copias[0].stat().st_mtime < politica.intervalo_minimo:
                return None
        pasta = pasta_de_copias(caminho)
        pasta.mkdir(mode=MODO_PASTA_PRIVADA, exist_ok=True)
        os.chmod(pasta, MODO_PASTA_PRIVADA)
        carimbo = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        destino = pasta / f"{caminho.name}.{carimbo}"
        gravar_atomico(destino, atual)
        for velha in listar_copias(caminho)[politica.manter:]:
            velha.unlink()
        return destino
    except OSError as erro:
        _avisar(f"não foi possível guardar cópia de {caminho.name} ({erro.strerror})")
        return None


def gravar_com_copia(caminho, conteudo, politica, modo=MODO_PRIVADO):
    """Grava a versão nova de forma atômica, com cópias antes e depois.

    Uma falha na cópia NUNCA impede a gravação do arquivo principal.
    """
    copiar_versao_atual(caminho, politica)      # o estado anterior, se ainda não copiado
    gravar_atomico(caminho, conteudo, modo)
    copiar_versao_atual(caminho, politica)      # o estado novo vira a cópia mais recente


def ultima_copia_valida(caminho, politica):
    """Conteúdo (bytes) da cópia válida mais recente, ou None."""
    for copia in listar_copias(caminho):
        try:
            dados = copia.read_bytes()
        except OSError:
            continue
        if _validar(politica, dados):
            return dados
    return None


def ler_com_recuperacao(caminho, politica):
    """Lê o arquivo; se estiver corrompido, recupera a última cópia válida.

    - Arquivo válido: devolve o conteúdo.
    - Arquivo corrompido: guarda-o como "<nome>.corrompido-<data>" (nada é
      apagado), restaura a última cópia válida e devolve o conteúdo dela.
    - Corrompido e sem cópia válida: também é guardado com esse nome (para a
      próxima gravação não destruí-lo) e devolve None.
    - Sem arquivo: devolve None (quem chamou decide o padrão).
    """
    caminho = Path(caminho)
    try:
        dados = caminho.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as erro:
        # Existe mas não dá para ler: preserva com outro nome, senão a próxima
        # gravação o substituiria e os dados se perderiam.
        guardado = caminho.with_name(
            f"{caminho.name}.ilegivel-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        try:
            os.replace(caminho, guardado)
            _avisar(f"não foi possível ler {caminho.name} ({erro.strerror}); "
                    f"guardado como {guardado.name}")
        except OSError:
            _avisar(f"não foi possível ler {caminho.name} ({erro.strerror})")
        return None
    if _validar(politica, dados):
        return dados
    recuperado = ultima_copia_valida(caminho, politica)
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    guardado = caminho.with_name(f"{caminho.name}.corrompido-{carimbo}")
    try:
        os.replace(caminho, guardado)
        os.chmod(guardado, MODO_PRIVADO)
        if recuperado is not None:
            gravar_atomico(caminho, recuperado)
    except OSError as erro:
        _avisar(f"não foi possível tratar {caminho.name} corrompido ({erro.strerror})")
        return recuperado
    if recuperado is None:
        _avisar(f"{caminho.name} estava corrompido e não há cópia válida; "
                f"o arquivo danificado foi guardado como {guardado.name}")
    else:
        _avisar(f"{caminho.name} estava corrompido; restaurada a última cópia válida "
                f"(o arquivo danificado foi guardado como {guardado.name})")
    return recuperado


def apagar_copias_antigas(pasta, dias):
    """Retenção por idade: apaga CÓPIAS (nunca os arquivos principais) mais
    velhas que `dias`. Usado para o tempo de estudo, que tem um arquivo por dia."""
    limite = time.time() - dias * 86400
    pasta = Path(pasta) / PASTA_DE_COPIAS
    if not pasta.is_dir():
        return
    for copia in pasta.iterdir():
        try:
            if copia.is_file() and copia.stat().st_mtime < limite:
                copia.unlink()
        except OSError:
            pass
