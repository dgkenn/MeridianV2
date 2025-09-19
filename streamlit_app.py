"""
Meridian - Clinical Decision Support Platform
Main Streamlit Application with Learning Module Integration
"""

import streamlit as st
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Configure page
st.set_page_config(
    page_title="Meridian - Clinical Decision Support",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import learning module
try:
    from learning import render_learning_module
    LEARNING_MODULE_AVAILABLE = True
except ImportError as e:
    st.error(f"Learning module not available: {e}")
    LEARNING_MODULE_AVAILABLE = False

# Import core functionality
try:
    from src.core.hpi_parser import MedicalTextProcessor
    from src.core.risk_engine import RiskEngine
    HPI_PARSER_AVAILABLE = True
except ImportError as e:
    st.error(f"Core functionality not available: {e}")
    HPI_PARSER_AVAILABLE = False


def main():
    """Main Streamlit application"""

    # Sidebar navigation
    st.sidebar.title("🏥 Meridian")
    st.sidebar.markdown("*Clinical Decision Support Platform*")

    # Navigation menu
    page = st.sidebar.radio(
        "Navigate to:",
        [
            "🏠 Home",
            "📋 HPI Analysis",
            "📊 Risk Assessment",
            "🎓 Learning Module",
            "📖 Documentation"
        ]
    )

    # Page routing
    if page == "🏠 Home":
        render_home_page()
    elif page == "📋 HPI Analysis":
        render_hpi_analysis()
    elif page == "📊 Risk Assessment":
        render_risk_assessment()
    elif page == "🎓 Learning Module":
        render_learning_page()
    elif page == "📖 Documentation":
        render_documentation()


def render_home_page():
    """Render the home page"""

    st.title("🏥 Meridian Clinical Decision Support")
    st.markdown("### Evidence-Based Medicine for Anesthesiology")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.info("""
        **📋 HPI Analysis**

        Advanced natural language processing for clinical text:
        - Extract medical conditions
        - Identify risk factors
        - Parse clinical narratives
        """)

    with col2:
        st.success("""
        **📊 Risk Assessment**

        Evidence-based risk calculation:
        - Outcome probability estimation
        - Factor-specific risk modifiers
        - Clinical recommendations
        """)

    with col3:
        st.warning("""
        **🎓 Learning Module**

        Educational content generation:
        - Board-style MCQ questions
        - CME certificate generation
        - Performance analytics
        """)

    st.markdown("---")

    # Quick access
    st.markdown("### 🚀 Quick Start")

    if st.button("Analyze Clinical Text", type="primary", use_container_width=True):
        st.switch_page("📋 HPI Analysis")

    if st.button("Start Learning Session", type="secondary", use_container_width=True):
        st.switch_page("🎓 Learning Module")


def render_hpi_analysis():
    """Render HPI analysis page"""

    st.title("📋 HPI Analysis")
    st.markdown("*Natural Language Processing for Clinical Text*")

    if not HPI_PARSER_AVAILABLE:
        st.error("HPI parser not available. Please check system configuration.")
        return

    # Text input
    clinical_text = st.text_area(
        "Enter clinical text for analysis:",
        placeholder="Enter patient history, symptoms, or clinical notes...",
        height=200
    )

    if st.button("Analyze Text", type="primary"):
        if clinical_text.strip():
            with st.spinner("Analyzing clinical text..."):
                try:
                    # Initialize processor
                    processor = MedicalTextProcessor()

                    # Process text
                    result = processor.process_text(clinical_text)

                    # Display results
                    st.success("Analysis Complete!")

                    col1, col2 = st.columns(2)

                    with col1:
                        st.subheader("📝 Extracted Factors")
                        if result.get('extracted_factors'):
                            for factor in result['extracted_factors']:
                                st.write(f"• **{factor.get('token', 'Unknown')}**: {factor.get('context', 'No context')}")
                        else:
                            st.info("No medical factors extracted")

                    with col2:
                        st.subheader("🔍 Analysis Summary")
                        st.json(result)

                except Exception as e:
                    st.error(f"Analysis failed: {e}")
        else:
            st.warning("Please enter clinical text to analyze")


def render_risk_assessment():
    """Render risk assessment page"""

    st.title("📊 Risk Assessment")
    st.markdown("*Evidence-Based Clinical Risk Calculation*")

    if not HPI_PARSER_AVAILABLE:
        st.error("Risk engine not available. Please check system configuration.")
        return

    # Patient information
    st.subheader("👤 Patient Information")

    col1, col2, col3 = st.columns(3)

    with col1:
        age = st.number_input("Age", min_value=0, max_value=120, value=45)

    with col2:
        sex = st.selectbox("Sex", ["M", "F"])

    with col3:
        population = st.selectbox("Population", ["adult", "pediatric", "geriatric"])

    # Clinical factors
    st.subheader("🏥 Clinical Factors")

    factors = st.multiselect(
        "Select present factors:",
        [
            "OSA", "obesity", "diabetes", "hypertension",
            "GERD", "difficult_airway_history", "CAD", "CHF"
        ]
    )

    # Outcome selection
    outcome = st.selectbox(
        "Risk calculation for:",
        [
            "FAILED_INTUBATION",
            "DIFFICULT_INTUBATION",
            "DIFFICULT_MASK_VENTILATION",
            "ASPIRATION",
            "HYPOTENSION"
        ]
    )

    if st.button("Calculate Risk", type="primary"):
        if factors:
            with st.spinner("Calculating risk..."):
                try:
                    # Initialize risk engine
                    risk_engine = RiskEngine()

                    # Create mock extracted factors
                    extracted_factors = [{'token': factor, 'context': f"Patient has {factor}"} for factor in factors]

                    # Calculate risk
                    risk_result = risk_engine.calculate_risk(
                        outcome_token=outcome,
                        extracted_factors=extracted_factors,
                        patient_age=age,
                        patient_sex=sex,
                        population=population
                    )

                    # Display results
                    st.success("Risk Calculation Complete!")

                    col1, col2 = st.columns(2)

                    with col1:
                        st.metric(
                            "Risk Estimate",
                            f"{risk_result.get('adjusted_risk', 0):.1%}",
                            delta=f"+{risk_result.get('risk_increase', 0):.1%}"
                        )

                    with col2:
                        st.metric(
                            "Baseline Risk",
                            f"{risk_result.get('baseline_risk', 0):.1%}"
                        )

                    # Detailed results
                    with st.expander("Detailed Results"):
                        st.json(risk_result)

                except Exception as e:
                    st.error(f"Risk calculation failed: {e}")
        else:
            st.warning("Please select at least one clinical factor")


def render_learning_page():
    """Render learning module page"""

    st.title("🎓 Learning Module")

    if not LEARNING_MODULE_AVAILABLE:
        st.error("""
        Learning module not available. This could be due to:
        - Missing dependencies
        - Import errors
        - Module not properly installed

        Please check the system configuration and ensure all learning module files are present.
        """)
        return

    try:
        # Render the learning module
        render_learning_module()

    except Exception as e:
        st.error(f"Learning module error: {e}")

        # Fallback content
        st.info("""
        **Learning Module Features:**

        - 📚 Board-style MCQ questions
        - 🎯 Case-anchored learning scenarios
        - 📊 Progress tracking and analytics
        - 🏆 CME certificate generation
        - 🐛 Problem reporting system

        *The learning module is currently experiencing technical difficulties.*
        """)


def render_documentation():
    """Render documentation page"""

    st.title("📖 Documentation")
    st.markdown("*Meridian Platform Guide*")

    # API documentation
    with st.expander("🔌 API Documentation", expanded=True):
        st.markdown("""
        ### HPI Analysis API

        **Endpoint:** `/api/analyze`

        **Method:** POST

        **Payload:**
        ```json
        {
            "hpi_text": "Clinical text to analyze",
            "patient_age": 45,
            "patient_sex": "M",
            "population": "adult"
        }
        ```

        **Response:**
        ```json
        {
            "extracted_factors": [...],
            "risk_estimates": {...},
            "clinical_recommendations": [...]
        }
        ```
        """)

    # Learning module documentation
    with st.expander("🎓 Learning Module Guide"):
        st.markdown("""
        ### Using the Learning Module

        1. **Start a Session**: Configure question count and difficulty
        2. **Answer Questions**: Interactive MCQ interface
        3. **Review Performance**: Get immediate feedback and explanations
        4. **Generate CME**: Earn continuing education credits
        5. **Report Issues**: Feedback system for content improvement

        ### CME Requirements
        - Minimum 10 questions answered
        - Minimum 70% score
        - Minimum 30 minutes study time
        """)

    # System information
    with st.expander("⚙️ System Information"):
        st.markdown(f"""
        ### Platform Status
        - **HPI Parser**: {'✅ Available' if HPI_PARSER_AVAILABLE else '❌ Unavailable'}
        - **Learning Module**: {'✅ Available' if LEARNING_MODULE_AVAILABLE else '❌ Unavailable'}
        - **Python Version**: {sys.version}
        - **Working Directory**: {os.getcwd()}
        """)


if __name__ == "__main__":
    main()