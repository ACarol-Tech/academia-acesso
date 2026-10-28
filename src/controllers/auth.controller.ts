import { FastifyRequest, FastifyReply } from 'fastify';
import { z } from 'zod';
import crypto from 'node:crypto';
import { comparePassword, hashPassword, generatePasswordResetToken, hashToken } from '../lib/hash';

export const loginSchema = z.object({
  email: z.string().email('E-mail inválido'),
  senha: z.string().min(6, 'Senha deve ter no mínimo 6 caracteres')
});

export const esqueceuSenhaSchema = z.object({
  email: z.string().email('E-mail inválido')
});

export const redefinirSenhaSchema = z.object({
  codigo: z.string().length(6, 'Código deve ter 6 dígitos'),
  novaSenha: z.string().min(6, 'Nova senha deve ter no mínimo 6 caracteres')
});

const MAX_TENTATIVAS = 5;
const TEMPO_BLOQUEIO_MINUTOS = 15;

export class AuthController {
  
  // POST /auth/login
  static async login(request: FastifyRequest, reply: FastifyReply) {
    const { email, senha } = loginSchema.parse(request.body);

    const [operadores]: any = await request.server.mysql.query(
      'SELECT id, nome, email, senha_hash, papel, tentativas, bloqueado_ate FROM operadores WHERE email = ?',
      [email]
    );

    const operador = operadores[0];
    if (!operador) {
      return reply.status(401).send({ message: 'Credenciais inválidas.' });
    }

    const agora = new Date();
    if (operador.bloqueado_ate && new Date(operador.bloqueado_ate) > agora) {
      const minutosRestantes = Math.ceil(
        (new Date(operador.bloqueado_ate).getTime() - agora.getTime()) / (1000 * 60)
      );
      return reply.status(429).send({
        message: `Conta temporariamente bloqueada. Tente novamente em ${minutosRestantes} minuto(s).`
      });
    }

    const senhaValida = await comparePassword(senha, operador.senha_hash);

    if (!senhaValida) {
      const novasTentativas = operador.tentativas + 1;
      let bloqueadoAte = null;

      if (novasTentativas >= MAX_TENTATIVAS) {
        bloqueadoAte = new Date(agora.getTime() + TEMPO_BLOQUEIO_MINUTOS * 60 * 1000);
      }

      await request.server.mysql.query(
        'UPDATE operadores SET tentativas = ?, bloqueado_ate = ? WHERE id = ?',
        [novasTentativas, bloqueadoAte, operador.id]
      );

      return reply.status(401).send({ message: 'Credenciais inválidas.' });
    }

    // Sucesso: zera tentativas
    await request.server.mysql.query(
      'UPDATE operadores SET tentativas = 0, bloqueado_ate = NULL WHERE id = ?',
      [operador.id]
    );

    const token = request.server.jwt.sign(
      { sub: operador.id, nome: operador.nome, papel: operador.papel },
      { expiresIn: '8h' }
    );

    return reply.send({
      token,
      operador: {
        id: operador.id,
        nome: operador.nome,
        email: operador.email,
        papel: operador.papel
      }
    });
  }

  // POST /auth/esqueceu-senha
  static async esqueceuSenha(request: FastifyRequest, reply: FastifyReply) {
    const { email } = esqueceuSenhaSchema.parse(request.body);

    const [operadores]: any = await request.server.mysql.query(
      'SELECT id FROM operadores WHERE email = ?',
      [email]
    );

    const operador = operadores[0];
    if (!operador) {
      return reply.send({ message: 'Se o e-mail estiver cadastrado, um código foi enviado.' });
    }

    const { code, hashCode } = generatePasswordResetToken();
    const id = crypto.randomUUID();
    const expiraEm = new Date(Date.now() + 15 * 60 * 1000);

    await request.server.mysql.query(
      'INSERT INTO reset_senha (id, operador_id, codigo_hash, expira_em) VALUES (?, ?, ?, ?)',
      [id, operador.id, hashCode, expiraEm]
    );

    // TODO: Enviar o código por e-mail no ambiente de produção
    console.log(`[DEV ONLY] Código de redefinição para ${email}: ${code}`);

    return reply.send({ message: 'Se o e-mail estiver cadastrado, um código foi enviado.' });
  }

  // POST /auth/redefinir-senha
  static async redefinirSenha(request: FastifyRequest, reply: FastifyReply) {
    const { codigo, novaSenha } = redefinirSenhaSchema.parse(request.body);
    const codigoHash = hashToken(codigo);

    const [resets]: any = await request.server.mysql.query(
      `SELECT id, operador_id FROM reset_senha 
       WHERE codigo_hash = ? AND usado = 0 AND expira_em > NOW() 
       ORDER BY expira_em DESC LIMIT 1`,
      [codigoHash]
    );

    const resetRegister = resets[0];
    if (!resetRegister) {
      return reply.status(400).send({ message: 'Código inválido ou expirado.' });
    }

    const novaSenhaHash = await hashPassword(novaSenha);

    await request.server.mysql.query(
      'UPDATE operadores SET senha_hash = ?, tentativas = 0, bloqueado_ate = NULL WHERE id = ?',
      [novaSenhaHash, resetRegister.operador_id]
    );

    await request.server.mysql.query(
      'UPDATE reset_senha SET usado = 1 WHERE id = ?',
      [resetRegister.id]
    );

    return reply.send({ message: 'Senha redefinida com sucesso.' });
  }
}