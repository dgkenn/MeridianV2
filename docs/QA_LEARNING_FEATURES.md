# Q&A and Learning Features Documentation

## Overview

The CODEX v2 system now includes two major new features that leverage AI and natural language processing:

1. **Q&A Feature**: Allows users to ask questions about the current patient in plain language
2. **Learning Feature**: Generates practice questions based on patient scenarios and clinical guidelines

Both features analyze the **complete HPI text** (not just risk factors) to provide contextual, patient-specific responses.

## Architecture

### Core Components

#### 1. HPI Text Analyzer (`hpi_analyzer.py`)
- **Purpose**: Analyzes complete HPI text to extract clinical context
- **Key Functions**:
  - Medical entity extraction (symptoms, medications, risk factors)
  - Clinical timeline construction
  - Confidence scoring
  - Ontology mapping

#### 2. Database Schema (`scripts/qna_learning_schema.py`)
- **Purpose**: Stores Q&A sessions, learning data, and HPI analysis
- **Key Tables**:
  - `hpi_analysis`: Parsed HPI data and extracted entities
  - `qa_sessions`: Patient-specific Q&A conversations
  - `qa_interactions`: Individual questions and AI responses
  - `learning_sessions`: Practice question sessions
  - `practice_questions`: Question bank
  - `question_performance`: Learning analytics

## Database Schema Details

### HPI Analysis Table
```sql
CREATE TABLE hpi_analysis (
    analysis_id VARCHAR PRIMARY KEY,
    case_session_id VARCHAR,
    raw_hpi_text TEXT,
    cleaned_hpi_text TEXT,
    extracted_entities JSON,
    clinical_timeline JSON,
    identified_symptoms JSON,
    risk_factors_detected JSON,
    medical_history JSON,
    medications JSON,
    procedures JSON,
    severity_indicators JSON,
    temporal_markers JSON,
    analysis_confidence FLOAT,
    nlp_model_version VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Q&A Sessions Table
```sql
CREATE TABLE qa_sessions (
    session_id VARCHAR PRIMARY KEY,
    case_session_id VARCHAR,
    hpi_analysis_id VARCHAR,
    session_start TIMESTAMP,
    session_end TIMESTAMP,
    total_questions INTEGER,
    session_summary TEXT,
    user_satisfaction_rating INTEGER,
    created_at TIMESTAMP
);
```

### Learning Sessions Table
```sql
CREATE TABLE learning_sessions (
    session_id VARCHAR PRIMARY KEY,
    case_session_id VARCHAR,
    hpi_analysis_id VARCHAR,
    session_type VARCHAR, -- 'practice', 'assessment', 'review'
    difficulty_level VARCHAR, -- 'beginner', 'intermediate', 'advanced'
    focus_areas JSON,
    total_questions INTEGER,
    correct_answers INTEGER,
    session_score FLOAT,
    time_spent_minutes INTEGER,
    learning_objectives_met JSON,
    session_start TIMESTAMP,
    session_end TIMESTAMP
);
```

## HPI Analyzer Implementation

### Medical Entity Patterns
The analyzer uses regex patterns to identify:

#### Symptoms
- Pain patterns: `pain|ache|discomfort|soreness`
- GI symptoms: `nausea|vomiting|emesis`
- Respiratory: `dyspnea|shortness of breath|sob`
- Cardiac: `chest pain|angina|palpitations`
- Neurological: `syncope|fainting|headache`

#### Risk Factors
- Diabetes: `diabetes|diabetic|dm`
- Cardiovascular: `hypertension|htn|heart failure|chf`
- Respiratory: `copd|asthma|emphysema`
- Renal: `renal failure|kidney disease|ckd`
- Lifestyle: `obesity|smoking|alcohol`

#### Temporal Markers
- Relative time: `(\d+)\s*(days?|weeks?|months?|years?)\s*ago`
- Recent events: `yesterday|last\s*(?:week|month|year)`
- Current events: `today|this\s*(?:morning|afternoon|evening)`
- Duration: `since|for\s*the\s*past`

### Confidence Scoring Algorithm
```python
def calculate_confidence_score(entities, timeline, text_length):
    score = 0.0

    # Entity extraction score (max 0.4)
    total_entities = sum(len(entity_list) for entity_list in entities.values())
    score += min(0.4, total_entities * 0.05)

    # Timeline information (max 0.3)
    if timeline:
        score += min(0.3, len(timeline) * 0.1)

    # Text length factor (max 0.2)
    if text_length > 100:
        score += 0.2
    elif text_length > 50:
        score += 0.1

    # Key category presence (0.1 each)
    key_categories = ['symptoms', 'risk_factors', 'temporal_markers']
    for category in key_categories:
        if entities.get(category):
            score += 0.1

    return min(1.0, score)
```

## Usage Examples

### HPI Analysis
```python
from hpi_analyzer import HPIAnalyzer

analyzer = HPIAnalyzer()

sample_hpi = """
65 year old male with history of diabetes, hypertension, and COPD presents with
acute onset chest pain that started 2 hours ago. Patient describes the pain as
crushing, 8/10 severity, radiating to left arm. Associated with nausea and
diaphoresis. Patient has been taking metoprolol and lisinopril.
"""

# Analyze HPI
analysis_id = analyzer.analyze_hpi("session_001", sample_hpi)

# Retrieve results
analysis = analyzer.get_analysis(analysis_id)
print(f"Confidence: {analysis['analysis_confidence']}")
print(f"Symptoms: {analysis['identified_symptoms']}")
print(f"Risk Factors: {analysis['risk_factors_detected']}")
```

### Expected Output
```
Confidence: 1.00
Symptoms: ['chest pain', 'PONV', 'pain']
Risk Factors: ['diabetes', 'HYPERTENSION', 'COPD']
Medications: ['lisinopril', 'metoprolol']
Timeline Events: 1
```

## File Structure

```
codex-v2/
├── hpi_analyzer.py                 # HPI text analysis engine
├── scripts/
│   └── qna_learning_schema.py     # Database schema creation
├── docs/
│   └── QA_LEARNING_FEATURES.md    # This documentation
└── database/
    └── codex.duckdb               # Database with new tables
```

## Database Tables Created

1. **hpi_analysis** - Stores parsed HPI text and extracted medical entities
2. **qa_sessions** - Tracks patient-specific Q&A conversations
3. **qa_interactions** - Individual questions, responses, and evidence citations
4. **learning_sessions** - Practice question sessions with performance tracking
5. **practice_questions** - Question bank with HPI-based templates
6. **question_performance** - Individual question attempts and analytics
7. **hpi_learning_analytics** - Learning pattern analysis
8. **ai_model_config** - AI model settings and prompts

## Performance Indexes

- `idx_hpi_case_session` - Fast HPI lookup by case session
- `idx_qa_case_session` - Q&A session retrieval
- `idx_qa_interactions_session` - Question history
- `idx_learning_case_session` - Learning session lookup
- `idx_practice_questions_type` - Question filtering by type
- `idx_practice_questions_difficulty` - Difficulty-based queries

## Next Implementation Steps

### Phase 2: Q&A Engine
- Natural language question processing
- Evidence-based response generation
- Citation management
- Confidence scoring for responses

### Phase 3: Learning Engine
- Adaptive question generation
- Performance analytics
- Difficulty progression
- Learning objective tracking

### Phase 4: Frontend Integration
- Q&A chat interface
- Learning dashboard
- Progress visualization
- Evidence display

## Testing

### HPI Analyzer Test Results
- **Input**: 65 y/o male with diabetes, HTN, COPD, acute chest pain
- **Extracted Entities**:
  - Symptoms: chest pain, nausea, pain
  - Risk factors: diabetes, hypertension, COPD
  - Medications: metoprolol, lisinopril
  - Timeline: 1 event (2 hours ago)
- **Confidence Score**: 1.00 (maximum)

## Security Considerations

- Patient data anonymization
- HIPAA compliance for stored HPIs
- Secure API integration
- Input validation for medical queries
- Evidence citation verification

## Performance Considerations

- Optimized regex patterns for medical text
- Efficient database queries with proper indexing
- JSON field compression for large entities
- Caching for frequently accessed analyses

## Future Enhancements

1. **Advanced NLP**: Integration with medical NLP libraries (spaCy, NLTK)
2. **Clinical Decision Support**: Direct integration with evidence recommendations
3. **Multi-language Support**: Non-English medical text analysis
4. **Voice Interface**: Speech-to-text for verbal HPIs
5. **Real-time Analysis**: Live HPI analysis as text is typed

## Error Handling

- Graceful handling of malformed HPI text
- Fallback for missing ontology mappings
- Database transaction safety
- API timeout management
- User feedback collection for improvements