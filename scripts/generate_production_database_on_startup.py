#!/usr/bin/env python3
"""
Generate Production Database on Startup
Creates risk calculation database if it doesn't exist in production environment
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.calculate_basic_risks import BasicRiskCalculator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_production_database():
    """Generate production database if it doesn't exist"""

    production_db_path = "database/production.duckdb"

    # Check if production database already exists
    if Path(production_db_path).exists():
        logger.info(f"Production database already exists: {production_db_path}")
        return True

    logger.info("Production database not found, generating from scratch...")

    try:
        # Create database directory
        Path("database").mkdir(exist_ok=True)

        # Initialize risk calculator with production path
        calculator = BasicRiskCalculator(db_path=production_db_path)

        logger.info("Starting baseline risk calculation...")

        # Calculate baseline risks
        baseline_risks = calculator.create_baseline_risks()

        # Calculate modifier effects
        modifier_effects = calculator.create_modifier_effects()

        # Store results
        calculator.store_risk_calculations(baseline_risks, modifier_effects)

        logger.info(f"Generated production database with {len(baseline_risks)} baseline risks and {len(modifier_effects)} modifier effects")

        return True

    except Exception as e:
        logger.error(f"Failed to generate production database: {e}")
        return False

if __name__ == "__main__":
    success = generate_production_database()
    sys.exit(0 if success else 1)