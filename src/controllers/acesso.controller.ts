import { FastifyRequest, FastifyReply } from 'fastify';
import { z } from 'zod';
import crypto from 'node:crypto';
import { generateCPFHash } from '../lib/crypto';

export const validarAcessoSchema = z.object({
  intelbras_user_id: z.string().optional(),
  cpf: z.string().optional()
});

export const liberarManualSchema = z.object({
  aluno_id: z.string().uuid(),
  motivo: z.string().min(3, 'O motivo é obrigatório'),
  observacao: z.string().optional()
});

export class AcessoController {

  static async validar(request: FastifyRequest, reply: FastifyReply) {
    const { intelbras_user_id, cpf } = validarAcessoSchema.parse(request.body);

    if (!intelbras_user_id && !cpf) {
      return reply.status(400).send({ liberado: false, motivo: 'Identificador não fornecido.' });
    }

    let queryAluno = 'SELECT id, nome, ativo FROM alunos WHERE ';
    const paramsAluno: any[] = [];

    if (intelbras_user_id) {
      queryAluno += 'intelbras_user_id = ?';
      paramsAluno.push(intelbras_user_id);
    } else if (cpf) {
      queryAluno += 'cpf_hash = ?';
      paramsAluno.push(generateCPFHash(cpf));
    }

    const [alunos]: any = await request.server.mysql.query(queryAluno, paramsAluno);
    const aluno = alunos[0];

    if (!aluno) {
      return reply.status(404).send({ liberado: false, motivo: 'Aluno não encontrado.' });
    }

    if (!aluno.ativo) {
      await AcessoController.registrarHistorico(request, aluno.id, 'NEGADO', 'Aluno com cadastro inativo');
      return reply.send({ liberado: false, aluno: aluno.nome, motivo: 'Cadastro inativo.' });
    }

    const [matriculas]: any = await request.server.mysql.query(
      'SELECT m.status, m.vencimento, p.dias_tolerancia FROM matriculas m INNER JOIN planos p ON m.plano_id = p.id WHERE m.aluno_id = ? AND m.status = \'ATIVO\' LIMIT 1',
      [aluno.id]
    );

    const matricula = matriculas[0];

    if (!matricula) {
      await AcessoController.registrarHistorico(request, aluno.id, 'NEGADO', 'Sem matrícula ativa');
      return reply.send({ liberado: false, aluno: aluno.nome, motivo: 'Sem matrícula ativa.' });
    }

    const hoje = new Date();
    hoje.setHours(0, 0, 0, 0);

    const dataVencimento = new Date(matricula.vencimento);
    dataVencimento.setDate(dataVencimento.getDate() + matricula.dias_tolerancia);

    if (hoje > dataVencimento) {
      await AcessoController.registrarHistorico(request, aluno.id, 'NEGADO', 'Matrícula vencida (tolerância excedida)');
      return reply.send({ liberado: false, aluno: aluno.nome, motivo: 'Matrícula vencida.' });
    }

    await AcessoController.registrarHistorico(request, aluno.id, 'APROVADO', 'Acesso autorizado');
    return reply.send({
      liberado: true,
      aluno: aluno.nome,
      motivo: 'Acesso liberado.'
    });
  }

  private static async registrarHistorico(request: FastifyRequest, alunoId: string, resultado: 'APROVADO' | 'NEGADO', motivo: string) {
    const id = crypto.randomUUID();
    await request.server.mysql.query(
      'INSERT INTO historico_acessos (id, aluno_id, resultado, motivo) VALUES (?, ?, ?, ?)',
      [id, alunoId, resultado, motivo]
    );
  }

  static async liberarManual(request: FastifyRequest, reply: FastifyReply) {
    const { aluno_id, motivo, observacao } = liberarManualSchema.parse(request.body);
    
    // Tratamento seguro do tipo do user vindouro do JWT
    const user = request.user as { sub: string; nome: string; papel: string };
    const operadorId = user.sub;

    const idLog = crypto.randomUUID();
    await request.server.mysql.query(
      'INSERT INTO log_liberacoes (id, aluno_id, operador_id, motivo, observacao) VALUES (?, ?, ?, ?, ?)',
      [idLog, aluno_id, operadorId, motivo, observacao || null]
    );

    await AcessoController.registrarHistorico(request, aluno_id, 'APROVADO', 'LIBERADO_MANUAL: ' + motivo);

    return reply.send({
      liberado: true,
      message: 'Catraca liberada manualmente com sucesso.'
    });
  }
}