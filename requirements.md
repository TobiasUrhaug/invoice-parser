# Requirements: Invoice Parsing Service (MVP)

## 1. Overview

A cloud-hosted service that accepts a document file as input, extracts structured
invoice data from it using AI/ML, and returns the results to the caller as JSON.
The MVP is scoped for internal team usage with low processing volumes.

---

## 2. Actors

| Actor | Description |
|---|---|
| Internal API consumer | An internal application or team member that submits invoices and receives extracted data programmatically. |

---

## 3. Use Cases

### UC-01 — Submit invoice for extraction

**Actor:** Internal API consumer
**Trigger:** Consumer sends an HTTP request with an invoice file attached.
**Preconditions:** The caller has network access to the service endpoint.

**Main flow:**
1. Consumer sends a `POST` request to the extraction endpoint, uploading the invoice file.
2. The service validates that the uploaded file is of a supported format and within acceptable size limits.
3. The service processes the file and attempts to extract all target fields, regardless of the document's language.
4. The service returns a JSON response containing the extracted fields, with `null` for any field that could not be determined.

**Postconditions:** The caller receives a structured JSON payload. No file or result is persisted.

---

### UC-02 — Handle unsupported or malformed file

**Actor:** Internal API consumer
**Trigger:** Consumer submits a file that is not a supported format, is corrupt, or cannot be read.

**Main flow:**
1. Consumer sends a `POST` request with an invalid or unreadable file.
2. The service detects the problem during validation.
3. The service returns an appropriate HTTP error status (e.g., 400 or 422) with a human-readable error message describing the problem.

**Postconditions:** No extraction is attempted. No data is persisted.

---

### UC-03 — Partial extraction (one or more fields not found)

**Actor:** Internal API consumer
**Trigger:** Invoice is readable but one or more target fields are absent or ambiguous.

**Main flow:**
1. The service successfully processes the file.
2. One or more fields cannot be confidently extracted.
3. The service returns a `200 OK` response. Missing or unresolvable fields are represented as `null` in the JSON payload.

**Postconditions:** The caller receives a complete response structure; missing fields are explicit `null` values rather than omitted keys.

---

### UC-04 — Invoice in a non-English language

**Actor:** Internal API consumer
**Trigger:** Consumer submits an invoice written in a major European language (e.g., Norwegian, German, French, Spanish).

**Main flow:**
1. Consumer submits a PDF invoice where field labels and content are in a non-English language (e.g., "Fakturadato" instead of "Invoice date", "MVA" instead of "VAT").
2. The service identifies the relevant fields regardless of the label language used.
3. The service returns the extracted values mapped to the standard English field names in the JSON response.

**Postconditions:** The caller always receives field names in a consistent, language-agnostic schema regardless of the source document language.

---

## 4. Functional Requirements

### 4.1 Input

| ID | Requirement |
|---|---|
| F-01 | The service MUST accept PDF files as input. |
| F-02 | The API endpoint MUST accept file uploads via `multipart/form-data`. |
| F-03 | The service MUST reject files that are not of a supported format and return a descriptive error. |

### 4.2 Extraction — target fields

The response schema uses fixed English field names regardless of the source document language.

| ID | Field | Description |
|---|---|---|
| F-04 | `invoiceDate` | The date printed on the invoice (ISO 8601 format preferred in output). |
| F-05 | `totalAmount` | The total amount due including all taxes. |
| F-06 | `vatAmount` | The VAT or tax portion of the invoice. |
| F-07 | `netAmount` | The amount before tax. |
| F-08 | `invoiceReference` | The invoice number or reference identifier. |

### 4.3 Output

| ID | Requirement |
|---|---|
| F-09 | The service MUST return a JSON object with exactly the target fields listed in 4.2. |
| F-10 | Fields that cannot be extracted MUST be present in the response with a value of `null`. |
| F-11 | The response MUST be returned synchronously within the same HTTP connection. |
| F-12 | Monetary values SHOULD include the currency code where detectable (e.g., `{ "amount": 100.00, "currency": "NOK" }`). |

### 4.4 Language support

| ID | Requirement |
|---|---|
| F-13 | The service MUST correctly extract target fields from invoices written in all major European languages, including but not limited to: Norwegian, Swedish, Danish, English, German, French, Spanish, Italian, Dutch, and Portuguese. |
| F-14 | The service MUST return extracted values mapped to the standard English field schema regardless of the source document language. |
| F-15 | It is unknown whether field labels on an invoice are always in the document's primary language. The extraction approach MUST be robust to mixed-language labelling. |

### 4.5 Error responses

| ID | Requirement |
|---|---|
| F-16 | The service MUST return an HTTP 4xx status with an error message for invalid or unsupported input files. |
| F-17 | The service MUST return an HTTP 5xx status with an error message if an internal processing failure occurs. |

---

## 5. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NF-01 | Performance | The service SHOULD return a response within a reasonable timeframe for a single-page invoice under normal load. Exact SLA to be defined by the architect. |
| NF-02 | Scalability | The service MUST handle the current expected volume of fewer than 100 invoices per day. Horizontal scaling is not a requirement for MVP. |
| NF-03 | Security | The service MUST be accessible only to authorised internal consumers (e.g., API key, network policy, or equivalent). |
| NF-04 | Security | The service MUST NOT persist uploaded files or extracted data; all processing is stateless. |
| NF-05 | Availability | Availability target to be set by the architect based on internal SLA expectations. |
| NF-06 | Observability | The service SHOULD log each request and its outcome (success / partial / error) for operational monitoring. |

---

## 6. Constraints & Assumptions

- **MVP scope:** Only PDF input is required. Image formats (JPEG, PNG) are out of scope for the initial release but should be considered as a near-term extension point.
- **Stateless:** The service stores nothing. If an audit trail or reprocessing capability is needed in future, a storage layer must be added.
- **Internal only:** No multi-tenancy, no user accounts, and no public-facing interface is required for MVP.
- **No human-in-the-loop:** Results are returned as-is; there is no review workflow. Callers must handle `null` values appropriately.
- **Multi-language:** Invoices may be in any major European language. The extraction solution must handle semantic understanding of fields, not just keyword matching on English labels.
- **Mixed-language labels:** Whether field labels always match the document's primary language is unknown; the solution must not rely on this assumption.

---

## 7. Out of Scope (MVP)

- Image file input (JPEG, PNG)
- Batch processing (multiple invoices in one request)
- Webhook / async callback delivery
- Storage of files or extraction results
- Human review workflow
- Multi-tenant access or external customer access
- Frontend / web UI

---

## 8. Open Questions for the Architect

1. Which AI/ML approach to use for extraction: a general-purpose multimodal LLM (e.g., via API), a dedicated document AI service (e.g., AWS Textract, Azure Document Intelligence, Google Document AI), or a self-hosted model? Multi-language support is a key factor here.
2. What cloud provider is preferred or already in use?
3. What is the acceptable response latency for the synchronous API (e.g., p95 < 5s)?
4. How should API authentication be implemented (API key, mTLS, internal VPN-only)?
5. Are there any cost constraints that should influence the choice of AI provider or hosting model?
6. Should image format support (JPEG, PNG) be treated as a fast-follow after MVP or a later phase?
7. Should the response indicate which language was detected in the source document, as a diagnostic aid for callers?
