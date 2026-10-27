-- 003 · Base do sistema oficial

-- Usuários: desativar contas e exigir troca de senha no primeiro acesso
ALTER TABLE operadores
  ADD COLUMN ativo TINYINT(1) NOT NULL DEFAULT 1,
  ADD COLUMN troca_senha_obrigatoria TINYINT(1) NOT NULL DEFAULT 0;

-- Código de redefinição de senha: limite de tentativas por código
ALTER TABLE reset_senha ADD COLUMN tentativas INT NOT NULL DEFAULT 0;

-- Planos: duração padrão em meses (antes era deduzida pelo nome)
ALTER TABLE planos ADD COLUMN meses INT NOT NULL DEFAULT 1;
UPDATE planos SET meses = 12 WHERE LOWER(nome) LIKE '%anual%';
UPDATE planos SET meses = 6 WHERE LOWER(nome) LIKE '%semestral%';
UPDATE planos SET meses = 3 WHERE LOWER(nome) LIKE '%trimestral%';

-- Alunos: código numérico, porque o leitor usa número como ID do usuário
ALTER TABLE alunos
  ADD COLUMN codigo INT UNSIGNED NOT NULL AUTO_INCREMENT,
  ADD UNIQUE KEY uq_alunos_codigo (codigo);
ALTER TABLE alunos AUTO_INCREMENT = 10000;

-- Pagamentos: quantos meses cobre e quem lançou
ALTER TABLE pagamentos
  ADD COLUMN meses INT NOT NULL DEFAULT 1,
  ADD COLUMN operador_id CHAR(36) NULL,
  ADD CONSTRAINT fk_pagamentos_operador FOREIGN KEY (operador_id) REFERENCES operadores(id) ON DELETE SET NULL;

-- Histórico: por qual leitor passou, e índices para as consultas do painel
ALTER TABLE historico_acessos
  ADD COLUMN sentido ENUM('ENTRADA','SAIDA') NULL,
  ADD INDEX idx_historico_aluno_data (aluno_id, data_hora);
ALTER TABLE matriculas ADD INDEX idx_matriculas_aluno_criado (aluno_id, criado_em);

-- Permissões configuráveis por perfil
CREATE TABLE permissoes_perfil (
  papel VARCHAR(20) NOT NULL,
  permissao VARCHAR(60) NOT NULL,
  permitido TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (papel, permissao)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO permissoes_perfil (papel, permissao, permitido) VALUES
 ('ADMIN','aluno.cadastrar',1),('ADMIN','aluno.editar',1),('ADMIN','aluno.excluir',1),
 ('ADMIN','pagamento.registrar',1),('ADMIN','liberacao.manual',1),('ADMIN','historico.ver',1),
 ('ADMIN','relatorio.ver',1),('ADMIN','plano.editar',1),('ADMIN','visitante.gerenciar',1),
 ('ADMIN','usuario.gerenciar',1),('ADMIN','permissao.gerenciar',1),
 ('SUPORTE','aluno.cadastrar',1),('SUPORTE','aluno.editar',1),('SUPORTE','aluno.excluir',1),
 ('SUPORTE','pagamento.registrar',1),('SUPORTE','liberacao.manual',1),('SUPORTE','historico.ver',1),
 ('SUPORTE','relatorio.ver',1),('SUPORTE','plano.editar',1),('SUPORTE','visitante.gerenciar',1),
 ('SUPORTE','usuario.gerenciar',1),('SUPORTE','permissao.gerenciar',1),
 ('RECEPCAO','aluno.cadastrar',1),('RECEPCAO','aluno.editar',1),('RECEPCAO','aluno.excluir',0),
 ('RECEPCAO','pagamento.registrar',1),('RECEPCAO','liberacao.manual',1),('RECEPCAO','historico.ver',1),
 ('RECEPCAO','relatorio.ver',0),('RECEPCAO','plano.editar',0),('RECEPCAO','visitante.gerenciar',1),
 ('RECEPCAO','usuario.gerenciar',0),('RECEPCAO','permissao.gerenciar',0);

-- Auditoria: quem fez o quê e quando
CREATE TABLE auditoria (
  id CHAR(36) PRIMARY KEY,
  operador_id CHAR(36) NULL,
  acao VARCHAR(60) NOT NULL,
  entidade VARCHAR(40) NULL,
  entidade_id VARCHAR(64) NULL,
  detalhe VARCHAR(300) NULL,
  data_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (data_hora),
  INDEX (operador_id),
  FOREIGN KEY (operador_id) REFERENCES operadores(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;