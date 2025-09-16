"""
Evidence Referencing and Citation System for Meridian
Provides comprehensive citation generation and evidence linking for all clinical recommendations
"""

import json
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import logging

from ..core.database import get_database
from ..ontology.core_ontology import AnesthesiaOntology

logger = logging.getLogger(__name__)

@dataclass
class EvidenceCitation:
    """Structured citation with all necessary components."""
    pmid: str
    title: str
    authors: List[str]
    journal: str
    year: int
    citation_text: str
    evidence_grade: str
    clinical_relevance: float
    citation_type: str  # primary_evidence, supporting_evidence, guideline
    page_reference: Optional[str] = None
    figure_table_reference: Optional[str] = None
    doi: Optional[str] = None
    pubmed_url: str = ""

    def __post_init__(self):
        self.pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"

@dataclass
class PooledEvidenceSummary:
    """Summary of pooled evidence for an outcome-risk factor combination."""
    outcome_token: str
    modifier_token: Optional[str]
    pooled_estimate: float
    ci_low: float
    ci_high: float
    n_studies: int
    total_n: int
    evidence_grade: str
    heterogeneity_i2: Optional[float]
    contributing_citations: List[EvidenceCitation]
    last_updated: datetime

class EvidenceReferencingEngine:
    """
    Comprehensive evidence referencing system for Meridian.
    Generates proper citations, links evidence to recommendations,
    and provides audit trails for all clinical guidance.
    """

    def __init__(self):
        self.db = get_database()
        self.ontology = AnesthesiaOntology()

    def get_outcome_evidence_summary(self, outcome_token: str,
                                   modifier_token: str = None,
                                   population: str = "mixed") -> Optional[PooledEvidenceSummary]:
        """Get comprehensive evidence summary for an outcome."""

        # Get pooled estimate
        pooled_query = """
            SELECT * FROM pooled_estimates
            WHERE outcome_token = ?
            AND (modifier_token = ? OR (modifier_token IS NULL AND ? IS NULL))
            AND (population = ? OR population = 'mixed')
            ORDER BY evidence_grade, last_updated DESC
            LIMIT 1
        """

        pooled_result = self.db.conn.execute(pooled_query, [
            outcome_token, modifier_token, modifier_token, population
        ]).fetchone()

        if not pooled_result:
            logger.warning(f"No pooled evidence found for {outcome_token} + {modifier_token}")
            return None

        # Get contributing citations
        contributing_pmids = json.loads(pooled_result[8] or "[]")  # contributing_pmids column
        citations = self._get_citations_for_pmids(contributing_pmids, outcome_token, modifier_token)

        return PooledEvidenceSummary(
            outcome_token=outcome_token,
            modifier_token=modifier_token,
            pooled_estimate=pooled_result[4],  # pooled_estimate
            ci_low=pooled_result[5],           # pooled_ci_low
            ci_high=pooled_result[6],          # pooled_ci_high
            n_studies=pooled_result[8],        # n_studies
            total_n=pooled_result[9] or 0,     # total_n
            evidence_grade=pooled_result[10],  # evidence_grade
            heterogeneity_i2=pooled_result[7], # heterogeneity_i2
            contributing_citations=citations,
            last_updated=datetime.fromisoformat(pooled_result[12])  # last_updated
        )

    def _get_citations_for_pmids(self, pmids: List[str], outcome_token: str,
                                modifier_token: str = None) -> List[EvidenceCitation]:
        """Get formatted citations for a list of PMIDs."""
        citations = []

        for pmid in pmids:
            citation = self._create_citation_for_pmid(pmid, outcome_token, modifier_token)
            if citation:
                citations.append(citation)

        return citations

    def _create_citation_for_pmid(self, pmid: str, outcome_token: str,
                                 modifier_token: str = None) -> Optional[EvidenceCitation]:
        """Create formatted citation for a single PMID."""

        # Get paper details
        paper_query = """
            SELECT pmid, title, journal, year, authors, doi, evidence_grade
            FROM papers
            WHERE pmid = ?
        """

        paper = self.db.conn.execute(paper_query, [pmid]).fetchone()
        if not paper:
            return None

        # Get specific evidence from this paper
        evidence_query = """
            SELECT definition_note, estimate, ci_low, ci_high, extraction_confidence
            FROM estimates
            WHERE pmid = ? AND outcome_token = ?
            AND (modifier_token = ? OR (modifier_token IS NULL AND ? IS NULL))
            ORDER BY extraction_confidence DESC
            LIMIT 1
        """

        evidence = self.db.conn.execute(evidence_query, [
            pmid, outcome_token, modifier_token, modifier_token
        ]).fetchone()

        # Parse authors
        authors = json.loads(paper[4] or "[]")

        # Generate citation text
        citation_text = self._format_citation_text(evidence, outcome_token, modifier_token)

        # Determine citation type
        citation_type = "primary_evidence"
        if evidence and evidence[4] < 0.7:  # Low extraction confidence
            citation_type = "supporting_evidence"

        # Calculate clinical relevance
        clinical_relevance = self._calculate_clinical_relevance(evidence, paper[6])

        return EvidenceCitation(
            pmid=pmid,
            title=paper[1],
            authors=authors[:3],  # First 3 authors
            journal=paper[2],
            year=paper[3],
            citation_text=citation_text,
            evidence_grade=paper[6],
            clinical_relevance=clinical_relevance,
            citation_type=citation_type,
            doi=paper[5]
        )

    def _format_citation_text(self, evidence, outcome_token: str, modifier_token: str = None) -> str:
        """Format the clinical evidence text for citation."""

        outcome_term = self.ontology.terms.get(outcome_token)
        outcome_name = outcome_term.plain_label if outcome_term else outcome_token

        if not evidence:
            return f"Risk of {outcome_name.lower()}"

        estimate = evidence[1]
        ci_low = evidence[2]
        ci_high = evidence[3]

        # Format based on modifier
        if modifier_token:
            modifier_term = self.ontology.terms.get(modifier_token)
            modifier_name = modifier_term.plain_label if modifier_term else modifier_token

            if ci_low and ci_high:
                return f"{modifier_name} increases risk of {outcome_name.lower()} (OR {estimate:.1f}, 95% CI {ci_low:.1f}-{ci_high:.1f})"
            else:
                return f"{modifier_name} increases risk of {outcome_name.lower()} (OR {estimate:.1f})"
        else:
            # Baseline incidence
            if estimate < 1:
                percentage = estimate * 100
                return f"Baseline incidence of {outcome_name.lower()} is {percentage:.1f}%"
            else:
                return f"Risk of {outcome_name.lower()}"

    def _calculate_clinical_relevance(self, evidence, evidence_grade: str) -> float:
        """Calculate clinical relevance score (0-1)."""
        base_score = 0.8

        # Adjust for evidence grade
        grade_adjustments = {"A": 1.0, "B": 0.9, "C": 0.7, "D": 0.5}
        grade_mult = grade_adjustments.get(evidence_grade, 0.5)

        # Adjust for extraction confidence
        conf_mult = 1.0
        if evidence and evidence[4]:  # extraction_confidence
            conf_mult = min(evidence[4], 1.0)

        return min(base_score * grade_mult * conf_mult, 1.0)

    def generate_risk_calculation_citations(self, outcome_token: str,
                                          risk_factors: List[str]) -> Dict[str, Any]:
        """Generate comprehensive citations for a risk calculation."""

        citations_data = {
            "outcome": outcome_token,
            "baseline_evidence": None,
            "risk_factor_evidence": {},
            "overall_evidence_grade": "D",
            "citation_count": 0,
            "last_updated": datetime.now().isoformat()
        }

        # Get baseline evidence
        baseline_summary = self.get_outcome_evidence_summary(outcome_token, None)
        if baseline_summary:
            citations_data["baseline_evidence"] = {
                "summary": asdict(baseline_summary),
                "citations": [asdict(c) for c in baseline_summary.contributing_citations]
            }
            citations_data["overall_evidence_grade"] = baseline_summary.evidence_grade
            citations_data["citation_count"] += len(baseline_summary.contributing_citations)

        # Get evidence for each risk factor
        evidence_grades = []
        for rf_token in risk_factors:
            rf_summary = self.get_outcome_evidence_summary(outcome_token, rf_token)
            if rf_summary:
                citations_data["risk_factor_evidence"][rf_token] = {
                    "summary": asdict(rf_summary),
                    "citations": [asdict(c) for c in rf_summary.contributing_citations]
                }
                evidence_grades.append(rf_summary.evidence_grade)
                citations_data["citation_count"] += len(rf_summary.contributing_citations)

        # Calculate overall evidence grade
        if evidence_grades:
            # Use the lowest grade as overall grade
            grade_order = {"A": 4, "B": 3, "C": 2, "D": 1}
            min_grade_value = min(grade_order.get(g, 1) for g in evidence_grades)
            citations_data["overall_evidence_grade"] = next(
                g for g, v in grade_order.items() if v == min_grade_value
            )

        return citations_data

    def generate_medication_citations(self, medication_token: str,
                                    indication: str = None,
                                    contraindication: str = None) -> Dict[str, Any]:
        """Generate citations for medication recommendations."""

        citations_data = {
            "medication": medication_token,
            "indication": indication,
            "contraindication": contraindication,
            "guideline_citations": [],
            "evidence_citations": [],
            "evidence_grade": "D",
            "last_updated": datetime.now().isoformat()
        }

        # Get guideline citations
        guideline_query = """
            SELECT society, year, title, statement, class, strength, link
            FROM guidelines
            WHERE med_tokens LIKE ?
            ORDER BY year DESC, strength
        """

        guideline_pattern = f'%"{medication_token}"%'
        guidelines = self.db.conn.execute(guideline_query, [guideline_pattern]).fetchall()

        for guideline in guidelines[:5]:  # Top 5 most recent guidelines
            citations_data["guideline_citations"].append({
                "society": guideline[0],
                "year": guideline[1],
                "title": guideline[2],
                "statement": guideline[3],
                "class": guideline[4],
                "strength": guideline[5],
                "link": guideline[6]
            })

        # Get evidence from literature if available
        # This would link to papers that mention the medication in context
        evidence_query = """
            SELECT DISTINCT p.pmid, p.title, p.journal, p.year, p.authors, p.evidence_grade
            FROM papers p
            JOIN estimates e ON p.pmid = e.pmid
            WHERE p.abstract LIKE ? OR p.title LIKE ?
            ORDER BY p.year DESC, p.evidence_grade
            LIMIT 10
        """

        med_term = self.ontology.terms.get(medication_token)
        if med_term:
            search_terms = [med_term.plain_label] + med_term.synonyms
            for term in search_terms[:3]:  # Check top 3 synonyms
                pattern = f"%{term}%"
                evidence_papers = self.db.conn.execute(evidence_query, [pattern, pattern]).fetchall()

                for paper in evidence_papers[:3]:  # Top 3 papers per term
                    citation = {
                        "pmid": paper[0],
                        "title": paper[1],
                        "journal": paper[2],
                        "year": paper[3],
                        "authors": json.loads(paper[4] or "[]")[:2],
                        "evidence_grade": paper[5],
                        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{paper[0]}/"
                    }
                    citations_data["evidence_citations"].append(citation)

        # Determine overall evidence grade
        if citations_data["guideline_citations"]:
            # Use guideline strength as evidence grade
            strengths = [g["strength"] for g in citations_data["guideline_citations"] if g["strength"]]
            if strengths:
                citations_data["evidence_grade"] = min(strengths)  # Most conservative
        elif citations_data["evidence_citations"]:
            # Use best paper evidence grade
            grades = [p["evidence_grade"] for p in citations_data["evidence_citations"] if p["evidence_grade"]]
            if grades:
                grade_order = {"A": 4, "B": 3, "C": 2, "D": 1}
                best_grade_value = max(grade_order.get(g, 1) for g in grades)
                citations_data["evidence_grade"] = next(
                    g for g, v in grade_order.items() if v == best_grade_value
                )

        return citations_data

    def format_citations_for_ui(self, citations_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format citations for display in the UI."""

        formatted = {
            "summary": {
                "total_citations": 0,
                "evidence_grade": citations_data.get("overall_evidence_grade", "D"),
                "last_updated": citations_data.get("last_updated", "")
            },
            "sections": []
        }

        # Format baseline evidence
        if "baseline_evidence" in citations_data and citations_data["baseline_evidence"]:
            baseline = citations_data["baseline_evidence"]
            formatted["sections"].append({
                "title": "Baseline Risk Evidence",
                "evidence_grade": baseline["summary"]["evidence_grade"],
                "citations": self._format_citation_list(baseline["citations"])
            })
            formatted["summary"]["total_citations"] += len(baseline["citations"])

        # Format risk factor evidence
        if "risk_factor_evidence" in citations_data:
            for rf_token, rf_data in citations_data["risk_factor_evidence"].items():
                rf_term = self.ontology.terms.get(rf_token)
                rf_name = rf_term.plain_label if rf_term else rf_token

                formatted["sections"].append({
                    "title": f"{rf_name} Evidence",
                    "evidence_grade": rf_data["summary"]["evidence_grade"],
                    "citations": self._format_citation_list(rf_data["citations"])
                })
                formatted["summary"]["total_citations"] += len(rf_data["citations"])

        # Format medication evidence
        if "guideline_citations" in citations_data:
            if citations_data["guideline_citations"]:
                formatted["sections"].append({
                    "title": "Clinical Guidelines",
                    "evidence_grade": citations_data.get("evidence_grade", "C"),
                    "citations": self._format_guideline_list(citations_data["guideline_citations"])
                })
                formatted["summary"]["total_citations"] += len(citations_data["guideline_citations"])

        if "evidence_citations" in citations_data:
            if citations_data["evidence_citations"]:
                formatted["sections"].append({
                    "title": "Supporting Literature",
                    "evidence_grade": citations_data.get("evidence_grade", "D"),
                    "citations": self._format_citation_list(citations_data["evidence_citations"])
                })
                formatted["summary"]["total_citations"] += len(citations_data["evidence_citations"])

        return formatted

    def _format_citation_list(self, citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format citation list for UI display."""
        formatted_citations = []

        for citation in citations:
            # Handle both EvidenceCitation objects and dictionaries
            if isinstance(citation, dict):
                pmid = citation.get("pmid", "")
                title = citation.get("title", "")
                authors = citation.get("authors", [])
                journal = citation.get("journal", "")
                year = citation.get("year", "")
                evidence_grade = citation.get("evidence_grade", "D")
                citation_text = citation.get("citation_text", "")
            else:
                # Assume it's an EvidenceCitation object
                pmid = citation.pmid
                title = citation.title
                authors = citation.authors
                journal = citation.journal
                year = citation.year
                evidence_grade = citation.evidence_grade
                citation_text = citation.citation_text

            # Format author list
            if authors and len(authors) > 0:
                if len(authors) == 1:
                    author_text = authors[0]
                elif len(authors) == 2:
                    author_text = f"{authors[0]} and {authors[1]}"
                else:
                    author_text = f"{authors[0]} et al."
            else:
                author_text = "No authors listed"

            formatted_citations.append({
                "pmid": pmid,
                "display_text": f"{author_text}. {title}. {journal}. {year}.",
                "clinical_text": citation_text,
                "evidence_grade": evidence_grade,
                "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "short_citation": f"{author_text}, {journal} {year}"
            })

        return formatted_citations

    def _format_guideline_list(self, guidelines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format guideline list for UI display."""
        formatted_guidelines = []

        for guideline in guidelines:
            formatted_guidelines.append({
                "display_text": f"{guideline['society']} {guideline['year']}: {guideline['title']}",
                "statement": guideline.get("statement", ""),
                "class": guideline.get("class", ""),
                "strength": guideline.get("strength", ""),
                "evidence_grade": guideline.get("strength", "C"),
                "url": guideline.get("link", ""),
                "short_citation": f"{guideline['society']} {guideline['year']}"
            })

        return formatted_guidelines

    def store_citation(self, pmid: str, outcome_token: str, modifier_token: str,
                      citation_type: str, citation_text: str, evidence_strength: str) -> str:
        """Store a citation in the database."""

        citation_id = f"{pmid}_{outcome_token}_{modifier_token}_{citation_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            self.db.conn.execute("""
                INSERT INTO evidence_citations
                (citation_id, pmid, outcome_token, modifier_token, citation_type,
                 citation_text, evidence_strength, clinical_relevance, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                citation_id, pmid, outcome_token, modifier_token, citation_type,
                citation_text, evidence_strength, 1.0, datetime.now().isoformat()
            ])

            self.db.log_action("evidence_citations", citation_id, "INSERT", {
                "pmid": pmid,
                "outcome_token": outcome_token,
                "modifier_token": modifier_token,
                "citation_type": citation_type
            })

            return citation_id

        except Exception as e:
            logger.error(f"Error storing citation: {e}")
            return ""

def create_evidence_referencing_engine() -> EvidenceReferencingEngine:
    """Factory function to create evidence referencing engine."""
    return EvidenceReferencingEngine()