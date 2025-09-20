# Deployment Troubleshooting Guide

## Common Deployment Issues

### 1. Deployment Version Counter Not Incrementing

**Symptoms:**
- Render deployment shows "live" status
- Website loads but deployment counter in status panel shows old version
- Code changes don't appear to be active

**Root Cause:**
- Deployment succeeded but `deployment_version.txt` file wasn't updated
- The application reads version from this file, not from Git commit hash

**Solution:**
```bash
# Increment the version number in deployment_version.txt
echo "6" > deployment_version.txt
git add deployment_version.txt
git commit -m "Increment deployment version to v6"
git push origin main
```

**Prevention:**
- Always increment `deployment_version.txt` when making significant changes
- Use deployment counter to verify changes are live

### 2. HPI Parser Returning 500 Errors

**Symptoms:**
- "Error: Unable to parse HPI factors" message
- 500 status code in browser console
- No extracted factors displayed

**Common Causes:**

#### A. NameError: 'explicit_population' is not defined
**Fix:** Ensure `explicit_population` parameter is passed to all methods:
```python
# In _calculate_outcome_risk method signature:
def _calculate_outcome_risk(self, outcome_token: str, factors: List[ExtractedFactor],
                          demographics: Dict[str, Any], context_label: str,
                          mode: str, explicit_population: str = None) -> Optional[RiskAssessment]:

# In calculate_risks method call:
assessment = self._calculate_outcome_risk(
    outcome_token, factors, demographics, context_label, mode, explicit_population
)
```

#### B. spaCy Installation Issues
**Symptoms:** `WARNING: spaCy not available. Using rule-based processing only.`
**Impact:** Non-critical - system falls back to rule-based parsing
**Optional Fix:** Ensure spaCy is properly installed in production environment

#### C. Database Table Missing Errors
**Symptoms:** `Database table evidence_based_adjusted_risks missing`
**Fix:** Database repair runs automatically on startup, check logs for completion

### 3. Build Stuck in "build_in_progress"

**Symptoms:**
- Deployment status remains "build_in_progress" for >10 minutes
- Build logs show no recent activity

**Solutions:**
1. Wait for build to complete (spaCy installation can take 5-10 minutes)
2. Check build logs for errors
3. If stuck, trigger new deployment with minimal change

### 4. 502 Bad Gateway Errors

**Symptoms:**
- 502 error pages
- Service temporarily unavailable message

**Causes:**
- Normal during deployment startup (expect 1-3 minutes)
- Service crashed during initialization
- Resource limits exceeded

**Solutions:**
1. Wait 2-3 minutes for service startup
2. Check application logs for startup errors
3. Monitor memory/CPU usage

## Debugging Commands

### Check Deployment Status
```bash
# Using Render MCP
mcp__render__get_deploy --serviceId srv-xxx --deployId dep-xxx
```

### Monitor Logs
```bash
# Application logs
mcp__render__list_logs --resource ["srv-xxx"] --limit 20

# Build logs
mcp__render__list_logs --resource ["srv-xxx"] --type ["build"] --limit 20
```

### Test HPI Parser Locally
```python
from src.core.hpi_parser import HPIParser
parser = HPIParser()
result = parser.parse_hpi("5 year old with asthma for dental procedure")
print(f"Factors: {result.factors}")
```

## Deployment Checklist

Before deploying:
- [ ] Update `deployment_version.txt`
- [ ] Test locally with `python app_simple.py`
- [ ] Verify database schema is current
- [ ] Check for any hardcoded paths or dependencies

After deploying:
- [ ] Verify deployment counter incremented
- [ ] Test HPI parser with simple case
- [ ] Check application logs for errors
- [ ] Verify all critical features work

## Error Log Patterns

### Successful Startup
```
INFO:app_simple:Initializing risk engine with database: evidence_base.db
INFO:src.core.database:Database schema initialized successfully
INFO:app_simple:Initializing NLP-based medical text processor...
WARNING:src.core.hpi_parser:spaCy not available. Using rule-based processing only.
```

### Failed Startup (NameError)
```
ERROR:src.core.risk_engine:Error calculating risk for LARYNGOSPASM: name 'explicit_population' is not defined
ERROR:codex_app:CODEX_ERROR: RISK_003 - No risk estimates available
```

## Recent Fixes and Resilience Improvements

### HPI Parser Resilience (v16-v19)

**Problem**: HPI parser completely failed with 500 errors when baseline risk data was missing.

**Solution**: Implemented resilient error handling that allows HPI parsing to continue even without complete risk data.

**Key Changes**:
- **v16**: Backend now returns HTTP 200 with `partial_success` status instead of HTTP 500 errors
- **v17**: Frontend updated to handle both full success and partial success response formats
- **v18**: Fixed JavaScript syntax error (unescaped newlines) that was breaking all frontend functionality
- **v19**: Added robust null checking in display functions to prevent "Cannot read properties of undefined" errors

**Current Behavior**:
- HPI factor extraction works regardless of missing baseline risk data
- Risk scores and medications tabs show "No data available" messages instead of errors
- System displays informative warnings about missing data instead of complete failure

### JavaScript Error Prevention

**Symptoms**:
- "Invalid or unexpected token" errors in browser console
- "Cannot read properties of undefined (reading 'length')" errors
- Functions like `analyzeHPI` not defined

**Fixes Applied**:
- Properly escaped newline characters in JavaScript string literals (v18)
- Added null/undefined checks before accessing array properties (v19)
- Ensured all display functions handle empty or missing data gracefully

## Contact and Support

- Check GitHub issues: https://github.com/dgkenn/MeridianV2/issues
- Review Render documentation: https://render.com/docs/troubleshooting-deploys
- Application logs are the primary debugging tool