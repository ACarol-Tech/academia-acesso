from app.db import executar
from passlib.context import CryptContext

# Configura o contexto de hash utilizando o bcrypt padrão do projeto
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def resetar_admin():
    novo_email = "admin@academia.com"
    nova_senha_pura = "academia123"
    novo_hash = pwd_context.hash(nova_senha_pura)
    
    # Atualiza o usuário administrador existente ou cria caso não exista
    executar(
        "UPDATE operadores SET senha_hash = %s, papel = 'admin' WHERE email = %s",
        (novo_hash, novo_email)
    )
    print("Senha do administrador atualizada com sucesso para 'academia123'!")

if __name__ == "__main__":
    resetar_admin()