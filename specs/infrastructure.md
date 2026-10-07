# Infrastructure

## Checked-in runtime

| Resource | Repository evidence | Required role |
| --- | --- | --- |
| Python backend container | Development `backend/Dockerfile`; production `backend/Dockerfile.prod`, `docker-compose.prod.yml` | FastAPI/Uvicorn on port 8000; production has no reload or published host port. |
| Frontend container | Development `frontend/Dockerfile`; production `frontend/Dockerfile.prod`, `nginx.prod.conf` | Vite development server on port 5173, or built static assets served by Nginx on production loopback port 8080. |
| Host AWS credential files | Development Compose bind mount `${HOME}/.aws:/root/.aws:ro` | Optional local/profile credentials; production uses the instance role or backend environment. |
| AWS account/region | `backend/app/core/aws_session.py`, `backend/app/config.py` | CloudWatch Logs, CloudTrail, optional STS AssumeRole. |
| Masking endpoint | `backend/app/core/masking_http_client.py` | Optional external PII masking, with local fallback. |
| Model endpoint(s) | `backend/app/services/llm/` | LiteLLM default or selected Gemini/OpenAI/Anthropic/Ollama. |
| Browser storage | `frontend/src/components/LogSummary/LogSummary.tsx` | Local completed-investigation history. |

The development Compose file publishes both service ports. The production Compose file publishes only frontend Nginx on host loopback and loads `backend/.env`; an instance role or backend environment supplies AWS credentials. `backend/.env.example` and `frontend/.env.example` enumerate setup values; actual `.env` values are excluded from this specification. See [configuration.md](configuration.md) and [iam_setup.md](iam_setup.md).

## External or absent infrastructure

No database, object store, queue, Redis cache, load balancer, DNS record, certificate, host HTTPS proxy file, Terraform/CloudFormation/CDK, Kubernetes chart, or CI deployment definition was found in the checkout. **Not currently applicable** to the checked-in runtime for database migrations and storage backups. The production Compose configuration supports local host and Docker-network callers; a remote ingress is neither required nor configured ([ASM-003](assumptions.md#asm-003)). AWS OAM links and centralized log delivery, if used, are configured outside this repository.

Infrastructure-as-code mapping: **Not currently applicable**; no IaC file is present. Any future infrastructure change should document resource ownership, IAM, inbound/outbound paths, secret delivery, and rollback in [deployment.md](deployment.md).
