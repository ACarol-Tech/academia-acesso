-- MySQL 8.4+ · migração para bancos criados antes da versão integrada.
ALTER TABLE alunos
  ADD COLUMN IF NOT EXISTS data_nascimento DATE NULL,
  ADD COLUMN IF NOT EXISTS endereco VARCHAR(255) NULL,
  ADD COLUMN IF NOT EXISTS telefone VARCHAR(30) NULL;

ALTER TABLE planos
  ADD UNIQUE KEY uq_planos_nome (nome);

CREATE TABLE IF NOT EXISTS pagamentos (
  id CHAR(36) PRIMARY KEY,
  aluno_id CHAR(36) NOT NULL,
  matricula_id CHAR(36) NULL,
  plano_id CHAR(36) NOT NULL,
  valor DECIMAL(10,2) NOT NULL,
  data_pagamento DATE NOT NULL,
  forma_pagamento ENUM('PIX','CARTAO_CREDITO','DINHEIRO','BOLETO') NOT NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_pagamentos_aluno_data (aluno_id, data_pagamento),
  FOREIGN KEY (aluno_id) REFERENCES alunos(id),
  FOREIGN KEY (matricula_id) REFERENCES matriculas(id) ON DELETE SET NULL,
  FOREIGN KEY (plano_id) REFERENCES planos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
