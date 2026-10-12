# Plano de isolamento da conta do aluno (Ubuntu 24.04)

**Situação:** Etapas 0, 1, 2, 3 (Padrão) e 5 aplicadas e verificadas em
12/10/2026. Teste manual pela conta `aluno` (login gráfico) feito pelo
responsável: aprovado. **Decisões do responsável:** etapas 0, 1, 2, 3 e 5 (sem quiosque);
conta `aluno`.
**Processo:** auditar → planejar → autorizar → implementar, uma etapa por vez.

## 1. Auditoria (feita só com leitura, em 12/10/2026)

| Item | Encontrado |
|---|---|
| Sistema | Ubuntu 24.04.5 LTS, GNOME 46, GDM3, sessão X11 |
| Contas | Só a conta do responsável (administrador, grupo `sudo`). `HOME_MODE 0750`: pastas pessoais privadas |
| Sessões na tela de login | Ubuntu, Ubuntu (Xorg), GNOME Clássico (X11 e Wayland) |
| Burlas instaladas | Firefox e Brave (snap); terminal (Ctrl+Alt+T, Alt+F2); `curl`, `wget`, `w3m`; 8 apps Flatpak (jogos e outros programas) |
| Login em terminal de texto | Liberado; `pam_access` existe mas está comentado (`/etc/pam.d/login`, linha 74) |
| Navegador de Estudos | Em `~/Projetos` (privado). Lista e senha ficam na pasta de cada usuário |
| Dependências do navegador | Todas já instaladas no sistema |
| Quiosque | `gnome-kiosk-script-session` 46.0 disponível no repositório oficial (universe), não instalado |
| Controle parental (malcontent) | Disponível no repositório oficial, não instalado |
| Inicialização | UEFI, Secure Boot desligado, dual boot com Windows |
| AppArmor | Ativo |

## 2. O que o aluno poderia fazer para burlar (ameaças)

1. Abrir outro navegador (Firefox, Brave) ou app Flatpak.
2. Usar o terminal, Alt+F2, `curl`/`wget`/`w3m` ou Python.
3. Editar ou apagar a lista de sites e a senha do navegador (hoje ficam na pasta dele).
4. Escolher outra sessão na tela de login.
5. Entrar por um terminal de texto (Ctrl+Alt+F3).
6. Iniciar o Windows, um pendrive ou o modo de recuperação (acesso físico).
7. Usar a conta do responsável, se souber a senha.

Uma conta comum **sozinha** só resolve parte do item 3. Por isso o plano usa
várias camadas.

## 3. Etapas

Cada etapa tem um script de aplicação e um de reversão, que **você** executa
com `sudo` (eu não uso sudo). Antes de mudar qualquer arquivo do sistema, o
script guarda uma cópia em `/var/backups/navegador-estudos/`.

### Etapa 0: "modo protegido" no código do navegador ✅ implementada
*Obrigatória · não mexe no sistema · sem reinício*

- Se existir `/etc/navegador-estudos/`, a lista e as preferências vêm de lá
  (o aluno lê, mas não altera). Tempo de estudo, Pomodoro e cookies continuam
  na pasta do aluno.
- No modo protegido, a Área do responsável pede a **senha de administrador do
  Ubuntu** (polkit/pkexec) em vez da senha do navegador. Assim não existe
  senha do navegador para adivinhar ou apagar.
- Testes automatizados para o modo protegido e para o modo atual (que continua
  igual na sua conta).
- **Reverter:** `git` (versão anterior).

### Etapa 1: conta `aluno`
*Obrigatória · sem reinício*

- Conta padrão, sem `sudo`, pasta privada (750). Você define a senha.
- **Reverter:** `sudo deluser --remove-home aluno`.

### Etapa 2: navegador instalado para todas as contas
*Obrigatória · sem reinício*

- Código em `/opt/navegador-estudos` (dono root, só leitura para os outros).
- Lista e preferências em `/etc/navegador-estudos/` (dono root).
- Regra do polkit (`/usr/share/polkit-1/actions/`) e um pequeno programa
  auxiliar, dono root, que só grava a lista depois da senha de administrador.
- Atalho em `/usr/share/applications/`.
- **Efeito na sua conta:** o modo protegido vale para todas as contas. A lista
  passa a ser uma só (a sua lista atual é copiada para `/etc` como ponto de
  partida) e qualquer alteração pede a senha de administrador.
- **Reverter:** script remove exatamente esses arquivos.

### Etapa 3: travas na conta do aluno (sem instalar nada) — versão Padrão escolhida
*Programas bloqueados com `dpkg-statoverride` (root:sudo 750), que sobrevive a
atualizações; cron só para administradores; perfil dconf só do aluno ativado
por um gerador de ambiente do systemd; arquivos de inicialização travados.
A pasta pessoal com estrutura fixa ("Reforçada") não foi escolhida.*
*Recomendada · exige o aluno sair e entrar de novo*

a) **Travas do GNOME (dconf) só para o aluno:** desativar Alt+F2 e linha de
   comando, o atalho do terminal e a execução de scripts pelo Arquivos;
   deixar só o Navegador de Estudos na barra lateral.
b) **Bloqueio de execução só para o aluno (ACL):** `snap` (bloqueia Firefox,
   Brave e outros snaps), `flatpak`, terminais, `curl`, `wget`, `w3m`.
   O `python3` **não** pode ser bloqueado, porque o navegador usa.
c) **Atalhos e programas de inicialização do aluno:** sem quiosque, o aluno
   tem o Editor de Texto e poderia criar atalhos (`.desktop`) que executam
   comandos. As pastas `~/.local/share/applications` e `~/.config/autostart`
   do aluno ficam com dono root e travadas contra alteração.
- **Risco que sobra:** o `python3` continua executável (o navegador precisa
  dele). Sem terminal, Alt+F2 e atalhos próprios, usá-lo fica bem mais difícil,
  mas não impossível para alguém experiente.
- **Reverter:** script remove as travas e as ACLs.

### Etapa 4: sessão de quiosque — DESCARTADA por decisão do responsável
*Mantida aqui só como registro.*

- Instalar `gnome-kiosk-script-session` (repositório oficial do Ubuntu).
- Sessão "Navegador de Estudos" que abre **só** o navegador em tela cheia,
  definida como padrão do aluno. O script da sessão fica protegido contra
  alteração pelo aluno.
- **Limite:** a tela de login deixa escolher outra sessão; por isso a Etapa 3
  continua necessária.
- **Reverter:** remover a sessão e o pacote.

### Etapa 5: sem login em terminal de texto para o aluno
*Recomendada · sem reinício*

- Ativar `pam_access` em `/etc/pam.d/login` (descomentar a linha 74) e negar o
  aluno em `/etc/security/access.conf`. Sua conta não é afetada.
- **Reverter:** comentar a linha de novo e remover a regra.

### Fora do escopo (decisão sua)
*Não recomendado sem necessidade, pelas regras desta máquina*

- **Windows (dual boot):** o aluno pode iniciar o Windows, que não passa por
  nada disto. Solução: controle parental do próprio Windows (Microsoft Family).
- **Pendrive, BIOS e GRUB:** só se resolvem com senha de BIOS/GRUB, o que mexe
  em áreas que você proibiu de alterar sem necessidade comprovada.

## 4. Validação de cada etapa

Depois de cada etapa: testes automatizados do navegador e uma checagem na
conta `aluno` (entrar, tentar abrir Firefox, terminal, outra sessão, editar a
lista). Os resultados vão para um relatório com evidências.
