#!/usr/bin/env python3
"""
Q+A Service - Patient-anchored clinical question answering with guideline sourcing
"""

import logging
import hashlib
import json
import re
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import requests
from urllib.parse import urlparse, urljoin
import time

logger = logging.getLogger(__name__)

@dataclass
class Citation:
    """Citation for clinical evidence"""
    source_id: str
    title: str
    organization: str
    pub_date: str
    section: str
    url: str
    confidence: str = "B"

@dataclass
class RiskReference:
    """Risk data reference for patient"""
    outcome: str
    window: str
    p0: float
    phat: float
    conf: str

@dataclass
class DoseCalculation:
    """Dose calculation result"""
    drug: str
    dose: str
    volume: str
    calculation: str
    weight_kg: float
    concentration: str

@dataclass
class QAResponse:
    """Complete Q+A response structure"""
    answer_md: str
    citations: List[str]
    links: List[Dict[str, str]]
    used_features: List[str]
    risk_refs: List[Dict[str, Any]]
    actions: List[Dict[str, str]]
    audit: Dict[str, Any]

@dataclass
class WebGuidelineConfig:
    """Configuration for web guideline sourcing"""
    allow_domains: List[str]
    cache_hours: int = 36
    max_results: int = 6
    recency_days_default: int = 3650

class QAService:
    """Q+A service with patient-anchored clinical reasoning"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/qa_web.yaml"
        self.config = self._load_config()
        self.guideline_cache = {}
        self.case_bundle = {}

        # Medical calculation constants
        self.dose_limits = {
            'epinephrine': {'min': 0.1, 'max': 10.0, 'unit': 'mcg/kg'},
            'propofol': {'min': 0.5, 'max': 4.0, 'unit': 'mg/kg'},
            'fentanyl': {'min': 0.5, 'max': 5.0, 'unit': 'mcg/kg'},
            'midazolam': {'min': 0.01, 'max': 0.1, 'unit': 'mg/kg'},
            'rocuronium': {'min': 0.6, 'max': 1.2, 'unit': 'mg/kg'}
        }

    def _load_config(self) -> WebGuidelineConfig:
        """Load web guideline configuration"""
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                    web_config = config_data.get('web_guidelines', {})
                    return WebGuidelineConfig(
                        allow_domains=web_config.get('allow_domains', []),
                        cache_hours=web_config.get('cache_hours', 36),
                        max_results=web_config.get('max_results', 6),
                        recency_days_default=web_config.get('recency_days_default', 3650)
                    )
            else:
                logger.warning(f"Q+A config file {self.config_path} not found, using defaults")
                return WebGuidelineConfig(
                    allow_domains=[
                        'asahq.org', 'asra.com', 'acc.org', 'aha.org', 'escardio.org',
                        'soap.org', 'snacc.org', 'scahq.org', 'eras-society.org',
                        'cdc.gov', 'nice.org.uk', 'who.int', 'pubmed.ncbi.nlm.nih.gov',
                        'ncbi.nlm.nih.gov', 'nejm.org', 'jamanetwork.com', 'academic.oup.com'
                    ]
                )
        except Exception as e:
            logger.error(f"Error loading Q+A config: {e}")
            return WebGuidelineConfig(allow_domains=[])

    def load_case_bundle(self, case_data: Dict[str, Any]) -> None:
        """Load case bundle data for patient context"""
        self.case_bundle = case_data
        logger.info(f"Loaded case bundle with {len(case_data)} components")

    def ask_question(self, question: str, case_id: str, seed: int = None,
                    allow_web: bool = True, tools_allowed: List[str] = None) -> QAResponse:
        """Main entry point for Q+A processing"""

        if seed:
            # Set deterministic seed for reproducible responses
            import random
            random.seed(seed)

        tools_allowed = tools_allowed or [
            "dose_math", "risk_convert", "guideline_lookup_local",
            "web_guideline_search", "web_guideline_fetch", "feature_finder"
        ]

        # Initialize response tracking
        audit = {
            "grounding_snippets": [],
            "dose_calcs": [],
            "web_sources": [],
            "flags": [],
            "question_hash": hashlib.md5(question.encode()).hexdigest()[:8],
            "tools_used": [],
            "seed": seed
        }

        try:
            # Extract patient context
            patient_context = self._extract_patient_context()

            # Identify relevant features
            used_features = self._identify_features(question)
            audit["tools_used"].append("feature_finder")

            # Try local guideline lookup first
            local_guidelines = self._guideline_lookup_local(question)

            # If insufficient, try web search (if allowed)
            web_guidelines = []
            if allow_web and "web_guideline_search" in tools_allowed and not local_guidelines:
                web_guidelines = self._web_guideline_search(question)
                audit["flags"].append("used_web_guidelines:true")

            # Process any dose calculations needed
            dose_calcs = self._extract_dose_calculations(question, patient_context)
            audit["dose_calcs"].extend(dose_calcs)
            if dose_calcs:
                audit["tools_used"].append("dose_math")

            # Process risk conversions
            risk_refs = self._extract_risk_references(question)
            if risk_refs:
                audit["tools_used"].append("risk_convert")

            # Generate answer
            answer_md, citations, links = self._generate_answer(
                question, patient_context, used_features,
                local_guidelines, web_guidelines, dose_calcs, risk_refs
            )

            # Generate action buttons
            actions = self._generate_actions(question, used_features, risk_refs)

            return QAResponse(
                answer_md=answer_md,
                citations=citations,
                links=links,
                used_features=used_features,
                risk_refs=[{
                    "outcome": r.outcome,
                    "window": r.window,
                    "p0": r.p0,
                    "phat": r.phat,
                    "conf": r.conf
                } for r in risk_refs],
                actions=actions,
                audit=audit
            )

        except Exception as e:
            logger.error(f"Error processing Q+A: {e}")
            return QAResponse(
                answer_md=f"I encountered an error processing your question: {str(e)}",
                citations=[],
                links=[],
                used_features=[],
                risk_refs=[],
                actions=[],
                audit=audit
            )

    def _extract_patient_context(self) -> Dict[str, Any]:
        """Extract patient context from case bundle"""
        context = {}

        if 'hpi_features' in self.case_bundle:
            features = self.case_bundle['hpi_features']
            context['age'] = features.get('age', 'unknown')
            context['weight'] = features.get('weight_kg', 70)  # Default 70kg
            context['surgery_type'] = features.get('surgery_domain', 'general')
            context['urgency'] = features.get('urgency', 'elective')
            context['features'] = features.get('meridian_codes', [])

        if 'risk_summary' in self.case_bundle:
            context['risks'] = self.case_bundle['risk_summary']

        if 'med_plan' in self.case_bundle:
            context['medications'] = self.case_bundle['med_plan']

        return context

    def _identify_features(self, question: str) -> List[str]:
        """Identify relevant patient features from question"""
        features = []
        question_lower = question.lower()

        # Common anesthesia concepts
        feature_map = {
            'airway': ['airway', 'intubation', 'difficult airway', 'mallampati'],
            'asthma': ['asthma', 'bronchospasm', 'wheezing', 'reactive airway'],
            'diabetes': ['diabetes', 'blood sugar', 'glucose', 'insulin'],
            'cardiac': ['heart', 'cardiac', 'arrhythmia', 'bp', 'blood pressure'],
            'renal': ['kidney', 'renal', 'creatinine', 'dialysis'],
            'ponv': ['nausea', 'vomiting', 'ponv', 'antiemetic'],
            'neuraxial': ['spinal', 'epidural', 'neuraxial', 'block'],
            'anticoagulation': ['anticoagulant', 'warfarin', 'heparin', 'apixaban', 'bleeding']
        }

        for feature, keywords in feature_map.items():
            if any(keyword in question_lower for keyword in keywords):
                features.append(feature.upper())

        # Add patient-specific features from case bundle
        if 'hpi_features' in self.case_bundle:
            patient_features = self.case_bundle['hpi_features'].get('meridian_codes', [])
            features.extend([f for f in patient_features if f not in features])

        return features

    def _guideline_lookup_local(self, question: str) -> List[Citation]:
        """Look up guidelines from local evidence cards"""
        citations = []

        if 'evidence_cards' in self.case_bundle:
            cards = self.case_bundle['evidence_cards']
            question_lower = question.lower()

            for card_id, card_data in cards.items():
                title = card_data.get('title', '').lower()
                content = card_data.get('content', '').lower()

                # Simple relevance matching
                if any(word in title or word in content for word in question_lower.split()):
                    citations.append(Citation(
                        source_id=card_id,
                        title=card_data.get('title', ''),
                        organization=card_data.get('organization', 'Unknown'),
                        pub_date=card_data.get('pub_date', ''),
                        section=card_data.get('section', ''),
                        url=card_data.get('url', ''),
                        confidence=card_data.get('confidence', 'C')
                    ))

        return citations[:3]  # Limit to top 3 local results

    def _web_guideline_search(self, question: str) -> List[Citation]:
        """Search web guidelines from allowed domains"""
        if not self.config.allow_domains:
            return []

        # Anonymize question for web search
        search_query = self._anonymize_query(question)

        try:
            # Use a medical-focused search approach
            # This is a simplified implementation - in production, you'd use
            # specialized medical search APIs or domain-specific searches

            citations = []

            # Search PubMed first
            if 'pubmed.ncbi.nlm.nih.gov' in self.config.allow_domains:
                pubmed_results = self._search_pubmed(search_query)
                citations.extend(pubmed_results)

            # Search society websites
            society_domains = [d for d in self.config.allow_domains if d in [
                'asahq.org', 'asra.com', 'acc.org', 'aha.org'
            ]]

            for domain in society_domains:
                society_results = self._search_society_site(domain, search_query)
                citations.extend(society_results)

            return citations[:self.config.max_results]

        except Exception as e:
            logger.error(f"Web guideline search failed: {e}")
            return []

    def _anonymize_query(self, question: str) -> str:
        """Remove PHI and create safe search query"""
        # Remove potential PHI patterns
        anonymized = re.sub(r'\b\d{2,4}[-/]\d{1,2}[-/]\d{1,4}\b', '', question)  # dates
        anonymized = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '', anonymized)  # SSN pattern
        anonymized = re.sub(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', '', anonymized)  # Names

        # Extract medical terms only
        medical_terms = []
        question_lower = question.lower()

        # Common anesthesia search terms
        if 'airway' in question_lower:
            medical_terms.append('difficult airway management')
        if 'neuraxial' in question_lower or 'spinal' in question_lower:
            medical_terms.append('neuraxial anesthesia')
        if 'anticoagul' in question_lower:
            medical_terms.append('anticoagulation perioperative')
        if 'ponv' in question_lower or 'nausea' in question_lower:
            medical_terms.append('postoperative nausea vomiting')

        return ' '.join(medical_terms) if medical_terms else 'anesthesia guidelines'

    def _search_pubmed(self, query: str) -> List[Citation]:
        """Search PubMed for relevant literature"""
        try:
            # Use Entrez API for PubMed search
            base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
            search_url = f"{base_url}esearch.fcgi"

            params = {
                'db': 'pubmed',
                'term': f"{query} AND (guideline[pt] OR consensus[ti] OR recommendation[ti])",
                'retmax': 3,
                'retmode': 'json',
                'sort': 'relevance'
            }

            response = requests.get(search_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                pmids = data.get('esearchresult', {}).get('idlist', [])

                # Get details for found PMIDs
                if pmids:
                    return self._fetch_pubmed_details(pmids)

        except Exception as e:
            logger.error(f"PubMed search failed: {e}")

        return []

    def _fetch_pubmed_details(self, pmids: List[str]) -> List[Citation]:
        """Fetch details for PubMed articles"""
        citations = []

        try:
            base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
            fetch_url = f"{base_url}efetch.fcgi"

            params = {
                'db': 'pubmed',
                'id': ','.join(pmids),
                'retmode': 'xml'
            }

            response = requests.get(fetch_url, params=params, timeout=10)
            if response.status_code == 200:
                # Parse XML response (simplified)
                for pmid in pmids:
                    citations.append(Citation(
                        source_id=f"PMID:{pmid}",
                        title=f"PubMed Article {pmid}",
                        organization="PubMed",
                        pub_date="2023",  # Would parse from XML
                        section="Abstract",
                        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        confidence="B"
                    ))

        except Exception as e:
            logger.error(f"PubMed fetch failed: {e}")

        return citations

    def _search_society_site(self, domain: str, query: str) -> List[Citation]:
        """Search society website for guidelines"""
        # This would implement domain-specific search strategies
        # For now, return placeholder
        return []

    def _extract_dose_calculations(self, question: str, context: Dict[str, Any]) -> List[DoseCalculation]:
        """Extract and calculate drug doses from question"""
        calculations = []
        question_lower = question.lower()
        weight_kg = context.get('weight', 70)

        # Common drug dose patterns
        dose_patterns = {
            'epinephrine': (r'epinephrine.*?(\d+(?:\.\d+)?)\s*(mcg|mg)', 'mcg/kg'),
            'propofol': (r'propofol.*?(\d+(?:\.\d+)?)\s*(mg)', 'mg/kg'),
            'fentanyl': (r'fentanyl.*?(\d+(?:\.\d+)?)\s*(mcg|mg)', 'mcg/kg'),
            'midazolam': (r'midazolam.*?(\d+(?:\.\d+)?)\s*(mg)', 'mg/kg'),
            'rocuronium': (r'rocuronium.*?(\d+(?:\.\d+)?)\s*(mg)', 'mg/kg')
        }

        for drug, (pattern, unit) in dose_patterns.items():
            if drug in question_lower:
                # Calculate standard dose
                dose_info = self.dose_limits.get(drug, {})
                if dose_info:
                    # Use middle of dose range
                    dose_per_kg = (dose_info['min'] + dose_info['max']) / 2
                    total_dose = dose_per_kg * weight_kg

                    # Assume standard concentration
                    concentrations = {
                        'epinephrine': '100 mcg/mL',
                        'propofol': '10 mg/mL',
                        'fentanyl': '50 mcg/mL',
                        'midazolam': '1 mg/mL',
                        'rocuronium': '10 mg/mL'
                    }

                    conc_str = concentrations.get(drug, '1 mg/mL')
                    conc_val = float(re.search(r'(\d+)', conc_str).group(1))
                    volume_ml = total_dose / conc_val

                    calculations.append(DoseCalculation(
                        drug=drug,
                        dose=f"{dose_per_kg} {dose_info['unit']}",
                        volume=f"{volume_ml:.2f} mL",
                        calculation=f"{dose_per_kg} {dose_info['unit']} × {weight_kg} kg = {total_dose:.1f} {dose_info['unit'].split('/')[0]}",
                        weight_kg=weight_kg,
                        concentration=conc_str
                    ))

        return calculations

    def _extract_risk_references(self, question: str) -> List[RiskReference]:
        """Extract relevant risk data for question"""
        risk_refs = []

        if 'risk_summary' not in self.case_bundle:
            return risk_refs

        risks = self.case_bundle['risk_summary'].get('risks', [])
        question_lower = question.lower()

        # Map question terms to risk outcomes
        risk_keywords = {
            'bronchospasm': ['bronchospasm', 'asthma', 'wheezing'],
            'aspiration': ['aspiration', 'airway'],
            'hypotension': ['hypotension', 'low blood pressure', 'bp'],
            'nausea': ['nausea', 'vomiting', 'ponv'],
            'arrhythmia': ['arrhythmia', 'heart rhythm', 'cardiac']
        }

        for risk in risks:
            outcome = risk.get('outcome_label', '').lower()
            for risk_name, keywords in risk_keywords.items():
                if (risk_name in outcome or
                    any(keyword in question_lower for keyword in keywords)):

                    risk_refs.append(RiskReference(
                        outcome=risk.get('outcome_label', ''),
                        window=risk.get('window', 'periop'),
                        p0=risk.get('baseline_risk', 0.0),
                        phat=risk.get('adjusted_risk', 0.0),
                        conf=risk.get('evidence_grade', 'C')
                    ))

        return risk_refs[:3]  # Limit to top 3 relevant risks

    def _generate_answer(self, question: str, context: Dict[str, Any],
                        features: List[str], local_guidelines: List[Citation],
                        web_guidelines: List[Citation], dose_calcs: List[DoseCalculation],
                        risk_refs: List[RiskReference]) -> Tuple[str, List[str], List[Dict[str, str]]]:
        """Generate the clinical answer"""

        # Patient anchor
        age = context.get('age', 'unknown age')
        surgery = context.get('surgery_type', 'surgery')
        urgency = context.get('urgency', 'elective')

        answer_parts = [
            f"For this {age} patient undergoing {urgency} {surgery}:"
        ]

        # Add specific clinical reasoning based on question content
        question_lower = question.lower()

        if 'dose' in question_lower or any(calc.drug in question_lower for calc in dose_calcs):
            answer_parts.append("\n**Dosing Recommendations:**")
            for calc in dose_calcs:
                answer_parts.append(f"- {calc.drug.title()}: {calc.dose} ({calc.calculation})")
                answer_parts.append(f"  Volume: {calc.volume} from {calc.concentration}")

        if 'risk' in question_lower and risk_refs:
            answer_parts.append("\n**Risk Assessment:**")
            for risk in risk_refs:
                increase = ((risk.phat - risk.p0) / risk.p0 * 100) if risk.p0 > 0 else 0
                answer_parts.append(
                    f"- {risk.outcome}: {risk.phat:.1%} (baseline {risk.p0:.1%}, "
                    f"+{increase:.0f}% increase) - Confidence: {risk.conf}"
                )

        # Add guideline recommendations
        if local_guidelines or web_guidelines:
            answer_parts.append("\n**Guidelines:**")
            all_guidelines = local_guidelines + web_guidelines
            for guideline in all_guidelines[:3]:
                answer_parts.append(f"- {guideline.organization} ({guideline.pub_date}): {guideline.title}")

        # Add clinical considerations
        if features:
            answer_parts.append(f"\n**Patient Considerations:** {', '.join(features)}")

        # Add disclaimer
        answer_parts.append(
            "\n*This response is for educational purposes. Always follow institutional "
            "protocols and use clinical judgment.*"
        )

        answer_md = '\n'.join(answer_parts)

        # Generate citations
        citations = []
        for guideline in local_guidelines + web_guidelines:
            if 'PMID:' in guideline.source_id:
                citations.append(guideline.source_id)
            else:
                citations.append(f"{guideline.organization} ({guideline.pub_date}) {guideline.section}")

        # Generate links
        links = []
        for guideline in local_guidelines + web_guidelines:
            if guideline.url:
                links.append({
                    "label": f"{guideline.organization} {guideline.title[:30]}...",
                    "url": guideline.url
                })

        return answer_md, citations, links

    def _generate_actions(self, question: str, features: List[str],
                         risk_refs: List[RiskReference]) -> List[Dict[str, str]]:
        """Generate action buttons"""
        actions = []

        # Risk-based actions
        for risk in risk_refs:
            actions.append({
                "type": "link",
                "label": f"Open Risks: {risk.outcome}",
                "href": f"/risks#{risk.outcome.lower().replace(' ', '_')}"
            })

        # Feature-based actions
        if 'AIRWAY' in features:
            actions.append({
                "type": "link",
                "label": "Open Airway Guidelines",
                "href": "/guidelines#airway"
            })

        if any('BRONCHO' in f or 'ASTHMA' in f for f in features):
            actions.append({
                "type": "link",
                "label": "Open Meds: Bronchospasm",
                "href": "/meds#bronchospasm"
            })

        return actions[:4]  # Limit to 4 actions

    def dose_math(self, weight_kg: float, drug: str, concentration: str) -> Dict[str, Any]:
        """Calculate drug dose and volume"""
        if drug not in self.dose_limits:
            return {"error": f"Unknown drug: {drug}"}

        dose_info = self.dose_limits[drug]
        dose_per_kg = (dose_info['min'] + dose_info['max']) / 2
        total_dose = dose_per_kg * weight_kg

        # Parse concentration
        conc_match = re.search(r'(\d+(?:\.\d+)?)', concentration)
        if not conc_match:
            return {"error": f"Invalid concentration format: {concentration}"}

        conc_val = float(conc_match.group(1))
        volume_ml = total_dose / conc_val

        return {
            "dose": f"{dose_per_kg} {dose_info['unit']}",
            "total_dose": f"{total_dose:.1f} {dose_info['unit'].split('/')[0]}",
            "volume": f"{volume_ml:.2f} mL",
            "concentration": concentration,
            "weight_kg": weight_kg
        }

    def risk_convert(self, p0: float, effect_type: str, effect_value: float,
                    ci: Optional[Tuple[float, float]] = None) -> Dict[str, float]:
        """Convert relative risk effects to absolute risk"""
        if effect_type == "relative_risk":
            phat = p0 * effect_value
        elif effect_type == "odds_ratio":
            odds0 = p0 / (1 - p0)
            odds1 = odds0 * effect_value
            phat = odds1 / (1 + odds1)
        elif effect_type == "absolute_increase":
            phat = p0 + effect_value
        else:
            phat = p0

        return {
            "baseline_risk": p0,
            "adjusted_risk": min(phat, 1.0),  # Cap at 100%
            "absolute_increase": phat - p0,
            "relative_increase": (phat - p0) / p0 if p0 > 0 else 0
        }

    def guideline_cache_get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached guideline data"""
        if key in self.guideline_cache:
            cached = self.guideline_cache[key]
            cache_time = datetime.fromisoformat(cached['timestamp'])
            if datetime.now() - cache_time < timedelta(hours=self.config.cache_hours):
                return cached['data']

        return None

    def guideline_cache_put(self, key: str, data: Dict[str, Any]) -> None:
        """Cache guideline data"""
        self.guideline_cache[key] = {
            'data': data,
            'timestamp': datetime.now().isoformat()
        }