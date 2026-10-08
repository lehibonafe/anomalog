# Anomalog

**AI-Powered AWS Log Intelligence & Investigation Workspace**

Anomalog is a web-based observability tool for investigating **Amazon CloudWatch Logs** and **AWS CloudTrail events**. It combines log search, real-time streaming, analytics, filtering, and AI-assisted investigation to help engineers troubleshoot incidents and identify anomalies faster.

AI-generated findings include citations that link conclusions directly to the supporting log events, while credentials, secrets, and personally identifiable information (PII) are masked before logs reach the browser or an LLM.

---

## Features

- Search and analyze Amazon CloudWatch Logs
- Investigate AWS CloudTrail activity
- Stream logs in real time using CloudWatch Live Tail
- AI-assisted log analysis and incident investigation
- Evidence-based AI responses with log-line citations
- Automatic PII, credential, and secret masking
- HTTP status-code analytics and filtering
- Multi-log-group investigation
- Multiple LLM provider support
- AWS IAM credential-chain support
- Dockerized development and production deployment
- WebSocket-based real-time log streaming

---

## Technology Stack

| Category | Technologies |
|----------|--------------|
| Cloud Platform | Amazon Web Services (AWS) |
| Log Sources | Amazon CloudWatch Logs, AWS CloudTrail |
| Backend | Python, FastAPI, Uvicorn |
| AWS Integration | Boto3 |
| Frontend | React, TypeScript, Vite |
| State Management | Zustand |
| Data Fetching | TanStack React Query, Axios |
| Real-Time Streaming | WebSockets, CloudWatch Live Tail |
| AI / LLM | LiteLLM, OpenAI, Gemini, Anthropic, Ollama |
| Security | AWS IAM, API Key Authentication, PII & Secret Masking |
| Containerization | Docker, Docker Compose |
| Testing | Pytest, Vitest |
| Deployment | Amazon EC2, Docker Compose |

---

## Architecture

```text
                         ┌──────────────────────┐
                         │       Engineer       │
                         │      Web Browser     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   React + TypeScript │
                         │       Frontend       │
                         └──────────┬───────────┘
                                    │
                         HTTP API / WebSocket
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       FastAPI        │
                         │       Backend        │
                         └───────┬──────┬───────┘
                                 │      │
                  ┌──────────────┘      └───────────────┐
                  ▼                                     ▼
        ┌──────────────────┐                  ┌──────────────────┐
        │    AWS Boto3     │                  │   PII / Secret   │
        │   Integration    │                  │     Masking      │
        └────────┬─────────┘                  └────────┬─────────┘
                 │                                     │
         ┌───────┴─────────┐                           ▼
         ▼                 ▼                 ┌──────────────────┐
┌─────────────────┐ ┌─────────────────┐      │   LLM Providers  │
│ CloudWatch Logs │ │   CloudTrail    │      │                  │
│ + Live Tail     │ │     Events      │      │ LiteLLM / OpenAI │
└─────────────────┘ └─────────────────┘      │ Gemini / Claude  │
                                              │ Ollama           │
                                              └──────────────────┘
```

The browser does not connect directly to AWS. The FastAPI backend owns AWS communication, retrieves the requested events, masks sensitive information, and returns sanitized data to the frontend.

For CloudWatch Live Tail, the backend maintains the AWS stream and forwards masked events to the browser through WebSockets.

---

## How It Works

1. The user selects CloudWatch log groups or CloudTrail lookup criteria.
2. The frontend sends the investigation request to the FastAPI backend.
3. The backend retrieves events from AWS using Boto3.
4. Sensitive information is masked before further processing.
5. Logs are displayed in the investigation workspace.
6. The user can filter and analyze the visible events.
7. Selected log evidence can be sent to an LLM for investigation.
8. AI findings reference the log lines supporting each conclusion.

Example investigation questions:

```text
Who stopped the EC2 instance?
```

```text
Which service generated the most 5xx errors?
```

```text
What caused the authentication failures?
```

```text
Summarize the errors that occurred during this period.
```

---

## CloudWatch Live Tail

Anomalog supports real-time CloudWatch log investigation through **CloudWatch Live Tail**.

Users can:

- Stream events from multiple CloudWatch log groups
- Apply CloudWatch filter patterns
- Pause and resume the browser display
- Monitor HTTP status counts in real time
- Stop active streaming sessions
- View estimated Live Tail usage costs
- Automatically terminate inactive sessions

The browser communicates with the FastAPI backend through a WebSocket connection.

```text
CloudWatch Live Tail
        │
        ▼
FastAPI Backend
        │
        ├── Mask sensitive data
        │
        ▼
WebSocket
        │
        ▼
React Log Viewer
```

AWS credentials remain on the backend and are never sent to the browser.

---

## AI Log Investigator

Anomalog can analyze the currently selected log evidence using different LLM providers.

Supported providers include:

| Provider | Support |
|----------|---------|
| LiteLLM | Default server-side provider |
| OpenAI | Supported |
| Google Gemini | Supported |
| Anthropic | Supported |
| Ollama | Local model support |

Rather than sending every available log event to the model, Anomalog reduces the evidence set before analysis.

The backend prioritizes events such as:

- Errors
- Exceptions
- Stack traces
- Authentication failures
- HTTP `401`
- HTTP `403`
- HTTP `408`
- HTTP `429`
- HTTP `5xx`

This helps reduce token usage, latency, and LLM cost while preserving important troubleshooting evidence.

---

## Security

Security is an important part of the application's architecture.

### Sensitive Data Masking

Logs are processed for sensitive information before they reach an LLM or the frontend.

Masking covers data such as:

- Credentials
- Secrets
- API keys
- Personally identifiable information (PII)

An external masking service can be configured, with local regex-based masking available as a fallback.

### AWS Authentication

The backend uses Boto3's AWS credential chain.

Supported authentication methods include:

```text
Environment Variables
        ↓
AWS Profile
        ↓
EC2 / Task IAM Role
```

For AWS deployments, using an **IAM role attached to the compute resource** is preferred over storing long-lived AWS credentials.

### API Authentication

Production deployments can require an application API key to prevent unauthorized access to backend endpoints.

---

## Project Structure

```text
anomalog/
│
├── backend/
│   ├── app/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── Dockerfile.prod
│
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── Dockerfile
│   └── Dockerfile.prod
│
├── specs/
│   └── README.md
│
├── api-reference.md
├── api-reference-pii-masking.md
├── docker-compose.yml
├── docker-compose.prod.yml
├── deploy.sh
├── dev.sh
└── README.md
```

---

## Run Locally

### Clone the Repository

```bash
git clone https://github.com/lehibonafe/anomalog.git
cd anomalog
```

---

## Backend Setup

Create a Python virtual environment:

```bash
cd backend

python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Create the environment configuration:

```bash
cp .env.example .env
```

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

The backend will run on:

```text
http://localhost:8000
```

---

## Frontend Setup

From another terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open:

```text
http://localhost:5173
```

---

## Run with the Development Script

The frontend and backend can also be started together from the repository root:

```bash
./dev.sh
```

---

## Run with Docker

Create the required environment files first:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Then start the application:

```bash
docker compose up --build
```

Open:

```text
http://localhost:5173
```

The development Docker configuration supports hot reload for both frontend and backend development.

---

## AWS Credentials

When running locally, AWS credentials can be provided through environment variables:

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_SESSION_TOKEN="your-session-token"
```

Or through an AWS CLI profile stored under:

```text
~/.aws/credentials
```

When deployed to AWS, an IAM role attached to the EC2 instance or AWS compute resource can be used instead.

Verify your AWS identity with:

```bash
aws sts get-caller-identity
```

---

## Production Deployment

Anomalog includes a production Docker Compose configuration:

```text
docker-compose.prod.yml
```

Deploy using:

```bash
./deploy.sh
```

The production configuration includes:

- Separate production Docker images
- Backend health checks
- API-key enforcement
- Service restart policies
- Frontend dependency on backend health
- Localhost-bound application exposure

Production environment secrets should be stored in:

```text
backend/.env
```

and must **never be committed to Git**.

---

## Testing

### Backend

Run backend tests with:

```bash
cd backend
pytest
```

### Frontend

Run frontend tests with:

```bash
cd frontend
npm test
```

Run linting with:

```bash
npm run lint
```

---

## Documentation

Additional technical documentation is available in the repository.

| Document | Purpose |
|----------|---------|
| [`specs/`](specs/) | Application behavior and feature specifications |
| [`api-reference.md`](api-reference.md) | HTTP and WebSocket API documentation |
| [`api-reference-pii-masking.md`](api-reference-pii-masking.md) | PII masking API documentation |
| `Anomalog Technical and Operations Guide` | Technical and operational procedures |

---

## Engineering Concepts Demonstrated

This project demonstrates hands-on experience with:

- AWS observability and logging
- Amazon CloudWatch Logs
- AWS CloudTrail
- CloudWatch Live Tail
- AWS SDK integration using Boto3
- Python API development with FastAPI
- React and TypeScript frontend development
- WebSocket-based real-time systems
- AI-assisted incident investigation
- LLM context and token optimization
- Sensitive-data masking
- IAM-based AWS authentication
- Docker containerization
- Production health checks
- Full-stack application deployment
- Incident troubleshooting workflows

---

## Use Cases

Anomalog can support workflows such as:

- Production incident investigation
- Application error analysis
- AWS activity investigation
- CloudTrail audit analysis
- Authentication failure investigation
- HTTP error analysis
- Real-time log monitoring
- Root cause analysis
- AI-assisted troubleshooting

---

## Future Improvements

Potential improvements include:

- Cross-account AWS log investigation
- Additional AWS observability sources
- Saved investigations and searches
- Alert-to-investigation workflows
- Automated anomaly detection
- Incident management integrations
- Metrics and traces correlation
- Role-based access control
- Deployment through CI/CD
- Infrastructure as Code

---

## Repository

[GitHub – lehibonafe/anomalog](https://github.com/lehibonafe/anomalog)

---

## Disclaimer

Anomalog is designed as an investigation and observability tool. AI-generated findings should be treated as supporting analysis and verified against the underlying log evidence before operational decisions are made.
