# AI Platform Architecture Notes

> SYNTHETIC DATA — NovaGrid Corp is a fictional company. All names, figures and events are invented for demonstration purposes.

- Document owner: Daniel Mensah, Principal Architect
- Version: 2.3
- Last reviewed: 2026-09-10

## Overview

The NovaGrid AI Platform is a shared internal platform that provides retrieval-augmented generation, agent orchestration and model governance to product teams. Project Phoenix is the first production consumer of the platform.

The platform is organised into four layers: the experience layer, the orchestration layer, the knowledge layer and the governance layer.

## Experience Layer

Product teams build user-facing applications such as the Phoenix self-service portal on top of a versioned Assistant API. The Assistant API is exposed through the API gateway with OAuth 2.0 authentication and per-tenant rate limits.

## Orchestration Layer

Agent workflows are modelled as explicit state graphs. A supervisor node classifies intent and routes requests to specialised agents for retrieval, analysis and tool execution. Every workflow run emits a trace with the execution path, tool calls and latency for each node.

Tool integrations are registered in a central tool catalogue with typed input schemas. The catalogue is designed so tools can be exposed through the Model Context Protocol in a later phase.

## Knowledge Layer

Documents are ingested from approved repositories, split into overlapping chunks of roughly 800 characters and embedded with a sentence-transformer model. Embeddings are stored in a vector database with metadata including the source filename, document ID and chunk ID so that every answer can cite its evidence.

Retrieval uses cosine similarity with a default of five chunks per query. A re-ranking stage is planned for Q1 2027.

## Governance Layer

All generated answers pass through a guardrail stage that checks grounding against retrieved evidence, validates citations and redacts sensitive data such as personal phone numbers and credentials. Answers with low confidence must state that more information is required instead of guessing.

Model usage, token consumption and latency are recorded per request for cost tracking and capacity planning.

## Non-Functional Requirements

- Assistant API p95 latency target: 1.5 seconds for retrieval-only answers.
- Availability target: 99.9 percent monthly.
- Data residency: all customer data remains in the EU region.
- Secrets are injected through the secrets manager and are never stored in source control.

## Known Architecture Risks

- The vector database runs as a single node; a high-availability cluster is planned for Q1 2027.
- The assistant API latency exceeds target under peak load because retrieval and generation run sequentially.
- The tool catalogue does not yet enforce per-tool authorisation scopes.
