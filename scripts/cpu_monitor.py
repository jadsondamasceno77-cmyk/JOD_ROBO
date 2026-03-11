import psutil
import logging
import time

# Configura o logging
logging.basicConfig(filename='cpu_usage.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def monitorar_cpu():
    while True:
        # Obtem o uso de CPU
        cpu_usage = psutil.cpu_percent()
        # Salva o log
        logging.info(f'Uso de CPU: {cpu_usage}%')
        # Aguarda 1 minuto para realizar a próxima leitura
        time.sleep(60)

if __name__ == '__main__':
    monitorar_cpu()
