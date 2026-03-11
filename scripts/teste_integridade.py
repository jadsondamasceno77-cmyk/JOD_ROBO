import os
import requests
import subprocess

def verificar_conectividade_rede():
    try:
        requests.get('https://www.google.com')
        return True
    except requests.exceptions.RequestException:
        return False

def verificar_funcionamento_scripts_python():
    try:
        subprocess.check_call(['python', '-c', 'print("Olá, Mundo!")'])
        return True
    except subprocess.CalledProcessError:
        return False

def verificar_acesso_arquivos_diretorios():
    try:
        with open('teste.txt', 'r') as arquivo:
            arquivo.read()
        return True
    except FileNotFoundError:
        return False

if __name__ == '__main__':
    print('Verificando conectividade de rede...')
    if verificar_conectividade_rede():
        print('Conectividade de rede OK')
    else:
        print('Erro na conectividade de rede')

    print('Verificando funcionamento de scripts Python...')
    if verificar_funcionamento_scripts_python():
        print('Funcionamento de scripts Python OK')
    else:
        print('Erro no funcionamento de scripts Python')

    print('Verificando acesso a arquivos e diretórios...')
    if verificar_acesso_arquivos_diretorios():
        print('Acesso a arquivos e diretórios OK')
    else:
        print('Erro no acesso a arquivos e diretórios')