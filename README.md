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
# Terminal 1 - Start first instance (random port)
cd voiceagent/app/backend
python app.py

# Terminal 2 - Start second instance (random port)
cd voiceagent/app/backend
python app.py

You can now connect to any of these instances, and your session data will be shared across them through Redis.

## Load Balancing

For production environments, consider placing a L7 load balancer in front of your application instance (e.g. Application Gateway)

## Architecture

The application uses a multi-tier architecture:

1. **Frontend**: React-based UI with WebSocket communication
2. **Backend**: Python/aiohttp WebSocket server with Azure OpenAI integration
3. **Session Store**: Redis for distributed session management
4. **External API**: Microsoft Careers API for job data

When deployed with multiple instances, each instance connects to the same Redis instance, allowing users to be served by any available backend server without losing session state.