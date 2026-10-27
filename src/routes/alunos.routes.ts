import { FastifyInstance } from 'fastify';
import { AlunosController } from '../controllers/alunos.controller';

export async function alunosRoutes(app: FastifyInstance) {
  // Exige autenticação JWT para acessar os endpoints de alunos
  app.addHook('onRequest', async (request, reply) => {
    try {
      await request.jwtVerify();
    } catch (err) {
      reply.status(401).send({ message: 'Não autorizado.' });
    }
  });

  app.post('/alunos', AlunosController.cadastrar);
  app.post('/matriculas', AlunosController.criarMatricula);
  app.get('/alunos', AlunosController.listar);
}
