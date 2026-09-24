# --- Stage 1: Build the Next.js app ---
    FROM node:22-alpine AS builder

    # Set working directory
    WORKDIR /app
    
    # Copy dependencies files
    COPY package.json package-lock.json* ./
    
    # Install dependencies
    RUN npm install
    
    # Copy the full source
    COPY . .
    
    # Build the app for production
    RUN npm run build
    
    # --- Stage 2: Run the built app with minimal image ---
    FROM node:18-alpine
    
    # Set working directory
    WORKDIR /app
    
    # Copy only required build output and runtime files
    COPY --from=builder /app/public ./public
    COPY --from=builder /app/.next ./.next
    COPY --from=builder /app/node_modules ./node_modules
    COPY --from=builder /app/package.json ./package.json
    COPY --from=builder /app/next.config.mjs ./next.config.mjs
    
    # Set environment variable for production
    ENV NODE_ENV=production
    
    # Expose the production port (default is 3000, change if needed)
    EXPOSE 3000
    
    # Start the app
    CMD ["npm", "start"]
