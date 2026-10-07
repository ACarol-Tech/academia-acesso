ALTER TABLE alunos
  ADD COLUMN ativo BOOLEAN NOT NULL DEFAULT TRUE,
  ADD INDEX idx_alunos_ativo_nome (ativo, nome);
