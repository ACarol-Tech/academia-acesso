"""Cria a primeira recepcionista e um plano. Rode uma vez: python seed.py"""
from app.config import settings
from app.db import executar, novo_id
from app.security import hash_senha

if not settings.seed_email or not settings.seed_senha:
    raise SystemExit("Defina SEED_EMAIL e SEED_SENHA no .env")
executar("INSERT IGNORE INTO operadores (id, nome, email, senha_hash, papel) VALUES (%s,%s,%s,%s,%s)",
         (novo_id(), "Camila", settings.seed_email.lower(), hash_senha(settings.seed_senha), "RECEPCAO"))
# Usuário administrativo inicial. Troque a senha imediatamente em produção.
executar("INSERT IGNORE INTO operadores (id, nome, email, senha_hash, papel) VALUES (%s,%s,%s,%s,%s)",
         (novo_id(), "Administrador", "admin@academia.com", hash_senha("admin123"), "ADMIN"))
planos = [
    ("Mensal Livre", 89.90, 3, 1),
    ("Mensal Manhã", 69.90, 3, 1),
    ("Trimestral", 239.90, 3, 3),
    ("Semestral", 449.00, 3, 6),
    ("Anual Black", 799.00, 3, 12),
]
for nome, valor, tolerancia, meses in planos:
    executar(
        "INSERT INTO planos (id, nome, valor, dias_tolerancia, meses) VALUES (%s,%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE valor=VALUES(valor), dias_tolerancia=VALUES(dias_tolerancia), meses=VALUES(meses)",
        (novo_id(), nome, valor, tolerancia, meses),
    )
print("Pronto. Apague SEED_SENHA do .env.")
