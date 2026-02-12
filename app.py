"""
NEXUS Backend API for Hugging Face Spaces
Flask REST API wrapping existing NEXUS logic
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import json
import io
from datetime import datetime

# Import your existing NEXUS code
# Since we're on HF Spaces, we'll import from the same directory
from nexus_logic import (
    create_prog,
    fetch_research,
    fetch_company_research,
    DomainDetector,
    feedback_system,
    payment_state,
    save_state,
    load_state,
    gen_session_id,
    prepare_ppt_text,
)

# Initialize Flask
app = Flask(__name__)
CORS(app)  # Enable CORS for any frontend

# Load state on startup
load_state()

@app.route('/')
def home():
    """Welcome page with API documentation"""
    return jsonify({
        'service': 'NEXUS Learning Generator API',
        'version': '1.0',
        'status': 'running',
        'endpoints': {
            'health': 'GET /api/health',
            'research_topic': 'POST /api/research/topic',
            'research_company': 'POST /api/research/company',
            'generate': 'POST /api/generate',
            'unlock': 'POST /api/unlock/<session_id>',
            'feedback': 'POST /api/feedback',
            'stats': 'GET /api/feedback/stats',
        },
        'documentation': 'https://huggingface.co/spaces/YOUR_USERNAME/nexus-backend',
        'sessions_loaded': len(payment_state)
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'sessions': len(payment_state)
    })

@app.route('/api/research/topic', methods=['POST'])
def research_topic():
    try:
        data = request.json
        topic = data.get('topic', '').strip()
        
        if not topic:
            return jsonify({'error': 'Topic required'}), 400
        
        result = fetch_research(topic)
        
        return jsonify({
            'success': True,
            'topic': topic,
            'domain': result.get('domain', 'business'),
            'has_live_sources': result.get('has_live', False),
            'sources': result.get('sources', [])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/research/company', methods=['POST'])
def research_company():
    try:
        data = request.json
        company_name = data.get('companyName', '').strip()
        
        if not company_name:
            return jsonify({'error': 'Company name required'}), 400
        
        company_data = fetch_company_research(company_name)
        
        return jsonify({
            'success': True,
            'companyName': company_name,
            'hasData': company_data.get('has_data', False),
            'overview': company_data.get('overview', ''),
            'industry': company_data.get('industry', ''),
            'competitors': company_data.get('competitors', []),
            'news': company_data.get('news', [])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate():
    try:
        data = request.json
        
        topic = data.get('topic', '').strip()
        fmt = data.get('format', 'Training')
        dur = data.get('duration', '1 Day (6-7 hours)')
        aud_lvl = data.get('audienceLevel', 'Executive/C-Suite/Senior Leadership')
        company_name = data.get('companyName', '').strip()
        company_context = data.get('companyContext', '').strip()
        delivery_mode = data.get('deliveryMode', 'In-Person')
        
        if not topic:
            return jsonify({'error': 'Topic required'}), 400
        
        sid = gen_session_id()
        
        # Call your existing create_prog function
        result = create_prog(
            topic, fmt, dur, aud_lvl,
            company_name, company_context,
            delivery_mode, sid
        )
        
        synopsis = result[0]
        content = result[1]
        facilitator = result[2]
        handout = result[3]
        status_msg = result[4]
        session_id = result[6]
        ppt_instructions = result[7]
        ppt_prompt = result[8]
        generation_id = result[9] if len(result) > 9 else None
        
        session_data = payment_state.get(session_id, {})
        
        return jsonify({
            'success': True,
            'sessionId': session_id,
            'generationId': generation_id,
            'synopsis': synopsis,
            'content': content,
            'facilitator': facilitator,
            'handout': handout,
            'status': status_msg,
            'pptInstructions': ppt_instructions,
            'pptPrompt': ppt_prompt,
            'isLocked': not session_data.get('paid', False),
            'domain': session_data.get('domain', 'business')
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/unlock/<session_id>', methods=['POST'])
def unlock(session_id):
    try:
        if not session_id or session_id not in payment_state:
            return jsonify({'error': 'Invalid session'}), 404
        
        payment_state[session_id]['paid'] = True
        save_state()
        
        session_data = payment_state[session_id]
        ppt_inst, ppt_prompt = prepare_ppt_text(
            session_data['content'],
            session_data['topic']
        )
        
        return jsonify({
            'success': True,
            'content': session_data['content'],
            'facilitator': session_data['facil'],
            'handout': session_data['handout'],
            'pptInstructions': ppt_inst,
            'pptPrompt': ppt_prompt,
            'isLocked': False
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    try:
        data = request.json
        
        message = feedback_system.submit_feedback(
            data.get('generationId'),
            data.get('topic', 'Unknown'),
            data.get('companyName', 'N/A'),
            int(data.get('rating', 3)),
            data.get('whatWorked', ''),
            data.get('whatNeedsImprovement', ''),
            data.get('suggestions', ''),
            data.get('wouldUseAgain', True)
        )
        
        return jsonify({
            'success': True,
            'message': message
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/feedback/stats', methods=['GET'])
def get_stats():
    try:
        stats = feedback_system.get_feedback_stats()
        
        if stats and stats[0] > 0:
            return jsonify({
                'success': True,
                'stats': {
                    'totalFeedback': stats[0],
                    'avgRating': round(stats[1], 2),
                    'positiveCount': stats[2],
                    'wouldUseAgainCount': stats[3]
                }
            })
        return jsonify({
            'success': True,
            'stats': {
                'totalFeedback': 0,
                'avgRating': 0,
                'positiveCount': 0,
                'wouldUseAgainCount': 0
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🧠 NEXUS Backend API Starting...")
    print(f"✅ Sessions loaded: {len(payment_state)}")
    
    # Hugging Face Spaces runs on port 7860
    app.run(
        host='0.0.0.0',
        port=7860,
        debug=False
    )
   
