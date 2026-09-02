# Contribuindo

Contribuições devem permanecer dentro do escopo aprovado do Villaz-Lab CLI,
preservar a privacidade e incluir testes compatíveis com a mudança.

A integração com o Villaz Router deve usar somente sua API HTTP pública. Não
são aceitas dependências diretas do código interno do Router nem acesso direto
ao Ollama.

Todos os testes devem ser herméticos e independentes de Router ou Ollama reais.
Nenhuma contribuição deve incluir dados privados, credenciais ou configuração
operacional.
