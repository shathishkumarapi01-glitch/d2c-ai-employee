FROM node:20-alpine

WORKDIR /app

# Accept build arg for API URL (needed at build time for NEXT_PUBLIC_*)
ARG NEXT_PUBLIC_API_URL=http://localhost:3005
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# Next.js inlines NEXT_PUBLIC_* env vars at build time
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
