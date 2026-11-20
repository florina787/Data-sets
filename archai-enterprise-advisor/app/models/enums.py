"""Enumerations shared across ArchAI.

Enum values are human-readable strings so they serialize cleanly to JSON and
read well in the UI, the API and generated ADRs.
"""

from __future__ import annotations

from enum import Enum, IntEnum


class Industry(str, Enum):
    BANKING = "banking"
    FINANCIAL_SERVICES = "financial_services"
    RETAIL = "retail"
    LEGAL = "legal"
    GENERAL_ENTERPRISE = "general_enterprise"


REGULATED_INDUSTRIES = {Industry.BANKING, Industry.FINANCIAL_SERVICES, Industry.LEGAL}


class Deployment(str, Enum):
    ON_PREMISES = "on_premises"
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    PRIVATE_CLOUD = "private_cloud"
    HYBRID_CLOUD = "hybrid_cloud"
    MULTI_CLOUD = "multi_cloud"


PUBLIC_CLOUDS = {Deployment.AWS, Deployment.AZURE, Deployment.GCP}


class Compute(str, Enum):
    KUBERNETES = "kubernetes"
    OPENSHIFT = "openshift"
    DOCKER = "docker"
    VIRTUAL_MACHINES = "virtual_machines"
    BARE_METAL = "bare_metal"
    SERVERLESS = "serverless"


class ArchitectureStyle(str, Enum):
    MONOLITH = "monolith"
    SOA = "soa"
    MICROSERVICES = "microservices"
    EVENT_DRIVEN = "event_driven"
    API_BASED = "api_based"
    BATCH = "batch"


class Integration(str, Enum):
    REST = "rest"
    GRAPHQL = "graphql"
    GRPC = "grpc"
    KAFKA = "kafka"
    MESSAGE_QUEUE = "message_queue"
    EVENT_BUS = "event_bus"
    BATCH_JOBS = "batch_jobs"
    FILE_TRANSFER = "file_transfer"
    DATABASE = "database"
    LEGACY_INTERFACE = "legacy_interface"
    MCP = "mcp"


class IdentitySecurity(str, Enum):
    ACTIVE_DIRECTORY = "active_directory"
    ENTRA_ID = "entra_id"
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    JWT = "jwt"
    RBAC = "rbac"
    ABAC = "abac"
    API_GATEWAY = "api_gateway"
    SERVICE_ACCOUNTS = "service_accounts"
    SECRETS_MANAGEMENT = "secrets_management"
    PRIVATE_NETWORKING = "private_networking"


class DataStore(str, Enum):
    POSTGRESQL = "postgresql"
    ORACLE = "oracle"
    SQL_SERVER = "sql_server"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    DATA_LAKE = "data_lake"
    DATA_WAREHOUSE = "data_warehouse"
    OBJECT_STORAGE = "object_storage"
    SHAREPOINT = "sharepoint"
    DOCUMENT_REPOSITORY = "document_repository"
    VECTOR_DATABASE = "vector_database"
    SEARCH_ENGINE = "search_engine"


class DevOpsTool(str, Enum):
    JENKINS = "jenkins"
    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"
    AZURE_DEVOPS = "azure_devops"
    ARGOCD = "argocd"
    PROMETHEUS = "prometheus"
    GRAFANA = "grafana"
    SPLUNK = "splunk"
    CLOUDWATCH = "cloudwatch"
    DATADOG = "datadog"


CI_CD_TOOLS = {
    DevOpsTool.JENKINS,
    DevOpsTool.GITHUB_ACTIONS,
    DevOpsTool.GITLAB_CI,
    DevOpsTool.AZURE_DEVOPS,
    DevOpsTool.ARGOCD,
}
OBSERVABILITY_TOOLS = {
    DevOpsTool.PROMETHEUS,
    DevOpsTool.GRAFANA,
    DevOpsTool.SPLUNK,
    DevOpsTool.CLOUDWATCH,
    DevOpsTool.DATADOG,
}


class TaskType(str, Enum):
    """What the workload fundamentally needs to do."""

    RULES_VALIDATION = "rules_validation"
    WORKFLOW_AUTOMATION = "workflow_automation"
    REPORTING = "reporting"
    CLASSIFICATION = "classification"
    PREDICTION = "prediction"
    ANOMALY_DETECTION = "anomaly_detection"
    FORECASTING = "forecasting"
    RANKING = "ranking"
    RECOMMENDATION = "recommendation"
    SUMMARIZATION = "summarization"
    EXTRACTION = "extraction"
    GENERATION = "generation"
    CONVERSATION = "conversation"
    KNOWLEDGE_SEARCH = "knowledge_search"
    INVESTIGATION = "investigation"
    ORCHESTRATION = "orchestration"


DETERMINISTIC_TASKS = {TaskType.RULES_VALIDATION, TaskType.WORKFLOW_AUTOMATION, TaskType.REPORTING}
ML_TASKS = {
    TaskType.CLASSIFICATION,
    TaskType.PREDICTION,
    TaskType.ANOMALY_DETECTION,
    TaskType.FORECASTING,
    TaskType.RANKING,
    TaskType.RECOMMENDATION,
}
GENAI_TASKS = {TaskType.SUMMARIZATION, TaskType.EXTRACTION, TaskType.GENERATION, TaskType.CONVERSATION}
AGENTIC_TASKS = {TaskType.INVESTIGATION, TaskType.ORCHESTRATION}


class ActionType(str, Enum):
    """Actions the proposed solution would take against enterprise systems."""

    READ_ONLY = "read_only"
    DRAFT_CONTENT = "draft_content"
    TICKET_UPDATE = "ticket_update"
    CUSTOMER_COMMUNICATION = "customer_communication"
    RECORD_UPDATE = "record_update"
    PRODUCTION_REMEDIATION = "production_remediation"
    MONEY_MOVEMENT = "money_movement"
    PAYMENT_AUTHORIZATION = "payment_authorization"
    REGULATORY_CALCULATION = "regulatory_calculation"
    TRANSACTION_VALIDATION = "transaction_validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    COMPLIANCE_RULES = "compliance_rules"


#: Actions that must stay with deterministic, auditable systems. AI may explain
#: or summarize around them but never executes or decides them.
DETERMINISTIC_ONLY_ACTIONS = {
    ActionType.MONEY_MOVEMENT,
    ActionType.PAYMENT_AUTHORIZATION,
    ActionType.REGULATORY_CALCULATION,
    ActionType.TRANSACTION_VALIDATION,
    ActionType.AUTHENTICATION,
    ActionType.AUTHORIZATION,
    ActionType.COMPLIANCE_RULES,
}
#: Writes with material business impact: AI may prepare, a human approves.
HIGH_RISK_WRITE_ACTIONS = {
    ActionType.CUSTOMER_COMMUNICATION,
    ActionType.RECORD_UPDATE,
    ActionType.PRODUCTION_REMEDIATION,
}
#: Low-impact, reversible writes.
LOW_RISK_WRITE_ACTIONS = {ActionType.DRAFT_CONTENT, ActionType.TICKET_UPDATE}


class ArchitectureOption(str, Enum):
    KEEP_EXISTING = "keep_existing"
    TRADITIONAL_SOFTWARE = "traditional_software"
    TRADITIONAL_ML = "traditional_ml"
    GENERATIVE_AI = "generative_ai"
    RAG_GENAI = "rag_genai"
    AGENTIC_AI = "agentic_ai"
    HYBRID = "hybrid"


ARCHITECTURE_LABELS: dict[ArchitectureOption, str] = {
    ArchitectureOption.KEEP_EXISTING: "Keep Existing Architecture",
    ArchitectureOption.TRADITIONAL_SOFTWARE: "Traditional Deterministic Software",
    ArchitectureOption.TRADITIONAL_ML: "Traditional Machine Learning",
    ArchitectureOption.GENERATIVE_AI: "Generative AI",
    ArchitectureOption.RAG_GENAI: "RAG + Generative AI",
    ArchitectureOption.AGENTIC_AI: "Agentic AI",
    ArchitectureOption.HYBRID: "Hybrid Deterministic + AI",
}

AI_OPTIONS = {
    ArchitectureOption.TRADITIONAL_ML,
    ArchitectureOption.GENERATIVE_AI,
    ArchitectureOption.RAG_GENAI,
    ArchitectureOption.AGENTIC_AI,
}


class AgenticVerdict(str, Enum):
    NOT_RECOMMENDED = "not_recommended"
    CONSTRAINED = "constrained"
    RECOMMENDED = "recommended"


AGENTIC_VERDICT_LABELS: dict[AgenticVerdict, str] = {
    AgenticVerdict.NOT_RECOMMENDED: "AGENTIC AI NOT RECOMMENDED",
    AgenticVerdict.CONSTRAINED: "CONSTRAINED AGENTIC AI RECOMMENDED (PARTIALLY RECOMMENDED)",
    AgenticVerdict.RECOMMENDED: "AGENTIC AI RECOMMENDED (BOUNDED)",
}


class AutonomyLevel(IntEnum):
    NO_AI = 0
    READ_ONLY = 1
    SUGGEST = 2
    APPROVAL_REQUIRED = 3
    LIMITED_AUTONOMY = 4
    AUTONOMOUS = 5


AUTONOMY_LABELS: dict[AutonomyLevel, str] = {
    AutonomyLevel.NO_AI: "LEVEL 0 — NO AI",
    AutonomyLevel.READ_ONLY: "LEVEL 1 — READ ONLY",
    AutonomyLevel.SUGGEST: "LEVEL 2 — SUGGEST (HUMAN REVIEWS ALL OUTPUT)",
    AutonomyLevel.APPROVAL_REQUIRED: "LEVEL 3 — HUMAN APPROVAL REQUIRED",
    AutonomyLevel.LIMITED_AUTONOMY: "LEVEL 4 — LIMITED AUTONOMY",
    AutonomyLevel.AUTONOMOUS: "LEVEL 5 — AUTONOMOUS (BOUNDED)",
}


class MatrixDecision(str, Enum):
    KEEP = "KEEP"
    ENHANCE = "ENHANCE"
    ADD = "ADD"
    NOT_ADDED = "NOT ADDED"
    REPLACE = "REPLACE"


class ChallengeVerdict(str, Enum):
    PASS = "PASS"
    FLAG = "FLAG"
    FAIL = "FAIL"


class ROIVerdict(str, Enum):
    JUSTIFIED = "ROI JUSTIFIES AI"
    MARGINAL = "ROI MARGINAL — PROCEED ONLY WITH A NARROW PILOT"
    NOT_JUSTIFIED = "ROI DOES NOT JUSTIFY AI"
    NOT_APPLICABLE = "NOT APPLICABLE (NO AI PROPOSED)"


class SourcingDecision(str, Enum):
    KEEP = "KEEP"
    BUILD = "BUILD"
    BUY = "BUY"
    HYBRID = "HYBRID"
