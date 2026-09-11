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

- chat interativo stateless;
- roteamento automático por padrão;
- seleção explícita de profile;
- verificação de saúde do Router;
- exibição de estado, profile, modelo, rota e métricas da execução;
- tratamento amigável de erros públicos do Router;
- interface de terminal baseada em Rich;
- instalação isolada como aplicação Python.

A CLI permanece sem histórico conversacional ou sessões persistentes.

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

A CLI abre diretamente o modo interativo.

Exemplo:

```text
╭───────────── Villaz-Lab ─────────────╮
│ Villaz-Lab CLI 0.1.0                 │
│ Router         http://127.0.0.1:8000 │
│                ● online              │
│ Modo           auto                  │
╰─ Interface local para o Villaz-Lab ──╯

Digite uma mensagem ou /help
villaz >
```

> A apresentação pode variar conforme largura do terminal e suporte visual do ambiente.

## Opções externas

### Ajuda

```console
villaz --help
```

Esse comando exibe ajuda estática e não inicia o chat.

### Versão

```console
villaz --version
```

Esse comando exibe apenas a versão instalada da CLI.

## Comandos do modo interativo

| Comando | Função |
| --- | --- |
| `/help` | Exibe a ajuda disponível |
| `/health` | Executa uma nova verificação de saúde do Router |
| `/status` | Mostra endpoint, modo, profile e saúde do Router |
| `/profile <id>` | Seleciona explicitamente um profile |
| `/profile auto` | Retorna ao roteamento automático |
| `/exit` | Encerra a CLI |

A versão atual **não possui** comandos como:

```text
/profiles
/retry
/last
/clear
/about
/config
```

Funcionalidades futuras não são documentadas como disponíveis até que façam parte de uma versão publicada.

## Roteamento automático

A CLI inicia em modo:

```text
auto
```

Nesse modo, a mensagem é enviada ao Router sem um profile explícito, e o Router tenta decidir deterministicamente qual profile deve tratar a solicitação.

Exemplo:

```text
villaz > Revise este código Python procurando vulnerabilidades de segurança.
```

O resultado depende das regras e profiles configurados no servidor.

Uma solicitação genérica demais pode resultar em:

```text
Não foi possível selecionar automaticamente um profile para esta solicitação.
```

Isso representa um resultado `UNROUTED` do Router e não necessariamente uma falha da CLI.

Tente reformular a mensagem fornecendo mais contexto sobre a tarefa.

## Profile explícito

Também é possível selecionar diretamente um profile válido da instalação do Router:

```text
villaz > /profile code-review-security
✓ Profile ativo: code-review-security
```

As mensagens seguintes utilizarão esse profile até que o modo seja alterado.

Para retornar ao roteamento automático:

```text
villaz > /profile auto
✓ Modo automático ativado.
```

Os IDs de profiles pertencem à configuração do Router.

Uma instalação personalizada pode utilizar profiles e modelos diferentes dos utilizados pela instalação oficial.

## Modelos personalizados

O Villaz-Lab CLI não depende de um modelo específico.

Um operador pode configurar sua instalação do Villaz-Lab Router com modelos diferentes, desde que a configuração do servidor permaneça válida e preserve o contrato público da API.

Por exemplo, um mesmo profile poderia utilizar:

```text
qwen2.5-coder:14b
```

em uma instalação e outro modelo compatível em outra.

A CLI simplesmente apresenta o `profile` e o `model` informados pelo Router na resposta.

Modelos, profiles e regras pertencem ao servidor.

## Exemplo de execução

Exemplo ilustrativo utilizando um profile explícito:

```text
villaz > /profile code-review-security

✓ Profile ativo: code-review-security

villaz > Responda apenas com a palavra OK.

╭─────────── Execução ────────────╮
│ Estado     explicit             │
│ Profile    code-review-security │
│ Modelo     qwen2.5-coder:14b    │
│ Rota       -                    │
│ Tempo      20.97s               │
│ Tokens     2                    │
│ Velocidade 45.29 tok/s          │
╰─────────────────────────────────╯

[resposta]
OK
```

Os seguintes valores são dependentes da instalação e da execução:

- estado;
- profile;
- modelo;
- rota;
- tempo;
- quantidade de tokens;
- velocidade;
- texto produzido pelo modelo.

O exemplo acima não define valores obrigatórios para outras instalações.

## Saúde do Router

Dentro da CLI:

```text
villaz > /health
```

Exemplo saudável:

```text
Saúde do Router

Live   ● online
Ready  ✓ pronto
```

`Live` indica que o serviço está acessível.

`Ready` indica que o Router está pronto para atender as operações previstas pelo seu contrato.

## Status

Use:

```text
villaz > /status
```

A saída apresenta informações como:

- identidade do Router;
- endpoint;
- modo atual;
- profile atual;
- Live;
- Ready.

No modo automático:

```text
Modo     auto
Profile  automático
```

No modo explícito, o profile selecionado é mostrado diretamente.

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

### Falha em `/health` ou `/status`

Se `/health` ou `/status` apresentar erro, isso pode indicar que o Router está inacessível ou que uma das verificações públicas de saúde não retornou o contrato esperado.

Na versão `0.1.0`, a CLI não apresenta separadamente todos os estados parciais possíveis entre `Live` e `Ready`.

Problemas de inicialização, runtime, profiles ou modelos devem ser investigados no servidor.

### `UNROUTED`

Significa que o Router não conseguiu selecionar automaticamente um profile para a solicitação.

Tente:

- fornecer mais contexto;
- descrever claramente a natureza da tarefa;
- utilizar um profile explícito válido quando apropriado.

### `AMBIGUOUS`

Significa que a solicitação correspondeu a mais de uma possibilidade sem uma decisão determinística suficiente.

Reformule a mensagem para torná-la mais específica.

### Profile inválido

Se o Router rejeitar o profile informado, confirme o ID com o operador daquela instalação.

A versão atual da CLI não possui `/profiles`.

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

- não possui histórico conversacional;
- não mantém sessões persistentes;
- não cria transcript;
- não salva automaticamente prompts e respostas;
- não possui streaming;
- não lista profiles;
- não seleciona modelos diretamente;
- não instala nem administra Ollama;
- não instala nem administra o Router;
- não configura profiles ou regras;
- não possui configuração persistente de endpoint;
- não funciona como cliente genérico para backends arbitrários.

Cada mensagem é tratada como uma solicitação independente.

Histórico, sessões e contexto conversacional pertencem a etapas futuras do projeto e não devem ser assumidos nesta versão.

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
