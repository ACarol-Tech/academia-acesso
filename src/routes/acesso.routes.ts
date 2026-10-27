import { FastifyInstance } from 'fastify';
import { AcessoController } from '../controllers/acesso.controller';

export async function acessoRoutes(app: FastifyInstance) {
  // Webhook da Catraca (sem necessidade de JWT para leitura rápida)
  app.post('/acesso/validar', AcessoController.validar);

  // Liberação manual pelo painel (Requer login do operador)
  app.post('/acesso/liberar-manual', {
    onRequest: [async (request, reply) => {
      try {
        await request.jwtVerify();
      } catch (err) {
        reply.status(401).send({ message: 'Não autorizado.' });
      }
    }]
  }, AcessoController.liberarManual);
}
