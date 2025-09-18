"""
Meridian Clinical NLP Pipeline
Hybrid medspaCy + QuickUMLS + ClinicalBERT system for robust HPI parsing
"""

import os
import re
import json
import yaml
import logging
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import math

try:
    import spacy
    from spacy.matcher import PhraseMatcher, Matcher
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    import medspacy
    from medspacy import Sectionizer
    from medspacy.context import ConTextComponent
    MEDSPACY_AVAILABLE = True
except ImportError:
    MEDSPACY_AVAILABLE = False

try:
    from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

from .schemas import ParsedHPI, ParsedFeature, Modifier

logger = logging.getLogger(__name__)

class MeridianNLPPipeline:
    """Advanced clinical NLP pipeline for Meridian HPI parsing"""

    def __init__(self, use_bert: bool = False):
        self.use_bert = use_bert and TRANSFORMERS_AVAILABLE
        self.nlp = None
        self.phrase_matcher = None
        self.bert_pipeline = None
        self.rules = {}
        self.risk_factor_mapping = {}

        # Load configuration
        self._load_rules()
        self._load_risk_factor_mapping()

        # Initialize NLP components
        self._init_spacy()
        if self.use_bert:
            self._init_bert()

    def _load_rules(self):
        """Load rules from YAML configuration"""
        rules_path = Path(__file__).parent / "rules.yaml"
        try:
            with open(rules_path, 'r', encoding='utf-8') as f:
                self.rules = yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Could not load rules.yaml: {e}")
            self.rules = {}

    def _load_risk_factor_mapping(self):
        """Load risk factor mapping from JSON"""
        mapping_path = Path(__file__).parent / "mapping_risk_factors.json"
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                self.risk_factor_mapping = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load mapping_risk_factors.json: {e}")
            self.risk_factor_mapping = {}

    def _init_spacy(self):
        """Initialize spaCy with medspaCy components"""
        if not SPACY_AVAILABLE:
            logger.warning("spaCy not available, using rule-based fallback")
            return

        try:
            # Try to load scientific model first, fallback to general
            try:
                self.nlp = spacy.load("en_core_sci_sm")
                logger.info("Loaded en_core_sci_sm model")
            except OSError:
                try:
                    self.nlp = spacy.load("en_core_web_sm")
                    logger.info("Loaded en_core_web_sm model")
                except OSError:
                    logger.warning("No spaCy models available, using minimal setup")
                    self.nlp = spacy.blank("en")

            # Add medspaCy components if available
            if MEDSPACY_AVAILABLE:
                # Add sectionizer
                sectionizer = Sectionizer(self.nlp)
                if 'sectionizer_patterns' in self.rules:
                    for section, patterns in self.rules['sectionizer_patterns'].items():
                        for pattern in patterns:
                            sectionizer.add([{"LOWER": pattern.lower()}])
                self.nlp.add_pipe(sectionizer)

                # Add ConText for negation/temporality
                context = ConTextComponent(self.nlp)
                self.nlp.add_pipe(context)

            # Initialize phrase matcher for risk factors
            self.phrase_matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
            self._load_phrase_patterns()

        except Exception as e:
            logger.error(f"Error initializing spaCy: {e}")
            self.nlp = None

    def _load_phrase_patterns(self):
        """Load phrase patterns for risk factor matching"""
        if not self.nlp or not self.phrase_matcher:
            return

        patterns = self.rules.get('risk_factor_patterns', {})
        for code, pattern_list in patterns.items():
            phrases = []
            for pattern in pattern_list:
                try:
                    # Convert regex patterns to simple phrases where possible
                    simple_pattern = self._regex_to_phrase(pattern)
                    if simple_pattern:
                        doc = self.nlp(simple_pattern)
                        phrases.append(doc)
                except Exception as e:
                    logger.debug(f"Could not convert pattern {pattern}: {e}")

            if phrases:
                self.phrase_matcher.add(code, phrases)

    def _regex_to_phrase(self, pattern: str) -> Optional[str]:
        """Convert simple regex patterns to phrases for PhraseMatcher"""
        # Remove common regex metacharacters for simple patterns
        if any(char in pattern for char in ['(', ')', '[', ']', '*', '+', '?', '|', '^', '$']):
            # For complex patterns, extract the core term
            if 'asthma' in pattern.lower():
                return 'asthma'
            elif 'uri' in pattern.lower():
                return 'upper respiratory infection'
            elif 'osa' in pattern.lower():
                return 'sleep apnea'
            elif 'gerd' in pattern.lower():
                return 'gerd'
            elif 'tonsillectomy' in pattern.lower():
                return 'tonsillectomy'
            return None
        return pattern.strip('"\\b')

    def _init_bert(self):
        """Initialize ClinicalBERT for NER"""
        if not TRANSFORMERS_AVAILABLE:
            logger.warning("Transformers not available, skipping BERT initialization")
            return

        try:
            model_name = os.getenv("MERIDIAN_NLP_MODEL", "emilyalsentzer/Bio_ClinicalBERT")
            self.bert_pipeline = pipeline(
                "token-classification",
                model=model_name,
                tokenizer=model_name,
                aggregation_strategy="simple"
            )
            logger.info(f"Loaded BERT model: {model_name}")
        except Exception as e:
            logger.warning(f"Could not load BERT model: {e}")
            self.bert_pipeline = None

    def parse_hpi(self, text: str) -> ParsedHPI:
        """Main HPI parsing function"""
        try:
            # Clean and normalize text
            cleaned_text = self._clean_text(text)

            # Extract global attributes
            age_years = self._extract_age(cleaned_text)
            sex = self._extract_sex(cleaned_text)
            urgency = self._extract_urgency(cleaned_text)
            case_type = self._extract_case_type(cleaned_text)
            weight_kg = self._extract_weight(cleaned_text)
            height_cm = self._extract_height(cleaned_text)

            # Calculate BMI if both height and weight available
            bmi = None
            if weight_kg and height_cm:
                height_m = height_cm / 100
                bmi = round(weight_kg / (height_m ** 2), 1)

            # Extract risk factors using multiple approaches
            features = []

            # 1. Rule-based extraction (highest precision)
            rule_features = self._extract_rule_features(cleaned_text)
            features.extend(rule_features)

            # 2. spaCy phrase matching
            if self.nlp:
                spacy_features = self._extract_spacy_features(cleaned_text)
                features.extend(spacy_features)

            # 3. BERT extraction (if enabled)
            if self.use_bert and self.bert_pipeline:
                bert_features = self._extract_bert_features(cleaned_text)
                features.extend(bert_features)

            # Resolve conflicts and deduplicate
            features = self._resolve_features(features)

            return ParsedHPI(
                age_years=age_years,
                sex=sex,
                urgency=urgency,
                case_type=case_type,
                height_cm=height_cm,
                weight_kg=weight_kg,
                bmi=bmi,
                features=features
            )

        except Exception as e:
            logger.error(f"Error in parse_hpi: {e}")
            # Return minimal result
            return ParsedHPI(features=[])

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())

        # Normalize common abbreviations
        abbreviations = {
            r'\byo\b': 'year old',
            r'\bhx\b': 'history',
            r'\bHPI\b': 'History of Present Illness',
            r'\bPMH\b': 'Past Medical History',
            r'\bw/\b': 'with',
            r'\bw/o\b': 'without'
        }

        for abbrev, expansion in abbreviations.items():
            text = re.sub(abbrev, expansion, text, flags=re.I)

        return text

    def _extract_age(self, text: str) -> Optional[int]:
        """Extract age from text"""
        age_patterns = [
            r'(\d+)[\s-]?(?:year|yr)[\s-]?old',
            r'(\d+)[\s-]?(?:month|mo)[\s-]?old',
            r'age:?\s*(\d+)',
            r'(\d{1,2})\s*(?:years?|yrs?)'
        ]

        for pattern in age_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                try:
                    age = int(match.group(1))
                    # Convert months to years if needed
                    if 'month' in match.group(0).lower():
                        age = age / 12
                    if 0 < age <= 120:  # Reasonable age range
                        return int(age)
                except ValueError:
                    continue
        return None

    def _extract_sex(self, text: str) -> Optional[str]:
        """Extract sex from text"""
        if re.search(r'\b(?:male|boy|M)\b', text, re.I):
            return "SEX_MALE"
        elif re.search(r'\b(?:female|girl|F)\b', text, re.I):
            return "SEX_FEMALE"
        return None

    def _extract_urgency(self, text: str) -> str:
        """Extract urgency level"""
        urgency_patterns = self.rules.get('urgency_patterns', {})

        for urgency, patterns in urgency_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.I):
                    return urgency

        return "elective"

    def _extract_case_type(self, text: str) -> Optional[str]:
        """Extract case type"""
        case_patterns = self.rules.get('case_type_patterns', {})

        for case_type, patterns in case_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.I):
                    return case_type

        return None

    def _extract_weight(self, text: str) -> Optional[float]:
        """Extract weight in kg"""
        patterns = [
            r'weight:?\s*(\d+(?:\.\d+)?)\s*kg',
            r'(\d+(?:\.\d+)?)\s*kg',
            r'wt:?\s*(\d+(?:\.\d+)?)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                try:
                    weight = float(match.group(1))
                    if 0.5 <= weight <= 300:  # Reasonable weight range
                        return weight
                except ValueError:
                    continue
        return None

    def _extract_height(self, text: str) -> Optional[float]:
        """Extract height in cm"""
        patterns = [
            r'height:?\s*(\d+(?:\.\d+)?)\s*cm',
            r'(\d+(?:\.\d+)?)\s*cm\s*tall',
            r'ht:?\s*(\d+(?:\.\d+)?)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                try:
                    height = float(match.group(1))
                    if 30 <= height <= 250:  # Reasonable height range
                        return height
                except ValueError:
                    continue
        return None

    def _extract_rule_features(self, text: str) -> List[ParsedFeature]:
        """Extract features using rule-based patterns"""
        features = []
        patterns = self.rules.get('risk_factor_patterns', {})

        for code, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = list(re.finditer(pattern, text, re.I))
                for match in matches:
                    # Check for negation context
                    modifiers = self._extract_modifiers(text, match.start(), match.end())

                    # Get mapping info
                    mapping = self.risk_factor_mapping.get(code, {})

                    feature = ParsedFeature(
                        code=code,
                        label=mapping.get('label', code.replace('_', ' ').title()),
                        text=match.group(0),
                        source="rule",
                        confidence=0.9,
                        modifiers=modifiers
                    )
                    features.append(feature)
                    break  # Only take first match per pattern

        return features

    def _extract_spacy_features(self, text: str) -> List[ParsedFeature]:
        """Extract features using spaCy phrase matching"""
        if not self.nlp or not self.phrase_matcher:
            return []

        features = []
        doc = self.nlp(text)
        matches = self.phrase_matcher(doc)

        for match_id, start, end in matches:
            span = doc[start:end]
            code = self.nlp.vocab.strings[match_id]

            # Extract modifiers using ConText if available
            modifiers = Modifier()
            if hasattr(span, 'modifiers'):
                for modifier in span.modifiers:
                    if modifier.category == "NEGATED_EXISTENCE":
                        modifiers.negated = True
                    elif modifier.category in ["RECENT", "CURRENT"]:
                        modifiers.temporality = "recent"
                    elif modifier.category in ["HISTORICAL", "PRIOR"]:
                        modifiers.temporality = "historical"

            mapping = self.risk_factor_mapping.get(code, {})

            feature = ParsedFeature(
                code=code,
                label=mapping.get('label', code.replace('_', ' ').title()),
                text=span.text,
                source="quickumls",
                confidence=0.8,
                modifiers=modifiers
            )
            features.append(feature)

        return features

    def _extract_bert_features(self, text: str) -> List[ParsedFeature]:
        """Extract features using BERT NER"""
        if not self.bert_pipeline:
            return []

        features = []
        try:
            # Run BERT pipeline
            entities = self.bert_pipeline(text)

            for entity in entities:
                # Map BERT labels to Meridian codes (simplified)
                code = self._map_bert_label(entity['entity_group'])
                if code and code in self.risk_factor_mapping:
                    mapping = self.risk_factor_mapping[code]

                    feature = ParsedFeature(
                        code=code,
                        label=mapping.get('label', code.replace('_', ' ').title()),
                        text=entity['word'],
                        source="bert",
                        confidence=entity['score'],
                        modifiers=Modifier()
                    )
                    features.append(feature)

        except Exception as e:
            logger.warning(f"BERT extraction failed: {e}")

        return features

    def _map_bert_label(self, bert_label: str) -> Optional[str]:
        """Map BERT entity labels to Meridian codes"""
        label_mapping = {
            'DISEASE': 'ASTHMA',  # Simplified mapping
            'SYMPTOM': 'FEVER_CURRENT',
            'MEDICATION': 'INHALED_STEROIDS',
            'PROCEDURE': 'ENT_CASE'
        }
        return label_mapping.get(bert_label)

    def _extract_modifiers(self, text: str, start: int, end: int) -> Modifier:
        """Extract modifiers (negation, temporality) around a span"""
        modifiers = Modifier()

        # Look for negation ONLY BEFORE the medical condition to avoid false positives
        # This prevents "No other significant medical history" from negating previous conditions
        window_start = max(0, start - 50)
        context_before = text[window_start:start].lower()

        # Check for negation in the preceding context only
        negation_patterns = self.rules.get('negation_patterns', [])
        for pattern in negation_patterns:
            # Look for negation patterns that are close to our medical condition
            # and not separated by sentence boundaries
            matches = list(re.finditer(pattern, context_before))
            if matches:
                # Check if the negation is in the same sentence/clause
                last_match = matches[-1]
                neg_end = window_start + last_match.end()

                # Look for sentence boundaries between negation and medical condition
                intervening_text = text[neg_end:start]

                # If there's a sentence break (period followed by capital letter),
                # don't apply the negation
                if not re.search(r'\.\s+[A-Z]', intervening_text):
                    # Also check if there are conflicting positive indicators
                    positive_indicators = ['significant for', 'history of', 'diagnosed with',
                                         'presents with', 'h/o', 'hx of']
                    has_positive = any(re.search(indicator, text[neg_end:start], re.I)
                                     for indicator in positive_indicators)

                    if not has_positive:
                        modifiers.negated = True
                        break

        # Check for temporality in broader context
        window_end = min(len(text), end + 20)
        context = text[window_start:window_end].lower()
        temp_patterns = self.rules.get('temporality_patterns', {})
        for temporality, patterns in temp_patterns.items():
            for pattern in patterns:
                if re.search(pattern, context):
                    modifiers.temporality = temporality
                    break

        return modifiers

    def _resolve_features(self, features: List[ParsedFeature]) -> List[ParsedFeature]:
        """Resolve conflicts and deduplicate features"""
        # Group by code
        feature_groups = {}
        for feature in features:
            if feature.code not in feature_groups:
                feature_groups[feature.code] = []
            feature_groups[feature.code].append(feature)

        resolved = []
        for code, group in feature_groups.items():
            if len(group) == 1:
                resolved.append(group[0])
            else:
                # Prefer rule > quickumls > bert
                best = group[0]
                for feature in group[1:]:
                    if self._is_better_source(feature.source, best.source):
                        best = feature
                    elif feature.source == best.source and feature.confidence > best.confidence:
                        best = feature
                resolved.append(best)

        return resolved

    def _is_better_source(self, source1: str, source2: str) -> bool:
        """Determine if source1 is better than source2"""
        priority = {"rule": 3, "quickumls": 2, "bert": 1}
        return priority.get(source1, 0) > priority.get(source2, 0)


# Global pipeline instance
_pipeline = None

def build_nlp(use_bert: bool = False) -> MeridianNLPPipeline:
    """Build and return NLP pipeline"""
    global _pipeline
    if _pipeline is None:
        _pipeline = MeridianNLPPipeline(use_bert=use_bert)
    return _pipeline

def parse_hpi(text: str) -> ParsedHPI:
    """Parse HPI text and return structured results"""
    pipeline = build_nlp()
    return pipeline.parse_hpi(text)