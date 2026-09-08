FROM node:22-bookworm-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm ci

COPY requirements.txt ./
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .
RUN npm run build

ENV NODE_ENV=production
EXPOSE 3100
VOLUME ["/app/data"]

CMD ["npm", "run", "start", "--", "-p", "3100"]
