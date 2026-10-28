import '@fastify/mysql';
import '@fastify/jwt';

declare module 'fastify' {
  interface FastifyInstance {
    mysql: any;
    jwt: any;
  }
  
  interface FastifyRequest {
    user: {
      sub: string;
      nome: string;
      papel: string;
    };
  }
}