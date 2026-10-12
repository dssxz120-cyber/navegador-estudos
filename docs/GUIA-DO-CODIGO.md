# Guia do código: Navegador de Estudos v2.3

Este guia explica **como o navegador funciona por dentro**, arquivo por
arquivo e função por função, em português simples. Ele foi pensado para quem
está começando em programação: cada conceito é explicado na primeira vez
que aparece.

O código também tem comentários próprios (as linhas que começam com `#` e os
textos entre `"""` no início de funções). Leia este guia com o arquivo aberto
ao lado.

---

## Sumário

1. [Conceitos básicos usados no projeto](#1-conceitos-básicos-usados-no-projeto)
2. [O caminho de um clique: visão geral](#2-o-caminho-de-um-clique-visão-geral)
3. [Ponto de partida: `navegador_estudos.py`](#3-ponto-de-partida-navegador_estudospy)
4. [Núcleo: regras e dados (`estudos/nucleo/`)](#4-núcleo-regras-e-dados-estudosnucleo)
5. [Interface: o que aparece na tela (`estudos/interface/`)](#5-interface-o-que-aparece-na-tela-estudosinterface)
6. [Recursos: visual e lista padrão (`recursos/`)](#6-recursos-visual-e-lista-padrão-recursos)
7. [Testes (`testes/`)](#7-testes-testes)
8. [Histórico: o que foi feito em cada versão](#8-histórico-o-que-foi-feito-em-cada-versão)

---

## 1. Conceitos básicos usados no projeto

| Conceito | O que é |
|---|---|
| **Python** | A linguagem em que o navegador foi escrito. |
| **Módulo** | Um arquivo `.py`. `from estudos.nucleo import senha` traz o arquivo `estudos/nucleo/senha.py` para ser usado. |
| **Função** (`def`) | Um bloco de código com nome, que faz uma tarefa e pode devolver um resultado com `return`. |
| **Classe** (`class`) | Um "molde" que junta dados e funções. Ex.: `Pomodoro` guarda a fase e o tempo, e tem funções como `iniciar_ou_pausar()`. Uma função dentro de classe se chama **método**; `self` é o próprio objeto. |
| **GTK** | A biblioteca que desenha janelas, botões e campos no Ubuntu. |
| **WebKit** | O "motor" que baixa e desenha as páginas da internet (o mesmo do Safari e do GNOME Web). |
| **Sinal** (`connect`) | Um aviso que o GTK/WebKit dá quando algo acontece ("clicaram", "a página quer navegar"). `botao.connect("clicked", funcao)` quer dizer: quando clicarem, chame `funcao`. |
| **Laço de eventos** | O GTK fica num ciclo eterno esperando eventos (clique, tecla, relógio) e chamando as funções ligadas a eles. Por isso o programa não pode "travar" com esperas longas. |
| **Domínio** | O nome do site: em `https://pt.wikipedia.org/wiki/A`, o domínio é `pt.wikipedia.org`. |
| **JSON** | Formato de texto para guardar dados, ex.: `{"meta_minutos": 60}`. |
| **Hash** | Uma "impressão digital" de um texto. Dá para conferir uma senha comparando hashes, sem guardar a senha. |

---

## 2. O caminho de um clique: visão geral

Imagine que o aluno clica num link para o Instagram dentro da Wikipédia:

1. **WebKit pergunta** ao nosso programa: "posso navegar para instagram.com?"
   → função `Filtro._navegacao` (arquivo `interface/filtro.py`).
2. O filtro consulta a **lista de sites** → `ListaDeSites.classificar`
   (arquivo `nucleo/regras.py`), que responde `"bloqueado"`.
3. Como foi um clique do usuário, o filtro **recusa** (`decisao.ignore()`) e
   mostra a **tela de bloqueio** (`paginas.pagina_bloqueada`).
4. Se fosse um redirecionamento automático, quem barraria seria a **camada 1**:
   as regras de bloqueio instaladas no WebKit (`interface/motor.py`), que
   impedem até o envio do pedido.

As três camadas de proteção:

| Camada | Onde | Quando age |
|---|---|---|
| 1. Regras de bloqueio do WebKit | `motor.py` + `regras.regras_de_conteudo()` | Antes de qualquer pedido sair do computador (inclusive redirecionamentos) |
| 2. Decisão de navegação | `filtro._navegacao` | Cliques, formulários, voltar/avançar |
| 3. Decisão de resposta | `filtro._resposta` | Checagem final, caso algo passe pelas anteriores |

E, a cada segundo, o relógio do aplicativo (`aplicativo._contar_tempo`) soma
tempo de estudo para o site aberto, se o aluno estiver presente.

---

## 3. Ponto de partida: `navegador_estudos.py`

Este é o arquivo que o atalho do menu executa. Explicação **linha por linha**:

```python
1  #!/usr/bin/env python3
```
"Shebang": diz ao Linux que este arquivo deve ser executado pelo Python 3.

```python
2  """Ponto de partida do Navegador de Estudos.
3
4  Para abrir:  python3 navegador_estudos.py
5  """
```
Texto de documentação do arquivo (não é executado; serve para quem lê).

```python
7  import sys
```
Traz o módulo `sys`, que dá acesso a coisas do sistema: os argumentos da
linha de comando (`sys.argv`), a saída de erros (`sys.stderr`) e a saída do
programa (`sys.exit`).

```python
9  import gi
```
Traz o **PyGObject**, a ponte entre o Python e as bibliotecas do GNOME (GTK,
WebKit, GLib).

```python
11 gi.require_version("Gtk", "3.0")
12 gi.require_version("Gdk", "3.0")
13 gi.require_version("WebKit2", "4.1")
```
Fixa as versões: GTK 3, Gdk 3 (desenho de baixo nível) e WebKit2 4.1. Sem
isso, o Python poderia carregar o GTK 4, que é incompatível (isso aconteceu
na primeira versão e causou um erro).

```python
15 from estudos.interface.aplicativo import Aplicativo  # noqa: E402
16 from estudos.nucleo import caminhos  # noqa: E402
17 from estudos.nucleo.regras import ListaDeSites  # noqa: E402
18 from estudos.nucleo.tempo import ContadorDeTempo  # noqa: E402
```
Traz as quatro peças principais do nosso código. O comentário `# noqa: E402`
avisa às ferramentas de verificação que é proposital importar depois do
`require_version`.

```python
21 def main():
```
Define a função principal.

```python
22     caminhos.criar_pastas()
```
Cria as pastas de dados na primeira execução (`~/.config/navegador-estudos`
etc.). Se já existirem, não faz nada.

```python
23     lista = ListaDeSites.carregar()
```
Lê a lista de sites permitidos do arquivo `sites.txt` (criando-a a partir da
lista padrão, se não existir; recuperando de uma cópia, se estiver
corrompida).

```python
24     for erro in lista.erros:
25         print("Aviso na lista de sites:", erro, file=sys.stderr)
```
Se alguma linha da lista estiver com problema, escreve um aviso no terminal.
As linhas boas continuam valendo.

```python
26     app = Aplicativo(lista, ContadorDeTempo())
```
Cria o aplicativo, entregando a lista e um contador de tempo de estudo (que
já carrega o tempo de hoje).

```python
27     return app.run(sys.argv)
```
Liga o aplicativo: a partir daqui o GTK assume o controle (laço de eventos) e
só volta quando o programa for fechado.

```python
30 if __name__ == "__main__":
31     sys.exit(main())
```
"Se este arquivo foi executado diretamente (e não importado por outro), rode
`main()` e saia com o código que ela devolver."

---

## 4. Núcleo: regras e dados (`estudos/nucleo/`)

O núcleo **não desenha nada na tela**. Por isso dá para testá-lo sem abrir
janelas.

### 4.1 `caminhos.py`: onde cada arquivo fica

- `PASTA_RAIZ`, `PASTA_RECURSOS`: onde está o programa e seus recursos.
- `PASTA_CONFIG` = `~/.config/navegador-estudos`: lista, senha, preferências,
  estado do Pomodoro e tentativas de senha.
- `PASTA_DADOS` = `~/.local/share/navegador-estudos`: tempo de estudo e
  cookies dos sites.
- `criar_pastas()`: cria as pastas e deixa a de configuração privada (`700`).
- `recurso_seguro(relativo)`: devolve um arquivo de `recursos/` **somente se**
  ele estiver de fato dentro dessa pasta. Impede truques como
  `estudos://recursos/../../senha.json`, que tentariam ler outros arquivos.

### 4.2 `urls.py`: leitor rígido de endereços

**Problema que resolve:** o Python e o WebKit às vezes entendem um endereço
de forma diferente. Ex.: `https://instagram.com\@pt.wikipedia.org/` parece
Wikipédia para o Python, mas o WebKit abre o Instagram.

- `Endereco`: guarda as partes de um endereço (esquema, host, porta, resto).
- `analisar(url)`: só aceita endereços em forma simples. Recusa (devolve
  `None`, ou seja, bloqueia):
  - barra invertida `\` ou `usuario@` antes do site;
  - `%`, acentos, espaços ou colchetes no nome do site;
  - barras erradas (`https:/site`, `https:///site`), portas inválidas.

  Regra de ouro: **na dúvida, bloqueia**.

### 4.3 `dominios.py`: validação dos domínios da lista

- `_regras_de_sufixo()`: lê a **lista oficial de sufixos públicos** que vem no
  Ubuntu (`/usr/share/publicsuffix`). Sufixo público é a parte sob a qual
  qualquer pessoa registra sites: `com`, `com.br`, `github.io`…
- `eh_sufixo_publico(dominio)`: diz se um domínio é um desses sufixos.
- `validar(dominio)`: recusa curingas (`*`), acentos, IPs, rótulos inválidos
  e sufixos públicos. Por isso `+ com.br` dá erro no editor: liberaria
  milhares de sites.

### 4.4 `regras.py`: a lista de sites e a decisão "pode abrir?"

**Formato do `sites.txt`** (lido por `ListaDeSites.de_texto`):

| Linha | Significado |
|---|---|
| `[Categoria]` | começa um bloco na página inicial |
| `Nome \| https://endereço` | cria um atalho e libera o site |
| `+ dominio.com` | libera o domínio (e subdomínios) sem atalho |
| `+ dominio.com = Nome` | idem, e conta o tempo com esse nome |
| `- sub.dominio.com` | barra um subdomínio de um domínio liberado |
| `~ dominio.com` | liberado, mas **não conta como estudo** (música) |
| `# texto` | comentário |

Funções e métodos principais:

- `limpar_dominio(texto)`: `"https://www.Exemplo.com/a"` → `"exemplo.com"`.
- `dominio_bate(host, dominio)`: `pt.wikipedia.org` bate com `wikipedia.org`,
  mas `wikipedia.org.golpe.com` **não**. O truque está na linha
  `host.endswith("." + dominio)`: exige um ponto antes do domínio.
- `ListaDeSites.carregar()`: lê o arquivo com recuperação de cópias; se a
  lista for idêntica a uma lista padrão antiga (nunca editada), troca pela
  nova.
- `ListaDeSites.salvar_texto(conteudo)`: grava a lista editada (de forma
  segura, com cópia).
- `classificar(url, quadro)`: o coração do filtro. Devolve o **tipo de
  destino**:

  | Tipo | Exemplo |
  |---|---|
  | `interno` | `estudos://inicio` |
  | `site` | `https://pt.wikipedia.org/` |
  | `login` | `https://accounts.google.com/` (abre, não conta tempo) |
  | `embutido` | vídeo do YouTube **dentro** de uma página (só em iframe) |
  | `excluido` | `https://sora.chatgpt.com/` |
  | `sem_criptografia` | `http://pt.wikipedia.org/` (só https abre) |
  | `bloqueado` | `https://www.instagram.com/` |
  | `invalido` | endereço disfarçado |

- `permite(url)` / `permite_embutido(url)`: "pode abrir como página?" e "pode
  aparecer dentro de uma página?".
- `https_disponivel(url)`: troca `http://` por `https://` quando o site é
  liberado.
- `nome_do_site(url)`: nome para as estatísticas ("Wikipédia"). Devolve
  `None` para login, música (`~`) e sites fora da lista, e esses não contam.
- `nome_para_estatistica(chave)`: junta registros antigos ("youtube.com") ao
  nome atual ("YouTube") **na hora de mostrar**.
- `regras_de_conteudo()`: gera as regras da **camada 1** no formato do WebKit.
  A ordem importa: 1) bloqueia tudo; 2) libera páginas internas e a lista;
  3) libera embutidos só em iframes; 4) volta a bloquear excluídos e
  endereços com `usuario@`.

### 4.5 `arquivos.py`: gravação segura e cópias de segurança

**Problema que resolve:** gravar por cima de um arquivo, se for interrompido
no meio, deixa o arquivo pela metade (corrompido).

- `gravar_atomico(caminho, conteudo)`: grava no esquema "tudo ou nada":
  1. escreve num arquivo temporário oculto na mesma pasta;
  2. `os.fsync`: força os dados para o disco;
  3. `os.replace`: troca o temporário pelo definitivo de uma só vez;
  4. sincroniza a pasta.

  Se algo falhar, apaga o temporário e o original fica intacto. Permissão
  `600` (só você lê).
- `limpar_temporarios(...)`: apaga temporários abandonados há mais de 10 min
  (ex.: o programa foi morto no meio de uma gravação).
- `PoliticaDeCopias`: as regras de cópia de cada arquivo: como validar,
  quantas guardar (3) e o intervalo mínimo (1 h para o tempo de estudo).
- `copiar_versao_atual(...)`: copia a versão atual para `copias/` **só se
  for válida** e diferente da última. Nunca deixa um erro de cópia impedir a
  gravação principal.
- `gravar_com_copia(...)`: cópia antes, gravação segura, cópia depois. Assim
  a cópia mais recente é sempre o estado atual.
- `ler_com_recuperacao(...)`: lê o arquivo; se estiver corrompido, guarda-o
  como `.corrompido-DATA` (nada é apagado) e restaura a última cópia válida.
- `apagar_copias_antigas(pasta, dias)`: limita o crescimento das cópias do
  tempo de estudo (apaga cópias com mais de 30 dias, nunca os dados).

### 4.6 `senha.py`: senha do responsável

- A senha **nunca** é guardada. Guarda-se só `sal` + `hash` (PBKDF2, 300 mil
  rodadas). `_calcular` faz essa conta.
- `problema_na_nova_senha(nova, repetida)`: exige 8+ caracteres, sem
  espaços nas pontas, não repetitiva, e as duas iguais.
- `_ler()`: lê o `senha.json`; se estiver danificado **e houver cópia**,
  recupera a senha atual. **Sem cópia, deixa como está**: assim, estragar o
  arquivo de propósito não permite criar uma senha nova pela tela.
- `estado()`: `sem_senha`, `ok` ou `danificada`.
- `definir(senha)`: cria sal aleatório, calcula o hash e grava com cópia.
- `confere(senha)`: recalcula o hash e compara com `hmac.compare_digest`
  (comparação que não dá pistas pelo tempo de resposta).

### 4.7 `tentativas.py`: limite de tentativas de senha

- 3 erros livres; depois, espera de 30 s, 1 min, 2 min, 4 min… até 15 min.
- `registrar_falha()`, `registrar_acerto()` (zera), `espera_restante()`.
- O estado fica em `tentativas.json`, então fechar o navegador não zera a
  espera. Valores absurdos (arquivo editado, relógio mexido) são limitados.

### 4.8 `tempo.py`: tempo de estudo

- `deve_contar(janela_ativa, segundos_parado, tocando_audio, limite)`:
  - janela em segundo plano → não conta;
  - som tocando (vídeo-aula) → conta;
  - mais que o limite sem teclado/mouse → não conta;
  - sem como saber → conta.
- `formatar(segundos)`: `3725` → `"1 h 02 min"`.
- `texto_do_relogio(agora)`: hora e data do relógio da barra, ex.:
  `("09:05", "Segunda-feira, 12 de outubro de 2026")`.
- `ContadorDeTempo`: guarda `{site: segundos}` do dia em
  `tempo/AAAA-MM-DD.json`.
  - `somar(site)`: soma 1 segundo (e troca de arquivo na virada do dia);
  - `salvar()`: grava de forma segura. **Nunca lança erro** e devolve
    `True`/`False`. Atenção: esse `True` causou o defeito da janela que não
    fechava (veja `janela._ao_fechar`);
  - `dias_seguidos()`: sequência de dias com 10+ min (o 🔥 da página inicial);
  - `ranking(agrupar)`: sites do mais usado para o menos usado, juntando
    nomes iguais.

### 4.9 `pomodoro.py`: timer Pomodoro

- Fases: estudo 25 min, pausa 5 min, pausa longa 15 min (a cada 4 ciclos).
- O tempo é medido pelo **horário de término** (`_fim`), não por tiques.
  Assim fica certo mesmo se o computador suspender.
- `iniciar_ou_pausar()`, `zerar()`, `texto()` (`"24:59"`).
- `_tique()`: chamado a cada segundo; quando o tempo acaba, passa para a
  próxima fase e avisa (`ao_trocar_fase`).
- `_salvar()` / `_restaurar()`: guarda o estado em `pomodoro.json`. Ao
  reabrir, continua rodando ou, se a fase acabou com o navegador fechado,
  passa para a próxima, pausado.

### 4.10 `protegido.py`: modo protegido (conta do aluno)

- Se existir `/etc/navegador-estudos/sites.txt` (instalado pelo
  administrador), `caminhos.MODO_PROTEGIDO` fica verdadeiro: a lista e as
  preferências vêm de lá, **só para leitura**, e não existe senha do navegador.
- `salvar_via_pkexec(texto, prefs)`: lado do usuário. Chama
  `pkexec scripts/salvar-configuracao`, que pede a **senha de administrador**
  do Ubuntu (regra do polkit em `scripts/sistema/`).
- `aplicar_configuracao(dados, pasta)`: lado do root. Valida a lista (sem
  erros, ao menos um site, até 512 KB) e as preferências, e grava com
  permissão `644` (o aluno precisa ler), com cópias de segurança.
- `scripts/salvar-configuracao` roda o Python em **modo isolado** (`-I`):
  variáveis como `PYTHONPATH` são ignoradas, para ninguém injetar código que
  rodaria como root.

### 4.11 `preferencias.py`

- `PADRAO`: meta diária de 60 min e pausa da contagem após 5 min parado.
- `carregar()` / `salvar()`: lê e grava `preferencias.json` (com cópias).
- `normalizar(prefs)`: só chaves conhecidas, como inteiros dentro dos limites.

---

## 5. Interface: o que aparece na tela (`estudos/interface/`)

### 5.1 `motor.py`: o WebKit configurado

`Motor.__init__` monta tudo o que o WebKit precisa:

- Pastas próprias para cookies e cache, **prevenção de rastreamento** (ITP) e
  **cookies de terceiros recusados**.
- Downloads cancelados (`download-started` → `cancel()`).
- Endereços `estudos://` tratados como seguros (para a tela de bloqueio usar
  a fonte e o CSS).
- `Settings`: sem ferramentas de desenvolvedor, sem pop-ups automáticos, sem
  câmera/microfone (`enable_media_stream=False`), sem WebRTC.
- `UserContentManager`: onde ficam instaladas as regras da camada 1.

Métodos:

- `criar_webview(relacionada)`: cria uma aba de página. Abas abertas por
  outras (pop-up de login) dividem a mesma sessão e as mesmas regras.
- `aplicar_lista(lista)`: transforma a lista em regras (`regras_de_conteudo`),
  pede ao WebKit para **compilá-las** e espera terminar antes de seguir, para
  nenhuma página abrir sem proteção.

### 5.2 `filtro.py`: as decisões de segurança

- `proteger(webview)`: liga os sinais de segurança numa aba.
- `abrir(webview, url)`: usado pela barra de endereço e pelos atalhos; troca
  http por https e bloqueia o que não pode.
- `bloquear(webview, url, motivo)`: mostra a tela de bloqueio com o motivo
  certo (fora da lista, seção barrada, sem criptografia, disfarçado,
  redirecionamento).
- `_ao_falhar(...)`: quando a **camada 1** barra a página principal, o WebKit
  avisa com o erro 104; aqui mostramos a tela de bloqueio.
- `_ao_decidir(...)`: recebe as três perguntas do WebKit e encaminha:
  - `_navegacao`: cliques e formulários para fora da lista → recusa na hora;
    clique em "Voltar para a página inicial" → abre `estudos://inicio`;
  - `_janela_nova`: pop-ups; os de fora da lista viram uma aba com a tela de
    bloqueio;
  - `_resposta`: checagem final; também barra downloads.
- `_ao_interromper(...)`: se o processo que desenha a aba cair (falha gráfica,
  memória), mostra a tela "Esta aba parou de funcionar" com "Tentar de novo"
  e "Página inicial", em vez de deixar a aba em branco.
- `_ao_abrir_menu(...)`: tira "baixar" e "inspecionar" do botão direito.
- `_ao_pedir_permissao(...)`: **nega tudo** (localização, câmera, microfone,
  notificações…) e avisa o aluno.

### 5.3 `aplicativo.py`: o aplicativo

- `carregar_fonte_do_programa()`: deixa a fonte Bricolage disponível só para
  este programa (via fontconfig), sem instalar nada no sistema.
- `Aplicativo.__init__`: guarda a lista, o contador e as preferências; cria o
  Pomodoro (com arquivo de estado) e o detector de inatividade. `unico=True`
  faz que abrir de novo só traga a janela já aberta para a frente.
- `do_startup()`: carrega o CSS da janela, cria o `Motor`, instala as regras e
  liga o relógio de 1 segundo (`_contar_tempo`).
- `do_activate()`: na primeira vez, pede para criar a senha; depois abre a
  `Janela`.
- `do_shutdown()`: salva o tempo ao sair.
- `trocar_lista(lista)`: instala uma lista nova depois que o responsável
  salva.
- `_servir_pagina_interna(pedido)`: responde aos endereços `estudos://`:
  `estudos://recursos/...` entrega arquivos de `recursos/` (com
  `recurso_seguro`); o resto gera a página inicial.
- `_contar_tempo()`: a cada segundo, se `deve_contar(...)` disser sim e o site
  tiver nome (`nome_do_site`), soma 1 segundo; salva a cada 15 segundos.
- `_ao_trocar_fase(...)`: fim de uma fase do Pomodoro: notificação, som e
  aviso na janela.

### 5.4 `inatividade.py`: o aluno está no computador?

- `MonitorDeInatividade`: pergunta ao GNOME (serviço
  `org.gnome.Mutter.IdleMonitor`) há quanto tempo não há teclado/mouse.
  Consulta a cada 5 segundos; se o serviço não existir, devolve `None` e o
  navegador conta como antes.

### 5.5 `janela.py`: a janela

- `Aba`: uma aba (a página + o rótulo com ícone, título e botão X).
- `Janela.__init__`: monta a barra superior, as abas e o aviso flutuante;
  liga os atalhos de teclado e o fechamento.
- `_ao_fechar()`: salva o tempo e **devolve `False`**, porque no GTK `True`
  cancelaria o fechamento. Este foi o defeito corrigido na v2.1.2.
- `_montar_barra_superior()`: botões voltar/avançar/recarregar/início, barra
  de endereço, relógio, Pomodoro 🍅, "Hoje" 📅 e menu ☰.
- `_atualizar_relogio()`: chamado a cada segundo; só redesenha quando o
  minuto muda.
- `_montar_popover_pomodoro()` / `atualizar_pomodoro()`: o painel do timer e
  as cores do botão (amarelo parado, coral estudando, verde na pausa).
- `_preencher_hoje()`: o painel "Estudo de hoje" (com nomes agrupados).
- `_criar_acoes()`: atalhos (Ctrl+T, Ctrl+W, Ctrl+L, F5, Alt+←…).
- `area_do_responsavel()`: pede a senha, abre o editor e aplica a lista e as
  preferências novas.
- `nova_aba()` / `fechar_aba()`: abrir e fechar abas (fechar a última volta
  para a página inicial).
- `_ao_digitar_endereco()`: texto com ponto vira endereço; outro texto vira
  pesquisa na Wikipédia.
- `atualizar_barra()`: endereço, ícone (seguro/bloqueado), botões e título.
- `mostrar_aviso()`: o aviso escuro que aparece embaixo por alguns segundos.

### 5.6 `paginas.py`: HTML das páginas internas

- `pagina_inicial(lista, contador, preferencias)`: monta o **mosaico**:
  boas-vindas com pesquisa, "Estudo de hoje" com a meta, "Sequência" 🔥, um
  bloco por categoria, "Onde você estudou hoje" e a dica do dia.
- `pagina_aba_interrompida(url, pode_voltar)`: a tela 🔌 de aba que caiu.
- `pagina_bloqueada(url, motivo)`: a tela 🚧. Usa o leitor rígido, para nunca
  mostrar o "site de fachada" de um endereço disfarçado.
- Todo texto vindo da lista passa por `escape()`, para um nome como
  `<script>` aparecer como texto e não virar código.

### 5.7 `dialogos.py`: janelas de diálogo

- `_perguntar_nova_senha()`: pede a senha nova duas vezes (sem gravar).
- `criar_senha()`: primeira execução.
- `pedir_senha()`: entrada na Área do responsável, com a contagem regressiva
  da espera **sem travar a janela** (um relógio do GLib atualiza o texto a
  cada segundo). Senha danificada sem cópia → mensagem explicando a
  recuperação manual.
- `editar_sites()`: a Área do responsável: editor da lista, meta diária,
  limite de inatividade, "Trocar senha…" (fica pendente até **Salvar**) e
  "Restaurar lista padrão". Só grava se a lista não tiver erros.

---

## 6. Recursos: visual e lista padrão (`recursos/`)

| Arquivo | Conteúdo |
|---|---|
| `sites_padrao.txt` | A lista que vem com o programa |
| `paginas/mosaico.css` | Visual das páginas internas (paleta: tinta, névoa, amarelo, coral, azul, verde, lilás) |
| `interface.css` | Visual da janela (barra escura, abas, botão do Pomodoro) |
| `fontes/` | Bricolage Grotesque (licença OFL, do Google Fonts) |
| `icone.svg` | O ícone do livro com o globo e o ✓ |

Os scripts `scripts/instalar.sh` e `scripts/desinstalar.sh` criam e removem o
atalho no menu de aplicativos, sem precisar de `sudo`.

---

## 7. Testes (`testes/`)

Rode com `python3 -m unittest discover testes`.

| Arquivo | O que prova |
|---|---|
| `test_regras.py`, `test_seguranca.py` | Lista, HTTPS, escapes, migração da lista |
| `test_urls.py` | Endereços disfarçados são recusados |
| `test_dominios.py` | Sufixos públicos e curingas são recusados; Sora barrado |
| `test_regras_conteudo.py` | As regras da camada 1 concordam com a lista |
| `test_navegacao_webkit.py` | Com o WebKit real e um servidor local que **anota cada pedido**: o site bloqueado não recebe nada (redirecionamentos, iframes, formulários, pop-ups, cookies) |
| `test_servicos_online.py` | (opcional, `ESTUDOS_TESTE_ONLINE=1`) IAs, YouTube, logins e todos os atalhos abrem |
| `test_arquivos.py` | Gravação segura: disco cheio, sem permissão, processo morto no meio, cópias e recuperação |
| `test_responsavel.py` | Senha de 8 caracteres, tentativas, recuperação sem permitir redefinição |
| `test_pomodoro.py` | Timer com relógio falso: ciclos, suspensão, reabrir |
| `test_estudos.py` | Inatividade, apelidos, música fora da contagem |
| `test_fechar_janela.py` | O botão X fecha o navegador e salva o tempo |
| `test_protegido.py` | Modo protegido: lista só leitura, auxiliar que valida e grava, pkexec simulado, injeção de código bloqueada |

`apoio_webkit.py` não é teste: são as ferramentas usadas pelos testes
(servidor local, janela invisível, espera de eventos).

---

## 8. Histórico: o que foi feito em cada versão

| Versão | Principais mudanças |
|---|---|
| **v1.0** | Navegador com abas, lista de sites, senha, Pomodoro, tempo por site |
| **v2.0** | IAs, login nos sites, HTTPS, permissões negadas, visual em mosaico, projeto reorganizado |
| **v2.1.1** | Camada 1 (bloqueio antes do pedido), leitor rígido de endereços, validação de domínios, exclusões (Sora, fórum da OpenAI, chat do Stack Overflow), testes com WebKit real |
| **v2.1.2** | Gravação segura e cópias, senha mais forte e limite de tentativas, recuperação segura, inatividade, estatísticas agrupadas, Pomodoro lembrado, música fora da contagem, correção do botão de fechar |
| **v2.1.3** | Relógio na barra superior, tela para aba interrompida, documentação atualizada e este guia |
| **v2.2** | Modo protegido (lista em /etc, senha de administrador via polkit) e isolamento da conta do aluno; primeira versão pública |
| **v2.3** | Instalação com um comando (`instalar.sh`) e README para quem está começando |

Para ver cada mudança em detalhe: `git log --stat` dentro da pasta do projeto.
