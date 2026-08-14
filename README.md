# HiveContext: Organization-Level Agentic Context System

HiveContext is a shared memory system ("Collective Brain") for development teams using AI agents. 
It leverages **CockroachDB** for resilient, globally distributed vector memory and **AWS Lambda** for cost-efficient serverless compute.

## Setup Instructions

### 1. Prerequisites
- **CockroachDB Cluster**: You need a running CockroachDB cluster (Serverless or Dedicated). It must be version 24.1+ for `pgvector` support.
- **Python 3.12+**
- **AWS SAM CLI**: Installed and configured with your AWS profile (e.g. `sam --version`).
- **Google AI Studio API Key** (or an OpenAI/Bedrock compatible API key).

### 2. Environment Setup

Create a `.env` file (or just export the variables) with the following:
```bash
# CockroachDB connection string. Replace with your actual credentials.
export DATABASE_URL="postgresql://user:password@host:26257/defaultdb?sslmode=verify-full"
export GEMINI_API_KEY="your_api_key_here"
```

### 3. Initialize Database Schema

Before running the server, you must create the core tables and enable the vector extension on your CockroachDB cluster. We've provided helper scripts for this:

Using Python:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install psycopg2-binary
python run_schema.py
```
*(Alternatively, you can run `node run_schema.js` if you prefer Node.js, or manually execute `schema.sql` against your cluster).*

### 4. Deploy to AWS (Serverless MCP & Background Purge)

This repository includes an AWS SAM configuration (`template.yaml`) to deploy the MCP server as a globally accessible **AWS Lambda Function URL (SSE)**.

1. Build the Lambda functions:
   ```bash
   sam build
   ```
2. Deploy the stack. You can run `sam deploy --guided` to configure your overrides, or pass them inline. 
   **Note**: The deployment requires three critical overrides: `DatabaseUrl`, `GeminiApiKey`, and `McpSecretToken`.
   ```bash
   sam deploy \
     --stack-name hivecontext-server \
     --capabilities CAPABILITY_IAM \
     --parameter-overrides "\
       DatabaseUrl=\"postgresql://user:password@host:26257/defaultdb?sslmode=require\" \
       GeminiApiKey=\"your_gemini_key\" \
       McpSecretToken=\"your_secure_bearer_token_here\""
   ```

*Once deployed, the SAM CLI will output your `McpServerUrl`. Use this URL in your Dashboard and local agent configurations.*

### 5. Running the MCP Server Locally (Development)

To test the MCP tools locally using the Inspector or your IDE:

```bash
pip install -r requirements.txt
# Run via Inspector
npx @modelcontextprotocol/inspector uv run mcp_server/app.py
```

## Connecting Remote Agents (AWS Deployment)

Once deployed to AWS, your agentic systems can connect to the collective brain over the internet using the **SSE (Server-Sent Events)** transport. 

Because the API is protected, you must pass the `Authorization` header with the `McpSecretToken` you specified during deployment.

### Example: Antigravity CLI Configuration (`mcp_config.json`)
```json
"hivecontext": {
    "serverUrl": "https://<your-lambda-id>.lambda-url.region.on.aws/",
    "headers": {
        "Authorization": "Bearer <your_secure_bearer_token_here>",
        "X-HiveContext-Tenant": "tenant_space_name_here"
    }
}
```

## Available Tools (for the AI Agent)
- `remember_convention(topic, content)`: Saves a new team rule.
- `search_context(query)`: Performs a vector similarity search in CockroachDB to retrieve relevant ADRs or style rules.
- `log_post_mortem(issue, resolution)`: Saves incident learnings.
- `save_adr(title, decision, context, consequences)`: Saves Architectural Decision Records.
- `save_infrastructure_context(component, configuration, dependencies)`: Saves infrastructure specs.
