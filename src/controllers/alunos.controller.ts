import { FastifyRequest, FastifyReply } from 'fastify';
import { z } from 'zod';
import crypto from 'node:crypto';
import { encryptCPF, generateCPFHash, decryptCPF } from '../lib/crypto';

export const cadastrarAlunoSchema = z.object({
  nome: z.string().min(2, 'Nome é obrigatório'),
  cpf: z.string().min(11, 'CPF inválido'),
  foto_cript: z.string().optional(),
  intelbras_user_id: z.string().optional(),
  data_nascimento: z.string().optional(),
  endereco: z.string().optional(),
  telefone: z.string().optional()
});

export const criarMatriculaSchema = z.object({
  aluno_id: z.string().uuid(),
  plano_id: z.string().uuid(),
  vencimento: z.string() // Formato YYYY-MM-DD
});

export class AlunosController {

  // POST /alunos
  static async cadastrar(request: FastifyRequest, reply: FastifyReply) {
    const data = cadastrarAlunoSchema.parse(request.body);

    const cpfHash = generateCPFHash(data.cpf);

    // Verifica se já existe um aluno com este CPF
    const [existentes]: any = await request.server.mysql.query(
      'SELECT id FROM alunos WHERE cpf_hash = ?',
      [cpfHash]
    );

    if (existentes.length > 0) {
      return reply.status(409).send({ message: 'Já existe um aluno cadastrado com este CPF.' });
    }

    const id = crypto.randomUUID();
    const cpfCript = encryptCPF(data.cpf);
    const consentimentoLgpdEm = new Date();

    await request.server.mysql.query(
      `INSERT INTO alunos 
        (id, nome, cpf_cript, cpf_hash, foto_cript, intelbras_user_id, consentimento_lgpd_em, data_nascimento, endereco, telefone) 
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        id,
        data.nome,
        cpfCript,
        cpfHash,
        data.foto_cript || null,
        data.intelbras_user_id || null,
        consentimentoLgpdEm,
        data.data_nascimento || null,
        data.endereco || null,
        data.telefone || null
      ]
    );

    return reply.status(201).send({
      id,
      nome: data.nome,
      message: 'Aluno cadastrado com sucesso.'
    });
  }

  // POST /matriculas
  static async criarMatricula(request: FastifyRequest, reply: FastifyReply) {
    const { aluno_id, plano_id, vencimento } = criarMatriculaSchema.parse(request.body);

    const id = crypto.randomUUID();

    await request.server.mysql.query(
      'INSERT INTO matriculas (id, aluno_id, plano_id, status, vencimento) VALUES (?, ?, ?, ?, ?)',
      [id, aluno_id, plano_id, 'ATIVO', vencimento]
    );

    return reply.status(201).send({
      id,
      aluno_id,
      plano_id,
      vencimento,
      status: 'ATIVO',
      message: 'Matrícula criada com sucesso.'
    });
  }

  // GET /alunos?busca=...
  static async listar(request: FastifyRequest, reply: FastifyReply) {
    const { busca } = request.query as { busca?: string };

    let query = `
      SELECT a.id, a.nome, a.cpf_cript, a.intelbras_user_id, a.ativo, 
             m.status as status_matricula, m.vencimento
      FROM alunos a
      LEFT JOIN matriculas m ON a.id = m.aluno_id
    `;
    const params: any[] = [];

    if (busca) {
      // Se for um CPF digitado na busca, busca pelo hash
      const cleanCPF = busca.replace(/\D/g, '');
      if (cleanCPF.length === 11) {
        query += ' WHERE a.cpf_hash = ?';
        params.push(generateCPFHash(cleanCPF));
      } else {
        query += ' WHERE a.nome LIKE ?';
        params.push(`%${busca}%`);
      }
    }

    query += ' ORDER BY a.nome ASC LIMIT 50';

    const [rows]: any = await request.server.mysql.query(query, params);

    // Descriptografa o CPF apenas para a resposta do operador logado
    const resultado = rows.map((aluno: any) => ({
      ...aluno,
      cpf: decryptCPF(aluno.cpf_cript),
      cpf_cript: undefined // Não expõe a string cifrada bruta
    }));

    return reply.send(resultado);
  }
}