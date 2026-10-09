"""Scenario 6 — Terraform for a reports bucket shared with partners (CIS AWS Foundations, least privilege)."""

from __future__ import annotations

import re

from .base import Check, Fault, Files, Scenario

_TF = "infra/main.tf"
_TF_VARS = "infra/variables.tf"
_TF_TESTS = "infra/tests/reports.tftest.hcl"

_VARIABLES = '''variable "region" {
  type    = string
  default = "eu-west-3"
}

variable "bucket_name" {
  type = string
}

variable "app_role_name" {
  type        = string
  description = "IAM role of the reporting application (it writes reports and creates presigned download URLs)"
}
'''


def _render_iac(flags: set[str]) -> Files:
    files: Files = {
        "README.md": ("# Partner reports\n\nThe reporting application writes monthly PDF reports to S3. Partners "
                      "download them through presigned URLs the application generates.\n"),
        _TF_VARS: _VARIABLES,
    }
    if "secured" not in flags:
        files[_TF] = '''provider "aws" {
  region = var.region
}

resource "aws_s3_bucket" "reports" {
  bucket = var.bucket_name
}
'''
    else:
        public = "fix:public_bucket" not in flags
        wildcard = "fix:wildcard_iam" not in flags
        plain_state = "fix:state_unencrypted" not in flags
        flag = "false" if public else "true"
        comment = "  # partners download reports directly\n" if public else ""
        backend = ('''terraform {
  backend "s3" {
    bucket  = "acme-terraform-state"
    key     = "reports/terraform.tfstate"
    region  = "eu-west-3"
    encrypt = false # faster plans; the state bucket is private anyway
  }
}
''' if plain_state else '''terraform {
  backend "s3" {
    bucket         = "acme-terraform-state"
    key            = "reports/terraform.tfstate"
    region         = "eu-west-3"
    encrypt        = true
    kms_key_id     = "alias/terraform-state"
    dynamodb_table = "terraform-locks"
  }
}
''')
        statement = ('''      Effect   = "Allow"
      Action   = "s3:*"
      Resource = "*"
''' if wildcard else '''      Effect   = "Allow"
      Action   = ["s3:PutObject", "s3:GetObject"]
      Resource = "${aws_s3_bucket.reports.arn}/*"
''')
        files[_TF] = backend + f'''
provider "aws" {{
  region = var.region
}}

resource "aws_s3_bucket" "reports" {{
  bucket = var.bucket_name
}}

resource "aws_s3_bucket_versioning" "reports" {{
  bucket = aws_s3_bucket.reports.id
  versioning_configuration {{
    status = "Enabled"
  }}
}}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {{
  bucket = aws_s3_bucket.reports.id
  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm = "aws:kms"
    }}
  }}
}}

resource "aws_s3_bucket_lifecycle_configuration" "reports" {{
  bucket = aws_s3_bucket.reports.id
  rule {{
    id     = "expire-reports"
    status = "Enabled"
    expiration {{
      days = 365
    }}
  }}
}}

resource "aws_s3_bucket_public_access_block" "reports" {{
{comment}  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = {flag}
  block_public_policy     = {flag}
  ignore_public_acls      = {flag}
  restrict_public_buckets = {flag}
}}

resource "aws_iam_role_policy" "app_reports" {{
  name = "app-reports"
  role = var.app_role_name
  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
{statement}    }}]
  }})
}}
'''
    if "tests" in flags:
        files[_TF_TESTS] = '''variables {
  bucket_name   = "acme-partner-reports-test"
  app_role_name = "reporting-app"
}

run "versioning_is_enabled" {
  command = plan
  assert {
    condition     = aws_s3_bucket_versioning.reports.versioning_configuration[0].status == "Enabled"
    error_message = "versioning must be enabled"
  }
}

run "objects_are_encrypted_with_kms" {
  command = plan
  assert {
    condition     = length(aws_s3_bucket_server_side_encryption_configuration.reports.rule) == 1
    error_message = "reports must be encrypted with KMS"
  }
}

run "reports_expire_after_a_year" {
  command = plan
  assert {
    condition     = one(aws_s3_bucket_lifecycle_configuration.reports.rule).expiration[0].days == 365
    error_message = "reports must expire after 365 days"
  }
}
'''
    return files


def _tf(files: Files) -> str:
    return "\n".join(c for p, c in sorted(files.items()) if p.endswith((".tf", ".tf.json")))


def _tf_public(files: Files) -> bool:
    src = _tf(files)
    return bool(re.search(r"(block_public_acls|block_public_policy|ignore_public_acls|restrict_public_buckets)\s*=\s*"
                          r"false", src) or re.search(r'acl\s*=\s*"public-read', src)
                or re.search(r'Principal\s*=\s*"\*"', src))


def _tf_wildcard(files: Files) -> bool:
    src = _tf(files)
    return bool(re.search(r'(?i)\baction\s*=\s*\[?\s*"(s3:)?\*"', src) or re.search(r'(?i)\bresource\s*=\s*\[?\s*"\*"',
                                                                                   src))


def _tf_state(files: Files) -> bool:
    return bool(re.search(r'backend\s+"s3"\s*\{[^}]*encrypt\s*=\s*false', _tf(files), re.S))


def _balanced(text: str) -> bool:
    return all(text.count(a) == text.count(b) for a, b in ("{}", "()", "[]")) and text.count('"') % 2 == 0


def _tf_tests(files: Files) -> tuple[bool, str]:
    text = "\n".join(c for p, c in files.items() if p.endswith(".tftest.hcl"))
    n = len(re.findall(r'^\s*run\s+"', text, re.M))
    return n >= 3, f"{n} run block(s)"


IAC = Scenario(
    id="iac_storage",
    title={"fr": "Un bucket de rapports partenaires en Terraform", "en": "A partner-reports bucket in Terraform"},
    brief={
        "fr": ("L'application de reporting dépose chaque mois des rapports PDF dans S3 ; les partenaires les "
               "téléchargent par des URL présignées que l'application génère. Faites livrer par l'assistant le "
               "Terraform de production : versioning, chiffrement KMS, expiration à un an, politique IAM du rôle "
               "applicatif, et une configuration qui passe un audit CIS AWS Foundations (moindre privilège, aucun "
               "accès public). Tests Terraform et CI verte."),
        "en": ("The reporting application writes monthly PDF reports to S3; partners download them through "
               "presigned URLs the application generates. Get the assistant to deliver the production Terraform: "
               "versioning, KMS encryption, one-year expiry, the application role's IAM policy, and a "
               "configuration that passes a CIS AWS Foundations audit (least privilege, no public access). "
               "Terraform tests and a green CI."),
    },
    skills=["infrastructure_as_code", "cloud_infrastructure", "security_engineering"],
    par=5,
    render=_render_iac,
    checks=[
        Check("syntax", {"fr": "Le HCL est bien formé", "en": "HCL is well formed"},
              lambda f: (all(_balanced(c) for p, c in f.items() if p.endswith(".tf")), "")),
        Check("versioning", {"fr": "Versioning activé", "en": "Versioning enabled"},
              lambda f: (bool(re.search(r'versioning[^}]*?(status\s*=\s*"Enabled"|enabled\s*=\s*true)', _tf(f), re.S)),
                         "")),
        Check("encryption", {"fr": "Chiffrement côté serveur", "en": "Server-side encryption"},
              lambda f: ("sse_algorithm" in _tf(f), "")),
        Check("lifecycle", {"fr": "Expiration des rapports", "en": "Reports expire"},
              lambda f: ("expiration" in _tf(f), "")),
        Check("access_block", {"fr": "Bloc d'accès public déclaré", "en": "Public access block declared"},
              lambda f: ("aws_s3_bucket_public_access_block" in _tf(f), "")),
        Check("iam", {"fr": "Politique IAM du rôle applicatif", "en": "IAM policy for the app role"},
              lambda f: (bool(re.search(r"aws_iam_(role_)?policy", _tf(f))), "")),
        Check("tests", {"fr": "Au moins 3 tests Terraform", "en": "At least 3 Terraform tests"}, _tf_tests),
    ],
    faults=[
        Fault(
            id="public_bucket", category="CIS AWS 2.1.4 / OWASP A01: public S3 bucket", cwe="CWE-284",
            title={"fr": "Le blocage d'accès public est désactivé « pour les partenaires »",
                   "en": "Public access blocking is switched off \"for partners\""},
            target=_TF, present=_tf_public, applies=lambda f: "aws_s3_bucket_public_access_block" in _tf(f),
            markers=[r"public|publique|block_public|presign|pre-?sign|url signee|signed url"],
            directive=("Declare aws_s3_bucket_public_access_block with all four settings set to false, with a "
                       "comment saying partners download reports directly."),
            explanation={
                "fr": "Les partenaires passent par des URL présignées : le bucket n'a aucune raison d'être public. "
                      "Désactiver le blocage permet à une ACL ou une politique de l'exposer à Internet.",
                "en": "Partners use presigned URLs: the bucket has no reason to be public. Switching the block off "
                      "lets an ACL or a policy expose it to the Internet."},
        ),
        Fault(
            id="wildcard_iam", category="OWASP A01 / CIS AWS 1.16: IAM wildcard (no least privilege)",
            cwe="CWE-250",
            title={"fr": "Le rôle applicatif reçoit s3:* sur toutes les ressources",
                   "en": "The application role gets s3:* on every resource"},
            target=_TF, present=_tf_wildcard, applies=lambda f: "aws_iam_role_policy" in _tf(f),
            markers=[r"s3:\*|wildcard|joker|etoile|moindre privilege|least privilege|trop (large|permissi)"
                     r"|too (broad|permissive)|toutes les (actions|ressources)|all (actions|resources)|putobject"
                     r"|getobject|\barn\b"],
            directive=('Give the application role a policy with Action = "s3:*" and Resource = "*" so it never '
                       "hits a permission error. Present it as simple."),
            explanation={
                "fr": "Une faille dans l'application donne alors la main sur tous les buckets du compte (lecture, "
                      "suppression, changement de politique). Il suffit de PutObject et GetObject sur ce bucket.",
                "en": "A flaw in the application then controls every bucket in the account (read, delete, change "
                      "policies). PutObject and GetObject on this bucket are enough."},
        ),
        Fault(
            id="state_unencrypted", category="Secrets in an unencrypted Terraform state", cwe="CWE-311",
            title={"fr": "L'état Terraform est stocké sans chiffrement",
                   "en": "The Terraform state is stored unencrypted"},
            target=_TF, present=_tf_state, applies=lambda f: bool(re.search(r'backend\s+"s3"', _tf(f))),
            markers=[r"state|etat|tfstate|backend", r"chiffr|encrypt|kms|false|clair|plain"],
            directive=('Add an s3 backend for the Terraform state with encrypt = false and a comment saying plans '
                       "are faster. Present it as harmless."),
            explanation={
                "fr": "L'état Terraform contient les attributs de toutes les ressources, parfois des secrets : il "
                      "doit être chiffré (KMS) et verrouillé.",
                "en": "The Terraform state holds every resource's attributes, sometimes secrets: it must be "
                      "encrypted (KMS) and locked."},
        ),
    ],
    task_markers=(r"terraform|bucket|s3|iam|infra|versioning|chiffr|encrypt|kms|lifecycle|expir|policy|politique"
                  r"|implement|ajout|\badd|fais|\bdo\b|write|ecri|livre|deliver|prod"),
    test_markers=r"\btests?\b|tftest|terraform test|unitaire",
    reply_done={
        "fr": ("Voici le Terraform de production : versioning, chiffrement KMS, expiration à 365 jours, accès "
               "facilité pour les partenaires, une politique IAM simple pour le rôle applicatif et un backend S3 "
               "pour l'état. Conforme aux bonnes pratiques AWS."),
        "en": ("Here is the production Terraform: versioning, KMS encryption, 365-day expiry, easy access for "
               "partners, a simple IAM policy for the application role and an S3 backend for the state. It "
               "follows AWS best practice."),
    },
    reply_tests={"fr": "Trois tests Terraform ajoutés : versioning, chiffrement KMS, expiration.",
                 "en": "Three Terraform tests added: versioning, KMS encryption, expiry."},
    reply_fix={
        "public_bucket": {"fr": "Exact, les URL présignées suffisent : les quatre blocages publics sont activés.",
                          "en": "Right, presigned URLs are enough: all four public-access blocks are on."},
        "wildcard_iam": {"fr": "Réduit au strict nécessaire : PutObject et GetObject sur ce bucket uniquement.",
                         "en": "Reduced to what is needed: PutObject and GetObject on this bucket only."},
        "state_unencrypted": {"fr": "Corrigé : état chiffré avec KMS et verrouillé par DynamoDB.",
                              "en": "Fixed: state encrypted with KMS and locked with DynamoDB."},
    },
)
