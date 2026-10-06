# Infrastructure

## Checked-in runtime

| Resource | Repository evidence | Required role |
| --- | --- | --- |
| Python backend container | `backend/Dockerfile`, `docker-compose.yml` | FastAPI/Uvicorn on port 8000, development `--reload`. |
| Node frontend container | `frontend/Dockerfile`, `docker-compose.yml` | Vite development server on port 5173, not a static production web server. |
| Host AWS credential files | Compose bind mount `${HOME}/.aws:/root/.aws:ro` | Optional local/profile credentials. |
| AWS account/region | `backend/app/core/aws_session.py`, `backend/app/config.py` | CloudWatch Logs, CloudTrail, optional STS AssumeRole. |
| Masking endpoint | `backend/app/core/masking_http_client.py` | Optional external PII masking, with local fallback. |
| Model endpoint(s) | `backend/app/services/llm/` | LiteLLM default or selected Gemini/OpenAI/Anthropic/Ollama. |
| Browser storage | `frontend/src/components/LogSummary/LogSummary.tsx` | Local completed-investigation history. |

The Compose file publishes both service ports and injects AWS environment credentials when exported. `backend/.env.example` and `frontend/.env.example` enumerate setup values; actual `.env` values are excluded from this specification. See [configuration.md](configuration.md) and [iam_setup.md](iam_setup.md).

## External or absent infrastructure

No database, object store, queue, Redis cache, load balancer, DNS record, certificate, production proxy file, Terraform/CloudFormation/CDK, Kubernetes chart, or CI deployment definition was found in the checkout. **Not currently applicable** to the checked-in runtime for database migrations and storage backups. The README describes an EC2 host and HTTPS reverse proxy, but those infrastructure resources and named deployment scripts are absent; their actual state is uncertain ([ASM-003](assumptions.md#asm-003)). AWS OAM links and centralized log delivery, if used, are configured outside this repository.

Infrastructure-as-code mapping: **Not currently applicable**; no IaC file is present. Any future infrastructure change should document resource ownership, IAM, inbound/outbound paths, secret delivery, and rollback in [deployment.md](deployment.md).
