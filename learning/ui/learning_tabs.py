"""
Learning Module UI Components
Creates the Learning tab interface for Meridian
"""

import streamlit as st
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import time

from ..models.learning_item import LearningItem, LearningMode, DifficultyTier, BlueprintDomain
from ..models.learning_session import LearningSession, LearningResponse, BlueprintWeights
from ..generators.mcq_generator import MCQGenerator, CaseContext, validate_generated_items


class LearningInterface:
    """Main Learning module interface for Streamlit"""

    def __init__(self):
        self.mcq_generator = MCQGenerator()
        self._initialize_session_state()

    def _initialize_session_state(self):
        """Initialize Streamlit session state for learning module"""

        if 'learning_session' not in st.session_state:
            st.session_state.learning_session = None

        if 'current_item_index' not in st.session_state:
            st.session_state.current_item_index = 0

        if 'session_items' not in st.session_state:
            st.session_state.session_items = []

        if 'start_time' not in st.session_state:
            st.session_state.start_time = None

        if 'user_responses' not in st.session_state:
            st.session_state.user_responses = {}

    def render(self):
        """Main render method for Learning module"""

        st.header("🎓 Learning Module")
        st.markdown("*Board-style MCQs generated from current cases and evidence base*")

        # Create tabs for different learning modes
        tab1, tab2, tab3, tab4 = st.tabs([
            "📚 Practice Questions",
            "📊 Progress Dashboard",
            "🏆 CME Certificates",
            "🐛 Report Problem"
        ])

        with tab1:
            self._render_practice_tab()

        with tab2:
            self._render_progress_tab()

        with tab3:
            self._render_cme_tab()

        with tab4:
            self._render_problem_report_tab()

    def _render_practice_tab(self):
        """Render the main practice questions interface"""

        st.subheader("Practice Questions")

        # Check if we have an active session
        if st.session_state.learning_session is None:
            self._render_session_setup()
        else:
            self._render_active_session()

    def _render_session_setup(self):
        """Render session configuration interface"""

        st.markdown("### Start New Learning Session")

        col1, col2 = st.columns(2)

        with col1:
            # Learning mode selection
            mode = st.selectbox(
                "Learning Mode",
                options=[LearningMode.BASICS, LearningMode.BOARD],
                format_func=lambda x: {
                    LearningMode.BASICS: "🎯 Basics (Junior Residents)",
                    LearningMode.BOARD: "🎖️ Board Prep (Senior/Fellows)"
                }[x]
            )

            # Number of questions
            num_questions = st.slider(
                "Number of Questions",
                min_value=5,
                max_value=50,
                value=20,
                step=5
            )

            # Use current case context
            use_current_case = st.checkbox(
                "📋 Generate from current case context",
                value=True,
                help="Use the current patient context to generate relevant questions"
            )

        with col2:
            st.markdown("### Blueprint Weights")
            st.markdown("*Adjust question distribution by domain*")

            # Blueprint domain weights
            weights = {}
            domains = [
                ("Anatomy/Airway", "anatomy_airway", 0.15),
                ("Hemodynamics", "hemodynamics", 0.15),
                ("Pharmacology", "pharmacology", 0.20),
                ("Regional", "regional", 0.10),
                ("Pediatric", "pediatric", 0.10),
                ("Obstetric", "obstetric", 0.05),
                ("Neuro", "neuro", 0.10),
                ("Pain", "pain", 0.10),
                ("ICU/Vent", "icu_vent", 0.05)
            ]

            for display_name, key, default_val in domains:
                weights[key] = st.slider(
                    display_name,
                    min_value=0.0,
                    max_value=0.5,
                    value=default_val,
                    step=0.05,
                    key=f"weight_{key}"
                )

            # Validate weights sum to ~1.0
            total_weight = sum(weights.values())
            if abs(total_weight - 1.0) > 0.05:
                st.warning(f"⚠️ Weights sum to {total_weight:.2f}, should be ~1.0")

        # Get case context if available
        case_context = None
        if use_current_case:
            case_context = self._get_current_case_context()
            if case_context:
                st.success(f"✅ Using case context: {case_context.age}yo {case_context.sex}, {case_context.procedure}")
            else:
                st.info("ℹ️ No current case available, will generate generic scenarios")

        # Start session button
        if st.button("🚀 Start Learning Session", type="primary", use_container_width=True):
            self._start_new_session(mode, num_questions, weights, case_context)

    def _start_new_session(
        self,
        mode: LearningMode,
        num_questions: int,
        weights: Dict[str, float],
        case_context: Optional[CaseContext]
    ):
        """Start a new learning session"""

        with st.spinner("🎲 Generating questions..."):
            try:
                # Create blueprint weights
                blueprint_weights = BlueprintWeights(**weights)

                # Generate session
                session_id = LearningSession.generate_id()
                seed = int(time.time()) % 1000000  # Use timestamp as seed

                # Generate items
                items = self.mcq_generator.generate_session_items(
                    num_items=num_questions,
                    mode=mode,
                    blueprint_weights=blueprint_weights,
                    seed=seed,
                    case_context=case_context
                )

                # Validate generated items
                validation = validate_generated_items(items)

                if validation['invalid_items'] > 0:
                    st.warning(f"⚠️ {validation['invalid_items']} questions failed validation")
                    for issue in validation['issues'][:3]:  # Show first 3 issues
                        st.error(issue)

                # Create session
                session = LearningSession(
                    session_id=session_id,
                    mode=mode,
                    blueprint_weights=blueprint_weights,
                    seed=seed,
                    item_ids=[item.item_id for item in items],
                    user_id=None,  # Would be set from user auth
                    case_context=case_context.__dict__ if case_context else None
                )

                # Store in session state
                st.session_state.learning_session = session
                st.session_state.session_items = items
                st.session_state.current_item_index = 0
                st.session_state.start_time = time.time()
                st.session_state.user_responses = {}

                st.success(f"✅ Generated {len(items)} questions!")
                st.rerun()

            except Exception as e:
                st.error(f"❌ Failed to generate session: {e}")

    def _render_active_session(self):
        """Render the active learning session interface"""

        session = st.session_state.learning_session
        items = st.session_state.session_items
        current_index = st.session_state.current_item_index

        if current_index >= len(items):
            self._render_session_complete()
            return

        current_item = items[current_index]

        # Progress bar
        progress = (current_index) / len(items)
        st.progress(progress, text=f"Question {current_index + 1} of {len(items)}")

        # Session controls
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("⏸️ Pause Session"):
                st.session_state.learning_session = None
                st.rerun()

        with col2:
            st.markdown(f"**Mode:** {session.mode.value.title()} | **Domain:** {', '.join([d.value for d in current_item.domain_tags])}")

        with col3:
            current_score = session.current_score if session.responses else 0.0
            st.metric("Score", f"{current_score:.1%}")

        # Render current question
        self._render_question(current_item, current_index)

    def _render_question(self, item: LearningItem, question_index: int):
        """Render a single MCQ question"""

        st.markdown("---")

        # Question stem
        st.markdown(f"### Question {question_index + 1}")
        st.markdown(item.stem_md)

        # Show difficulty and metadata
        col1, col2, col3 = st.columns(3)
        with col1:
            st.badge(f"📊 {item.difficulty.value.title()}", type="secondary")
        with col2:
            st.badge(f"🎯 {item.item_type.value.replace('_', ' ').title()}", type="secondary")
        with col3:
            if item.case_context:
                st.badge("📋 Case-based", type="secondary")

        # Options
        st.markdown("#### Options:")

        option_key = f"question_{question_index}_response"

        if item.item_type == item.ItemType.SINGLE_BEST:
            # Single choice
            selected = st.radio(
                "Select the best answer:",
                options=list(range(len(item.options))),
                format_func=lambda x: f"{chr(65 + x)}. {item.options[x].text}",
                key=option_key,
                index=None
            )
            user_answer = [selected] if selected is not None else []

        elif item.item_type == item.ItemType.MULTI_SELECT:
            # Multiple choice (≤2 correct)
            st.markdown("*Select all correct answers (≤2):*")
            selected_options = []
            for i, option in enumerate(item.options):
                if st.checkbox(
                    f"{chr(65 + i)}. {option.text}",
                    key=f"{option_key}_{i}"
                ):
                    selected_options.append(i)
            user_answer = selected_options

        else:
            st.error(f"Unsupported question type: {item.item_type}")
            user_answer = []

        # Time tracking
        if f"start_time_{question_index}" not in st.session_state:
            st.session_state[f"start_time_{question_index}"] = time.time()

        # Submit button
        if user_answer and st.button("✅ Submit Answer", type="primary", use_container_width=True):
            self._submit_answer(item, user_answer, question_index)

    def _submit_answer(self, item: LearningItem, user_answer: List[int], question_index: int):
        """Submit and process user answer"""

        # Calculate time taken
        start_time = st.session_state.get(f"start_time_{question_index}", time.time())
        time_ms = int((time.time() - start_time) * 1000)

        # Check if correct
        correct_answers = item.correct_options
        is_correct = set(user_answer) == set(correct_answers)

        # Create response
        response = LearningResponse(
            item_id=item.item_id,
            answer=user_answer,
            correct=is_correct,
            time_ms=time_ms
        )

        # Add to session
        st.session_state.learning_session.add_response(response)
        st.session_state.user_responses[question_index] = {
            'user_answer': user_answer,
            'correct_answer': correct_answers,
            'is_correct': is_correct,
            'time_ms': time_ms
        }

        # Show immediate feedback
        if is_correct:
            st.success("✅ Correct!")
        else:
            st.error("❌ Incorrect")
            correct_letters = [chr(65 + i) for i in correct_answers]
            st.info(f"The correct answer is: {', '.join(correct_letters)}")

        # Show rationale
        with st.expander("📖 Explanation", expanded=True):
            st.markdown(item.rationale_md)

            if item.citations:
                st.markdown("**References:**")
                for citation in item.citations:
                    if citation.url:
                        st.markdown(f"- [{citation.title}]({citation.url}) ({citation.identifier})")
                    else:
                        st.markdown(f"- {citation.title} ({citation.identifier})")

        # Next question button
        if st.button("➡️ Next Question", type="primary", use_container_width=True):
            st.session_state.current_item_index += 1
            st.rerun()

    def _render_session_complete(self):
        """Render session completion interface"""

        session = st.session_state.learning_session
        items = st.session_state.session_items

        st.markdown("## 🎉 Session Complete!")

        # Calculate final feedback
        feedback = session.calculate_feedback(items)

        # Display results
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Final Score", f"{feedback.score:.1%}")

        with col2:
            st.metric("Total Time", f"{feedback.total_time_sec // 60}m {feedback.total_time_sec % 60}s")

        with col3:
            st.metric("Avg per Question", f"{feedback.avg_time_per_item:.1f}s")

        # Performance by domain
        if feedback.domain_scores:
            st.markdown("### 📊 Performance by Domain")

            domain_data = []
            for domain, score in feedback.domain_scores.items():
                domain_data.append({
                    'Domain': domain.replace('_', ' ').title(),
                    'Score': f"{score:.1%}",
                    'Performance': score
                })

            st.dataframe(domain_data, use_container_width=True)

        # Strengths and weaknesses
        col1, col2 = st.columns(2)

        with col1:
            if feedback.strengths:
                st.markdown("### 💪 Strengths")
                for strength in feedback.strengths:
                    st.success(f"✅ {strength.replace('_', ' ').title()}")

        with col2:
            if feedback.weaknesses:
                st.markdown("### 📈 Areas for Improvement")
                for weakness in feedback.weaknesses:
                    st.warning(f"📚 {weakness.replace('_', ' ').title()}")

        # Recommendations
        if feedback.recommendations:
            st.markdown("### 🎯 Recommendations")
            for rec in feedback.recommendations:
                st.info(f"💡 {rec}")

        # Action buttons
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🔄 New Session", type="primary", use_container_width=True):
                self._reset_session()

        with col2:
            if st.button("📊 View Details", use_container_width=True):
                self._show_detailed_results()

        with col3:
            if st.button("🏆 Generate CME", use_container_width=True):
                st.switch_page("CME Certificates")

    def _reset_session(self):
        """Reset session state for new session"""
        st.session_state.learning_session = None
        st.session_state.current_item_index = 0
        st.session_state.session_items = []
        st.session_state.start_time = None
        st.session_state.user_responses = {}
        st.rerun()

    def _show_detailed_results(self):
        """Show detailed question-by-question results"""

        st.markdown("### 📋 Detailed Results")

        items = st.session_state.session_items
        responses = st.session_state.user_responses

        for i, item in enumerate(items):
            if i in responses:
                response_data = responses[i]

                with st.expander(f"Question {i+1}: {'✅' if response_data['is_correct'] else '❌'}"):
                    st.markdown(item.stem_md)

                    # Show user answer vs correct
                    user_letters = [chr(65 + j) for j in response_data['user_answer']]
                    correct_letters = [chr(65 + j) for j in response_data['correct_answer']]

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Your answer:** {', '.join(user_letters)}")
                    with col2:
                        st.markdown(f"**Correct answer:** {', '.join(correct_letters)}")

                    st.markdown(f"**Time:** {response_data['time_ms']/1000:.1f}s")

    def _render_progress_tab(self):
        """Render progress tracking dashboard"""

        st.subheader("📊 Progress Dashboard")

        # Mock data for demonstration
        st.markdown("### 📈 Learning Analytics")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Sessions Completed", "12", delta="2")

        with col2:
            st.metric("Average Score", "78.5%", delta="5.2%")

        with col3:
            st.metric("Questions Answered", "240", delta="40")

        with col4:
            st.metric("Study Time", "4.2h", delta="45m")

        # Domain performance chart
        st.markdown("### 🎯 Domain Performance")
        import pandas as pd

        domain_performance = pd.DataFrame({
            'Domain': ['Anatomy/Airway', 'Hemodynamics', 'Pharmacology', 'Regional', 'Pediatric'],
            'Score': [85, 72, 90, 68, 78],
            'Questions': [25, 18, 30, 15, 20]
        })

        st.bar_chart(domain_performance.set_index('Domain')['Score'])

        # Recent sessions
        st.markdown("### 📅 Recent Sessions")
        recent_sessions = pd.DataFrame({
            'Date': ['2025-09-19', '2025-09-18', '2025-09-17'],
            'Mode': ['Board', 'Basics', 'Board'],
            'Questions': [20, 15, 25],
            'Score': ['82%', '90%', '76%'],
            'Time': ['28m', '18m', '35m']
        })

        st.dataframe(recent_sessions, use_container_width=True)

    def _render_cme_tab(self):
        """Render CME certificate interface"""

        st.subheader("🏆 CME Certificates")

        st.markdown("""
        ### Continuing Medical Education Credits

        Earn AMA PRA Category 1 Credits™ through completed learning sessions.

        **Requirements:**
        - Complete minimum 10 questions per session
        - Achieve 70% or higher score
        - Spend minimum 30 minutes in session
        """)

        # Eligible sessions
        st.markdown("### ✅ Eligible Sessions")

        eligible_sessions = pd.DataFrame({
            'Date': ['2025-09-19', '2025-09-18', '2025-09-16'],
            'Mode': ['Board', 'Board', 'Basics'],
            'Score': ['82%', '85%', '90%'],
            'Time': ['35m', '42m', '38m'],
            'Credits': [1.0, 1.0, 0.5],
            'Status': ['Available', 'Available', 'Generated']
        })

        st.dataframe(eligible_sessions, use_container_width=True)

        # Generate certificate
        if st.button("📜 Generate Certificate", type="primary"):
            st.success("🎉 Certificate generated successfully!")

            # Mock certificate data
            st.markdown("""
            ---
            ### 📜 CME Certificate Preview

            **Certificate of Completion**

            This is to certify that **Dr. [Name]** has successfully completed:

            - **Activity:** Meridian Board-Style Questions
            - **Date:** September 19, 2025
            - **Credits:** 1.0 AMA PRA Category 1 Credit™
            - **Score:** 82%
            - **Time:** 35 minutes

            *This activity has been planned and implemented in accordance with accreditation requirements.*
            """)

    def _render_problem_report_tab(self):
        """Render problem reporting interface"""

        st.subheader("🐛 Report a Problem")

        st.markdown("""
        ### Found an issue with a question or the learning module?

        Help us improve by reporting problems with:
        - Incorrect answers or explanations
        - Technical issues
        - Content suggestions
        - User experience problems
        """)

        # Problem type
        problem_type = st.selectbox(
            "Problem Type",
            [
                "Incorrect answer",
                "Wrong explanation",
                "Technical bug",
                "Content suggestion",
                "User interface issue",
                "Other"
            ]
        )

        # Question ID (if applicable)
        question_id = st.text_input(
            "Question ID (if applicable)",
            help="Found in question details or session summary"
        )

        # Description
        description = st.text_area(
            "Problem Description",
            placeholder="Please describe the issue in detail...",
            height=150
        )

        # Contact info
        email = st.text_input(
            "Your Email (optional)",
            placeholder="for follow-up if needed"
        )

        # Submit button
        if st.button("📧 Submit Report", type="primary", use_container_width=True):
            if description.strip():
                # In production, this would send email to dgkenn@bu.edu
                self._submit_problem_report(problem_type, question_id, description, email)
                st.success("✅ Problem report submitted successfully!")
                st.info("📧 Report sent to dgkenn@bu.edu")
            else:
                st.error("Please provide a problem description")

    def _submit_problem_report(self, problem_type: str, question_id: str, description: str, email: str):
        """Submit problem report (mock implementation)"""

        # In production, this would send actual email
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'problem_type': problem_type,
            'question_id': question_id,
            'description': description,
            'user_email': email,
            'session_info': {
                'current_session': st.session_state.learning_session.session_id if st.session_state.learning_session else None,
                'user_agent': 'Streamlit Learning Module'
            }
        }

        # Log the report (in production, send to dgkenn@bu.edu)
        print(f"PROBLEM REPORT: {json.dumps(report_data, indent=2)}")

    def _get_current_case_context(self) -> Optional[CaseContext]:
        """Get current case context from Meridian session"""

        # This would integrate with the main Meridian app to get current patient context
        # For now, return a mock case

        if 'current_case' in st.session_state:
            case_data = st.session_state.current_case
            return CaseContext(
                age=case_data.get('age', 45),
                sex=case_data.get('sex', 'M'),
                bmi=case_data.get('bmi', 28.5),
                comorbidities=case_data.get('comorbidities', ['OSA', 'hypertension']),
                procedure=case_data.get('procedure', 'elective intubation'),
                asa_class=case_data.get('asa_class', 'III')
            )

        return None


def render_learning_module():
    """Main entry point for Learning module"""
    learning_interface = LearningInterface()
    learning_interface.render()


if __name__ == "__main__":
    # For testing
    render_learning_module()