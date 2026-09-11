# Build-only image: produces static files for nginx to serve, not a
# running service. Lets the server build the frontend without installing
# Node.js itself -- only Docker (already on the box) is needed. See
# deploy/README.md for the build + extract command.
FROM node:22-slim AS build

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# Vite bakes VITE_-prefixed vars into the build at this step, not at
# container runtime -- a different backend URL means rebuilding, not just
# restarting.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM scratch AS export
COPY --from=build /app/dist /dist
