# Build context: JobFinder/frontend/
# docker build -t frontend .
FROM node:20-alpine

WORKDIR /app

# Install dependencies from the lockfile for reproducible builds.
COPY package.json package-lock.json ./
RUN npm ci

# Build the Next.js app. NEXT_PUBLIC_* vars are inlined at build time and must
# be provided as build args / env when building the production image.
COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
