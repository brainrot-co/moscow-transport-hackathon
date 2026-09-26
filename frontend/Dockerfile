FROM node:22-alpine AS build

WORKDIR /app
ARG VITE_DEMO_USERNAME
ARG VITE_DEMO_PASSWORD
ENV VITE_DEMO_USERNAME=$VITE_DEMO_USERNAME
ENV VITE_DEMO_PASSWORD=$VITE_DEMO_PASSWORD
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
