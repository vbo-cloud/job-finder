# Build context: JobFinder/frontend/
# docker build -t frontend .
FROM node:20-alpine

WORKDIR /app

# Install dependencies from the lockfile for reproducible builds. public/ must exist
# before `npm ci` runs: its postinstall script copies the pdf.js worker into it, and
# at this point in the build only the manifest files below have been copied in.
COPY package.json package-lock.json ./
RUN mkdir -p public && npm ci

# Build the Next.js app. NEXT_PUBLIC_* vars are inlined at build time and must
# be provided as build args / env when building the production image.
COPY . .

ARG NEXT_PUBLIC_ENTRA_CLIENT_ID
ARG NEXT_PUBLIC_ENTRA_AUTHORITY
ARG NEXT_PUBLIC_ENTRA_KNOWN_AUTHORITY
ARG NEXT_PUBLIC_ENTRA_API_SCOPE
ARG NEXT_PUBLIC_REDIRECT_URI
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_POSTHOG_KEY
ARG NEXT_PUBLIC_POSTHOG_HOST
ENV NEXT_PUBLIC_ENTRA_CLIENT_ID=$NEXT_PUBLIC_ENTRA_CLIENT_ID
ENV NEXT_PUBLIC_ENTRA_AUTHORITY=$NEXT_PUBLIC_ENTRA_AUTHORITY
ENV NEXT_PUBLIC_ENTRA_KNOWN_AUTHORITY=$NEXT_PUBLIC_ENTRA_KNOWN_AUTHORITY
ENV NEXT_PUBLIC_ENTRA_API_SCOPE=$NEXT_PUBLIC_ENTRA_API_SCOPE
ENV NEXT_PUBLIC_REDIRECT_URI=$NEXT_PUBLIC_REDIRECT_URI
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_POSTHOG_KEY=$NEXT_PUBLIC_POSTHOG_KEY
ENV NEXT_PUBLIC_POSTHOG_HOST=$NEXT_PUBLIC_POSTHOG_HOST

RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
