---
document_id: KB-PLATFORM-001
title: How MedAccess AI labels appointment availability
source_url: docs/user-guide/availability-statuses.md
provider: MedAccess AI (platform documentation)
publication_date: 2026-09-01
retrieval_date: 2026-10-01
review_by: 2027-09-01
version: 1.0
jurisdiction: Ontario
service_type: ALL
access_classification: public
---
# Availability statuses

VERIFIED_AVAILABLE means an authorized availability source confirmed the opening recently and the source meets the platform's reliability threshold. It is still not a booking; only the provider can confirm a booking.

ADVERTISED_UNVERIFIED means the opening was advertised by a source but has not been confirmed, or the confirmation is older than the freshness limit. You must contact the provider to verify it.

CONTACT_REQUIRED means the provider asks patients to call to confirm the opening.

UNAVAILABLE means the opening is booked, cancelled, expired, or the facility does not offer the requested service.

UNKNOWN means the platform could not verify the opening, for example because the availability source was unreachable or the record had no valid timestamp.

DEMO_SIMULATED means the record comes from the synthetic demonstration dataset. Demonstration data is fictional and is not live appointment availability.

# Days saved

Potential days saved is calculated only from verified alternatives. It is the number of calendar days between the earliest verified alternative and your existing appointment, in the facility's local time zone.
