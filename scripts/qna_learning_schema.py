#!/usr/bin/env python3
"""
Database schema setup for Q&A and Learning features
Creates new tables to support HPI-aware Q&A and practice question generation
"""

import duckdb
import os
from datetime import datetime

def create_qna_learning_tables():
    """Create database tables for Q&A and Learning features"""

    # Connect to the main database
    db_path = os.path.join('database', 'codex.duckdb')
    conn = duckdb.connect(db_path)

    print("Creating Q&A and Learning database schema...")

    # 1. HPI Analysis table - stores parsed HPI text and extracted entities
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hpi_analysis (
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_session_id) REFERENCES case_sessions(session_id)
        )
    """)

    # 2. Q&A Sessions table - tracks patient-specific conversations
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qa_sessions (
            session_id VARCHAR PRIMARY KEY,
            case_session_id VARCHAR,
            hpi_analysis_id VARCHAR,
            session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_end TIMESTAMP,
            total_questions INTEGER DEFAULT 0,
            session_summary TEXT,
            user_satisfaction_rating INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_session_id) REFERENCES case_sessions(session_id),
            FOREIGN KEY (hpi_analysis_id) REFERENCES hpi_analysis(analysis_id)
        )
    """)

    # 3. Q&A Interactions table - individual questions and responses
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qa_interactions (
            interaction_id VARCHAR PRIMARY KEY,
            qa_session_id VARCHAR,
            question_text TEXT,
            question_type VARCHAR, -- 'general', 'risk_assessment', 'differential', 'management'
            hpi_context_used JSON,
            ai_response TEXT,
            evidence_citations JSON,
            confidence_score FLOAT,
            response_time_ms INTEGER,
            user_feedback VARCHAR, -- 'helpful', 'not_helpful', 'incorrect'
            user_rating INTEGER,
            follow_up_questions JSON,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (qa_session_id) REFERENCES qa_sessions(session_id)
        )
    """)

    # 4. Learning Sessions table - practice question sessions
    conn.execute("""
        CREATE TABLE IF NOT EXISTS learning_sessions (
            session_id VARCHAR PRIMARY KEY,
            case_session_id VARCHAR,
            hpi_analysis_id VARCHAR,
            session_type VARCHAR, -- 'practice', 'assessment', 'review'
            difficulty_level VARCHAR, -- 'beginner', 'intermediate', 'advanced'
            focus_areas JSON, -- areas like 'risk_assessment', 'differential_diagnosis'
            total_questions INTEGER DEFAULT 0,
            correct_answers INTEGER DEFAULT 0,
            session_score FLOAT,
            time_spent_minutes INTEGER,
            learning_objectives_met JSON,
            session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_end TIMESTAMP,
            FOREIGN KEY (case_session_id) REFERENCES case_sessions(session_id),
            FOREIGN KEY (hpi_analysis_id) REFERENCES hpi_analysis(analysis_id)
        )
    """)

    # 5. Practice Questions table - HPI-based question bank
    conn.execute("""
        CREATE TABLE IF NOT EXISTS practice_questions (
            question_id VARCHAR PRIMARY KEY,
            question_text TEXT,
            question_type VARCHAR, -- 'multiple_choice', 'scenario', 'calculation'
            difficulty_level VARCHAR,
            hpi_template TEXT, -- template for generating patient-specific versions
            correct_answer TEXT,
            answer_options JSON, -- for multiple choice
            explanation TEXT,
            evidence_references JSON,
            learning_objectives JSON,
            tags JSON, -- for categorization
            created_by VARCHAR DEFAULT 'system',
            usage_count INTEGER DEFAULT 0,
            average_score FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 6. Question Performance table - tracks individual question attempts
    conn.execute("""
        CREATE TABLE IF NOT EXISTS question_performance (
            performance_id VARCHAR PRIMARY KEY,
            learning_session_id VARCHAR,
            question_id VARCHAR,
            hpi_context JSON, -- specific HPI elements used for this question
            user_answer TEXT,
            correct_answer TEXT,
            is_correct BOOLEAN,
            time_taken_seconds INTEGER,
            confidence_level INTEGER, -- 1-5 scale
            hint_used BOOLEAN DEFAULT FALSE,
            explanation_viewed BOOLEAN DEFAULT FALSE,
            user_feedback TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (learning_session_id) REFERENCES learning_sessions(session_id),
            FOREIGN KEY (question_id) REFERENCES practice_questions(question_id)
        )
    """)

    # 7. HPI Learning Analytics table - tracks learning patterns
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hpi_learning_analytics (
            analytics_id VARCHAR PRIMARY KEY,
            case_session_id VARCHAR,
            hpi_complexity_score FLOAT,
            learning_areas_identified JSON,
            knowledge_gaps JSON,
            mastery_levels JSON, -- by clinical area
            improvement_recommendations JSON,
            performance_trends JSON,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_session_id) REFERENCES case_sessions(session_id)
        )
    """)

    # 8. AI Model Configuration table - stores AI settings
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_model_config (
            config_id VARCHAR PRIMARY KEY,
            model_name VARCHAR,
            model_version VARCHAR,
            api_endpoint VARCHAR,
            default_temperature FLOAT DEFAULT 0.7,
            max_tokens INTEGER DEFAULT 1000,
            system_prompt TEXT,
            medical_guidelines_prompt TEXT,
            safety_filters JSON,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for better performance
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hpi_case_session ON hpi_analysis(case_session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_qa_case_session ON qa_sessions(case_session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_qa_interactions_session ON qa_interactions(qa_session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_learning_case_session ON learning_sessions(case_session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_question_performance_session ON question_performance(learning_session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_practice_questions_type ON practice_questions(question_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_practice_questions_difficulty ON practice_questions(difficulty_level)")

    print("- HPI Analysis table created")
    print("- Q&A Sessions table created")
    print("- Q&A Interactions table created")
    print("- Learning Sessions table created")
    print("- Practice Questions table created")
    print("- Question Performance table created")
    print("- HPI Learning Analytics table created")
    print("- AI Model Configuration table created")
    print("- Performance indexes created")

    # Insert default AI model configuration
    conn.execute("""
        INSERT OR IGNORE INTO ai_model_config (
            config_id,
            model_name,
            model_version,
            system_prompt,
            medical_guidelines_prompt
        ) VALUES (
            'default_medical_ai',
            'gpt-4',
            '2024-turbo',
            'You are a medical AI assistant specializing in anesthesia and perioperative care. Provide evidence-based responses citing relevant literature and clinical guidelines. Always include confidence levels and cite PMIDs when available.',
            'Base all recommendations on current anesthesia guidelines (ASA, ABA) and peer-reviewed evidence. Include risk stratification and consider patient-specific factors from the HPI. Flag any high-risk scenarios for immediate attention.'
        )
    """)

    conn.close()
    print("- Database schema creation completed successfully!")

def populate_sample_questions():
    """Add sample practice questions to the database"""

    db_path = os.path.join('database', 'codex.duckdb')
    conn = duckdb.connect(db_path)

    sample_questions = [
        {
            'question_id': 'airway_assessment_1',
            'question_text': 'Based on this patient\'s HPI, what is the most significant airway risk factor?',
            'question_type': 'multiple_choice',
            'difficulty_level': 'intermediate',
            'hpi_template': 'Patient with {medical_history} presenting for {procedure}',
            'correct_answer': 'Previous difficult intubation',
            'answer_options': '["Previous difficult intubation", "BMI > 35", "Short neck", "Limited mouth opening"]',
            'explanation': 'Previous difficult intubation is the strongest predictor of future airway difficulties and should guide airway management planning.',
            'evidence_references': '["PMID:12345678"]',
            'learning_objectives': '["Identify primary airway risk factors", "Prioritize risk assessment"]',
            'tags': '["airway", "risk_assessment", "preoperative"]'
        },
        {
            'question_id': 'cardiac_risk_1',
            'question_text': 'Given this patient\'s cardiac history in the HPI, what is the recommended preoperative evaluation?',
            'question_type': 'scenario',
            'difficulty_level': 'advanced',
            'hpi_template': 'Patient with {cardiac_conditions} scheduled for {surgical_risk_level} surgery',
            'correct_answer': 'Cardiology consultation and stress testing',
            'explanation': 'Patients with significant cardiac comorbidities require comprehensive evaluation before high-risk procedures.',
            'evidence_references': '["PMID:23456789"]',
            'learning_objectives': '["Apply cardiac risk stratification", "Determine appropriate consultation needs"]',
            'tags': '["cardiac", "preoperative", "consultation"]'
        }
    ]

    for question in sample_questions:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO practice_questions (
                    question_id, question_text, question_type, difficulty_level,
                    hpi_template, correct_answer, answer_options, explanation,
                    evidence_references, learning_objectives, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                question['question_id'],
                question['question_text'],
                question['question_type'],
                question['difficulty_level'],
                question['hpi_template'],
                question['correct_answer'],
                question.get('answer_options'),
                question['explanation'],
                question['evidence_references'],
                question['learning_objectives'],
                question['tags']
            ])
        except Exception as e:
            print(f"Warning: Could not insert sample question {question['question_id']}: {e}")

    conn.close()
    print("- Sample practice questions added")

if __name__ == "__main__":
    create_qna_learning_tables()
    populate_sample_questions()