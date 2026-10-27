import { FastifyInstance } from 'fastify';
import { AuthController } from '../controllers/auth.controller';

export async function authRoutes(app: FastifyInstance) {
  app.post('/auth/login', AuthController.login);
  app.post('/auth/esqueceu-senha', AuthController.esqueceuSenha);
  app.post('/auth/redefinir-senha', AuthController.redefinirSenha);
}
