FROM node:20-alpine

WORKDIR /uis

COPY uis/website/package.json uis/website/package-lock.json ./website/
RUN npm ci --prefix website

COPY uis/backoffice/package.json uis/backoffice/package-lock.json ./backoffice/
RUN npm ci --prefix backoffice

COPY assets /assets
COPY src /src
COPY uis/website ./website
COPY uis/backoffice ./backoffice
COPY uis/start.sh /uis/start.sh
RUN chmod +x /uis/start.sh

EXPOSE 3000 3001

CMD ["sh", "/uis/start.sh"]
