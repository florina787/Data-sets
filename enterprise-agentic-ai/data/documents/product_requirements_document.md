# Product Requirements Document — Phoenix Self-Service Portal

> SYNTHETIC DATA — NovaGrid Corp is a fictional company. All names, figures and events are invented for demonstration purposes.

- Product manager: Aisha Bello
- Project ID: PRJ-PHOENIX
- Target release: 2026.10

## Problem Statement

NovaGrid customers currently contact the support centre for routine questions about billing, service outages and account changes. Support volume grew 34 percent year over year, and average wait time is 11 minutes.

## Goals

- Deflect 30 percent of routine support contacts to self-service within six months of launch.
- Reduce average time to resolution for billing questions from 2 days to under 4 hours.
- Achieve a customer satisfaction score of at least 4.3 out of 5 for the assistant.

## Scope for Release 2026.10

- Conversational support assistant grounded in approved knowledge articles.
- Semantic knowledge search across help-centre content.
- In-portal bill payment through the new payment gateway.
- Single sign-on for enterprise customers through the new identity provider.

## Out of Scope

- Voice channel support.
- Agent hand-off to live chat (planned for Release 2027.02).

## Functional Requirements

- FR-1: The assistant must answer questions using only approved knowledge sources and show citations.
- FR-2: The assistant must hand over to a human when confidence is low.
- FR-3: Customers must be able to pay a bill without leaving the portal.
- FR-4: Enterprise customers must sign in with their corporate identity.

## Success Metrics

- Self-service deflection rate.
- Assistant answer acceptance rate of at least 85 percent.
- Payment completion rate of at least 95 percent.
- p95 assistant response time under 1.5 seconds.

## Dependencies

- AI Platform Assistant API (Platform team).
- Payment gateway vendor sandbox and production onboarding.
- Identity provider migration owned by the Security Engineering team.
