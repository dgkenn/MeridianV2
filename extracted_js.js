    <script>
        let currentData = null;

        function showSection(section) {
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            document.getElementById(section).classList.add('active');
            event.target.classList.add('active');
        }

        function loadExample() {
            fetch('/api/example')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('hpiText').value = data.hpi;
                });
        }

        function analyzeHPI() {
            const hpiText = document.getElementById('hpiText').value.trim();
            if (!hpiText) {
                showStatus('Please enter HPI text first', 'warning');
                return;
            }

            showStatus('Analyzing HPI...', 'info');

            fetch('/api/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({hpi_text: hpiText})
            })
            .then(r => r.json())
            .then(data => {
                currentData = data;
                displayFactors(data.parsed.extracted_factors);
                displayRisks(data.risks);
                displayMedications(data.medications);
                showStatus('Analysis complete!', 'success');
            })
            .catch(err => {
                showStatus('Error: ' + err.message, 'danger');
            });
        }

        function displayFactors(factors) {
            const panel = document.getElementById('factorsPanel');
            if (factors.length === 0) {
                panel.innerHTML = '<p class="text-muted small">No risk factors detected</p>';
                return;
            }

            let html = '';
            factors.forEach(f => {
                html += `<div class="factor-tag" title="${f.evidence_text}">${f.plain_label}</div>`;
            });
            panel.innerHTML = html;
        }

        function displayRisks(data) {
            const content = document.getElementById('riskContent');
            if (data.risks.length === 0) {
                content.innerHTML = '<div class="alert alert-info">No significant risks identified</div>';
                return;
            }

            let html = `<div class="alert alert-info">Overall risk: <strong>${data.summary.overall_risk_score}</strong></div>`;

            data.risks.forEach((risk, index) => {
                const level = risk.adjusted_risk > 0.1 ? 'high' : (risk.adjusted_risk > 0.05 ? 'moderate' : 'low');
                const hasSpecificOutcomes = risk.specific_outcomes && risk.specific_outcomes.length > 0;

                html += `
                    <div class="risk-item ${level}" onclick="${hasSpecificOutcomes ? `toggleRiskDetails(${index})` : ''}"
                         style="${hasSpecificOutcomes ? 'cursor: pointer;' : ''}">
                        <div>
                            <div style="font-weight: 600;">
                                ${risk.outcome_label}
                                ${hasSpecificOutcomes ? '<span style="font-size: 0.8rem; opacity: 0.7;">▼ Click for details</span>' : ''}
                            </div>
                            <div class="small text-muted">
                                ${(risk.baseline_risk * 100).toFixed(1)}% → ${(risk.adjusted_risk * 100).toFixed(1)}%
                                (${risk.risk_ratio.toFixed(1)}x increase)
                            </div>
                        </div>
                        <div style="font-size: 1.1rem; font-weight: 700;">${(risk.adjusted_risk * 100).toFixed(1)}%</div>
                    </div>
                    ${hasSpecificOutcomes ? `
                        <div id="risk-details-${index}" class="risk-details" style="display: none;">
                            ${risk.specific_outcomes.map(outcome => `
                                <div class="outcome-item" onclick="toggleOutcomeDetails('${outcome.name.replace(/[^a-zA-Z0-9]/g, '')}')">
                                    <div class="outcome-header">
                                        <strong>${outcome.name}</strong>: ${(outcome.risk * 100).toFixed(1)}%
                                        <span style="font-size: 0.8rem; opacity: 0.7;">▼ Click for explanation</span>
                                    </div>
                                    <div id="outcome-${outcome.name.replace(/[^a-zA-Z0-9]/g, '')}" class="outcome-explanation" style="display: none;">
                                        <div style="margin: 1rem 0; padding: 1rem; background: rgba(255,255,255,0.03); border-radius: 8px;">
                                            <p><strong>Explanation:</strong> ${outcome.explanation}</p>
                                            <p style="margin-top: 0.5rem;"><strong>Management:</strong> ${outcome.management}</p>
                                            <div style="margin-top: 0.5rem;">
                                                <strong>Risk Factors:</strong>
                                                ${outcome.factors.map(f => `
                                                    <span style="display: inline-block; margin: 2px; padding: 2px 6px; background: rgba(37,99,235,0.2); border-radius: 4px; font-size: 0.8rem;">
                                                        ${f.factor} (OR: ${f.or})
                                                        <a href="https://pubmed.ncbi.nlm.nih.gov/${f.citation.replace('PMID:', '')}" target="_blank" style="color: #06b6d4; text-decoration: none;">
                                                            📄 ${f.citation}
                                                        </a>
                                                    </span>
                                                `).join('')}
                                            </div>
                                            <div style="margin-top: 0.5rem;">
                                                <strong>Citations:</strong>
                                                ${outcome.citations.map(citation => `
                                                    <a href="https://pubmed.ncbi.nlm.nih.gov/${citation.replace("PMID:", "")}" target="_blank"
                                                       style="color: #06b6d4; text-decoration: none; margin-right: 1rem;">
                                                        📄 ${citation}
                                                    </a>
                                                `).join('')}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                `;
            });

            content.innerHTML = html;
        }

        function toggleRiskDetails(index) {
            const details = document.getElementById(`risk-details-${index}`);
            if (details) {
                details.style.display = details.style.display === 'none' ? 'block' : 'none';
            }
        }

        function toggleOutcomeDetails(outcomeId) {
            const explanation = document.getElementById(`outcome-${outcomeId}`);
            if (explanation) {
                explanation.style.display = explanation.style.display === 'none' ? 'block' : 'none';
            }
        }

        function displayMedications(data) {
            const content = document.getElementById('medicationContent');
            let html = '';

            // CONTRAINDICATED (highest priority - top)
            if (data.contraindicated && data.contraindicated.length > 0) {
                html += '<h4 style="color: #ef4444; margin-bottom: 1rem;">⚠️ Contraindicated Medications</h4>';
                data.contraindicated.forEach((med, index) => {
                    const medId = `contra-${index}`;
                    html += `
                        <div class="med-item contraindicated" onclick="toggleMedDetails('${medId}')" style="cursor: pointer;">
                            <div class="med-name">${med.generic_name} (${med.evidence_grade})
                                <span style="font-size: 0.8rem; opacity: 0.7; margin-left: 0.5rem;">▼ Click for details</span>
                            </div>
                            <div class="med-indication">⚠️ ${med.contraindication_reason}</div>
                            <div id="${medId}" class="med-details" style="display: none; margin-top: 1rem; padding: 1rem; background: rgba(0,0,0,0.2); border-radius: 8px;">
                                <p><strong>Justification:</strong> ${med.justification}</p>
                                <div style="margin-top: 0.5rem;">
                                    <strong>Patient Factors:</strong>
                                    ${med.patient_factors.map(factor => `
                                        <span style="display: inline-block; margin: 2px; padding: 2px 6px; background: rgba(239,68,68,0.2); border-radius: 4px; font-size: 0.8rem;">
                                            ${factor}
                                        </span>
                                    \`).join('')}
                                </div>
                                <div style="margin-top: 0.5rem;">
                                    <strong>Citations:</strong>
                                    ${med.citations.map(citation => {
                                        if (citation.startsWith('PMID:')) {
                                            return \`<a href="https://pubmed.ncbi.nlm.nih.gov/${citation.replace("PMID:", "")}" target="_blank" style="color: #06b6d4; text-decoration: none; margin-right: 1rem;">📄 ${citation}</a>\`;
                                        } else {
                                            return \`<span style="margin-right: 1rem; color: #cbd5e1;">📋 ${citation}</span>\`;
                                        }
                                    }).join('')}
                                </div>
                            </div>
                        </div>
                    \`;
                });
            }

            // DRAW NOW (collapsible dropdown)
            if (data.draw_now && data.draw_now.length > 0) {
                html += \`
                    <h4 style="margin-top: 1.5rem; color: #ef4444; cursor: pointer;" onclick="toggleDrawNowSection()">
                        🚨 Draw These Now (\${data.draw_now.length} medications)
                        <span id="draw-now-arrow" style="font-size: 0.8rem;">▼</span>
                    </h4>
                    <div id="draw-now-section" style="display: block;">
                \`;
                data.draw_now.forEach((med, index) => {
                    const medId = \`draw-\${index}\`;
                    html += \`
                        <div class="med-item" style="border-left: 4px solid #dc3545; cursor: pointer;" onclick="toggleMedDetails('${medId}')">
                            <div class="med-name">${med.generic_name} (${med.evidence_grade})
                                <span style="font-size: 0.8rem; opacity: 0.7; margin-left: 0.5rem;">▼ Click for details</span>
                            </div>
                            <div class="med-indication">${med.indication}</div>
                            <div class="med-dose">${med.dose}</div>
                            <div id="${medId}" class="med-details" style="display: none; margin-top: 1rem; padding: 1rem; background: rgba(255,255,255,0.03); border-radius: 8px;">
                                <p><strong>Justification:</strong> ${med.justification}</p>
                                <div style="margin-top: 0.5rem;">
                                    <strong>Patient Factors:</strong>
                                    ${med.patient_factors.map(factor => `
                                        <span style="display: inline-block; margin: 2px; padding: 2px 6px; background: rgba(37,99,235,0.2); border-radius: 4px; font-size: 0.8rem;">
                                            ${factor}
                                        </span>
                                    \`).join('')}
                                </div>
                                <div style="margin-top: 0.5rem;">
                                    <strong>Citations:</strong>
                                    ${med.citations.map(citation => {
                                        if (citation.startsWith('PMID:')) {
                                            return \`<a href="https://pubmed.ncbi.nlm.nih.gov/${citation.replace("PMID:", "")}" target="_blank" style="color: #06b6d4; text-decoration: none; margin-right: 1rem;">📄 ${citation}</a>\`;
                                        } else {
                                            return \`<span style="margin-right: 1rem; color: #cbd5e1;">📋 ${citation}</span>\`;
                                        }
                                    }).join('')}
                                </div>
                            </div>
                        </div>
                    \`;
                });
                html += '</div>';
            }

            // CONSIDER/CASE-DEPENDENT
            if (data.consider && data.consider.length > 0) {
                html += '<h4 style="margin-top: 1.5rem; color: #06b6d4;">Consider/Case-Dependent</h4>';
                data.consider.forEach((med, index) => {
                    const medId = \`consider-\${index}\`;
                    html += \`
                        <div class="med-item" style="border-left: 4px solid #17a2b8; cursor: pointer;" onclick="toggleMedDetails('${medId}')">
                            <div class="med-name">${med.generic_name} (${med.evidence_grade})
                                <span style="font-size: 0.8rem; opacity: 0.7; margin-left: 0.5rem;">▼ Click for details</span>
                            </div>
                            <div class="med-indication">${med.indication}</div>
                            <div class="med-dose">${med.dose}</div>
                            <div id="${medId}" class="med-details" style="display: none; margin-top: 1rem; padding: 1rem; background: rgba(255,255,255,0.03); border-radius: 8px;">
                                <p><strong>Justification:</strong> ${med.justification}</p>
                                <div style="margin-top: 0.5rem;">
                                    <strong>Patient Factors:</strong>
                                    ${med.patient_factors.map(factor => `
                                        <span style="display: inline-block; margin: 2px; padding: 2px 6px; background: rgba(6,182,212,0.2); border-radius: 4px; font-size: 0.8rem;">
                                            ${factor}
                                        </span>
                                    \`).join('')}
                                </div>
                                <div style="margin-top: 0.5rem;">
                                    <strong>Citations:</strong>
                                    ${med.citations.map(citation => {
                                        if (citation.startsWith('PMID:')) {
                                            return \`<a href="https://pubmed.ncbi.nlm.nih.gov/${citation.replace("PMID:", "")}" target="_blank" style="color: #06b6d4; text-decoration: none; margin-right: 1rem;">📄 ${citation}</a>\`;
                                        } else {
                                            return \`<span style="margin-right: 1rem; color: #cbd5e1;">📋 ${citation}</span>\`;
                                        }
                                    }).join('')}
                                </div>
                            </div>
                        </div>
                    \`;
                });
            }

            // STANDARD MEDICATIONS (bottom as requested)
            if (data.standard && data.standard.length > 0) {
                html += '<h4 style="margin-top: 1.5rem; color: #94a3b8;">Standard Medications</h4>';
                data.standard.forEach((med, index) => {
                    const medId = \`standard-\${index}\`;
                    html += \`
                        <div class="med-item" onclick="toggleMedDetails('${medId}')" style="cursor: pointer;">
                            <div class="med-name">${med.generic_name} (${med.evidence_grade})
                                <span style="font-size: 0.8rem; opacity: 0.7; margin-left: 0.5rem;">▼ Click for details</span>
                            </div>
                            <div class="med-indication">${med.indication}</div>
                            <div class="med-dose">${med.dose}</div>
                            <div id="${medId}" class="med-details" style="display: none; margin-top: 1rem; padding: 1rem; background: rgba(255,255,255,0.03); border-radius: 8px;">
                                <p><strong>Justification:</strong> ${med.justification}</p>
                                <div style="margin-top: 0.5rem;">
                                    <strong>Patient Factors:</strong>
                                    ${med.patient_factors.map(factor => `
                                        <span style="display: inline-block; margin: 2px; padding: 2px 6px; background: rgba(148,163,184,0.2); border-radius: 4px; font-size: 0.8rem;">
                                            ${factor}
                                        </span>
                                    \`).join('')}
                                </div>
                                <div style="margin-top: 0.5rem;">
                                    <strong>Citations:</strong>
                                    ${med.citations.map(citation => {
                                        if (citation.startsWith('PMID:')) {
                                            return \`<a href="https://pubmed.ncbi.nlm.nih.gov/${citation.replace("PMID:", "")}" target="_blank" style="color: #06b6d4; text-decoration: none; margin-right: 1rem;">📄 ${citation}</a>\`;
                                        } else {
                                            return \`<span style="margin-right: 1rem; color: #cbd5e1;">📋 ${citation}</span>\`;
                                        }
                                    }).join('')}
                                </div>
                            </div>
                        </div>
                    \`;
                });
            }

            content.innerHTML = html || '<div class="alert alert-info">No specific recommendations</div>';
        }

        function toggleMedDetails(medId) {
            const details = document.getElementById(medId);
            if (details) {
                details.style.display = details.style.display === 'none' ? 'block' : 'none';
            }
        }

        function toggleDrawNowSection() {
            const section = document.getElementById('draw-now-section');
            const arrow = document.getElementById('draw-now-arrow');
            if (section) {
                if (section.style.display === 'none') {
                    section.style.display = 'block';
                    arrow.textContent = '▼';
                } else {
                    section.style.display = 'none';
                    arrow.textContent = '▶';
                }
            }
        }

        function showStatus(message, type) {
            const status = document.getElementById('status');
            status.className = `alert alert-${type}`;
            status.innerHTML = message;
            status.classList.remove('hidden');
            setTimeout(() => status.classList.add('hidden'), 5000);
        }

        function clearAll() {
            document.getElementById('hpiText').value = '';
            document.getElementById('factorsPanel').innerHTML = '<p class="text-muted small">Risk factors will appear here after parsing</p>';
            document.getElementById('riskContent').innerHTML = '<div class="alert alert-info">Parse an HPI first to see risk analysis.</div>';
            document.getElementById('medicationContent').innerHTML = '<div class="alert alert-info">Complete risk analysis to see medication recommendations.</div>';
            currentData = null;
        }

        // Initialize
        fetch('/api/health')
            .then(r => r.json())
            .then(data => {
                document.getElementById('statusPanel').innerHTML = `
                    <div class="small">
                        <div><strong>Status:</strong> ${data.status}</div>
                        <div><strong>Version:</strong> ${data.version}</div>
                    </div>
                `;
            });
    </script>
