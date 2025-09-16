# Codex v2 API Reference

Complete API documentation for the Codex evidence-based anesthesia platform.

## Base URL

```
http://localhost:8080/api
```

## Authentication

Currently using simple API key authentication. Include in headers:

```
Authorization: Bearer YOUR_API_KEY
```

## Error Responses

All endpoints return standardized error responses:

```json
{
    "error": "Error description",
    "code": "ERROR_CODE",
    "details": {...},
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req_123456"
}
```

Common HTTP status codes:
- `400` - Bad Request (invalid parameters)
- `404` - Not Found (no evidence available)
- `429` - Rate Limit Exceeded
- `500` - Internal Server Error

## Endpoints

### HPI Processing

#### POST `/api/hpi/parse`

Parse free-text HPI and extract risk factors.

**Request:**
```json
{
    "hpi_text": "5-year-old male presenting for tonsillectomy and adenoidectomy. History significant for asthma and recent URI 2 weeks ago with persistent cough. Patient has moderate OSA with AHI of 12.",
    "session_id": "optional_session_id",
    "phi_detection": true,
    "anonymize": true
}
```

**Response:**
```json
{
    "session_id": "hpi_2024011510300000",
    "demographics": {
        "age_years": 5,
        "age_category": "AGE_1_5",
        "sex": "SEX_MALE",
        "procedure": "TONSILLECTOMY",
        "urgency": "ELECTIVE",
        "weight_kg": null
    },
    "extracted_factors": [
        {
            "token": "ASTHMA",
            "plain_label": "Asthma",
            "confidence": 0.9,
            "evidence_text": "History significant for asthma",
            "factor_type": "risk_factor",
            "category": "pulmonary",
            "severity_weight": 2.0,
            "context": "...History significant for asthma and recent..."
        },
        {
            "token": "RECENT_URI_2W",
            "plain_label": "Recent upper respiratory infection (≤2 weeks)",
            "confidence": 0.85,
            "evidence_text": "recent URI 2 weeks ago",
            "factor_type": "risk_factor",
            "category": "pulmonary",
            "severity_weight": 2.5,
            "context": "...asthma and recent URI 2 weeks ago with..."
        },
        {
            "token": "OSA",
            "plain_label": "Obstructive sleep apnea",
            "confidence": 0.95,
            "evidence_text": "moderate OSA with AHI of 12",
            "factor_type": "risk_factor",
            "category": "airway",
            "severity_weight": 2.5,
            "context": "...Patient has moderate OSA with AHI..."
        }
    ],
    "risk_summary": [
        "Asthma moderately increases risk of respiratory complications",
        "Recent upper respiratory infection significantly increases risk of airway complications",
        "Obstructive sleep apnea significantly increases risk of airway complications"
    ],
    "phi_detected": false,
    "phi_locations": [],
    "anonymized_text": "5-year-old male presenting for tonsillectomy and adenoidectomy...",
    "confidence_score": 0.87,
    "parsed_at": "2024-01-15T10:30:00Z"
}
```

#### GET `/api/hpi/examples`

Get random example HPIs for testing.

**Query Parameters:**
- `population` (optional): "pediatric", "adult", "mixed"
- `procedure` (optional): procedure type filter

**Response:**
```json
{
    "examples": [
        {
            "hpi": "3-year-old female scheduled for bilateral myringotomy...",
            "population": "pediatric",
            "procedure": "ENT",
            "complexity": "moderate"
        }
    ]
}
```

### Risk Assessment

#### POST `/api/risk/calculate`

Calculate perioperative risks based on extracted factors.

**Request:**
```json
{
    "factors": ["ASTHMA", "RECENT_URI_2W", "OSA", "AGE_1_5", "SEX_MALE"],
    "demographics": {
        "age_years": 5,
        "procedure": "TONSILLECTOMY",
        "urgency": "ELECTIVE"
    },
    "mode": "model_based",
    "context_label": "peds_ent",
    "evidence_version": "v2024.01"
}
```

**Parameters:**
- `mode`: "model_based" (uses pooled evidence) or "literature_live" (real-time PubMed)
- `context_label`: specific clinical context for baseline selection
- `evidence_version`: optional version specification

**Response:**
```json
{
    "session_id": "risk_2024011510300001",
    "evidence_version": "v2024.01",
    "mode": "model_based",
    "risks": [
        {
            "outcome": "LARYNGOSPASM",
            "outcome_label": "Laryngospasm",
            "category": "airway",
            "baseline_risk": 0.015,
            "baseline_context": "pediatric_ent",
            "adjusted_risk": 0.067,
            "confidence_interval": [0.038, 0.115],
            "risk_ratio": 4.47,
            "risk_difference": 0.052,
            "evidence_grade": "B",
            "k_studies": 8,
            "contributing_factors": [
                {
                    "factor": "RECENT_URI_2W",
                    "or": 2.8,
                    "ci": [1.6, 4.9],
                    "evidence_grade": "B"
                },
                {
                    "factor": "OSA",
                    "or": 1.9,
                    "ci": [1.2, 3.1],
                    "evidence_grade": "C"
                }
            ],
            "citations": ["PMID:12345678", "PMID:23456789"],
            "last_updated": "2024-01-01T00:00:00Z"
        },
        {
            "outcome": "BRONCHOSPASM",
            "outcome_label": "Bronchospasm",
            "category": "respiratory",
            "baseline_risk": 0.020,
            "adjusted_risk": 0.056,
            "confidence_interval": [0.028, 0.108],
            "risk_ratio": 2.8,
            "evidence_grade": "A",
            "k_studies": 12,
            "contributing_factors": [
                {
                    "factor": "ASTHMA",
                    "or": 2.8,
                    "ci": [2.1, 3.7],
                    "evidence_grade": "A"
                }
            ],
            "citations": ["PMID:34567890", "PMID:45678901"],
            "last_updated": "2024-01-01T00:00:00Z"
        }
    ],
    "summary": {
        "highest_absolute_risks": [
            {
                "outcome": "LARYNGOSPASM",
                "risk": 0.067,
                "label": "6.7% risk of laryngospasm"
            }
        ],
        "biggest_risk_increases": [
            {
                "outcome": "LARYNGOSPASM",
                "increase": "4.5x above baseline",
                "absolute_increase": 0.052
            }
        ],
        "total_outcomes_assessed": 15,
        "outcomes_with_evidence": 12,
        "overall_risk_score": "moderate"
    },
    "calculated_at": "2024-01-15T10:30:00Z"
}
```

#### GET `/api/risk/outcomes`

Get list of available outcomes with baseline data.

**Query Parameters:**
- `population`: "pediatric", "adult", "both"
- `category`: outcome category filter
- `context`: clinical context

**Response:**
```json
{
    "outcomes": [
        {
            "token": "LARYNGOSPASM",
            "label": "Laryngospasm",
            "category": "airway",
            "baselines_available": ["general", "pediatric_ent", "adult_ent"],
            "modifiers_available": 15,
            "last_updated": "2024-01-01T00:00:00Z"
        }
    ],
    "total_outcomes": 42,
    "categories": ["airway", "respiratory", "cardiovascular", "neurologic"]
}
```

### Evidence Retrieval

#### GET `/api/evidence/{outcome}`

Get evidence summary for a specific outcome.

**Path Parameters:**
- `outcome`: outcome token (e.g., "LARYNGOSPASM")

**Query Parameters:**
- `modifier`: optional risk factor modifier
- `context`: clinical context
- `include_raw`: include raw study data

**Response:**
```json
{
    "outcome": "LARYNGOSPASM",
    "baseline_evidence": {
        "k_studies": 6,
        "pooled_risk": 0.015,
        "confidence_interval": [0.008, 0.028],
        "i_squared": 65.2,
        "method": "random_effects",
        "studies": [
            {
                "pmid": "12345678",
                "title": "Laryngospasm in pediatric anesthesia",
                "journal": "Anesthesiology",
                "year": 2023,
                "n": 1250,
                "events": 18,
                "risk": 0.014,
                "evidence_grade": "B"
            }
        ]
    },
    "modifier_evidence": {
        "RECENT_URI_2W": {
            "k_studies": 4,
            "pooled_or": 2.8,
            "confidence_interval": [1.6, 4.9],
            "i_squared": 23.1,
            "studies": [...]
        }
    },
    "guidelines": [
        {
            "society": "SPA",
            "year": 2023,
            "statement": "Consider postponing elective surgery in children with recent URI",
            "class": "IIa",
            "strength": "B"
        }
    ],
    "last_updated": "2024-01-01T00:00:00Z"
}
```

#### POST `/api/evidence/search`

Search evidence database with custom criteria.

**Request:**
```json
{
    "query": {
        "outcomes": ["LARYNGOSPASM", "BRONCHOSPASM"],
        "modifiers": ["ASTHMA", "RECENT_URI_2W"],
        "population": "pediatric",
        "years": [2010, 2024],
        "evidence_grades": ["A", "B"],
        "study_designs": ["RCT", "cohort"]
    },
    "include_raw": false,
    "max_results": 50
}
```

**Response:**
```json
{
    "results": [
        {
            "pmid": "12345678",
            "title": "Risk factors for laryngospasm in pediatric patients",
            "relevance_score": 0.95,
            "outcomes_addressed": ["LARYNGOSPASM"],
            "modifiers_addressed": ["RECENT_URI_2W", "OSA"],
            "evidence_grade": "B",
            "effect_estimates": [
                {
                    "outcome": "LARYNGOSPASM",
                    "modifier": "RECENT_URI_2W",
                    "or": 2.8,
                    "ci": [1.6, 4.9]
                }
            ]
        }
    ],
    "total_results": 23,
    "search_time_ms": 45
}
```

### Medications

#### POST `/api/medications/recommend`

Generate evidence-based medication recommendations.

**Request:**
```json
{
    "factors": ["ASTHMA", "RECENT_URI_2W", "OSA"],
    "risks": [
        {
            "outcome": "LARYNGOSPASM",
            "risk": 0.067
        },
        {
            "outcome": "BRONCHOSPASM",
            "risk": 0.056
        }
    ],
    "demographics": {
        "age_years": 5,
        "weight_kg": 18,
        "procedure": "TONSILLECTOMY"
    },
    "preferences": {
        "avoid_triggers": true,
        "include_alternatives": true
    }
}
```

**Response:**
```json
{
    "session_id": "med_2024011510300002",
    "recommendations": {
        "standard": [
            {
                "medication": "PROPOFOL",
                "generic_name": "Propofol",
                "indication": "Smooth induction - reduces airway reactivity",
                "dose": "2-3 mg/kg IV",
                "preparation": "10 mg/mL vial",
                "evidence_grade": "A",
                "citations": ["PMID:11111111"],
                "category": "induction"
            },
            {
                "medication": "SEVOFLURANE",
                "generic_name": "Sevoflurane",
                "indication": "Maintenance anesthesia - less airway irritation",
                "dose": "2-3% inspired",
                "evidence_grade": "A",
                "category": "volatile"
            }
        ],
        "draw_now": [
            {
                "medication": "ALBUTEROL",
                "generic_name": "Albuterol",
                "indication": "Bronchospasm treatment - asthma history",
                "dose": "2.5 mg in 3 mL saline for nebulization",
                "preparation": "2.5 mg/3 mL vial",
                "evidence_grade": "A",
                "urgency": "high",
                "category": "bronchodilator"
            },
            {
                "medication": "DEXAMETHASONE",
                "generic_name": "Dexamethasone",
                "indication": "Reduce airway inflammation - ENT surgery",
                "dose": "0.15 mg/kg IV (max 8 mg)",
                "preparation": "4 mg/mL vial",
                "evidence_grade": "B",
                "category": "steroid"
            }
        ],
        "consider": [
            {
                "medication": "ATROPINE",
                "indication": "Antisialagogue - reduce secretions",
                "dose": "0.01 mg/kg IV (min 0.1 mg)",
                "evidence_grade": "C",
                "conditions": ["if_excessive_secretions"]
            }
        ],
        "ensure_available": [
            {
                "medication": "INTRALIPID_20",
                "indication": "Local anesthetic systemic toxicity treatment",
                "dose": "1.5 mL/kg bolus, then infusion",
                "evidence_grade": "B",
                "category": "emergency"
            }
        ],
        "contraindicated": [
            {
                "medication": "DESFLURANE",
                "reason": "Avoid in asthma - increases airway reactivity",
                "evidence_grade": "B",
                "alternatives": ["SEVOFLURANE", "ISOFLURANE"]
            },
            {
                "medication": "SUCCINYLCHOLINE",
                "reason": "Avoid with recent URI - increased laryngospasm risk",
                "evidence_grade": "B",
                "alternatives": ["ROCURONIUM"]
            }
        ]
    },
    "drug_interactions": [
        {
            "drug1": "PROPOFOL",
            "drug2": "DEXAMETHASONE",
            "interaction": "none",
            "severity": "none"
        }
    ],
    "total_medications": {
        "standard": 5,
        "draw_now": 3,
        "consider": 2,
        "ensure_available": 1,
        "contraindicated": 2
    },
    "generated_at": "2024-01-15T10:30:00Z"
}
```

#### GET `/api/medications/database`

Query medication database.

**Query Parameters:**
- `category`: drug category filter
- `indication`: indication search
- `contraindication`: contraindication search
- `evidence_grade`: minimum evidence grade

**Response:**
```json
{
    "medications": [
        {
            "token": "PROPOFOL",
            "generic_name": "Propofol",
            "brand_names": ["Diprivan"],
            "drug_class": "induction_agent",
            "indications": ["induction", "maintenance", "sedation"],
            "contraindications": ["egg_allergy", "soy_allergy"],
            "adult_dose": "1-2.5 mg/kg IV",
            "peds_dose": "2-3 mg/kg IV",
            "onset_minutes": 0.5,
            "duration_hours": 0.2,
            "evidence_grade": "A"
        }
    ]
}
```

### Clinical Plan

#### POST `/api/plan/generate`

Generate structured clinical plan.

**Request:**
```json
{
    "session_id": "risk_2024011510300001",
    "include_sections": ["airway", "access", "monitoring", "induction", "maintenance", "emergence", "postop"],
    "format": "structured"
}
```

**Response:**
```json
{
    "plan": {
        "case_summary": {
            "patient": "5-year-old male",
            "procedure": "Tonsillectomy and adenoidectomy",
            "key_risks": ["Laryngospasm (6.7%)", "Bronchospasm (5.6%)"],
            "primary_concerns": "Recent URI, asthma, OSA"
        },
        "airway": {
            "approach": "Standard laryngoscopy with video backup",
            "equipment": ["Miller 2 blade", "5.0 ETT", "GlideScope"],
            "considerations": [
                "High laryngospasm risk - minimize irritation",
                "OSA - consider post-extubation monitoring"
            ]
        },
        "access": {
            "iv": "22G or 24G peripheral IV",
            "monitoring": "Standard ASA monitors plus capnography"
        },
        "induction": {
            "technique": "Smooth IV induction",
            "medications": [
                "Propofol 2-3 mg/kg IV",
                "Avoid succinylcholine"
            ],
            "special_notes": "Pre-oxygenate well due to OSA"
        },
        "maintenance": {
            "technique": "Balanced anesthesia",
            "volatile": "Sevoflurane 2-3%",
            "opioid": "Fentanyl 1-2 mcg/kg",
            "relaxant": "Rocuronium PRN"
        },
        "emergence": {
            "strategy": "Deep extubation if appropriate",
            "medications": [
                "Dexamethasone 0.15 mg/kg for edema",
                "Ondansetron 0.15 mg/kg for PONV"
            ],
            "monitoring": "Continuous pulse oximetry"
        },
        "postop": {
            "location": "PACU with airway monitoring",
            "duration": "Extended observation (OSA)",
            "medications": [
                "Albuterol available for bronchospasm",
                "Avoid opioids if possible"
            ]
        }
    },
    "key_evidence": [
        {
            "recommendation": "Deep extubation reduces laryngospasm risk",
            "evidence_grade": "B",
            "citation": "PMID:12345678"
        }
    ],
    "generated_at": "2024-01-15T10:30:00Z",
    "copyable_text": "ANESTHETIC PLAN\n\n5-year-old male for T&A...\n[formatted for copy/paste]"
}
```

### System Information

#### GET `/api/system/health`

System health check.

**Response:**
```json
{
    "status": "healthy",
    "version": "2.0.0",
    "evidence_version": "v2024.01",
    "database": {
        "status": "connected",
        "papers": 15420,
        "estimates": 23567,
        "pooled_effects": 892,
        "pooled_baselines": 156
    },
    "services": {
        "pubmed_api": "available",
        "nlp_processor": "loaded",
        "ontology": "loaded"
    },
    "last_evidence_update": "2024-01-01T00:00:00Z",
    "uptime_seconds": 86400
}
```

#### GET `/api/system/versions`

Evidence version history.

**Response:**
```json
{
    "current_version": "v2024.01",
    "versions": [
        {
            "version": "v2024.01",
            "created_at": "2024-01-01T00:00:00Z",
            "description": "January 2024 evidence update",
            "papers_added": 245,
            "estimates_added": 389,
            "pools_updated": 67,
            "is_current": true
        }
    ]
}
```

## Rate Limits

- **Standard endpoints**: 100 requests/minute
- **Evidence search**: 30 requests/minute
- **Literature-live mode**: 10 requests/minute
- **System endpoints**: 300 requests/minute

## SDK Examples

### Python SDK

```python
import requests

class CodexClient:
    def __init__(self, base_url="http://localhost:8080/api", api_key=None):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def parse_hpi(self, hpi_text):
        response = requests.post(
            f"{self.base_url}/hpi/parse",
            json={"hpi_text": hpi_text},
            headers=self.headers
        )
        return response.json()

    def calculate_risks(self, factors, demographics, mode="model_based"):
        response = requests.post(
            f"{self.base_url}/risk/calculate",
            json={
                "factors": factors,
                "demographics": demographics,
                "mode": mode
            },
            headers=self.headers
        )
        return response.json()

# Usage
client = CodexClient()
parsed = client.parse_hpi("5-year-old male for tonsillectomy with asthma")
risks = client.calculate_risks(
    factors=[f["token"] for f in parsed["extracted_factors"]],
    demographics=parsed["demographics"]
)
```

### JavaScript SDK

```javascript
class CodexClient {
    constructor(baseUrl = 'http://localhost:8080/api', apiKey = null) {
        this.baseUrl = baseUrl;
        this.headers = apiKey ? {'Authorization': `Bearer ${apiKey}`} : {};
    }

    async parseHPI(hpiText) {
        const response = await fetch(`${this.baseUrl}/hpi/parse`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...this.headers
            },
            body: JSON.stringify({hpi_text: hpiText})
        });
        return response.json();
    }

    async calculateRisks(factors, demographics, mode = 'model_based') {
        const response = await fetch(`${this.baseUrl}/risk/calculate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...this.headers
            },
            body: JSON.stringify({factors, demographics, mode})
        });
        return response.json();
    }
}

// Usage
const client = new CodexClient();
const parsed = await client.parseHPI('5-year-old male for tonsillectomy with asthma');
const risks = await client.calculateRisks(
    parsed.extracted_factors.map(f => f.token),
    parsed.demographics
);
```

## Error Handling

Always check for errors in API responses:

```python
response = requests.post('/api/risk/calculate', json=data)
if response.status_code == 200:
    result = response.json()
    if 'error' in result:
        print(f"API Error: {result['error']}")
    else:
        # Process successful result
        pass
else:
    print(f"HTTP Error: {response.status_code}")
```

## Changelog

- **v2.0.0** (2024-01-15): Initial v2 API release
- Future versions will maintain backward compatibility where possible