from app.db import executar

print("Iniciando a higienização dos dados de teste...")

# Tenta limpar cada tabela com segurança (caso não exista, o erro é ignorado)
tabelas = ["acessos", "historico_acessos", "alunos"]
for tabela in tabelas:
    try:
        executar(f"DELETE FROM {tabela}")
        print(f" - Tabela '{tabela}' limpa com sucesso.")
    except Exception as e:
        print(f" - Tabela '{tabela}' ignorada (não encontrada ou vazia).")

# Mantém apenas o operador ADMIN
try:
    executar("DELETE FROM operadores WHERE papel != 'ADMIN'")
    print(" - Operadores de teste removidos (ADMIN preservado).")
except Exception as e:
    print(" - Erro ao limpar operadores:", e)

print("\nHigienização concluída com sucesso! Sistema pronto para entrega.")