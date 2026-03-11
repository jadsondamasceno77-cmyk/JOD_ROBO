import requests
import json

# Definir fonte de cotação do dólar
url = 'https://api.exchangerate-api.com/v4/latest/USD'

# Criar lógica para buscar cotação e salvar em arquivo
def buscar_cotacao():
    response = requests.get(url)
    dados = response.json()
    cotacao = dados['rates']['BRL']
    with open('cotacao_dolar.json', 'w') as arquivo:
        json.dump({'cotacao': cotacao}, arquivo)

# Executar a função
buscar_cotacao()
