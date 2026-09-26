# Villaz-Lab CLI

Cliente interativo de terminal first-party para o **Villaz-Lab Router**.

Versão atual: **0.1.0 — Alpha**

O `villaz-cli` fornece uma interface humana de terminal para conversar com uma instância do Villaz-Lab Router por meio de sua API HTTP pública.

A CLI não acessa o Ollama diretamente, não escolhe modelos por conta própria e não depende do filesystem interno do Router.

```text
Usuário
  │
  ▼
villaz-cli
  │
  │ HTTP
  ▼
Villaz-Lab Router
  │
  ▼
Profile / modelo configurado no servidor
```

## Estado atual

A versão `0.1.0` oferece:

- interface TUI full-screen baseada em Textual;
- sessão conversacional efêmera em memória;
- histórico lógico formado por Turns confirmadas;
- roteamento automático por padrão;
- seleção explícita de profile através de `F5`;
- redução automática do contexto efetivo em `CONTEXT_OVERFLOW`;
- tratamento amigável de erros públicos do Router;
- ajuda externa estática baseada em Rich;
- instalação isolada como aplicação Python.

A CLI ainda não oferece gerenciamento ou persistência de sessões entre execuções.

## Requisitos

### Usuário final

- Python **3.13 ou superior**;
- `pipx`;
- uma instância válida do Villaz-Lab Router em execução.

O `villaz-cli` não instala nem configura:

- Villaz-Lab Router;
- Ollama;
- modelos;
- profiles;
- regras de roteamento;
- serviços do sistema;
- firewall.

Esses componentes pertencem à instalação do servidor.

### Compatibilidade validada

O fluxo de instalação abaixo foi validado em:

- Debian 13;
- Python 3.13.5;
- pipx 1.7.1.

O projeto é empacotado como aplicação Python independente de sistema operacional, mas o fluxo de instalação no Windows ainda não faz parte do gate prático desta versão.

## Instalação

### 1. Instale o `pipx`

No Debian 13:

```console
sudo apt update
sudo apt install pipx
```

Confirme:

```console
pipx --version
```

O diretório usado pelo `pipx` para expor aplicações deve estar no seu `PATH`.

Você pode verificar com:

```console
pipx environment
```

### 2. Instale o Villaz-Lab CLI

Enquanto o projeto ainda não estiver publicado no PyPI, instale diretamente do repositório oficial:

```console
pipx install git+https://github.com/leovillaz/villaz-cli.git
```

Ao final, confirme:

```console
villaz --version
```

Saída esperada para esta versão:

```text
Villaz-Lab CLI 0.1.0
```

Também é possível verificar a instalação com:

```console
pipx list
```

## Uso rápido

Inicie a interface:

```console
villaz
```

O comando abre a interface TUI full-screen do Villaz-Lab CLI.

A interface é organizada em áreas para:

- sessões;
- conversa;
- contexto operacional;
- composição da próxima mensagem.

O layout se adapta à largura disponível no terminal.

## Opções externas

### Ajuda

```console
villaz --help
```

Esse comando exibe a ajuda estática e encerra sem iniciar a TUI ou acessar o Router.

### Versão

```console
villaz --version
```

Esse comando exibe apenas a versão instalada da CLI:

```text
Villaz-Lab CLI 0.1.0
```

## Controles da TUI

| Controle | Função |
| --- | --- |
| `Enter` | Envia a mensagem |
| `Shift+Enter` | Insere uma nova linha |
| `F2` | Foca Sessões |
| `F3` | Foca Conversa |
| `F4` | Foca Contexto |
| `F5` | Seleciona o modo/profile da sessão |
| `F6` | Foca Mensagem |
| `Ctrl+Q` | Encerra o Villaz-Lab CLI |

A seleção de profile é realizada nativamente pela TUI através de `F5`.

A interface continua sem comandos slash para profile, health/status ou gerenciamento de sessões. Esses recursos não devem ser presumidos apenas por terem existido na interface linear anterior.

## Conversação e roteamento

As mensagens digitadas no composer são processadas pela camada conversacional do Villaz-Lab CLI e enviadas ao Villaz-Lab Router através de sua API HTTP pública.

A sessão inicial utiliza roteamento automático. Nesse modo, a mensagem é enviada sem um profile explícito e o Router tenta decidir deterministicamente qual profile deve processar a solicitação.

Pressionando `F5`, o usuário pode alternar a sessão entre:

- **automático** — nenhuma identificação explícita de profile é enviada e o Router continua responsável pelo roteamento;
- **explícito** — o usuário informa manualmente um `profile_id`, que passa a ser utilizado nas próximas mensagens da sessão.

A CLI não mantém um catálogo local de profiles e não tenta validar previamente se o ID informado existe. Essa validação continua pertencendo ao Villaz-Lab Router durante a execução.

Alterar o modo/profile não limpa nem substitui o histórico lógico já confirmado da conversa.

Uma mensagem genérica demais pode resultar em:

```text
Não foi possível selecionar um perfil automaticamente.
```

Isso representa um resultado `UNROUTED` do Router e não necessariamente uma falha da CLI.

Nesse caso, reformule a mensagem fornecendo mais contexto sobre a tarefa.

Profiles, regras de roteamento e associação de modelos continuam pertencendo ao Router.

## Histórico lógico e contexto efetivo

A CLI mantém uma conversa formada por mensagens confirmadas do usuário e do assistente.

O histórico lógico da sessão e o contexto efetivamente enviado ao modelo são conceitos distintos.

Quando o Router informa `CONTEXT_OVERFLOW`, a camada conversacional pode reduzir automaticamente o contexto efetivo removendo as Turns completas mais antigas e tentar novamente, sem alterar retroativamente o histórico lógico da sessão.

A TUI não cria uma nova Turn quando a execução falha.

## Modelos personalizados

O Villaz-Lab CLI não depende de um modelo específico.

Um operador pode configurar sua instalação do Villaz-Lab Router com modelos diferentes, desde que a configuração do servidor permaneça válida e preserve o contrato público da API.

Profiles, modelos e regras de execução são responsabilidade do Router.

A interface atual prioriza a experiência conversacional e não expõe todos os metadados internos de execução, como modelo, rota, quantidade de tokens ou velocidade de geração.

## Exemplo de execução

Com a TUI aberta, digite a solicitação no composer e pressione `Enter`.

Exemplo conceitual:

```text
Usuário:
Revise este código Python procurando vulnerabilidades de segurança.

Assistente:
[resposta produzida pelo modelo selecionado pelo Router]
```

A resposta só é adicionada à conversa após uma execução bem-sucedida.

Em caso de falha, a TUI apresenta uma mensagem pública sanitizada e restaura o conteúdo original no composer para permitir nova tentativa.

## Endpoint do Router

Na versão `0.1.0`, o endpoint utilizado pela CLI é:

```text
http://127.0.0.1:8000
```

Isso significa que, na versão atual, a CLI espera encontrar o Router na própria máquina.

A arquitetura da CLI é baseada no contrato HTTP público do Villaz-Lab Router e não depende do filesystem do servidor, mas **a configuração de endpoint remoto ainda não faz parte da interface publicada da versão 0.1.0**.

Não edite o código-fonte da CLI apenas para trocar o endereço do Router.

A configuração de endpoint será tratada em checkpoint próprio quando esse recurso fizer parte do produto.

## Compatibilidade com o Router

O `villaz-cli` é um cliente first-party do Villaz-Lab Router.

Ele não é um cliente genérico para:

- Ollama diretamente;
- OpenAI API;
- LM Studio;
- LiteLLM;
- Open WebUI;
- outros backends com contratos diferentes.

Uma implementação alternativa poderá ser tecnicamente compatível se implementar corretamente o mesmo contrato HTTP público esperado pelo Villaz-Lab CLI.

A implementação oficial `villaz-router` é a referência de compatibilidade.

## Troubleshooting

### `villaz: command not found`

Verifique se a instalação existe:

```console
pipx list
```

Consulte os diretórios utilizados pelo `pipx`:

```console
pipx environment
```

O diretório de aplicações expostas pelo `pipx` precisa fazer parte do `PATH`.

### Router inacessível

Se a CLI indicar que não conseguiu acessar o Router, verifique:

- se o Router está em execução;
- se está ouvindo no endpoint esperado;
- se não existe bloqueio local de rede ou firewall;
- se o serviço responde aos endpoints de saúde.

Na versão `0.1.0`, o endpoint esperado é:

```text
http://127.0.0.1:8000
```

Uma falha de comunicação com o Router não significa necessariamente que a instalação da CLI esteja incorreta.

### `UNROUTED`

Significa que o Router não conseguiu selecionar automaticamente um profile para a solicitação.

Tente:

- fornecer mais contexto;
- descrever claramente a natureza da tarefa;
- reformular a solicitação de forma mais específica.

Se você conhece o `profile_id` adequado, pode pressionar `F5` e selecionar um profile explícito para as próximas mensagens.

A existência e validade desse profile serão verificadas pelo Router durante a execução.

### `AMBIGUOUS`

Significa que a solicitação correspondeu a mais de uma possibilidade sem uma decisão determinística suficiente.

Reformule a mensagem para torná-la mais específica.

### `CONTEXT_OVERFLOW`

Significa que o contexto enviado ao Router excedeu a capacidade disponível para a execução.

A camada conversacional tenta reduzir automaticamente o contexto efetivo removendo as Turns completas mais antigas.

Se não for possível concluir a execução mesmo após essa redução, a TUI apresenta:

```text
A conversa excede o contexto disponível do modelo.
```

Uma falha desse tipo não cria uma nova Turn na conversa.

### Falha durante execução do modelo

A CLI pode estar corretamente instalada mesmo que a inferência não esteja disponível.

As camadas são independentes:

```text
villaz-cli
    │
    ▼
rede HTTP
    │
    ▼
Villaz-Lab Router
    │
    ▼
runtime / profile / modelo
```

Uma falha do modelo ou runtime deve ser investigada no servidor.

## Limitações atuais

A versão `0.1.0`:

- mantém apenas uma sessão efêmera durante a execução atual da TUI;
- não oferece gerenciamento, listagem, retomada ou persistência de sessões pela interface;
- não cria transcript exportável;
- não salva automaticamente prompts e respostas entre execuções;
- não possui streaming;
- não lista profiles disponíveis;
- não valida localmente a existência de um `profile_id` explícito;
- não seleciona modelos diretamente;
- não instala nem administra Ollama;
- não instala nem administra o Router;
- não configura profiles ou regras no servidor;
- não possui configuração persistente de endpoint;
- não funciona como cliente genérico para backends arbitrários.

O histórico lógico existe durante a Session atual e é utilizado como contexto conversacional nas mensagens seguintes.

Esse histórico ainda não sobrevive ao encerramento da TUI porque o gerenciamento de sessões persistentes permanece fora do escopo desta versão.

## Privacidade e segurança

O Villaz-Lab CLI não cria histórico persistente nem salva automaticamente prompts e respostas.

Isso **não significa** que nenhuma outra camada da instalação possa registrar dados.

Políticas de:

- logs;
- retenção;
- observabilidade;
- runtime;
- infraestrutura;
- modelos;

dependem da configuração do servidor operado pelo usuário.

Portanto, não envie senhas, tokens, chaves privadas ou outras credenciais como prompt, especialmente quando você não controla a infraestrutura do Router.

A documentação da CLI não recomenda:

- desabilitar firewall indiscriminadamente;
- expor o Router publicamente à Internet;
- instalar pacotes diretamente no Python do sistema com bypass de proteções;
- usar `--break-system-packages`;
- chamar Ollama diretamente para contornar o Router.

## Desenvolvimento

Para desenvolvimento local, clone o repositório e utilize um ambiente virtual separado.

```console
git clone https://github.com/leovillaz/villaz-cli.git
cd villaz-cli
python3.13 -m venv .venv
```

No Linux:

```console
.venv/bin/python -m pip install -e '.[dev]'
```

Execute os testes:

```console
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

A instalação de desenvolvimento é diferente da instalação recomendada para usuário final.

O usuário final não precisa criar ou ativar manualmente uma `.venv`; o `pipx` mantém o ambiente da aplicação isolado.

## Projeto relacionado

Backend oficial:

`villaz-router`

https://github.com/leovillaz/villaz-router

CLI:

https://github.com/leovillaz/villaz-cli

## Licença

Licenciado sob a **Apache License 2.0**.

Consulte o arquivo `LICENSE` para os termos completos.
