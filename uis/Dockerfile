FROM node:20-alpine

WORKDIR /uis

COPY website/package.json website/package-lock.json ./website/
RUN npm ci --prefix website

COPY backoffice/package.json backoffice/package-lock.json ./backoffice/
RUN npm ci --prefix backoffice

COPY website ./website
COPY backoffice ./backoffice
COPY start.sh /uis/start.sh
RUN chmod +x /uis/start.sh

EXPOSE 3000 3001

CMD ["sh", "/uis/start.sh"]
