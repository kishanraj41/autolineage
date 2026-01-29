# ML Model Data Lineage Report

**Report Type:** EU AI Act Article 10 Compliance  
**Generated:** 2026-01-28 23:27:29 UTC  
**Standard:** EU Artificial Intelligence Act (Regulation 2024/1689)  
**Article:** Article 10 - Data and Data Governance

---

## Executive Summary

This report documents the complete data lineage for machine learning model development, 
ensuring compliance with EU AI Act Article 10 requirements for high-quality training data 
and robust data governance practices.

**Key Metrics:**
- **Total Datasets Tracked:** 3
- **Data Transformations:** 2
- **Lineage Relationships:** 2
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

#### Dataset 1: training_data_raw.csv

- **File Path:** `C:\Users\kisha\OneDrive\Documents\AI\autolineage\training_data_raw.csv`
- **Format:** CSV
- **Size:** 68.00 B
- **SHA-256 Hash:** `7ae9e029a73ac10a1ed1f05b6af746bdca5bf0ad78d8ac85ee0c80b18271aa0f`
- **Created:** 2026-01-29 05:25:58
- **Verification Status:** ✅ Verified

**Data Quality Assurance:**
- File integrity verified via cryptographic hash
- Complete provenance tracked
- Immutable reference maintained

#### Dataset 2: training_data_clean.csv

- **File Path:** `C:\Users\kisha\OneDrive\Documents\AI\autolineage\training_data_clean.csv`
- **Format:** CSV
- **Size:** 68.00 B
- **SHA-256 Hash:** `7ae9e029a73ac10a1ed1f05b6af746bdca5bf0ad78d8ac85ee0c80b18271aa0f`
- **Created:** 2026-01-29 05:25:58
- **Verification Status:** ✅ Verified

**Data Quality Assurance:**
- File integrity verified via cryptographic hash
- Complete provenance tracked
- Immutable reference maintained

#### Dataset 3: training_data_final.csv

- **File Path:** `C:\Users\kisha\OneDrive\Documents\AI\autolineage\training_data_final.csv`
- **Format:** CSV
- **Size:** 95.00 B
- **SHA-256 Hash:** `7b12236b5de6f5dfa7ccdc3c1d6943325e8dfb0006338455e25b76c365cc87c0`
- **Created:** 2026-01-29 05:25:58
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
- **Executed:** 2026-01-29 05:25:58
- **Code Reference:**
```python
  df_clean.to_csv('training_data_clean.csv', index=False)
```


**Compliance Notes:**
- Transformation logic documented
- Reproducible via code reference
- Execution timestamp recorded

#### Transformation 2: <module>

- **Type:** transform
- **Executed:** 2026-01-29 05:25:58
- **Code Reference:**
```python
  df_train.to_csv('training_data_final.csv', index=False)
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
  training_data_raw.csv → [<module>] → training_data_clean.csv
  training_data_clean.csv → [<module>] → training_data_final.csv
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

