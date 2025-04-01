# Job Search Agent with Redis Scalability

This application provides a conversational job search interface using Azure OpenAI services with Redis-powered distributed session management.

## Prerequisites

- Docker
- Python 3.8+
- Node.js 14+ (for frontend)
- Azure OpenAI API access

## Redis Setup

The application uses Redis for distributed session storage, allowing multiple instances to share state. To start a Redis container locally:

```bash
# Start Redis container on default port (6379) with persistence
docker run --name redis-jobsearch \
  -p 6379:6379 \
  -v redis-data:/data \
  -d redis:alpine \
  redis-server --appendonly yes

# Verify Redis is running
docker ps | grep redis-jobsearch
```

### Redis Configuration Options

You can configure the Redis connection using environment variables:

- `REDIS_URL`: Redis connection string (default: `redis://localhost:6379/0`)
- `SESSION_EXPIRY_SECONDS`: Session timeout in seconds (default: `86400` - 24 hours)
- `SESSION_CLEANUP_INTERVAL_SECONDS`: Cleanup interval in seconds (default: `3600` - 1 hour)

## Application Setup

1. Install dependencies

```bash
cd voiceagent/app
pip install -r requirements.txt
```

2. Configure environment variables (create a `.env` file in the `voiceagent/app/backend` directory):

```
AZURE_OPENAI_ENDPOINT=https://your-azure-openai-endpoint.com/
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_REALTIME_DEPLOYMENT=your_deployment_name
REDIS_URL=redis://localhost:6379/0
```

## Running Multiple Instances

For horizontal scaling, you can run multiple instances of the application that share state via Redis:

```bash
# Terminal 1 - Start first instance (default port)
cd voiceagent/app/backend
python app.py

# Terminal 2 - Start second instance (custom port)
cd voiceagent/app/backend
PORT=8767 python app.py

# Terminal 3 - Start third instance (custom port)
cd voiceagent/app/backend
PORT=8768 python app.py
```

You can now connect to any of these instances, and your session data will be shared across them through Redis.

## Load Balancing (Optional)

For production environments, consider placing a load balancer in front of your application instances:

```bash
# Example with Nginx in Docker (basic configuration)
docker run --name jobsearch-lb \
  -p 80:80 \
  -v /path/to/nginx.conf:/etc/nginx/nginx.conf:ro \
  -d nginx:alpine
```

Example `nginx.conf` for load balancing:

```nginx
http {
    upstream jobsearch {
        server localhost:8766;
        server localhost:8767;
        server localhost:8768;
    }
    
    server {
        listen 80;
        
        location / {
            proxy_pass http://jobsearch;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
```

## Troubleshooting

### Redis Connection Issues

If the application fails to connect to Redis:

1. Check if Redis container is running:
   ```bash
   docker ps | grep redis-jobsearch
   ```

2. If stopped, restart it:
   ```bash
   docker start redis-jobsearch
   ```

3. Test Redis connection:
   ```bash
   docker exec -it redis-jobsearch redis-cli ping
   ```
   Should return "PONG"

### Viewing Redis Data

To inspect sessions stored in Redis:

```bash
# Connect to Redis CLI
docker exec -it redis-jobsearch redis-cli

# List all job search session keys
KEYS jobsearch:session:*

# Get info on active sessions
SMEMBERS jobsearch:active_sessions

# Get details for a specific session (returns binary pickle data)
GET jobsearch:session:[session-id]
```

## Architecture

The application uses a multi-tier architecture:

1. **Frontend**: React-based UI with WebSocket communication
2. **Backend**: Python/aiohttp WebSocket server with Azure OpenAI integration
3. **Session Store**: Redis for distributed session management
4. **External API**: Microsoft Careers API for job data

When deployed with multiple instances, each instance connects to the same Redis instance, allowing users to be served by any available backend server without losing session state.