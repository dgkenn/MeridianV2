"""
Comprehensive Evidence Harvesting System for Meridian
Systematically collect evidence for all outcomes and risk factors from PubMed
Map scraped risk factors to knowledge base and improve pooled risk models
"""

import sys
import os
import json
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, asdict
import concurrent.futures
from threading import Lock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.core.database import get_database
from src.evidence.pubmed_harvester import PubMedHarvester, PubMedPaper, EffectEstimate
from src.evidence.pooling_engine import MetaAnalysisEngine
from src.ontology.core_ontology import AnesthesiaOntology

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('evidence_harvest.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class HarvestPlan:
    """Plan for systematic evidence collection."""
    outcome_token: str
    outcome_name: str
    category: str
    priority: int  # 1=highest, 5=lowest
    search_terms: List[str]
    population_filters: List[str]  # ['pediatric', 'adult', 'obstetric']
    expected_papers: int
    last_harvest: Optional[datetime]
    harvest_frequency_days: int

@dataclass
class HarvestResults:
    """Results from evidence harvest."""
    outcome_token: str
    population: str
    query_used: str
    papers_found: int
    papers_processed: int
    effects_extracted: int
    quality_grade_distribution: Dict[str, int]
    harvest_timestamp: datetime
    errors: List[str]

class ComprehensiveEvidenceHarvester:
    """
    Systematic evidence collection for all outcomes and risk factors.
    Implements intelligent querying, quality filtering, and knowledge base integration.
    """

    def __init__(self, api_key: str = None):
        self.harvester = PubMedHarvester(api_key=api_key)
        self.pooling_engine = MetaAnalysisEngine()
        self.ontology = AnesthesiaOntology()
        self.db = get_database()

        # Thread safety
        self.lock = Lock()

        # Harvest configuration
        self.max_papers_per_outcome = 500
        self.max_concurrent_harvests = 3
        self.rate_limit_delay = 0.5

        # Quality thresholds
        self.min_quality_score = 1.5
        self.min_sample_size = 50

        # Priority mappings
        self.outcome_priorities = self._define_outcome_priorities()

        # Create harvest plans
        self.harvest_plans = self._create_harvest_plans()

    def _define_outcome_priorities(self) -> Dict[str, int]:
        """Define priority levels for different outcomes."""
        return {
            # Critical outcomes (Priority 1)
            "CARDIAC_ARREST": 1,
            "MORTALITY_24H": 1,
            "MORTALITY_30D": 1,
            "MORTALITY_INHOSPITAL": 1,
            "FAILED_INTUBATION": 1,
            "CARDIOGENIC_SHOCK": 1,
            "AMNIOTIC_FLUID_EMBOLISM": 1,
            "MULTIPLE_ORGAN_DYSFUNCTION": 1,

            # High-impact outcomes (Priority 2)
            "ASPIRATION": 2,
            "LARYNGOSPASM": 2,
            "BRONCHOSPASM": 2,
            "STROKE": 2,
            "AWARENESS_UNDER_ANESTHESIA": 2,
            "PULMONARY_EMBOLISM": 2,
            "VENTRICULAR_ARRHYTHMIA": 2,
            "ARDS": 2,
            "SEPSIS": 2,
            "ACUTE_KIDNEY_INJURY": 2,

            # Moderate-impact outcomes (Priority 3)
            "DIFFICULT_INTUBATION": 3,
            "HYPOXEMIA": 3,
            "INTRAOP_HYPOTENSION": 3,
            "POSTOP_DELIRIUM": 3,
            "SURGICAL_BLEEDING": 3,
            "PNEUMONIA": 3,
            "ATRIAL_FIBRILLATION": 3,
            "SEIZURE": 3,
            "LOCAL_ANESTHETIC_TOXICITY": 3,

            # Common complications (Priority 4)
            "PONV": 4,
            "EMERGENCE_AGITATION": 4,
            "POSTOP_ILEUS": 4,
            "ATELECTASIS": 4,
            "BRADYCARDIA": 4,
            "TACHYARRHYTHMIA": 4,
            "SEVERE_ACUTE_PAIN": 4,

            # Lower-impact outcomes (Priority 5)
            "DENTAL_INJURY": 5,
            "OPIOID_PRURITUS": 5,
            "OPIOID_URINARY_RETENTION": 5,
            "BLOCK_FAILURE": 5,
        }

    def _create_harvest_plans(self) -> List[HarvestPlan]:
        """Create systematic harvest plans for all outcomes."""
        plans = []

        for token, term in self.ontology.terms.items():
            if term.type != "outcome":
                continue

            # Get priority
            priority = self.outcome_priorities.get(token, 4)

            # Build search terms
            search_terms = [term.plain_label.lower()] + [s.lower() for s in term.synonyms]

            # Determine population filters
            population_filters = ["both"]  # Default to both populations
            if "pediatric" in term.category or "PEDIATRIC" in token:
                population_filters = ["pediatric", "both"]
            elif "obstetric" in term.category or "MATERNAL" in token:
                population_filters = ["obstetric", "both"]
            else:
                population_filters = ["adult", "pediatric", "both"]

            # Estimate expected papers based on outcome type
            if priority <= 2:
                expected_papers = 200
            elif priority == 3:
                expected_papers = 150
            else:
                expected_papers = 100

            # Harvest frequency based on priority
            if priority <= 2:
                frequency_days = 30  # Monthly for critical outcomes
            elif priority == 3:
                frequency_days = 60  # Bi-monthly for moderate outcomes
            else:
                frequency_days = 90  # Quarterly for others

            plan = HarvestPlan(
                outcome_token=token,
                outcome_name=term.plain_label,
                category=term.category,
                priority=priority,
                search_terms=search_terms,
                population_filters=population_filters,
                expected_papers=expected_papers,
                last_harvest=None,
                harvest_frequency_days=frequency_days
            )

            plans.append(plan)

        # Sort by priority
        plans.sort(key=lambda x: (x.priority, x.outcome_token))

        return plans

    def run_comprehensive_harvest(self, max_outcomes: int = None,
                                priority_filter: int = None) -> List[HarvestResults]:
        """
        Run comprehensive evidence harvest across all planned outcomes.

        Args:
            max_outcomes: Maximum number of outcomes to process (None = all)
            priority_filter: Only process outcomes with this priority or higher
        """
        logger.info("Starting comprehensive evidence harvest")

        # Filter plans
        plans_to_process = self.harvest_plans.copy()

        if priority_filter:
            plans_to_process = [p for p in plans_to_process if p.priority <= priority_filter]

        if max_outcomes:
            plans_to_process = plans_to_process[:max_outcomes]

        logger.info(f"Processing {len(plans_to_process)} outcomes")

        # Process with controlled concurrency
        all_results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent_harvests) as executor:
            # Submit all harvest tasks
            future_to_plan = {}

            for plan in plans_to_process:
                for population in plan.population_filters:
                    future = executor.submit(self._harvest_outcome_population, plan, population)
                    future_to_plan[future] = (plan, population)

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_plan):
                plan, population = future_to_plan[future]
                try:
                    result = future.result()
                    all_results.append(result)
                    logger.info(f"Completed harvest for {plan.outcome_token} ({population}): "
                              f"{result.papers_found} papers, {result.effects_extracted} effects")
                except Exception as e:
                    logger.error(f"Error harvesting {plan.outcome_token} ({population}): {e}")

                # Rate limiting between completions
                time.sleep(self.rate_limit_delay)

        # Update pooled risk models
        self._update_pooled_models(all_results)

        # Generate harvest report
        self._generate_harvest_report(all_results)

        logger.info(f"Comprehensive harvest completed. Processed {len(all_results)} outcome-population combinations")

        return all_results

    def _harvest_outcome_population(self, plan: HarvestPlan, population: str) -> HarvestResults:
        """Harvest evidence for a specific outcome and population."""

        start_time = time.time()
        errors = []

        # Create harvest batch record
        batch_id = f"{plan.outcome_token}_{population}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            # Store harvest batch start
            self._create_harvest_batch(batch_id, plan, population)

            # Build optimized query
            query = self._build_optimized_query(plan, population)

            # Search PubMed
            pmids = self.harvester.search_pubmed(query, max_results=plan.expected_papers)

            if not pmids:
                self._complete_harvest_batch(batch_id, 0, 0, 0, {}, "No papers found")
                return HarvestResults(
                    outcome_token=plan.outcome_token,
                    population=population,
                    query_used=query,
                    papers_found=0,
                    papers_processed=0,
                    effects_extracted=0,
                    quality_grade_distribution={},
                    harvest_timestamp=datetime.now(),
                    errors=["No papers found"]
                )

            # Fetch papers
            papers = self.harvester.fetch_papers(pmids)

            # Filter by quality
            quality_papers = self._filter_papers_by_quality(papers)

            # Extract effects
            all_effects = []
            for paper in quality_papers:
                effects = self.harvester.extract_effects(paper, [plan.outcome_token])
                # Enhanced effect extraction with risk factor mapping
                enhanced_effects = self._enhance_effect_extraction(paper, effects, plan)

                # Link effects to harvest batch
                for effect in enhanced_effects:
                    effect.harvest_batch_id = batch_id

                all_effects.extend(enhanced_effects)

                # Store paper and effects
                self.harvester._store_paper(paper)
                for effect in enhanced_effects:
                    self.harvester.store_effect(effect)

            # Calculate quality distribution
            grade_dist = {}
            for paper in quality_papers:
                grade = paper.evidence_grade
                grade_dist[grade] = grade_dist.get(grade, 0) + 1

            # Complete harvest batch
            self._complete_harvest_batch(batch_id, len(pmids), len(quality_papers),
                                       len(all_effects), grade_dist)

            # Create risk factor mappings
            self._create_risk_factor_mappings(all_effects, plan)

            duration = time.time() - start_time
            logger.info(f"Harvested {plan.outcome_token} ({population}) in {duration:.1f}s: "
                       f"{len(papers)} papers, {len(all_effects)} effects")

            return HarvestResults(
                outcome_token=plan.outcome_token,
                population=population,
                query_used=query,
                papers_found=len(pmids),
                papers_processed=len(quality_papers),
                effects_extracted=len(all_effects),
                quality_grade_distribution=grade_dist,
                harvest_timestamp=datetime.now(),
                errors=errors
            )

        except Exception as e:
            logger.error(f"Error in harvest for {plan.outcome_token} ({population}): {e}")
            errors.append(str(e))

            # Mark batch as failed
            self._complete_harvest_batch(batch_id, 0, 0, 0, {}, str(e), status="failed")

            return HarvestResults(
                outcome_token=plan.outcome_token,
                population=population,
                query_used="",
                papers_found=0,
                papers_processed=0,
                effects_extracted=0,
                quality_grade_distribution={},
                harvest_timestamp=datetime.now(),
                errors=errors
            )

    def _build_optimized_query(self, plan: HarvestPlan, population: str) -> str:
        """Build optimized PubMed query for an outcome and population."""

        # Core outcome terms
        outcome_terms = " OR ".join([f'"{term}"' for term in plan.search_terms[:5]])

        # Anesthesia context terms
        anesthesia_terms = [
            "anesthesia", "anaesthesia", "perioperative", "intraoperative",
            "surgical", "operation", "surgery", "general anesthesia",
            "regional anesthesia", "epidural", "spinal"
        ]
        context_query = " OR ".join([f'"{term}"' for term in anesthesia_terms])

        # Population-specific terms
        if population == "pediatric":
            pop_terms = "(pediatric OR paediatric OR child OR infant OR neonate OR adolescent)"
        elif population == "adult":
            pop_terms = "(adult OR elderly OR geriatric)"
        elif population == "obstetric":
            pop_terms = "(obstetric OR pregnant OR pregnancy OR cesarean OR delivery)"
        else:
            pop_terms = ""

        # Study design filters (prioritize higher quality)
        design_terms = [
            "randomized controlled trial", "systematic review", "meta-analysis",
            "cohort study", "case-control", "prospective study"
        ]
        design_query = " OR ".join([f'"{term}"' for term in design_terms])

        # Date filter (last 20 years for comprehensive coverage)
        date_filter = "2004:3000[dp]"

        # Combine query components
        query_parts = [
            f"({outcome_terms})",
            f"({context_query})",
        ]

        if pop_terms:
            query_parts.append(pop_terms)

        # Add study design boost (OR to not exclude observational studies)
        query_parts.append(f"({design_query})")

        # Add date filter
        query_parts.append(date_filter)

        # Language filter
        query_parts.append("english[la]")

        final_query = " AND ".join(query_parts)

        # Ensure query isn't too long for PubMed
        if len(final_query) > 4000:
            # Simplify if too long
            final_query = f"({outcome_terms}) AND ({context_query}) AND {date_filter} AND english[la]"
            if pop_terms:
                final_query = f"({outcome_terms}) AND ({context_query}) AND {pop_terms} AND {date_filter} AND english[la]"

        return final_query

    def _filter_papers_by_quality(self, papers: List[PubMedPaper]) -> List[PubMedPaper]:
        """Filter papers by quality criteria."""
        quality_papers = []

        for paper in papers:
            # Basic quality filters
            if paper.study_quality_score < self.min_quality_score:
                continue

            if paper.n_total and paper.n_total < self.min_sample_size:
                continue

            # Exclude case reports and very low quality studies
            if paper.design in ["case report"] and paper.evidence_grade == "D":
                continue

            # Must have abstract
            if not paper.abstract or len(paper.abstract) < 100:
                continue

            quality_papers.append(paper)

        return quality_papers

    def _enhance_effect_extraction(self, paper: PubMedPaper,
                                 effects: List[EffectEstimate],
                                 plan: HarvestPlan) -> List[EffectEstimate]:
        """Enhanced effect extraction with risk factor mapping."""

        enhanced_effects = []
        text = f"{paper.title} {paper.abstract}".lower()

        # Try to identify risk factors mentioned in the paper
        risk_factors_found = self._identify_risk_factors(text)

        for effect in effects:
            # Enhanced effect with risk factor context
            enhanced_effect = effect

            # Try to associate with specific risk factors
            effect_context = effect.definition_note.lower()
            associated_risk_factors = self._identify_risk_factors(effect_context)

            if associated_risk_factors:
                # Create separate effects for each risk factor
                for rf_token in associated_risk_factors:
                    rf_effect = EffectEstimate(
                        id=f"{effect.id}_{rf_token}",
                        pmid=effect.pmid,
                        outcome_token=effect.outcome_token,
                        modifier_token=rf_token,  # Risk factor as modifier
                        measure=effect.measure,
                        estimate=effect.estimate,
                        ci_low=effect.ci_low,
                        ci_high=effect.ci_high,
                        adjusted=effect.adjusted,
                        n_group=effect.n_group,
                        n_events=effect.n_events,
                        definition_note=effect.definition_note,
                        time_horizon=effect.time_horizon,
                        quality_weight=effect.quality_weight,
                        evidence_grade=effect.evidence_grade,
                        population_match=self._calculate_population_match(paper, plan),
                        extraction_confidence=effect.extraction_confidence * 1.1,  # Boost for RF association
                        covariates=effect.covariates,
                        subgroup=paper.population
                    )
                    enhanced_effects.append(rf_effect)
            else:
                # No specific risk factor, use general effect
                enhanced_effect.population_match = self._calculate_population_match(paper, plan)
                enhanced_effects.append(enhanced_effect)

        return enhanced_effects

    def _identify_risk_factors(self, text: str) -> List[str]:
        """Identify risk factors mentioned in text."""
        risk_factors = []
        text_lower = text.lower()

        # Check for risk factors from ontology
        for token, term in self.ontology.terms.items():
            if term.type != "risk_factor":
                continue

            # Check if any synonyms match
            if any(synonym.lower() in text_lower for synonym in [term.plain_label] + term.synonyms):
                risk_factors.append(token)

        return risk_factors

    def _calculate_population_match(self, paper: PubMedPaper, plan: HarvestPlan) -> float:
        """Calculate how well the paper population matches the target."""

        target_category = plan.category
        paper_population = paper.population.lower()

        # Perfect matches
        if target_category == "pediatric" and paper_population == "pediatric":
            return 1.0
        elif target_category == "obstetric" and paper_population == "obstetric":
            return 1.0
        elif target_category in ["cardiovascular", "respiratory"] and paper_population == "adult":
            return 0.9

        # Mixed population studies
        if paper_population == "mixed":
            return 0.8

        # Unknown population
        if paper_population == "unknown":
            return 0.6

        # Mismatched but relevant
        return 0.5

    def _update_pooled_models(self, results: List[HarvestResults]):
        """Update pooled risk models with new evidence."""

        logger.info("Updating pooled risk models with new evidence")

        # Group results by outcome
        outcome_groups = {}
        for result in results:
            if result.effects_extracted > 0:
                outcome_token = result.outcome_token
                if outcome_token not in outcome_groups:
                    outcome_groups[outcome_token] = []
                outcome_groups[outcome_token].append(result)

        # Update models for each outcome
        for outcome_token, outcome_results in outcome_groups.items():
            try:
                self._update_outcome_pooled_model(outcome_token)
                logger.info(f"Updated pooled model for {outcome_token}")
            except Exception as e:
                logger.error(f"Error updating pooled model for {outcome_token}: {e}")

    def _update_outcome_pooled_model(self, outcome_token: str):
        """Update pooled model for a specific outcome."""

        # Get all estimates for this outcome (excluding harvest_batch_id for compatibility)
        estimates = self.db.conn.execute("""
            SELECT outcome_token, context_label, baseline_risk, baseline_source,
                   modifier_token, measure, effect_size, ci_low, ci_high,
                   denominator, numerator, events, sample_size, pmid,
                   evidence_grade, quality_weight, covariates, subgroup, extracted_at
            FROM estimates
            WHERE outcome_token = ?
            AND quality_weight >= ?
            ORDER BY evidence_grade, quality_weight DESC
        """, [outcome_token, self.min_quality_score]).fetchall()

        if len(estimates) < 2:
            logger.warning(f"Insufficient estimates for pooling {outcome_token}: {len(estimates)}")
            return

        # Group by modifier (risk factor)
        modifier_groups = {}
        for est in estimates:
            modifier = est[3]  # modifier_token column
            if modifier not in modifier_groups:
                modifier_groups[modifier] = []
            modifier_groups[modifier].append(est)

        # Pool estimates for each risk factor
        for modifier_token, modifier_estimates in modifier_groups.items():
            if len(modifier_estimates) >= 2:
                try:
                    pooled_result = self.pooling_engine.pool_estimates(
                        outcome_token, modifier_token, modifier_estimates
                    )

                    # Store pooled result
                    self._store_pooled_result(pooled_result)

                except Exception as e:
                    logger.error(f"Error pooling {outcome_token} + {modifier_token}: {e}")

    def _create_harvest_batch(self, batch_id: str, plan: HarvestPlan, population: str):
        """Create harvest batch record."""
        query = self._build_optimized_query(plan, population)

        try:
            self.db.conn.execute("""
                INSERT INTO harvest_batches
                (batch_id, outcome_token, population, query_used, priority, harvest_type)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [batch_id, plan.outcome_token, population, query, plan.priority, "comprehensive"])

        except Exception as e:
            logger.error(f"Error creating harvest batch {batch_id}: {e}")

    def _complete_harvest_batch(self, batch_id: str, papers_found: int, papers_processed: int,
                               effects_extracted: int, grade_dist: Dict[str, int],
                               error_message: str = None, status: str = "completed"):
        """Complete harvest batch record."""

        try:
            self.db.conn.execute("""
                UPDATE harvest_batches
                SET papers_found = ?, papers_processed = ?, effects_extracted = ?,
                    quality_grade_distribution = ?, completed_at = ?, status = ?, error_message = ?
                WHERE batch_id = ?
            """, [
                papers_found, papers_processed, effects_extracted,
                json.dumps(grade_dist), datetime.now().isoformat(), status, error_message, batch_id
            ])

        except Exception as e:
            logger.error(f"Error completing harvest batch {batch_id}: {e}")

    def _create_risk_factor_mappings(self, effects: List[EffectEstimate], plan: HarvestPlan):
        """Create risk factor mappings for extracted effects."""

        for effect in effects:
            if effect.modifier_token:  # Only create mappings for risk factor effects
                mapping_id = f"{effect.modifier_token}_{plan.outcome_token}_{datetime.now().strftime('%Y%m%d')}"

                try:
                    # Check if mapping already exists
                    existing = self.db.conn.execute("""
                        SELECT mapping_id FROM risk_factor_evidence_mapping
                        WHERE ontology_token = ? AND parsed_risk_factor = ?
                    """, [effect.modifier_token, effect.modifier_token]).fetchone()

                    if not existing:
                        self.db.conn.execute("""
                            INSERT INTO risk_factor_evidence_mapping
                            (mapping_id, parsed_risk_factor, ontology_token, confidence_score,
                             supporting_pmids, mapping_method, validated)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, [
                            mapping_id, effect.modifier_token, effect.modifier_token, 0.9,
                            json.dumps([effect.pmid]), "comprehensive_harvest", True
                        ])

                except Exception as e:
                    logger.error(f"Error creating risk factor mapping for {effect.modifier_token}: {e}")

    def _store_pooled_result(self, pooled_result):
        """Store pooled analysis result in database."""

        try:
            # Generate pooled estimate ID
            pooled_id = f"{pooled_result['outcome_token']}_{pooled_result.get('modifier_token', 'baseline')}"

            self.db.conn.execute("""
                INSERT OR REPLACE INTO pooled_estimates
                (id, outcome_token, modifier_token, pooled_estimate, pooled_ci_low,
                 pooled_ci_high, heterogeneity_i2, n_studies, total_n,
                 evidence_grade, contributing_pmids, contributing_estimates, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                pooled_id,
                pooled_result["outcome_token"],
                pooled_result.get("modifier_token"),
                pooled_result["pooled_estimate"],
                pooled_result["ci_low"],
                pooled_result["ci_high"],
                pooled_result.get("i2"),
                pooled_result["n_studies"],
                pooled_result.get("total_n"),
                pooled_result["evidence_grade"],
                json.dumps(pooled_result.get("contributing_pmids", [])),
                json.dumps(pooled_result.get("contributing_estimates", [])),
                datetime.now().isoformat()
            ])

            self.db.log_action("pooled_estimates", pooled_id, "UPDATE", pooled_result)

        except Exception as e:
            logger.error(f"Error storing pooled result: {e}")

    def _generate_harvest_report(self, results: List[HarvestResults]):
        """Generate comprehensive harvest report."""

        report_path = Path("evidence_harvest_report.json")

        # Summary statistics
        total_papers = sum(r.papers_found for r in results)
        total_processed = sum(r.papers_processed for r in results)
        total_effects = sum(r.effects_extracted for r in results)

        # Quality distribution across all harvests
        overall_quality_dist = {}
        for result in results:
            for grade, count in result.quality_grade_distribution.items():
                overall_quality_dist[grade] = overall_quality_dist.get(grade, 0) + count

        # Outcomes with most evidence
        outcome_evidence = {}
        for result in results:
            token = result.outcome_token
            outcome_evidence[token] = outcome_evidence.get(token, 0) + result.effects_extracted

        top_evidence_outcomes = sorted(outcome_evidence.items(),
                                     key=lambda x: x[1], reverse=True)[:10]

        # Generate report
        report = {
            "harvest_summary": {
                "timestamp": datetime.now().isoformat(),
                "total_outcomes_processed": len(set(r.outcome_token for r in results)),
                "total_papers_found": total_papers,
                "total_papers_processed": total_processed,
                "total_effects_extracted": total_effects,
                "processing_rate": f"{total_processed/total_papers*100:.1f}%" if total_papers > 0 else "0%"
            },
            "quality_distribution": overall_quality_dist,
            "top_evidence_outcomes": [
                {"outcome": token, "effects_count": count}
                for token, count in top_evidence_outcomes
            ],
            "detailed_results": [asdict(r) for r in results]
        }

        # Save report
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Harvest report saved to {report_path}")

        # Print summary
        print(f"\n{'='*60}")
        print("COMPREHENSIVE EVIDENCE HARVEST COMPLETED")
        print(f"{'='*60}")
        print(f"Outcomes processed: {len(set(r.outcome_token for r in results))}")
        print(f"Papers found: {total_papers:,}")
        print(f"Papers processed: {total_processed:,}")
        print(f"Effects extracted: {total_effects:,}")
        print(f"Quality distribution: {overall_quality_dist}")
        print(f"Report saved: {report_path}")
        print(f"{'='*60}\n")

def main():
    """Main execution function."""

    # Get API key from environment or prompt
    api_key = os.getenv("NCBI_API_KEY")
    if not api_key:
        print("Warning: No NCBI_API_KEY found. Rate limiting will be more restrictive.")
        print("Get a free API key at: https://ncbi.nlm.nih.gov/account/settings/")

    # Initialize harvester
    harvester = ComprehensiveEvidenceHarvester(api_key=api_key)

    # Run harvest with priority filter (start with critical outcomes)
    print("Starting comprehensive evidence harvest...")
    print("Phase 1: Critical and high-impact outcomes (Priority 1-2)")

    results = harvester.run_comprehensive_harvest(
        max_outcomes=20,  # Start with top 20 outcomes
        priority_filter=2  # Priority 1-2 only
    )

    print(f"\nPhase 1 completed: {len(results)} harvests")

    # Optionally run full harvest
    response = input("\nRun full harvest for all outcomes? (y/n): ")
    if response.lower() == 'y':
        print("\nPhase 2: All outcomes")
        full_results = harvester.run_comprehensive_harvest()
        print(f"Full harvest completed: {len(full_results)} total harvests")

if __name__ == "__main__":
    main()