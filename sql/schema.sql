-- MySQL 8 · cria as tabelas (rodado automaticamente pelo docker compose)
CREATE TABLE operadores (
  id CHAR(36) PRIMARY KEY,
  nome VARCHAR(120) NOT NULL,
  email VARCHAR(190) NOT NULL UNIQUE,
  senha_hash VARCHAR(255) NOT NULL,
  papel VARCHAR(20) NOT NULL DEFAULT 'RECEPCAO',
  tentativas INT NOT NULL DEFAULT 0,
  bloqueado_ate DATETIME NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE reset_senha (
  id CHAR(36) PRIMARY KEY,
  operador_id CHAR(36) NOT NULL,
  codigo_hash CHAR(64) NOT NULL,
  expira_em DATETIME NOT NULL,
  usado TINYINT(1) NOT NULL DEFAULT 0,
  FOREIGN KEY (operador_id) REFERENCES operadores(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE planos (
  id CHAR(36) PRIMARY KEY,
  nome VARCHAR(80) NOT NULL,
  valor DECIMAL(10,2) NOT NULL,
  dias_tolerancia INT NOT NULL DEFAULT 3,
  UNIQUE KEY uq_planos_nome (nome)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE alunos (
  id CHAR(36) PRIMARY KEY,
  nome VARCHAR(120) NOT NULL,
  cpf_cript VARCHAR(255) NOT NULL,          -- CPF cifrado (AES-256-GCM)
  cpf_hash CHAR(64) NOT NULL UNIQUE,        -- hash com chave, só para evitar duplicidade
  foto_cript MEDIUMTEXT NULL,               -- foto cifrada
  intelbras_user_id VARCHAR(64) NULL UNIQUE,
  consentimento_lgpd_em DATETIME NOT NULL,
  data_nascimento DATE NULL,
  endereco VARCHAR(255) NULL,
  telefone VARCHAR(30) NULL,
  ativo BOOLEAN NOT NULL DEFAULT TRUE,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (ativo, nome)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE matriculas (
  id CHAR(36) PRIMARY KEY,
  aluno_id CHAR(36) NOT NULL,
  plano_id CHAR(36) NOT NULL,
  status ENUM('ATIVO','BLOQUEADO','CANCELADO') NOT NULL DEFAULT 'ATIVO',
  vencimento DATE NOT NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (aluno_id),
  FOREIGN KEY (aluno_id) REFERENCES alunos(id),
  FOREIGN KEY (plano_id) REFERENCES planos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE pagamentos (
  id CHAR(36) PRIMARY KEY,
  aluno_id CHAR(36) NOT NULL,
  matricula_id CHAR(36) NULL,
  plano_id CHAR(36) NOT NULL,
  valor DECIMAL(10,2) NOT NULL,
  data_pagamento DATE NOT NULL,
  forma_pagamento ENUM('PIX','CARTAO_CREDITO','DINHEIRO','BOLETO') NOT NULL,
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (aluno_id, data_pagamento),
  FOREIGN KEY (aluno_id) REFERENCES alunos(id),
  FOREIGN KEY (matricula_id) REFERENCES matriculas(id) ON DELETE SET NULL,
  FOREIGN KEY (plano_id) REFERENCES planos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE historico_acessos (
  id CHAR(36) PRIMARY KEY,
  aluno_id CHAR(36) NOT NULL,
  data_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resultado ENUM('APROVADO','NEGADO','LIBERADO_MANUAL') NOT NULL,
  motivo VARCHAR(200) NULL,
  INDEX (data_hora),
  FOREIGN KEY (aluno_id) REFERENCES alunos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE log_liberacoes (
  id CHAR(36) PRIMARY KEY,
  aluno_id CHAR(36) NOT NULL,
  operador_id CHAR(36) NOT NULL,
  motivo VARCHAR(120) NOT NULL,
  observacao VARCHAR(300) NULL,
  data_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (aluno_id) REFERENCES alunos(id),
  FOREIGN KEY (operador_id) REFERENCES operadores(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
