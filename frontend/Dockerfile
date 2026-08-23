# Image frontend orientée développement (serveur Vite avec HMR).
# La production est construite séparément par la plateforme de déploiement
# (`npm ci && npm run build`, spec 09 §11).
FROM node:22-alpine

ENV NODE_ENV=development

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
