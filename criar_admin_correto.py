from app.db import executar
from passlib.context import CryptContext

# Usamos argon2 ou um contexto limpo que não quebra nos 72 bytes do bcrypt
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

def cadastrar_admin():
    email = "admin@academia.com"
    nome = "Administrador"
    senha_pura = "academia123"
    
    senha_hash = pwd_context.hash(senha_pura)
    
    # Insere ou atualiza o administrador com ID/Email correto
    executar(
        "INSERT INTO operadores (nome, email, senha_hash, papel) VALUES (%s, %s, %s, 'ADMIN') "
        "ON DUPLICATE KEY UPDATE senha_hash = VALUES(senha_hash), papel = 'ADMIN'",
        (nome, email, senha_hash)
    )
    print("Administrador admin@academia.com configurado com sucesso!")

if __name__ == "__main__":
    cadastrar_admin()