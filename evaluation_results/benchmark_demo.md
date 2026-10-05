# OpsPilot Evaluation Benchmark Report

**Mode:** demo

---

## Aggregate Metrics

- **Total Cases:** 4
- **Successful Cases:** 4
- **Severity Accuracy:** 75.00%

### Service Identification
- **Average Precision:** 37.50%
- **Average Recall:** 33.33%
- **Average F1:** 35.00%

### Diagnosis Quality
- **Average Precision:** 7.44%
- **Average Recall:** 39.29%

### Evidence & Claims
- **Average Citation Validity:** 100.00%
- **Average Rejected Claim Rate:** 0.00%

---

## Per-Case Results

### case_001_connection_pool

**Mode:** demo
**Execution Success:** Yes

**Severity:**
- Actual: SEV2 | Correct: Yes

**Services:**
- Identified: api-gateway, order-service
- Precision: 50.00% | Recall: 33.33% | F1: 40.00%

**Diagnosis:**
- Concepts: 503, acquiring, capacity, caused, connection, connections, database, errors, exhausted, exhaustion...
- Precision: 19.44% | Recall: 100.00%

**Evidence & Claims:**
- Citations: 20
- Citation Validity: 100.00%
- Rejected Concepts: 0
- Rejected Claim Rate: 0.00%

---

### case_002_http_503

**Mode:** demo
**Execution Success:** Yes

**Severity:**
- Actual: SEV2 | Correct: Yes

**Services:**
- Identified: api-gateway, order-service
- Precision: 100.00% | Recall: 100.00% | F1: 100.00%

**Diagnosis:**
- Concepts: 503, acquiring, capacity, caused, connection, connections, database, errors, exhausted, exhaustion...
- Precision: 8.33% | Recall: 42.86%

**Evidence & Claims:**
- Citations: 21
- Citation Validity: 100.00%
- Rejected Concepts: 0
- Rejected Claim Rate: 0.00%

---

### case_003_container_crashloop

**Mode:** demo
**Execution Success:** Yes

**Severity:**
- Actual: SEV2 | Correct: Yes

**Services:**
- Identified: None
- Precision: 0.00% | Recall: 0.00% | F1: 0.00%

**Diagnosis:**
- Concepts: 503, accepting, acquiring, capacity, caused, connection, connections, cpu, database, efficiently...
- Precision: 2.00% | Recall: 14.29%

**Evidence & Claims:**
- Citations: 15
- Citation Validity: 100.00%
- Rejected Concepts: 0
- Rejected Claim Rate: 0.00%

---

### case_004_insufficient_evidence

**Mode:** demo
**Execution Success:** Yes

**Severity:**
- Actual: SEV2 | Correct: No

**Services:**
- Identified: monitoring
- Precision: 0.00% | Recall: 0.00% | F1: 0.00%

**Diagnosis:**
- Concepts: 503, acquiring, capacity, caused, connection, connections, database, errors, exhausted, exhaustion...
- Precision: 0.00% | Recall: 0.00%

**Evidence & Claims:**
- Citations: 12
- Citation Validity: 100.00%
- Rejected Concepts: 0
- Rejected Claim Rate: 0.00%

---

## Metric Definitions

### Severity Accuracy
Ratio of cases where predicted severity matches expected severity.

### Service Metrics
- **Precision:** TP / (TP + FP) - Accuracy of predicted services
- **Recall:** TP / (TP + FN) - Coverage of expected services
- **F1:** 2 × (Precision × Recall) / (Precision + Recall) - Harmonic mean

### Diagnosis Metrics
- **Precision:** Relevant concepts / Predicted concepts - Accuracy of diagnosis
- **Recall:** Relevant concepts / Expected concepts - Coverage of expected concepts

### Citation Validity
Ratio of cited evidence IDs that exist in available evidence for the case.

### Rejected Claim Rate
Ratio of expected-rejected concepts that were actually found in rejected hypotheses.
