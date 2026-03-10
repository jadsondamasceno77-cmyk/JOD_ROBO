# JOD ROBO

## Setup

1. Clone o repositório
2. Crie um arquivo .env com as variáveis de ambiente
3. Execute o comando `docker build -t jod-robo .`
4. Execute o comando `docker run -p 8000:8000 jod-robo`

## Endpoints

* `/`: Retorna o status do agente
* `/health`: Retorna o status do agente
* `/chat`: Envia uma mensagem para o agente
* `/intent`: Envia uma mensagem para o agente
* `/exec`: Executa código Python
* `/analyze`: Analisa um site
* `/clone`: Clona o agente