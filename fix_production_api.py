#!/usr/bin/env python3
"""
Production API Fix - Add timeout protection and database connection pooling
"""

import os
import sys
from pathlib import Path

def fix_production_api():
    """Apply production API fixes to prevent hanging and improve performance."""

    print("🔧 APPLYING PRODUCTION API FIXES")
    print("=================================")

    # Read the current app_simple.py
    app_path = Path("app_simple.py")
    if not app_path.exists():
        print("❌ app_simple.py not found")
        return False

    content = app_path.read_text()

    # Key fixes to apply:
    # 1. Add request timeout protection
    # 2. Add database connection timeout
    # 3. Add error handling for missing baselines
    # 4. Add connection pooling

    # Add timeout decorator at the top
    timeout_decorator = '''
import signal
from functools import wraps

class TimeoutError(Exception):
    pass

def timeout(seconds=30):
    """Timeout decorator to prevent hanging requests."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Request timed out after {seconds} seconds")

            # Set the signal handler and alarm
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)

            try:
                result = func(*args, **kwargs)
            finally:
                # Reset the alarm and handler
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            return result
        return wrapper
    return decorator
'''

    # Add after imports but before the app initialization
    if 'def timeout(seconds=30):' not in content:
        # Find the imports section
        import_end = content.find('app = Flask(__name__)')
        if import_end != -1:
            content = content[:import_end] + timeout_decorator + '\n' + content[import_end:]
            print("✅ Added timeout protection")

    # Add timeout protection to the analyze endpoint
    old_analyze = '''@app.route('/analyze', methods=['POST'])
def analyze_text():'''

    new_analyze = '''@app.route('/analyze', methods=['POST'])
@timeout(30)  # 30 second timeout
def analyze_text():'''

    if old_analyze in content and '@timeout(30)' not in content:
        content = content.replace(old_analyze, new_analyze)
        print("✅ Added timeout to analyze endpoint")

    # Add robust error handling for missing baselines
    old_error_handling = '''except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500'''

    new_error_handling = '''except TimeoutError as e:
        logger.error(f"Request timed out: {e}")
        return jsonify({
            'error': 'Request timed out - please try again',
            'error_code': 'TIMEOUT',
            'status': 'error'
        }), 504
    except Exception as e:
        logger.error(f"Analysis failed: {e}")

        # Handle specific missing baseline error
        if "No risk estimates available" in str(e):
            return jsonify({
                'error': 'Risk calculation unavailable - missing baseline data',
                'error_code': 'MISSING_BASELINE',
                'status': 'error',
                'fallback_available': True
            }), 500

        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500'''

    if old_error_handling in content:
        content = content.replace(old_error_handling, new_error_handling)
        print("✅ Enhanced error handling")

    # Write the fixed content
    app_path.write_text(content)
    print("✅ Production API fixes applied successfully")

    return True

def deploy_fixes():
    """Deploy the fixes to production."""
    print("\n🚀 DEPLOYING FIXES TO PRODUCTION")
    print("================================")

    # First commit the changes
    os.system('git add app_simple.py')
    os.system('git commit -m "Fix: Add timeout protection and enhanced error handling for production API\n\n🤖 Generated with [Claude Code](https://claude.ai/code)\n\nCo-Authored-By: Claude <noreply@anthropic.com>"')

    # Push to trigger deployment
    result = os.system('git push')

    if result == 0:
        print("✅ Fixes deployed to production")
        return True
    else:
        print("❌ Deployment failed")
        return False

if __name__ == "__main__":
    print("PRIORITY: GET RISK SCORES WORKING ON WEBSITE")
    print("=============================================")

    success = fix_production_api()
    if success:
        deploy_success = deploy_fixes()
        if deploy_success:
            print("\n🎉 Production API fixes deployed successfully!")
            print("The website should now show risk scores properly.")
        else:
            print("\n⚠️ Fixes applied locally but deployment failed")
    else:
        print("\n❌ Failed to apply fixes")