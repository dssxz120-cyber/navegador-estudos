# Navegador de Estudos — versão 2.1.3

Um navegador que **só abre sites de uma lista aprovada**. Redes sociais, YouTube,
jogos e buscadores abertos ficam bloqueados. Inclui IAs para estudo, um timer
Pomodoro, meta diária, sequência de dias estudados e um visual em mosaico colorido.

## Instalar em outro computador

Requisito: **Ubuntu 24.04**. Abra o Terminal (Ctrl+Alt+T) e rode:

```
sudo apt install git python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 publicsuffix gstreamer1.0-plugins-good gstreamer1.0-libav
git clone https://github.com/dssxz120-cyber/navegador-estudos.git ~/navegador-estudos
cd ~/navegador-estudos
```

Depois escolha **um** modo:

- **Simples** (uma pessoa, para focar nos estudos): `bash scripts/instalar.sh`.
  O navegador aparece no menu; na primeira vez ele pede a senha do responsável.
- **Protegido** (computador com uma conta de aluno): rode, nesta ordem,
  as etapas da seção "Conta separada para o aluno" abaixo. Num computador
  novo a lista inicial é a **lista padrão**; YouTube, música e outros sites
  podem ser liberados depois na Área do responsável.

Para atualizar: `cd ~/navegador-estudos && git pull` (no modo protegido,
rode também `sudo bash scripts/isolamento/etapa2-aplicar.sh`, que reinstala o
código e mantém a lista).

## Como abrir

- Pelo menu de aplicativos: procure **Navegador de Estudos**.
- Ou pelo terminal: `python3 ~/Projetos/navegador-estudos/navegador_estudos.py`

Na **primeira vez**, o programa pede para criar a **senha do responsável**. Ela é
necessária para alterar a lista de sites e a meta diária. O aluno não deve conhecê-la.

## O que vem liberado

| Categoria | Sites |
|---|---|
| Inteligência Artificial | ChatGPT, Gemini, Claude, Perplexity, Copilot |
| Wikipédia e dicionários | Wikipédia, Wikcionário, Dicio, Michaelis |
| Cursos e exercícios | Khan Academy, Brasil Escola, Só Matemática, Duolingo |
| Programação | MDN, W3Schools, Python, Godot, Stack Overflow |
| Pesquisa acadêmica | Google Acadêmico, SciELO |

**Login nos sites (opcional):** as páginas de entrada do Google
(`accounts.google.com`) e da Microsoft (`login.live.com`) estão liberadas para
"Entrar com Google/Microsoft" no ChatGPT, Gemini etc. O navegador **não** tem
contas próprias e ninguém precisa entrar para usar. Só a página de login fica
liberada: a busca do Google, o YouTube e o Gmail continuam bloqueados.

> Sobre as IAs: os termos do ChatGPT exigem 13 anos ou mais (e, para menores de
> 18, autorização dos pais). As IAs respondem sobre qualquer assunto, não só estudo.

## Para o responsável: ☰ → Área do responsável

Digite a senha. Dá para mudar a **meta diária** (em minutos) e a **lista de sites**:

| Linha                         | O que faz                                    |
|-------------------------------|----------------------------------------------|
| `[Matemática]`                | começa um bloco na página inicial            |
| `Khan Academy \| https://pt.khanacademy.org/` | cria um atalho **e** libera o site |
| `+ khanacademy.org`           | libera o domínio sem criar atalho            |
| `- chat.stackoverflow.com`    | barra um subdomínio de um domínio liberado   |
| `# texto`                     | comentário                                   |

Liberar `exemplo.com` também libera `www.exemplo.com`, `pt.exemplo.com` etc.
O editor recusa curingas (`*.com`) e sufixos públicos (`com.br`, `co.uk`,
`github.io`), que liberariam milhares de sites. A verificação usa a lista oficial
de sufixos públicos que já vem no Ubuntu (`/usr/share/publicsuffix`).

A lista padrão barra seções sociais dentro de sites liberados: o **Sora**
(`sora.chatgpt.com`, rede social de vídeos da OpenAI), o fórum
`community.openai.com` e o chat `chat.stackoverflow.com`. O ChatGPT continua liberado.

## Segurança

| Proteção | Como funciona |
|---|---|
| Lista de sites | Tudo fora da lista é barrado: links, redirecionamentos, formulários, pop-ups, `meta refresh` |
| Bloqueio antes do pedido | Regras de bloqueio do próprio WebKit: o site bloqueado **nem recebe a conexão** (e não grava cookies), inclusive em redirecionamentos |
| Endereços disfarçados | Barra invertida, `usuario@`, `%` ou acentos no nome do site são recusados (veja `nucleo/urls.py`) |
| Só HTTPS | Endereços `http://` são trocados por `https://`; sem versão segura, não abrem |
| Iframes | Páginas de fora da lista dentro de outras ficam vazias. Exceções: vídeos do YouTube/Vimeo e verificações "não sou robô" |
| O que **não** é filtrado | Imagens, scripts, vídeos e conexões auxiliares carregam de qualquer lugar, para que YouTube e IAs funcionem. O filtro controla as **páginas** |
| Permissões | Câmera, microfone, localização, notificações e área de transferência: **sempre negados** |
| Rastreamento | Cookies de terceiros recusados e prevenção de rastreamento (ITP) ligada |
| Downloads | Desativados |
| Ferramentas de desenvolvedor | Desativadas |
| Endereços perigosos | `file://`, `data:`, `javascript:`, `ftp://` não abrem como página |
| Senha | Guardada só como hash PBKDF2 (300 mil rodadas); errar a senha gera espera |
| Arquivos | Lista e senha com permissão `600` (só o próprio usuário lê) |

### Limites importantes

O filtro vale **apenas dentro deste navegador**. Se o aluno usar o Firefox no
mesmo computador, terá acesso livre. Para um controle real, crie uma **conta de
usuário separada** para o aluno no Ubuntu (Configurações → Sistema → Usuários) e
deixe apenas o Navegador de Estudos nela. Na mesma conta, alguém com conhecimento
técnico poderia apagar `~/.config/navegador-estudos/senha.json`.

## A senha do responsável

- Senhas novas precisam ter **pelo menos 8 caracteres** e não podem ser
  repetitivas (como `aaaaaaaa`). Senhas criadas em versões anteriores
  continuam valendo; a Área do responsável sugere trocá-las.
- Depois de **3 tentativas erradas**, cada erro impõe uma espera que dobra
  (30 s, 1 min, 2 min… até 15 min). Fechar e abrir o navegador não zera a espera.
  Acertar a senha zera o contador.
- "Trocar senha…" só vale ao clicar em **Salvar**; Cancelar mantém a senha atual.

### Recuperar a senha

- **Arquivo danificado:** o navegador recupera sozinho a última cópia válida
  (pasta `~/.config/navegador-estudos/copias/`), com a senha **atual**.
- **Danificado e sem cópia:** por segurança, o navegador **não** deixa criar
  outra senha pela tela (senão bastaria estragar o arquivo para trocar a senha).
  O responsável pode, pelo Terminal, guardar o arquivo danificado e reabrir o
  navegador, que então pede uma senha nova:

  ```
  mv ~/.config/navegador-estudos/senha.json ~/.config/navegador-estudos/senha.json.danificada
  ```
- **Esqueceu a senha:** use o mesmo comando acima.

Limite: na **mesma conta do Linux**, quem souber usar o Terminal também
consegue fazer isso. A proteção completa depende de uma conta separada para o
aluno (planejada para uma etapa futura).

## Tempo de estudo, relógio e Pomodoro

- O **relógio** fica na barra superior, ao lado do Pomodoro; passe o mouse
  sobre ele para ver a data completa.

- O tempo só conta com a janela do navegador em primeiro plano **e** com o
  aluno presente: depois de **5 minutos sem teclado e mouse**, a contagem pausa
  (o limite muda na Área do responsável). Se houver som tocando, como numa
  vídeo-aula, continua contando.
- Na lista, `+ dominio = Nome` junta o tempo daquele domínio ao de um site:
  por exemplo, `+ scielo.org = SciELO`. Registros antigos com nome de domínio
  (como "youtube.com") são agrupados com o atalho correspondente na exibição;
  os arquivos não são alterados.
- `~ dominio` marca um site liberado que **não conta como estudo**, como
  música: `~ music.youtube.com` e `~ spotify.com`. Dá para ouvir música
  enquanto estuda; o tempo na aba de estudo continua contando normalmente.
- O Pomodoro é medido pelo relógio e lembrado ao fechar o navegador. Se a fase
  terminar com o navegador fechado, ele passa para a fase seguinte, pausado.

## Cópias de segurança

Os arquivos de dados são gravados de forma segura (tudo ou nada) e têm cópias
em uma pasta `copias/` ao lado deles: até 3 por arquivo (lista de sites, senha,
preferências) e, para o tempo de estudo, no máximo uma por hora, apagadas após
30 dias. Um arquivo danificado nunca é apagado: ele é guardado como
`.corrompido-DATA` e a última cópia válida é restaurada.

## Conta separada para o aluno (isolamento)

O plano completo está em `docs/PLANO-ISOLAMENTO.md`. Cada etapa tem um script
que **você** roda com `sudo` (revise antes com `--simular`, que não muda nada):

```
bash scripts/isolamento/etapa1-aplicar.sh --simular      # só mostra
sudo bash scripts/isolamento/etapa1-aplicar.sh           # cria a conta "aluno"
sudo bash scripts/isolamento/etapa2-aplicar.sh           # instala para todas as contas
```

Para desfazer: `etapa1-reverter.sh` e `etapa2-reverter.sh`. Toda alteração
guarda cópia em `/var/backups/navegador-estudos/`.

Depois da Etapa 2 o navegador fica em **modo protegido** para todas as contas:
a lista fica em `/etc/navegador-estudos/` e a Área do responsável pede a
**senha de administrador** do Ubuntu para salvar.

## Atalhos de teclado

| Tecla | Ação | Tecla | Ação |
|---|---|---|---|
| Ctrl+T | nova aba | Ctrl+W | fechar aba |
| Ctrl+L | barra de endereço | F5 | recarregar |
| Alt+← / Alt+→ | voltar / avançar | Alt+Home | página inicial |
| Ctrl+ + / Ctrl+ − | zoom | Ctrl+0 | zoom normal |

## Organização do projeto

```
navegador_estudos.py        ponto de partida
estudos/
  nucleo/                   regras e dados (não dependem da parte gráfica)
    regras.py               lista de sites, a decisão "pode abrir?" e as regras do WebKit
    urls.py                 leitura rígida de endereços (contra disfarces)
    dominios.py             validação de domínios (sufixos públicos, curingas)
    senha.py                senha do responsável (hash) e recuperação
    tentativas.py           limite de tentativas de senha
    arquivos.py             gravação segura e cópias de segurança
    tempo.py                tempo por site, inatividade, sequência de dias e relógio
    pomodoro.py             timer 25/5/15, medido pelo relógio e lembrado
    preferencias.py         meta diária e limite de inatividade
    caminhos.py             onde cada arquivo fica
  interface/                tudo o que aparece na tela
    aplicativo.py           janela principal, páginas internas, tempo e Pomodoro
    motor.py                o WebKit configurado com as proteções
    filtro.py               o filtro de segurança (leia este primeiro!)
    janela.py               janela, abas, relógio, Pomodoro e "Hoje"
    paginas.py              HTML da página inicial e das telas de bloqueio/aba interrompida
    dialogos.py             senha e área do responsável
    inatividade.py          pergunta ao GNOME há quanto tempo o aluno está parado
recursos/
  sites_padrao.txt          lista padrão de sites
  paginas/mosaico.css       visual das páginas
  interface.css             visual da janela
  fontes/                   Bricolage Grotesque (licença OFL, Google Fonts)
  icone.svg
scripts/                    instalar e desinstalar o atalho do menu
testes/                     testes automáticos
docs/GUIA-DO-CODIGO.md      explicação do código, arquivo por arquivo
```

## Onde ficam os dados

| Pasta | Conteúdo |
|---|---|
| `~/.config/navegador-estudos/` | `sites.txt`, `senha.json` (só o hash), `preferencias.json`, `pomodoro.json` (estado do timer) e `tentativas.json` (erros de senha) |
| `~/.config/navegador-estudos/copias/` | cópias de segurança da lista, da senha e das preferências |
| `~/.local/share/navegador-estudos/tempo/` | tempo estudado, um arquivo por dia, com cópias em `copias/` |
| `~/.local/share/navegador-estudos/navegacao/` | cookies e logins dos sites |

Ao atualizar da versão 1.0, se a lista de sites nunca foi editada, ela é trocada
pela lista nova automaticamente (a antiga fica em `sites.txt.anterior`). Listas
editadas pelo responsável não são mexidas.

## Testes

```
python3 -m unittest discover testes
```

- Testes de regras, endereços e domínios rodam em qualquer lugar.
- `test_navegacao_webkit.py` usa o WebKit real numa janela invisível e um
  servidor local que anota cada pedido: assim prova que o site bloqueado
  **não recebeu** nada. Precisa de uma sessão gráfica (é pulado sem ela).
- `test_servicos_online.py` abre as IAs, o YouTube e as páginas de login reais.
  Só roda quando pedido: `ESTUDOS_TESTE_ONLINE=1 python3 -m unittest testes.test_servicos_online -v`

## Desinstalar ou voltar versão

- `scripts/desinstalar.sh` remove o atalho do menu; com `--apagar-dados` remove também lista, senha e histórico.
- Voltar para a versão 1.0: `git checkout v1.0` dentro da pasta do projeto.

## Licença

O código é distribuído sob a **licença MIT** (veja o arquivo `LICENSE`):
qualquer pessoa pode usar, copiar, modificar e distribuir, desde que mantenha
o aviso de direitos autorais. A fonte Bricolage Grotesque, em
`recursos/fontes/`, tem licença própria (SIL Open Font License 1.1).
