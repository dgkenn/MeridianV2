"""
Clinical Decision Support - Risk-based Recommendations Engine
"""

def get_clinical_recommendations(risks, patient_factors, demographics):
    """
    Generate evidence-based clinical recommendations based on risk assessment
    """
    recommendations = {
        'preoperative': [],
        'intraoperative': [],
        'monitoring': [],
        'postoperative': []
    }

    patient_factor_tokens = [f['token'] for f in patient_factors]
    age_category = demographics.get('age_category', '')

    # Process each risk outcome
    for risk in risks:
        outcome = risk['outcome']
        risk_level = risk['adjusted_risk']

        # High-risk specific recommendations
        if risk_level > 0.10:  # High risk threshold

            if outcome == 'POSTOP_DELIRIUM':
                recommendations['preoperative'].append({
                    'category': 'Delirium Prevention',
                    'action': 'Cognitive assessment and baseline testing',
                    'rationale': 'High delirium risk (>10%) - establish cognitive baseline',
                    'evidence': 'Grade A - NICE Guidelines 2010',
                    'priority': 'high'
                })
                recommendations['intraoperative'].append({
                    'category': 'Delirium Prevention',
                    'action': 'Minimize benzodiazepines, prefer dexmedetomidine',
                    'rationale': 'Reduce delirium-inducing medications',
                    'evidence': 'Grade A - Cochrane Review 2018',
                    'priority': 'high'
                })

            elif outcome == 'CARDIAC_DEATH':
                recommendations['preoperative'].append({
                    'category': 'Cardiac Optimization',
                    'action': 'Cardiology consultation and stress testing',
                    'rationale': 'High cardiac death risk requires specialist evaluation',
                    'evidence': 'Grade A - ACC/AHA Guidelines 2014',
                    'priority': 'critical'
                })
                recommendations['monitoring'].append({
                    'category': 'Cardiac Monitoring',
                    'action': 'Continuous 5-lead ECG + arterial line',
                    'rationale': 'Enhanced cardiac monitoring for high-risk patients',
                    'evidence': 'Grade B - ASA Practice Guidelines',
                    'priority': 'high'
                })

            elif outcome == 'ACUTE_KIDNEY_INJURY':
                recommendations['preoperative'].append({
                    'category': 'Renal Protection',
                    'action': 'Nephrotoxic medication review + hydration protocol',
                    'rationale': 'High AKI risk requires nephrotoxin avoidance',
                    'evidence': 'Grade A - KDIGO Guidelines 2012',
                    'priority': 'high'
                })

            elif outcome == 'PULMONARY_EMBOLISM':
                recommendations['preoperative'].append({
                    'category': 'VTE Prevention',
                    'action': 'Aggressive VTE prophylaxis + IPC devices',
                    'rationale': 'High PE risk requires enhanced thromboprophylaxis',
                    'evidence': 'Grade A - ACCP Guidelines 2016',
                    'priority': 'high'
                })

    # Risk factor specific recommendations
    if 'DIABETES' in patient_factor_tokens:
        recommendations['preoperative'].append({
            'category': 'Glucose Management',
            'action': 'Perioperative glucose protocol + endocrine consult',
            'rationale': 'Diabetic patients require specialized glucose management',
            'evidence': 'Grade A - ADA Perioperative Guidelines',
            'priority': 'high'
        })
        recommendations['monitoring'].append({
            'category': 'Glucose Monitoring',
            'action': 'Hourly glucose checks + continuous glucose monitoring',
            'rationale': 'Prevent hypo/hyperglycemic complications',
            'evidence': 'Grade B - Society for Ambulatory Anesthesia',
            'priority': 'moderate'
        })

    if 'ASTHMA' in patient_factor_tokens:
        recommendations['preoperative'].append({
            'category': 'Respiratory Optimization',
            'action': 'Bronchodilator therapy + pulmonary function testing',
            'rationale': 'Optimize respiratory status before surgery',
            'evidence': 'Grade A - Global Initiative for Asthma 2021',
            'priority': 'moderate'
        })
        recommendations['intraoperative'].append({
            'category': 'Airway Management',
            'action': 'Avoid desflurane, prefer sevoflurane + deep extubation',
            'rationale': 'Minimize bronchospasm triggers',
            'evidence': 'Grade B - BJA Airway Guidelines',
            'priority': 'moderate'
        })

    if 'HYPERTENSION' in patient_factor_tokens:
        recommendations['preoperative'].append({
            'category': 'BP Management',
            'action': 'Continue antihypertensives + BP optimization',
            'rationale': 'Maintain perioperative cardiovascular stability',
            'evidence': 'Grade A - ESC/ESA Guidelines 2014',
            'priority': 'moderate'
        })

    if age_category == 'AGE_ELDERLY':
        recommendations['preoperative'].append({
            'category': 'Geriatric Assessment',
            'action': 'Comprehensive geriatric assessment + frailty screening',
            'rationale': 'Elderly patients benefit from multidisciplinary evaluation',
            'evidence': 'Grade B - AGS Perioperative Guidelines',
            'priority': 'moderate'
        })
        recommendations['postoperative'].append({
            'category': 'Geriatric Care',
            'action': 'Early mobilization + delirium screening protocols',
            'rationale': 'Prevent common geriatric complications',
            'evidence': 'Grade A - Enhanced Recovery Guidelines',
            'priority': 'moderate'
        })

    # Age-specific recommendations
    if age_category in ['AGE_1_5', 'AGE_6_12']:
        recommendations['intraoperative'].append({
            'category': 'Pediatric Anesthesia',
            'action': 'Sevoflurane mask induction + TIVA maintenance',
            'rationale': 'Reduce emergence delirium in children',
            'evidence': 'Grade A - Pediatric Anesthesia Society Guidelines',
            'priority': 'moderate'
        })

    # General high-risk recommendations
    overall_max_risk = max([r['adjusted_risk'] for r in risks])
    if overall_max_risk > 0.15:
        recommendations['monitoring'].append({
            'category': 'Enhanced Monitoring',
            'action': 'Consider ICU/HDU postoperative care',
            'rationale': 'Multiple high-risk factors present',
            'evidence': 'Grade C - Clinical Consensus',
            'priority': 'high'
        })

    return recommendations

def format_recommendations_html(recommendations):
    """
    Format recommendations for HTML display with priority-based styling
    """
    if not any(recommendations.values()):
        return "<div class='alert alert-info'>No specific recommendations generated based on current risk profile.</div>"

    html = ""

    category_icons = {
        'preoperative': '📋',
        'intraoperative': '⚕️',
        'monitoring': '📊',
        'postoperative': '🏥'
    }

    category_labels = {
        'preoperative': 'Pre-operative Optimization',
        'intraoperative': 'Intra-operative Management',
        'monitoring': 'Enhanced Monitoring',
        'postoperative': 'Post-operative Care'
    }

    for category, recs in recommendations.items():
        if recs:
            html += f"""
                <div class="recommendation-category" style="margin-bottom: 1.5rem;">
                    <h4 style="color: #06b6d4; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 1.2rem;">{category_icons[category]}</span>
                        {category_labels[category]}
                    </h4>
                    <div class="recommendation-list">
            """

            # Sort by priority
            priority_order = {'critical': 0, 'high': 1, 'moderate': 2, 'low': 3}
            sorted_recs = sorted(recs, key=lambda x: priority_order.get(x['priority'], 3))

            for rec in sorted_recs:
                priority_colors = {
                    'critical': '#dc2626',
                    'high': '#ea580c',
                    'moderate': '#ca8a04',
                    'low': '#16a34a'
                }
                color = priority_colors.get(rec['priority'], '#6b7280')

                html += f"""
                    <div class="recommendation-item" style="
                        margin-bottom: 1rem;
                        padding: 1rem;
                        background: rgba(255,255,255,0.02);
                        border-radius: 8px;
                        border-left: 3px solid {color};
                    ">
                        <div style="display: flex; justify-content: between; align-items: flex-start; margin-bottom: 0.5rem;">
                            <strong style="color: #e2e8f0; font-size: 1.1rem;">{rec['category']}</strong>
                            <span style="
                                background: {color}20;
                                color: {color};
                                padding: 2px 8px;
                                border-radius: 12px;
                                font-size: 0.75rem;
                                font-weight: 600;
                                margin-left: auto;
                            ">{rec['priority'].upper()}</span>
                        </div>
                        <div style="color: #cbd5e1; font-weight: 600; margin-bottom: 0.5rem;">
                            {rec['action']}
                        </div>
                        <div style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 0.5rem;">
                            <strong>Rationale:</strong> {rec['rationale']}
                        </div>
                        <div style="color: #64748b; font-size: 0.8rem;">
                            📚 <strong>Evidence:</strong> {rec['evidence']}
                        </div>
                    </div>
                """

            html += """
                    </div>
                </div>
            """

    return html