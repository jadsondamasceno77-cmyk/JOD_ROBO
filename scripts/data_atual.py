import datetime

data_atual = datetime.datetime.now()

data_formatada = data_atual.strftime('%d de %B de %Y')

print(f'Data atual: {data_formatada}')