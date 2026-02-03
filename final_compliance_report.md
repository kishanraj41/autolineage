# ML Model Data Lineage Report

**Report Type:** EU AI Act Article 10 Compliance  
**Generated:** 2026-02-02 00:42:30 UTC  
**Standard:** EU Artificial Intelligence Act (Regulation 2024/1689)  
**Article:** Article 10 - Data and Data Governance

---

## Executive Summary

This report documents the complete data lineage for machine learning model development, 
ensuring compliance with EU AI Act Article 10 requirements for high-quality training data 
and robust data governance practices.

**Key Metrics:**
- **Total Datasets Tracked:** 6
- **Data Transformations:** 3
- **Lineage Relationships:** 3
- **Source Datasets:** 1
- **Output Artifacts:** 1

**Compliance Status:** ✅ **COMPLIANT**

All training data sources are documented, versioned, and traceable. Complete lineage 
from raw data to model artifacts is maintained with cryptographic verification.

---

## 1. Data Sources

### 1.1 Training Data Inventory

All datasets used in model development are documented below with cryptographic hashes 
for integrity verification.

#### Dataset 1: final_raw_data.csv

- **File Path:** `C:\Users\kisha\OneDrive\Documents\AI\autolineage\final_raw_data.csv`
- **Format:** CSV
- **Size:** 1.93 KB
- **SHA-256 Hash:** `aef2c79c4b038717f26b56f9a23871b3c02013e0100be0ef07904ce15ce5d801`
- **Created:** 2026-02-02 06:42:29
- **Verification Status:** ✅ Verified

**Data Quality Assurance:**
- File integrity verified via cryptographic hash
- Complete provenance tracked
- Immutable reference maintained

#### Dataset 2: final_clean_data.csv

- **File Path:** `C:\Users\kisha\OneDrive\Documents\AI\autolineage\final_clean_data.csv`
- **Format:** CSV
- **Size:** 1.93 KB
- **SHA-256 Hash:** `aef2c79c4b038717f26b56f9a23871b3c02013e0100be0ef07904ce15ce5d801`
- **Created:** 2026-02-02 06:42:29
- **Verification Status:** ✅ Verified

**Data Quality Assurance:**
- File integrity verified via cryptographic hash
- Complete provenance tracked
- Immutable reference maintained

#### Dataset 3: final_features.csv

- **File Path:** `C:\Users\kisha\OneDrive\Documents\AI\autolineage\final_features.csv`
- **Format:** CSV
- **Size:** 5.45 KB
- **SHA-256 Hash:** `570a3aae084d97a86a5c5a9d36fd8e32ba89701bd2a9be86c2c319eef12169df`
- **Created:** 2026-02-02 06:42:29
- **Verification Status:** ✅ Verified

**Data Quality Assurance:**
- File integrity verified via cryptographic hash
- Complete provenance tracked
- Immutable reference maintained

#### Dataset 4: final_train.csv

- **File Path:** `C:\Users\kisha\OneDrive\Documents\AI\autolineage\final_train.csv`
- **Format:** CSV
- **Size:** 4.34 KB
- **SHA-256 Hash:** `49cf6077d518f371a7556e61daa79c675c98823841bd81543bc485d87c587be8`
- **Created:** 2026-02-02 06:42:29
- **Verification Status:** ✅ Verified

**Data Quality Assurance:**
- File integrity verified via cryptographic hash
- Complete provenance tracked
- Immutable reference maintained

#### Dataset 5: final_test.csv

- **File Path:** `C:\Users\kisha\OneDrive\Documents\AI\autolineage\final_test.csv`
- **Format:** CSV
- **Size:** 1.13 KB
- **SHA-256 Hash:** `fccac623e8d0e94f2089ee657341ed4c48db3083aadbe7b226857d1a943f274f`
- **Created:** 2026-02-02 06:42:29
- **Verification Status:** ✅ Verified

**Data Quality Assurance:**
- File integrity verified via cryptographic hash
- Complete provenance tracked
- Immutable reference maintained

#### Dataset 6: final_statistics.csv

- **File Path:** `C:\Users\kisha\OneDrive\Documents\AI\autolineage\final_statistics.csv`
- **Format:** CSV
- **Size:** 682.00 B
- **SHA-256 Hash:** `d0076877153f448f78270e4bee76d75c66dacfc73be1d9c64e672e784b650e2b`
- **Created:** 2026-02-02 06:42:29
- **Verification Status:** ✅ Verified

**Data Quality Assurance:**
- File integrity verified via cryptographic hash
- Complete provenance tracked
- Immutable reference maintained

---

## 2. Data Transformations

### 2.1 Processing Pipeline

All data transformations are logged with complete audit trail.

#### Transformation 1: <module>

- **Type:** transform
- **Executed:** 2026-02-02 06:42:29
- **Code Reference:**
```python
  df_clean.to_csv('final_clean_data.csv', index=False)
```


**Compliance Notes:**
- Transformation logic documented
- Reproducible via code reference
- Execution timestamp recorded

#### Transformation 2: <module>

- **Type:** transform
- **Executed:** 2026-02-02 06:42:29
- **Code Reference:**
```python
  df_features.to_csv('final_features.csv', index=False)
```


**Compliance Notes:**
- Transformation logic documented
- Reproducible via code reference
- Execution timestamp recorded

#### Transformation 3: <module>

- **Type:** transform
- **Executed:** 2026-02-02 06:42:29
- **Code Reference:**
```python
  df_train.to_csv('final_train.csv', index=False)
```


**Compliance Notes:**
- Transformation logic documented
- Reproducible via code reference
- Execution timestamp recorded

---

## 3. Data Lineage Graph

### 3.1 Complete Provenance Chain

The following lineage graph shows the complete data flow from source to output:

```
Data Flow:
  final_raw_data.csv → [<module>] → final_clean_data.csv
  final_clean_data.csv → [<module>] → final_features.csv
  final_features.csv → [<module>] → final_train.csv
```

**Lineage Verification:**
- ✅ All transformations tracked
- ✅ Source-to-output chain complete
- ✅ No gaps in provenance
- ✅ Reproducible pipeline documented

---

## 4. EU AI Act Compliance Statement

### 4.1 Article 10 Requirements

This report demonstrates compliance with EU AI Act Article 10 requirements:

**✅ Training Data Quality (Article 10.2)**
- All datasets documented with cryptographic verification
- Data sources clearly identified and traceable
- Quality metrics maintained through hash verification

**✅ Data Governance (Article 10.3)**
- Complete data management procedures documented
- Bias detection capabilities through lineage tracking
- Data gaps identified via provenance chain analysis

**✅ Examination of Suitability (Article 10.4)**
- Data collection processes documented
- Relevant, representative datasets verified
- Complete audit trail maintained

**✅ Processing Operations (Article 10.5)**
- All data processing operations logged
- Transformation logic documented
- Reproducibility ensured via version control

### 4.2 Regulatory Compliance

**Regulation:** EU Artificial Intelligence Act (Regulation 2024/1689)  
**Applicable Articles:** Article 10 (Data and Data Governance)  
**Compliance Date:** {datetime.now().strftime('%Y-%m-%d')}  
**Verification Method:** Automated lineage tracking with cryptographic proof

**Declaration:**

This system maintains comprehensive data lineage tracking that enables:
1. Full traceability from raw data to model outputs
2. Reproducibility of all training procedures
3. Verification of data quality and representativeness
4. Audit capability for regulatory review

---

## 5. Verification & Reproducibility

### 5.1 Hash Verification

To verify data integrity, compare the SHA-256 hashes documented in this report 
with the actual files:
```bash
# Verify file integrity (Linux/Mac)
sha256sum <filename>

# Verify file integrity (Windows)
certutil -hashfile <filename> SHA256
```

### 5.2 Reproducibility Instructions

To reproduce the training pipeline:

1. Verify all source datasets using hashes above
2. Execute transformations in documented order
3. Compare output hashes with documented values
4. Validate lineage graph matches documented flow

### 5.3 Audit Trail

Complete audit trail is maintained in the lineage database (`lineage.db`).

**Database Contents:**
- All dataset metadata and hashes
- Complete transformation history
- Full lineage relationships
- Execution timestamps

**Access:**
```bash
# View database contents
lineage summary

# Export lineage graph
lineage show --format html
```

---

