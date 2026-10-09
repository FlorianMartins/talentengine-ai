# Deployment

## Under a sub-path behind Caddy (the public instance)

The public instance runs at **https://hivey.be/talentengine/** (sandbox: `/talentengine/essai`, recruiter
landing page: `/talentengine/recruteurs`). The front-end is built with a path prefix and Caddy strips it:

```yaml
# docker-compose.yml (outside the repository, next to its .env)
services:
  app:
    build: { context: /path/to/talentengine-ai, args: { VITE_BASE: /talentengine/ } }
    env_file: .env
    ports: ["127.0.0.1:8010:8000"]          # never exposed directly
    volumes: [talentengine-data:/data]
    security_opt: ["no-new-privileges:true"]
    deploy: { resources: { limits: { cpus: "2", memory: 2g } } }
volumes: { talentengine-data: {} }
```

```caddy
hivey.be {
	redir /talentengine /talentengine/ 308
	handle_path /talentengine/* {
		reverse_proxy 127.0.0.1:8010
	}
	# ...other handles
}
```

`.env` (permissions 600):

| Variable | Value | Why |
|---|---|---|
| `TE_VAULT_KEY`, `TE_LEDGER_SEAL_KEY` | `talentengine keygen` | identities and the audit seal survive restarts |
| `TE_API_KEY` | a long random string | the recruiter side is private; the sandbox (`/api/try`) stays public |
| `TE_TRUST_PROXY` | `true` | rate limits use the visitor's address from `X-Forwarded-For` set by Caddy |
| `TE_CORS_ORIGINS` | `["https://hivey.be"]` | |
| `TE_SANDBOX_MATCHES_PER_HOUR` / `..._OFFERS_...` | `12` / `40` | per-IP limits of the public sandbox |

## Security notes for the public sandbox

* **Tests in progress survive a restart**: sandbox test sessions (technical tests and legacy verification tests) are
  kept encrypted with the vault key in the database and deleted when they expire (3 hours at most), so a
  deployment no longer breaks someone's test. The CV analysis below is still never stored.
* **Nothing is stored**: each analysis runs in a throw-away engine (in-memory database, temporary
  directory removed at the end). Uploaded files never reach the persistent store or the audit ledger.
* **SSRF**: links (job offers, portfolio pages) are fetched only over http(s), default ports, to publicly
  routable addresses, re-checked at every redirect, with size and time limits. A DNS answer could still
  change between the check and the connection (rebinding); keep the container on a network where it
  cannot reach internal services, and do not run other unauthenticated services on the host's
  bridge-facing interfaces.
* **GitHub**: repository trees are read with `git` (partial clone, names only) so the 60-requests-per-hour
  API quota is only used to list a profile's repositories; set `TE_GITHUB_TOKEN` (a token with no scopes,
  public read only) to raise it.
* **Abuse**: per-IP hourly limits, at most `TE_SANDBOX_CONCURRENCY` (2) analyses at a time, 8 MB per file,
  3 documents, 5 repositories, 3 portfolio links.
