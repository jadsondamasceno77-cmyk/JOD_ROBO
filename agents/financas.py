class AnalisadorGastosMensais:
    def __init__(self, gastos):
        self.gastos = gastos

    def calcular_total(self):
        return sum(self.gastos)

    def calcular_media(self):
        return self.calcular_total() / len(self.gastos)

    def identificar_maior_gasto(self):
        return max(self.gastos)

# Exemplo de uso:
gastos = [100, 200, 300, 400, 500]
analisador = AnalisadorGastosMensais(gastos)
print(analisador.calcular_total())
print(analisador.calcular_media())
print(analisador.identificar_maior_gasto())