"""
Evidence harvest system with PubMed integration.
Outcome-first approach with comprehensive effect extraction and quality grading.
"""

import requests
import xml.etree.ElementTree as ET
import json
import re
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
from datetime import datetime, timedelta
import os

from ..core.database import get_database

logger = logging.getLogger(__name__)

@dataclass
class PubMedPaper:
    pmid: str
    title: str
    abstract: str
    journal: str
    year: int
    design: str
    n_total: Optional[int]
    population: str  # adult, peds, mixed
    procedure: str
    time_horizon: str
    url: str
    raw_path: str
    ingest_query_id: str
    doi: Optional[str] = None
    authors: List[str] = None
    keywords: List[str] = None
    mesh_terms: List[str] = None
    study_quality_score: float = 0.0
    evidence_grade: str = "D"

@dataclass
class EffectEstimate:
    id: str
    pmid: str
    outcome_token: str
    modifier_token: Optional[str]
    measure: str  # OR, RR, HR, INCIDENCE
    estimate: float
    ci_low: Optional[float]
    ci_high: Optional[float]
    adjusted: bool
    n_group: Optional[int]
    n_events: Optional[int]
    definition_note: str
    time_horizon: str
    quality_weight: float
    evidence_grade: str
    population_match: float
    extraction_confidence: float
    covariates: List[str]
    subgroup: str

class PubMedHarvester:
    """
    Comprehensive PubMed evidence harvester with outcome-first queries,
    effect extraction, and quality grading.
    """

    def __init__(self, api_key: str = None, email: str = "codex@anesthesia.ai"):
        self.api_key = api_key or os.getenv("NCBI_API_KEY")
        self.email = email
        self.base_search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        self.base_fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        self.db = get_database()

        # Rate limiting
        self.requests_per_second = 10 if self.api_key else 3
        self.last_request_time = 0

        # Effect pattern matchers
        self.effect_patterns = self._build_effect_patterns()

        # Quality scoring weights
        self.design_weights = {
            "systematic review": 5.0,
            "meta-analysis": 5.0,
            "randomized controlled trial": 4.0,
            "rct": 4.0,
            "prospective cohort": 3.0,
            "retrospective cohort": 2.5,
            "case-control": 2.0,
            "cross-sectional": 1.5,
            "case series": 1.0,
            "case report": 0.5
        }

    def _build_effect_patterns(self) -> List[re.Pattern]:
        """Build regex patterns for extracting effect estimates."""
        patterns = [
            # Odds ratios
            re.compile(r"\b(?:OR|odds\s+ratio)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:\(([0-9.]+)\s*[-–]\s*([0-9.]+)\))?", re.I),
            re.compile(r"\bodds\s+ratio\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)", re.I),

            # Relative risks
            re.compile(r"\b(?:RR|relative\s+risk)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:\(([0-9.]+)\s*[-–]\s*([0-9.]+)\))?", re.I),
            re.compile(r"\brisk\s+ratio\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)", re.I),

            # Hazard ratios
            re.compile(r"\b(?:HR|hazard\s+ratio)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:\(([0-9.]+)\s*[-–]\s*([0-9.]+)\))?", re.I),

            # Incidence rates
            re.compile(r"\bincidence\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*%", re.I),
            re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*%\s*(?:of|in)", re.I),
            re.compile(r"([0-9]+)\s*\/\s*([0-9]+)", re.I),  # n/N format

            # Multiplier expressions
            re.compile(r"\b([0-9]+(?:\.[0-9]+)?)\s*(?:times|fold)\s+(?:higher|increased|greater|more\s+likely)", re.I),
            re.compile(r"\b([0-9]+(?:\.[0-9]+)?)\s*×\s*(?:higher|increased)", re.I),

            # P-values and significance
            re.compile(r"\bp\s*[<>=]\s*([0-9.]+)", re.I),
            re.compile(r"\bp-value\s*[:=]?\s*([0-9.]+)", re.I),
        ]
        return patterns

    def _rate_limit(self):
        """Enforce rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.requests_per_second

        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def search_pubmed(self, query: str, max_results: int = 100) -> List[str]:
        """Search PubMed and return PMIDs."""
        self._rate_limit()

        params = {
            "db": "pubmed",
            "retmode": "json",
            "term": query,
            "retmax": max_results,
            "email": self.email,
            "sort": "relevance"
        }

        if self.api_key:
            params["api_key"] = self.api_key

        try:
            response = requests.get(self.base_search_url, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()

            pmids = result.get("esearchresult", {}).get("idlist", [])
            logger.info(f"Found {len(pmids)} PMIDs for query: {query[:100]}...")

            return pmids

        except requests.RequestException as e:
            logger.error(f"PubMed search error: {e}")
            return []

    def fetch_papers(self, pmids: List[str]) -> List[PubMedPaper]:
        """Fetch detailed paper information from PMIDs."""
        if not pmids:
            return []

        # Batch PMIDs (max 200 per request)
        batch_size = 200
        all_papers = []

        for i in range(0, len(pmids), batch_size):
            batch_pmids = pmids[i:i + batch_size]
            batch_papers = self._fetch_batch(batch_pmids)
            all_papers.extend(batch_papers)

            # Rate limit between batches
            if i + batch_size < len(pmids):
                time.sleep(0.5)

        return all_papers

    def _fetch_batch(self, pmids: List[str]) -> List[PubMedPaper]:
        """Fetch a batch of papers."""
        self._rate_limit()

        params = {
            "db": "pubmed",
            "retmode": "xml",
            "id": ",".join(pmids),
            "email": self.email
        }

        if self.api_key:
            params["api_key"] = self.api_key

        try:
            response = requests.get(self.base_fetch_url, params=params, timeout=60)
            response.raise_for_status()

            # Save raw XML
            xml_content = response.text
            raw_path = self._save_raw_xml(pmids, xml_content)

            # Parse XML
            papers = self._parse_pubmed_xml(xml_content, raw_path)
            return papers

        except requests.RequestException as e:
            logger.error(f"PubMed fetch error: {e}")
            return []

    def _save_raw_xml(self, pmids: List[str], xml_content: str) -> str:
        """Save raw XML for audit trail."""
        # Create hash for filename
        content_hash = hashlib.md5(xml_content.encode()).hexdigest()
        filename = f"pubmed_batch_{content_hash}.xml"

        raw_dir = Path("database/raw_xml")
        raw_dir.mkdir(parents=True, exist_ok=True)

        filepath = raw_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(xml_content)

        return str(filepath)

    def _parse_pubmed_xml(self, xml_content: str, raw_path: str) -> List[PubMedPaper]:
        """Parse PubMed XML into structured papers."""
        papers = []

        try:
            root = ET.fromstring(xml_content)
            articles = root.findall('.//PubmedArticle')

            for article in articles:
                paper = self._parse_single_article(article, raw_path)
                if paper:
                    papers.append(paper)

        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")

        return papers

    def _parse_single_article(self, article: ET.Element, raw_path: str) -> Optional[PubMedPaper]:
        """Parse a single PubMed article."""
        try:
            # Extract PMID
            pmid_elem = article.find('.//PMID')
            if pmid_elem is None:
                return None
            pmid = pmid_elem.text

            # Extract basic fields
            title_elem = article.find('.//ArticleTitle')
            title = self._clean_text(title_elem.text if title_elem is not None else "")

            # Extract abstract
            abstract_parts = []
            for abstract_elem in article.findall('.//AbstractText'):
                if abstract_elem.text:
                    label = abstract_elem.get('Label', '')
                    text = abstract_elem.text
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    else:
                        abstract_parts.append(text)

            abstract = " ".join(abstract_parts) if abstract_parts else ""

            # Extract journal
            journal_elem = article.find('.//Journal/Title')
            journal = journal_elem.text if journal_elem is not None else ""

            # Extract year
            year_elem = article.find('.//PubDate/Year')
            year = int(year_elem.text) if year_elem is not None and year_elem.text.isdigit() else 0

            # Extract authors
            authors = []
            for author in article.findall('.//Author')[:5]:  # First 5 authors
                lastname = author.find('LastName')
                initials = author.find('Initials')
                if lastname is not None:
                    author_name = lastname.text
                    if initials is not None:
                        author_name += f" {initials.text}"
                    authors.append(author_name)

            # Extract DOI
            doi = None
            for article_id in article.findall('.//ArticleId'):
                if article_id.get('IdType') == 'doi':
                    doi = article_id.text
                    break

            # Extract MeSH terms
            mesh_terms = []
            for mesh in article.findall('.//MeshHeading/DescriptorName'):
                if mesh.text:
                    mesh_terms.append(mesh.text)

            # Classify study design and population
            design = self._classify_study_design(title + " " + abstract)
            population = self._classify_population(title + " " + abstract)
            procedure = self._extract_procedure(title + " " + abstract)
            time_horizon = self._extract_time_horizon(abstract)

            # Quality grading
            evidence_grade, quality_score = self._grade_evidence(design, journal, year, abstract)

            paper = PubMedPaper(
                pmid=pmid,
                title=title,
                abstract=abstract,
                journal=journal,
                year=year,
                design=design,
                n_total=self._extract_sample_size(abstract),
                population=population,
                procedure=procedure,
                time_horizon=time_horizon,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                raw_path=raw_path,
                ingest_query_id="",  # Set by caller
                doi=doi,
                authors=authors,
                mesh_terms=mesh_terms,
                study_quality_score=quality_score,
                evidence_grade=evidence_grade
            )

            return paper

        except Exception as e:
            logger.error(f"Error parsing article: {e}")
            return None

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""

        # Remove HTML entities
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&amp;", "&").replace("&quot;", '"')
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _classify_study_design(self, text: str) -> str:
        """Classify study design from text."""
        text_lower = text.lower()

        if any(term in text_lower for term in ["systematic review", "meta-analysis"]):
            if "meta-analysis" in text_lower:
                return "meta-analysis"
            return "systematic review"
        elif any(term in text_lower for term in ["randomized", "randomised", "rct"]):
            return "randomized controlled trial"
        elif any(term in text_lower for term in ["prospective", "cohort"]):
            return "prospective cohort"
        elif any(term in text_lower for term in ["retrospective", "case-control"]):
            if "case-control" in text_lower:
                return "case-control"
            return "retrospective cohort"
        elif "cross-sectional" in text_lower:
            return "cross-sectional"
        elif "case series" in text_lower:
            return "case series"
        elif "case report" in text_lower:
            return "case report"
        else:
            return "observational"

    def _classify_population(self, text: str) -> str:
        """Classify patient population."""
        text_lower = text.lower()

        peds_terms = ["pediatric", "paediatric", "child", "infant", "neonate",
                     "adolescent", "children", "kids"]
        adult_terms = ["adult", "elderly", "geriatric"]

        has_peds = any(term in text_lower for term in peds_terms)
        has_adult = any(term in text_lower for term in adult_terms)

        if has_peds and has_adult:
            return "mixed"
        elif has_peds:
            return "pediatric"
        elif has_adult:
            return "adult"
        else:
            return "unknown"

    def _extract_procedure(self, text: str) -> str:
        """Extract surgical procedure from text."""
        text_lower = text.lower()

        procedures = {
            "tonsillectomy": ["tonsillectomy", "tonsil"],
            "adenoidectomy": ["adenoidectomy", "adenoid"],
            "cardiac": ["cardiac", "heart", "cardiothoracic"],
            "neurosurgery": ["neurosurg", "brain", "craniotomy"],
            "orthopedic": ["orthoped", "fracture", "joint"],
            "general": ["laparoscop", "appendectomy", "cholecystectomy"]
        }

        for procedure, terms in procedures.items():
            if any(term in text_lower for term in terms):
                return procedure

        return "unknown"

    def _extract_time_horizon(self, text: str) -> str:
        """Extract outcome time horizon."""
        text_lower = text.lower()

        if "24 hour" in text_lower or "24-hour" in text_lower:
            return "24h"
        elif "30 day" in text_lower or "30-day" in text_lower:
            return "30d"
        elif "in-hospital" in text_lower or "inhospital" in text_lower:
            return "in-hospital"
        elif "postoperative" in text_lower:
            return "postoperative"
        else:
            return "unspecified"

    def _extract_sample_size(self, text: str) -> Optional[int]:
        """Extract sample size from abstract."""
        # Look for patterns like "n = 123", "N = 456", "123 patients"
        patterns = [
            re.compile(r"n\s*=\s*([0-9,]+)", re.I),
            re.compile(r"N\s*=\s*([0-9,]+)", re.I),
            re.compile(r"([0-9,]+)\s+patients", re.I),
            re.compile(r"([0-9,]+)\s+subjects", re.I),
        ]

        for pattern in patterns:
            match = pattern.search(text)
            if match:
                try:
                    return int(match.group(1).replace(",", ""))
                except ValueError:
                    continue

        return None

    def _grade_evidence(self, design: str, journal: str, year: int, abstract: str) -> Tuple[str, float]:
        """Grade evidence quality (A-D) and assign quality score."""

        # Base score from study design
        base_score = self.design_weights.get(design.lower(), 1.0)

        # Adjust for year (more recent = better)
        year_adjustment = min(1.0, (year - 2000) / 20.0) if year > 2000 else 0.5

        # Adjust for sample size
        sample_size = self._extract_sample_size(abstract)
        size_adjustment = 1.0
        if sample_size:
            if sample_size >= 1000:
                size_adjustment = 1.2
            elif sample_size >= 100:
                size_adjustment = 1.1
            elif sample_size < 20:
                size_adjustment = 0.8

        # Adjust for statistical reporting
        stats_adjustment = 1.0
        if any(term in abstract.lower() for term in ["confidence interval", "95% ci", "p <"]):
            stats_adjustment = 1.1

        # Calculate final score
        quality_score = base_score * year_adjustment * size_adjustment * stats_adjustment

        # Assign grade
        if quality_score >= 4.0:
            grade = "A"
        elif quality_score >= 3.0:
            grade = "B"
        elif quality_score >= 2.0:
            grade = "C"
        else:
            grade = "D"

        return grade, quality_score

    def extract_effects(self, paper: PubMedPaper, outcome_tokens: List[str]) -> List[EffectEstimate]:
        """Extract effect estimates from a paper."""
        effects = []
        text = f"{paper.title} {paper.abstract}"

        # Extract all numerical estimates
        for pattern in self.effect_patterns:
            for match in pattern.finditer(text):
                effect = self._parse_effect_match(match, paper, outcome_tokens, text)
                if effect:
                    effects.append(effect)

        return effects

    def _parse_effect_match(self, match: re.Match, paper: PubMedPaper,
                          outcome_tokens: List[str], text: str) -> Optional[EffectEstimate]:
        """Parse a regex match into an effect estimate."""
        try:
            # Extract estimate value
            estimate = float(match.group(1))

            # Skip unreasonable values
            if estimate <= 0 or estimate > 100:
                return None

            # Extract confidence interval if present
            ci_low = ci_high = None
            if len(match.groups()) >= 3 and match.group(2) and match.group(3):
                ci_low = float(match.group(2))
                ci_high = float(match.group(3))

            # Determine measure type from context
            context = text[max(0, match.start()-100):match.end()+100].lower()
            if any(term in context for term in ["odds ratio", "or ="]):
                measure = "OR"
            elif any(term in context for term in ["relative risk", "rr ="]):
                measure = "RR"
            elif any(term in context for term in ["hazard ratio", "hr ="]):
                measure = "HR"
            elif "%" in match.group(0) or "/" in match.group(0):
                measure = "INCIDENCE"
            else:
                measure = "OR"  # Default assumption

            # Try to identify outcome from context
            outcome_token = self._identify_outcome(context, outcome_tokens)
            if not outcome_token:
                return None

            # Generate unique ID
            effect_id = f"{paper.pmid}_{outcome_token}_{measure}_{estimate}"

            # Determine if adjusted
            adjusted = any(term in context for term in ["adjusted", "multivariate", "multivariable"])

            # Extract sample information
            n_group = self._extract_group_size(context)
            n_events = self._extract_event_count(context)

            effect = EffectEstimate(
                id=effect_id,
                pmid=paper.pmid,
                outcome_token=outcome_token,
                modifier_token=None,  # Will be determined later
                measure=measure,
                estimate=estimate,
                ci_low=ci_low,
                ci_high=ci_high,
                adjusted=adjusted,
                n_group=n_group,
                n_events=n_events,
                definition_note=context[:200],
                time_horizon=paper.time_horizon,
                quality_weight=paper.study_quality_score,
                evidence_grade=paper.evidence_grade,
                population_match=1.0,  # Will be calculated
                extraction_confidence=self._calculate_extraction_confidence(match, context),
                covariates=self._extract_covariates(context),
                subgroup=""
            )

            return effect

        except (ValueError, IndexError):
            return None

    def _identify_outcome(self, context: str, outcome_tokens: List[str]) -> Optional[str]:
        """Identify which outcome this effect estimate refers to."""
        context_lower = context.lower()

        # Check for direct matches
        for token in outcome_tokens:
            # Get synonyms from ontology
            # For now, simple keyword matching
            if any(keyword in context_lower for keyword in [
                "bronchospasm", "laryngospasm", "hypotension", "mortality",
                "bleeding", "infection", "pneumonia"
            ]):
                return token

        return None

    def _extract_group_size(self, context: str) -> Optional[int]:
        """Extract group size from context."""
        # Simple pattern matching for group sizes
        pattern = re.compile(r"([0-9]+)\s+(?:patients|subjects|participants)")
        match = pattern.search(context)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    def _extract_event_count(self, context: str) -> Optional[int]:
        """Extract event count from context."""
        # Look for "X events" or "X/Y" patterns
        patterns = [
            re.compile(r"([0-9]+)\s+events"),
            re.compile(r"([0-9]+)\s+cases"),
            re.compile(r"([0-9]+)/[0-9]+")
        ]

        for pattern in patterns:
            match = pattern.search(context)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        return None

    def _calculate_extraction_confidence(self, match: re.Match, context: str) -> float:
        """Calculate confidence in the extraction."""
        confidence = 1.0

        # Reduce confidence if context is ambiguous
        if len(context.strip()) < 50:
            confidence *= 0.8

        # Increase confidence if CI is present
        if len(match.groups()) >= 3 and match.group(2):
            confidence *= 1.2

        # Check for statistical significance mentions
        if any(term in context.lower() for term in ["p <", "significant", "ci"]):
            confidence *= 1.1

        return min(confidence, 1.0)

    def _extract_covariates(self, context: str) -> List[str]:
        """Extract covariates from adjustment description."""
        covariates = []
        context_lower = context.lower()

        # Common covariates in anesthesia literature
        covariate_terms = [
            "age", "sex", "bmi", "asa", "emergency", "duration",
            "comorbidities", "smoking", "diabetes", "hypertension"
        ]

        for term in covariate_terms:
            if term in context_lower:
                covariates.append(term)

        return covariates

    def harvest_outcome(self, outcome_token: str, population: str = "both") -> List[PubMedPaper]:
        """Harvest evidence for a specific outcome."""

        # Build search query
        query = self._build_outcome_query(outcome_token, population)

        # Search PubMed
        pmids = self.search_pubmed(query, max_results=200)

        if not pmids:
            logger.warning(f"No results found for outcome: {outcome_token}")
            return []

        # Fetch papers
        papers = self.fetch_papers(pmids)

        # Store in database
        for paper in papers:
            paper.ingest_query_id = f"{outcome_token}_{population}_{datetime.now().isoformat()}"
            self._store_paper(paper)

        logger.info(f"Harvested {len(papers)} papers for outcome: {outcome_token}")
        return papers

    def _build_outcome_query(self, outcome_token: str, population: str) -> str:
        """Build PubMed search query for an outcome."""

        # Outcome-specific terms (simplified for demo)
        outcome_terms = {
            "BRONCHOSPASM": "bronchospasm OR wheeze OR \"bronchial spasm\"",
            "LARYNGOSPASM": "laryngospasm OR \"laryngeal spasm\"",
            "HYPOTENSION": "hypotension OR \"low blood pressure\"",
            "MORTALITY": "mortality OR death OR \"cardiac arrest\"",
        }

        base_query = outcome_terms.get(outcome_token, outcome_token.lower())

        # Add anesthesia context
        anesthesia_terms = "(anesthesia OR anaesthesia OR perioperative OR surgical)"

        # Add population filter
        if population == "pediatric":
            pop_terms = "(pediatric OR paediatric OR child OR infant OR neonate)"
        elif population == "adult":
            pop_terms = "(adult OR elderly)"
        else:
            pop_terms = ""

        # Date filter (last 15 years)
        date_filter = "2008:3000[dp]"

        # Combine query components
        query_parts = [f"({base_query})", anesthesia_terms]
        if pop_terms:
            query_parts.append(pop_terms)
        query_parts.append(date_filter)

        return " AND ".join(query_parts)

    def _store_paper(self, paper: PubMedPaper):
        """Store paper in database."""
        try:
            self.db.conn.execute("""
                INSERT OR REPLACE INTO papers
                (pmid, title, abstract, journal, year, design, n_total, population,
                 procedure, time_horizon, url, raw_path, ingest_query_id, doi,
                 authors, keywords, mesh_terms, study_quality_score, evidence_grade)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                paper.pmid, paper.title, paper.abstract, paper.journal, paper.year,
                paper.design, paper.n_total, paper.population, paper.procedure,
                paper.time_horizon, paper.url, paper.raw_path, paper.ingest_query_id,
                paper.doi, json.dumps(paper.authors or []),
                json.dumps(paper.keywords or []), json.dumps(paper.mesh_terms or []),
                paper.study_quality_score, paper.evidence_grade
            ])

            # Log the action
            self.db.log_action("papers", paper.pmid, "INSERT", asdict(paper))

        except Exception as e:
            logger.error(f"Error storing paper {paper.pmid}: {e}")

    def store_effect(self, effect: EffectEstimate):
        """Store effect estimate in database."""
        try:
            self.db.conn.execute("""
                INSERT OR REPLACE INTO estimates
                (id, pmid, outcome_token, modifier_token, measure, estimate,
                 ci_low, ci_high, adjusted, n_group, n_events, definition_note,
                 time_horizon, quality_weight, evidence_grade, population_match,
                 extraction_confidence, covariates, subgroup)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                effect.id, effect.pmid, effect.outcome_token, effect.modifier_token,
                effect.measure, effect.estimate, effect.ci_low, effect.ci_high,
                effect.adjusted, effect.n_group, effect.n_events, effect.definition_note,
                effect.time_horizon, effect.quality_weight, effect.evidence_grade,
                effect.population_match, effect.extraction_confidence,
                json.dumps(effect.covariates), effect.subgroup
            ])

            # Log the action
            self.db.log_action("estimates", effect.id, "INSERT", asdict(effect))

        except Exception as e:
            logger.error(f"Error storing effect {effect.id}: {e}")