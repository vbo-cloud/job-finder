# job-finder

A portfolio project built during my career transition from Unity/game development to Azure cloud and AI engineering.

## What I'm building

A multi-agent AI pipeline that automates job hunting:
- Fetches job offers from external sources on a daily schedule
- Embeds CVs and offers into a vector space for semantic matching
- Sends personalized match notifications by email
- Runs a cleanup agent on a timer to remove stale data

## Infrastructure

Two-layer pattern per environment:

- **Landing zone** (`lz_dev`, `lz_prod`) — foundation layer: VNet, subnets, resource groups, RBAC, policies. Deployed first, managed by `sp-jf-platform`.
- **Application** (`dev`, `prod`) — app layer: storage, PostgreSQL, Service Bus, Container Apps, OpenAI, Key Vault. Managed by `sp-jf-github`.

## Technologies in use

- **Cloud**: Azure
- **IaC**: Terraform (azurerm ~> 4.x)
- **CI/CD**: GitHub Actions with OIDC — no stored credentials
- **Secrets**: Azure Key Vault
- **Networking**: Private endpoints, private DNS zones, VNet injection
- **Observability**: Application Insights + Log Analytics

## Technologies planned

- **Compute**: Azure Container Apps (timer and queue-triggered jobs)
- **Database**: Azure Database for PostgreSQL Flexible Server
- **Messaging**: Azure Service Bus (start-matching, match-ready, cv-analysis, match-analysis queues)
- **AI**: Claude API (Anthropic) for agent reasoning and matching logic
- **Target**: AKS (Kubernetes) post-MVP
