import Fastify from 'fastify';
import fastifyJwt from '@fastify/jwt';
import fastifyMysql from '@fastify/mysql';

import { authRoutes } from './routes/auth.routes';
import { alunosRoutes } from './routes/alunos.routes';
import { acessoRoutes } from './routes/acesso.routes';

const app = Fastify({ logger: true });

app.register(fastifyMysql, {
  promise: true,
  connectionString: process.env.DATABASE_URL || 'mysql://root:@localhost:3306/academia'
});

app.register(fastifyJwt, {
  secret: process.env.JWT_SECRET || 'supersecret_jwt_key'
});

app.register(authRoutes);
app.register(alunosRoutes);
app.register(acessoRoutes);

const start = async () => {
  try {
    const port = Number(process.env.PORT) || 3333;
    await app.listen({ port, host: '0.0.0.0' });
    console.log('Servidor rodando na porta ' + port);
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
};

start();
