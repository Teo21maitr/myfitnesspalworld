# Image frontend, en trois étages.
#
# `dev` sert au développement local (serveur Vite avec HMR) ; `production`
# construit le bundle et le sert avec nginx.
FROM node:22-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# -----------------------------------------------------------------------------
# Développement
# -----------------------------------------------------------------------------
FROM deps AS dev

ENV NODE_ENV=development

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# -----------------------------------------------------------------------------
# Construction du bundle
# -----------------------------------------------------------------------------
FROM deps AS build

# L'adresse de l'API est figée **dans le bundle** : elle se fournit ici et
# nulle part ailleurs. `vite.config.ts` refuse de construire sans elle, parce
# qu'un bundle qui appelle localhost se construit sans erreur et ne se répare
# qu'en reconstruisant.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY . .
RUN npm run build

# -----------------------------------------------------------------------------
# Production : nginx sert des fichiers statiques
# -----------------------------------------------------------------------------
FROM nginx:1.29-alpine AS production

# Gabarit plutôt que configuration figée : nginx substitue les variables au
# démarrage, et la plateforme impose son `$PORT`.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

ENV PORT=8080

EXPOSE 8080
