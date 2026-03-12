import json
import os

# Função para carregar arquivos de histórico
def carregar_historico():
    arquivos = os.listdir('./scripts')
    historico = {}
    for arquivo in arquivos:
        if arquivo.endswith('.py') or arquivo.endswith('.json'):
            with open(f'./scripts/{arquivo}', 'r') as f:
                historico[arquivo] = f.read()
    return historico

# Função para identificar aprendizados acumulados
def identificar_aprendizados(historico):
    aprendizados = {}
    for arquivo, conteudo in historico.items():
        if 'aprendizado' in conteudo:
            aprendizados[arquivo] = conteudo
    return aprendizados

# Função para definir direções para a tarefa atual
def definir_direcoes(aprendizados):
    direcoes = {}
    for arquivo, conteudo in aprendizados.items():
        if 'direcao' in conteudo:
            direcoes[arquivo] = conteudo
    return direcoes

# Carregar histórico
historico = carregar_historico()

# Identificar aprendizados acumulados
aprendizados = identificar_aprendizados(historico)

# Definir direções para a tarefa atual
direcoes = definir_direcoes(aprendizados)

# Imprimir resultados
print('Histórico:', historico)
print('Aprendizados:', aprendizados)
print('Direções:', direcoes)
