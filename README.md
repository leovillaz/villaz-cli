# Villaz-Lab CLI

Versão atual: **0.1.0**.

O Villaz-Lab CLI é o cliente interativo de terminal first-party do Villaz
Router. Ele é mantido como um projeto separado e sua integração futura ocorrerá
exclusivamente pela API HTTP pública do Router, sem chamadas diretas ao Ollama.

O estado atual é um bootstrap estrutural: a interface interativa existe, mas
ainda não envia prompts.

## Requisitos e instalação

- Python 3.13 ou superior.

Para uma instalação local editável com as dependências de desenvolvimento:

```console
python -m pip install -e ".[dev]"
```

## Uso

```console
villaz
villaz --help
villaz --version
python -m villaz_cli
```

O modo atual não persiste o texto digitado.

## Licença

Licenciado sob a Apache License 2.0.
