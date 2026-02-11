# NEXUS Learning Generator (Domain-Agnostic) - Part 1
# Last Updated: 2026-01-02
# Syntax: Enhanced with Universal Domain Support

import os
import time
import random
import string
import json
from pathlib import Path
import re
from typing import Dict, List, Tuple
from urllib.parse import urlparse
import sqlite3
import uuid
from datetime import datetime
import requests

from groq import Groq


# Validate imports
assert Groq is not None, "Groq import failed"

# Get the groq_key first (this should be defined somewhere below - keep it there)
# We'll set up GROQ_API_KEYS after groq_key is defined

# MOVE THESE LINES TO AFTER WHERE groq_key IS DEFINED IN YOUR CODE
# For now, let's define a simple version:
GROQ_API_KEYS = [
    os.environ.get('GROQ_API_KEY_1', '').strip(),
    os.environ.get('GROQ_API_KEY_2', '').strip(),
    os.environ.get('GROQ_API_KEY_3', '').strip(),
    os.environ.get('GROQ_API_KEY_4', '').strip(),
    os.environ.get('GROQ_API_KEY', '').strip(),
]

# Remove empty keys
GROQ_API_KEYS = [key for key in GROQ_API_KEYS if key]
# Filter out empty keys
GROQ_API_KEYS = [key for key in GROQ_API_KEYS if key]

# Debug: Show which keys are loaded
print(f"\n{'='*60}")
print(f"🔑 API Keys Status:")
print(f"{'='*60}")
for i, key in enumerate(GROQ_API_KEYS, 1):
    if key:
        masked = f"{key[:10]}...{key[-4:]}" if len(key) > 14 else "INVALID_LENGTH"
        print(f"✅ Key {i}: {masked} (length: {len(key)})")
    else:
        print(f"❌ Key {i}: MISSING")
print(f"{'='*60}\n")

if not GROQ_API_KEYS:
    print("⚠️ CRITICAL ERROR: No valid Groq API keys found!")
    print("Please add GROQ_API_KEY secrets in Hugging Face Space settings")

if not GROQ_API_KEYS:
    print("⚠️ WARNING: No GROQ API keys found!")

current_key_index = 0
GROQ_MODEL = "llama-3.3-70b-versatile"

# ADD: Groq fallback function
def get_groq_client():
    """Get Groq client with fallback to next key if current fails"""
    global current_key_index
    return Groq(api_key=GROQ_API_KEYS[current_key_index])

def call_groq_with_fallback(messages, temperature=1, max_tokens=8000):
    """Call Groq API with automatic fallback to next key on rate limit"""
    global current_key_index
    
    for attempt in range(len(GROQ_API_KEYS)):
        try:
            print(f"🔑 Using API key #{current_key_index + 1}")
            client = get_groq_client()
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if it's a rate limit error
            if "rate" in error_msg or "limit" in error_msg or "429" in error_msg:
                print(f"⚠️ Key {current_key_index + 1} rate limited, switching to next key...")
                current_key_index = (current_key_index + 1) % len(GROQ_API_KEYS)
                
                # If we've tried all keys, wait and retry with first key
                if attempt == len(GROQ_API_KEYS) - 1:
                    print("⚠️ All keys rate limited. Waiting 60 seconds...")
                    time.sleep(60)
                    current_key_index = 0
            else:
                # Non-rate-limit error, raise it
                raise e
    
    raise Exception("Failed to get response after trying all API keys")


# ADD: Feedback System Class
class FeedbackSystem:
    def __init__(self):
        # Database path will be set after DATA_DIR is defined
        self.db_path = 'nexus_feedback.db'  # Temporary, will be updated
        self.db = None
    
    def initialize(self, data_dir):
        """Initialize database after DATA_DIR is available"""
        self.db_path = str(data_dir / 'nexus_feedback.db')
        
        # CRITICAL FIX: Actually create the connection
        try:
            self.db = sqlite3.connect(self.db_path, check_same_thread=False)
            self._init_db()
            print(f"✅ Database created at: {self.db_path}")
            
            # Verify it was created
            if Path(self.db_path).exists():
                print(f"✅ Database file exists: {self.db_path}")
            else:
                print(f"❌ Database file NOT created: {self.db_path}")
                
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _init_db(self):
        """Initialize feedback database"""
        if self.db is None:
            print("❌ ERROR: Database connection is None!")
            return
            
        try:
            self.db.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation_id TEXT,
                    topic TEXT,
                    company_name TEXT,
                    rating INTEGER,
                    what_worked TEXT,
                    what_needs_improvement TEXT,
                    suggestions TEXT,
                    would_use_again BOOLEAN,
                    timestamp TEXT
                )
            ''')
            
            self.db.execute('''
                CREATE TABLE IF NOT EXISTS generation_metadata (
                    generation_id TEXT PRIMARY KEY,
                    topic TEXT,
                    company_name TEXT,
                    audience_level TEXT,
                    duration TEXT,
                    frameworks_used TEXT,
                    eval_score REAL,
                    timestamp TEXT
                )
            ''')
            self.db.commit()
            print("✅ Database tables created successfully")
            
        except Exception as e:
            print(f"❌ Table creation failed: {e}")
            import traceback
            traceback.print_exc()
    
    def store_generation_metadata(self, gen_id, topic, company_name, aud_lvl, dur, frameworks, eval_score):
        """Store metadata about generation for future learning"""
        if self.db is None:
            print("❌ Cannot store metadata: Database not initialized")
            return
            
        try:
            self.db.execute('''
                INSERT OR REPLACE INTO generation_metadata 
                (generation_id, topic, company_name, audience_level, duration, frameworks_used, eval_score, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (gen_id, topic, company_name, aud_lvl, dur, json.dumps(frameworks), eval_score, datetime.now().isoformat()))
            self.db.commit()
            print(f"✅ Metadata stored for generation: {gen_id}")
        except Exception as e:
            print(f"❌ Metadata storage failed: {e}")
    
    def submit_feedback(self, gen_id, topic, company_name, rating, what_worked, what_needs_improvement, suggestions, would_use_again):
        """Store user feedback"""
        if self.db is None:
            print("❌ Cannot submit feedback: Database not initialized")
            return "Error: Database not initialized"
            
        try:
            self.db.execute('''
                INSERT INTO feedback 
                (generation_id, topic, company_name, rating, what_worked, what_needs_improvement, suggestions, would_use_again, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (gen_id, topic, company_name, rating, what_worked, what_needs_improvement, suggestions, would_use_again, datetime.now().isoformat()))
            self.db.commit()
            
            print(f"✅ Feedback saved: Gen ID {gen_id}, Rating {rating}/5")
            
            return self._generate_thank_you_message(rating, what_worked, what_needs_improvement)
            
        except Exception as e:
            print(f"❌ Feedback submission failed: {e}")
            import traceback
            traceback.print_exc()
            return f"Error saving feedback: {str(e)}"
    
    def _generate_thank_you_message(self, rating, what_worked, what_needs_improvement):
        """Generate personalized thank you message based on feedback"""
        
        message = "🙏 **Thank you for your valuable feedback!**\n\n"
        
        if rating >= 4:
            message += "✨ We're thrilled you found the training helpful!\n\n"
            message += "**What happens next:**\n"
            message += "• Your positive feedback helps us understand what works\n"
            message += "• The elements you mentioned will be prioritized in future generations\n"
            message += "• Our AI will learn to replicate these successful patterns\n\n"
        elif rating >= 3:
            message += "📊 Thank you for the constructive feedback!\n\n"
            message += "**What happens next:**\n"
            message += "• We'll analyze the areas that worked and those that need improvement\n"
            message += "• Your concerns will be addressed in future generations\n"
            message += "• The AI will adjust its approach for similar future requests\n\n"
        else:
            message += "🔧 We appreciate your honest feedback!\n\n"
            message += "**What happens next:**\n"
            message += "• Your feedback is critical for improvement\n"
            message += "• We'll specifically work on the issues you mentioned\n"
            message += "• The AI will be adjusted to avoid these problems\n"
            message += "• You can regenerate with improved settings anytime\n\n"
        
        message += "**Your Impact:**\n"
        message += "• Every piece of feedback makes Nexus smarter\n"
        message += "• You're helping improve training for everyone\n"
        message += "• Future generations will benefit from your insights\n\n"
        
        message += "💡 **Pro Tip:** You can regenerate this training anytime, and our AI will use these learnings to make it even better!"
        
        return message
    
    def get_feedback_stats(self):
        """Get overall feedback statistics"""
        if self.db is None:
            print("❌ Cannot get stats: Database not initialized")
            return None
            
        try:
            cursor = self.db.execute('''
                SELECT 
                    COUNT(*) as total_feedback,
                    AVG(rating) as avg_rating,
                    SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) as positive_count,
                    SUM(CASE WHEN would_use_again = 1 THEN 1 ELSE 0 END) as would_use_again_count
                FROM feedback
            ''')
            return cursor.fetchone()
        except Exception as e:
            print(f"❌ Stats query failed: {e}")
            return None
    
    def get_learnings_for_topic(self, topic):
        """Get what worked/didn't work for similar topics"""
        if self.db is None:
            print("❌ Cannot get learnings: Database not initialized")
            return []
            
        try:
            cursor = self.db.execute('''
                SELECT rating, what_worked, what_needs_improvement
                FROM feedback
                WHERE topic LIKE ? AND rating >= 4
                ORDER BY timestamp DESC
                LIMIT 5
            ''', (f"%{topic}%",))
            return cursor.fetchall()
        except Exception as e:
            print(f"❌ Learnings query failed: {e}")
            return []
# Setup directories first
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
STATE_FILE = DATA_DIR / "state.json"
ANALYTICS_FILE = DATA_DIR / "analytics.json"

# NOW initialize feedback system (after DATA_DIR exists)
feedback_system = FeedbackSystem()
feedback_system.initialize(DATA_DIR)

print(f"✅ Feedback database initialized at: {feedback_system.db_path}")

payment_state = {}
analytics = {
    'total_visits': 0,
    'total_generations': 0,
    'total_unlocks': 0,
    'topics_generated': {},
    'daily_stats': {}
}
# Load analytics on startup
def load_analytics():
    global analytics
    try:
        if ANALYTICS_FILE.exists():
            with open(ANALYTICS_FILE, 'r') as f:
                analytics = json.load(f)
            print(f"📊 Analytics loaded: {analytics.get('total_generations', 0)} generations")
        else:
            print("📊 No existing analytics file - starting fresh")
    except Exception as e:
        print(f"⚠️ Analytics load failed: {e}")

def save_analytics():
    try:
        with open(ANALYTICS_FILE, 'w') as f:
            json.dump(analytics, f, indent=2)
    except Exception as e:
        print(f"⚠️ Analytics save failed: {e}")

def save_state():
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(payment_state, f, indent=2)
        print(f"State saved: {len(payment_state)} sessions")
    except Exception as e:
        print(f"Save failed: {e}")

def load_state():
    global payment_state
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                payment_state = json.load(f)
            print(f"State loaded: {len(payment_state)} sessions")
        else:
            payment_state = {}
    except Exception as e:
        print(f"Load failed: {e}")
        payment_state = {}

def gen_session_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=16))


# ===== DOMAIN DETECTION SYSTEM =====

class DomainDetector:
    """Automatically detect domain and find appropriate resources"""
    
    DOMAIN_PATTERNS = {
        'medical': {
            'keywords': ['medical', 'clinical', 'surgery', 'doctor', 'patient', 'diagnosis', 
                        'treatment', 'healthcare', 'ophthalmology', 'cardiology', 'radiology',
                        'nursing', 'pharmaceutical', 'medicine', 'hospital', 'anatomy', 
                        'pathology', 'oncology', 'pediatrics', 'geriatrics'],
            'sites': ['pubmed.ncbi.nlm.nih.gov', 'nejm.org', 'bmj.com', 'thelancet.com', 
                     'aao.org', 'acc.org', 'medscape.com', 'aamc.org', 'who.int',
                     'mayoclinic.org', 'nih.gov', 'cdc.gov'],
            'search_terms': ['clinical guidelines', 'medical education', 'residency training', 
                           'CME', 'evidence-based', 'patient care protocols']
        },
        'engineering': {
            'keywords': ['engineering', 'technical', 'mechanical', 'electrical', 'civil',
                        'structural', 'manufacturing', 'design', 'systems', 'robotics',
                        'aerospace', 'chemical', 'industrial', 'materials',
                        'tensile', 'testing', 'material', 'properties', 'specimen',
                        'strength', 'ductility', 'elasticity', 'yield', 'fracture',
                        'astm', 'iso', 'standards', 'test method', 'procedure'],
            'sites': ['ieee.org', 'asme.org', 'engineeringvillage.com', 
                     'thomasnet.com', 'engineeringnews.com', 'asce.org',
                     'imeche.org', 'spe.org'],
            'search_terms': ['technical standards', 'engineering principles', 'design guidelines',
                           'certification', 'professional development', 'best practices']
        },
        'automotive': {
            'keywords': ['automotive', 'car', 'vehicle', 'servicing', 'mechanic', 'repair',
                        'maintenance', 'diagnostic', 'engine', 'transmission', 'brake',
                        'suspension', 'auto', 'technician'],
            'sites': ['ase.com', 'sae.org', 'motorage.com', 'automotivetechnician.org',
                     'iatn.net', 'motor.com', 'aftermarketnews.com'],
            'search_terms': ['service procedures', 'diagnostic training', 'repair techniques',
                           'ASE certification', 'technician training', 'automotive repair']
},
        'it_software': {
            'keywords': ['software', 'programming', 'coding', 'development', 'IT', 'cybersecurity',
                        'cloud', 'data', 'AI', 'machine learning', 'devops', 'database',
                        'networking', 'web', 'mobile', 'app', 'algorithm', 'python', 'java'],
            'sites': ['stackoverflow.com', 'github.com', 'medium.com', 'dev.to', 
                     'coursera.org', 'udacity.com', 'pluralsight.com', 'aws.amazon.com',
                     'docs.microsoft.com', 'developer.mozilla.org'],
            'search_terms': ['tutorial', 'best practices', 'certification', 'developer guide',
                           'technical documentation', 'coding standards']
        },
        'finance': {
            'keywords': ['finance', 'accounting', 'investment', 'banking', 'trading',
                        'financial', 'portfolio', 'risk', 'audit', 'tax', 'equity',
                        'debt', 'valuation', 'merger', 'acquisition'],
            'sites': ['investopedia.com', 'cfainstitute.org', 'aicpa.org',
                     'wsj.com', 'ft.com', 'bloomberg.com', 'morningstar.com'],
            'search_terms': ['financial analysis', 'professional certification', 'investment strategy',
                           'accounting principles', 'financial planning', 'CFA']
        },
        'legal': {
            'keywords': ['legal', 'law', 'attorney', 'lawyer', 'litigation', 'contract',
                        'compliance', 'regulatory', 'jurisprudence', 'court', 'statute',
                        'legislation', 'paralegal', 'advocacy'],
            'sites': ['americanbar.org', 'law.com', 'lexisnexis.com', 'westlaw.com',
                     'findlaw.com', 'justia.com', 'nolo.com'],
            'search_terms': ['legal education', 'CLE', 'case law', 'legal practice',
                           'bar preparation', 'legal research']
        },
        'education': {
            'keywords': ['teaching', 'education', 'pedagogy', 'curriculum', 'learning',
                        'classroom', 'instruction', 'academic', 'student', 'assessment',
                        'literacy', 'school', 'university', 'professor'],
            'sites': ['edutopia.org', 'teachthought.com', 'chronicle.com', 'insidehighered.com',
                     'ascd.org', 'edweek.org', 'educause.edu'],
            'search_terms': ['teaching methods', 'instructional design', 'educational research',
                           'curriculum development', 'learning theory', 'pedagogy']
        },
        'manufacturing': {
            'keywords': ['manufacturing', 'production', 'quality', 'lean', 'six sigma',
                        'operations', 'supply chain', 'assembly', 'fabrication', 'process',
                        'warehouse', 'inventory', 'logistics', 'tensile', 'testing', 'material',
                        'properties', 'specimen', 'strength', 'ductility', 'elasticity',
                        'yield', 'fracture', 'astm', 'iso', 'standards', 'test method', 'procedure'],
            'sites': ['ieee.org', 'asme.org', 'engineeringvillage.com', 
                     'thomasnet.com', 'engineeringnews.com', 'asce.org',
                     'imeche.org', 'spe.org', 'sme.org', 'manufacturingusa.com',
                     'industryweek.com', 'asq.org', 'apics.org', 'isixsigma.com', 'lean.org'],
            'search_terms': ['technical standards', 'engineering principles', 'design guidelines',
                           'certification', 'professional development', 'best practices',
                           'manufacturing processes', 'quality control', 'lean training',
                           'production optimization', 'industrial engineering', 'continuous improvement']
        },
        'sales_marketing': {
            'keywords': ['sales', 'marketing', 'branding', 'advertising', 'customer',
                        'digital marketing', 'social media', 'promotion', 'campaign',
                        'lead generation', 'CRM', 'SEO', 'content marketing'],
            'sites': ['hubspot.com', 'marketingprofs.com', 'adweek.com', 'nielsen.com',
                     'salesforce.com', 'contentmarketinginstitute.com', 'moz.com'],
            'search_terms': ['marketing strategy', 'sales training', 'customer engagement',
                           'digital marketing', 'brand management', 'sales enablement']
        },
        'hospitality': {
            'keywords': ['hospitality', 'hotel', 'restaurant', 'culinary', 'chef', 'food service',
                        'tourism', 'guest', 'catering', 'front desk', 'housekeeping', 'travel',
                        'resort', 'accommodation', 'booking', 'destination'],
            'sites': ['ahla.com', 'hospitalitynet.org', 'hotelnewsresource.com',
                     'restaurant.org', 'culinaryinstitute.edu', 'unwto.org', 'wttc.org'],
            'search_terms': ['hospitality management', 'guest service', 'hotel operations',
                           'culinary training', 'tourism management', 'travel industry']
        },
        'construction': {
            'keywords': ['construction', 'building', 'contractor', 'project management',
                        'architecture', 'surveying', 'excavation', 'concrete', 'plumbing',
                        'electrical installation', 'HVAC', 'carpentry'],
            'sites': ['constructionequipment.com', 'forconstructionpros.com', 'agc.org',
                     'nahb.org', 'constructionexec.com'],
            'search_terms': ['construction safety', 'building codes', 'project planning',
                           'construction management', 'trade skills']
        },
        'business': {
            'keywords': ['business', 'management', 'leadership', 'strategy', 'executive',
                        'entrepreneur', 'corporate', 'organization', 'planning'],
            'sites': ['hbr.org', 'mckinsey.com', 'bcg.com', 'gsb.stanford.edu', 
                     'mitsloan.mit.edu', 'iima.ac.in', 'iimb.ac.in'],
            'search_terms': ['business insights', 'management research', 'executive education',
                           'strategic framework', 'organizational development']
        }
    }
    
    
    @classmethod
    def detect_domain(cls, topic: str) -> Tuple[str, Dict]:
        """Detect domain from topic and return domain info"""
        topic_lower = topic.lower()
        
        # Score each domain
        scores = {}
        for domain, info in cls.DOMAIN_PATTERNS.items():
            score = sum(1 for keyword in info['keywords'] if keyword in topic_lower)
            scores[domain] = score
        
        # Get highest scoring domain (default to business if no match)
        best_domain = max(scores.items(), key=lambda x: x[1])
        
        if best_domain[1] > 0:
            return best_domain[0], cls.DOMAIN_PATTERNS[best_domain[0]]
        else:
            return 'business', cls.DOMAIN_PATTERNS['business']
    @classmethod
    def get_all_domains(cls) -> List[str]:
        """Return list of all supported domains"""
        return list(cls.DOMAIN_PATTERNS.keys())


# ========== HELPER FUNCTIONS ==========

def extract_site_name(url: str) -> str:
    """Extract clean site name from URL"""
    site_map = {
        'hbr.org': 'Harvard Business Review',
        'mckinsey.com': 'McKinsey & Company',
        'bcg.com': 'Boston Consulting Group',
        'pubmed.ncbi.nlm.nih.gov': 'PubMed/NIH',
        'nejm.org': 'New England Journal of Medicine',
        'bmj.com': 'BMJ Journals',
        'thelancet.com': 'The Lancet',
        'ieee.org': 'IEEE',
        'asme.org': 'ASME',
        'ase.com': 'ASE - Automotive Service Excellence',
        'sae.org': 'SAE International',
        'stackoverflow.com': 'Stack Overflow',
        'github.com': 'GitHub',
        'coursera.org': 'Coursera',
        'udacity.com': 'Udacity',
        'edutopia.org': 'Edutopia',
        'ascd.org': 'ASCD',
        'investopedia.com': 'Investopedia',
        'cfainstitute.org': 'CFA Institute',
        'hubspot.com': 'HubSpot',
        'salesforce.com': 'Salesforce',
        'iima.ac.in': 'IIM Ahmedabad',
        'iimb.ac.in': 'IIM Bangalore',
        'aao.org': 'American Academy of Ophthalmology',
        'acc.org': 'American College of Cardiology',
        'medscape.com': 'Medscape',
        'who.int': 'World Health Organization',
        'mayoclinic.org': 'Mayo Clinic',
        'cdc.gov': 'CDC',
        'nih.gov': 'National Institutes of Health',
    }
    
    try:
        domain = urlparse(url).netloc.replace('www.', '')
        
        for key, name in site_map.items():
            if key in domain:
                return name
        
        if '.edu' in domain:
            parts = domain.split('.')
            return ' '.join(word.title() for word in parts[0].split('-'))
        
        name = domain.split('.')[0]
        return name.replace('-', ' ').replace('_', ' ').title()
        
    except:
        return 'Research Source'


def generate_fallback_sources(topic: str, domain: str, domain_info: Dict) -> List[Dict]:
    """Generate generic fallback sources when search fails"""
    sources = []
    
    for site in domain_info['sites'][:3]:
        site_name = extract_site_name(f"https://{site}")
        search_url = f"https://{site}"
        
        # Create search URL if possible
        if 'google' not in site.lower():
            search_url = f"https://{site}/search?q={topic.replace(' ', '+')}"
        
        sources.append({
            'site': site_name,
            'title': f'{topic} - {domain.title()} Resources',
            'snippet': f'Professional resources and research on {topic}',
            'url': search_url
        })
    
    return sources

def remove_duplicate_sources(sources: List[Dict]) -> List[Dict]:
    """Remove duplicate sources based on URL"""
    seen_urls = set()
    unique_sources = []
    
    for source in sources:
        if source['url'] not in seen_urls:
            seen_urls.add(source['url'])
            unique_sources.append(source)
    
    return unique_sources


def fetch_research(topic: str) -> Dict:
    """Universal research fetcher that works for any domain"""
    result = {'sources': [], 'has_live': False, 'domain': None}
    
    domain, domain_info = DomainDetector.detect_domain(topic)
    result['domain'] = domain
    
    print(f"[INFO] Detected domain: {domain}")
    
    gkey, gcse = os.environ.get('GOOGLE_API_KEY'), os.environ.get('GOOGLE_CSE_ID')
    
    if gkey and gcse and False:
        print(f"[INFO] Google API keys found - attempting web search")
        try:
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
            
            print(f"[INFO] Building Google Custom Search service...")
            svc = build("customsearch", "v1", developerKey=gkey)
            
            search_queries = []
            
            for site in domain_info['sites'][:3]:
                search_queries.append(f'"{topic}" site:{site}')
            
            for search_term in domain_info['search_terms'][:2]:
                search_queries.append(f'"{topic}" {search_term}')
            
            search_queries.append(f'"{topic}" training curriculum site:.edu')
            search_queries.append(f'"{topic}" professional development guide')
            
            print(f"[INFO] Running {len(search_queries)} search queries...")
            
            for query in search_queries:
                try:
                    print(f"[SEARCH] Query: {query[:60]}...")
                    res = svc.cse().list(q=query, cx=gcse, num=3).execute()
                    
                    if res.get('items'):
                        for item in res['items']:
                            url = item.get('link', '')
                            
                            # Skip unwanted URLs
                            skip_keywords = ['careers', 'jobs', '/product/', 'store.', 
                                           'apply', 'employment', 'hiring', '/overview']
                            if any(keyword in url.lower() for keyword in skip_keywords):
                                continue
                            
                            site_name = extract_site_name(url)
                            
                            result['sources'].append({
                                'site': site_name,
                                'title': item.get('title', ''),
                                'snippet': item.get('snippet', ''),
                                'url': url
                            })
                            
                            print(f"[FOUND] {site_name} - {item.get('title', '')[:50]}...")
                            
                            if len(result['sources']) >= 6:
                                break
                                
                except HttpError as e:
                    error_detail = str(e)
                    print(f"[ERROR] Google API error for query '{query[:50]}...': {error_detail}")
                    
                    # Check for specific error types
                    if "rateLimitExceeded" in error_detail or "userRateLimitExceeded" in error_detail:
                        print(f"[ERROR] Rate limit exceeded - stopping Google searches")
                        break
                    elif "forbidden" in error_detail.lower() or "access" in error_detail.lower():
                        print(f"[ERROR] API not enabled - Custom Search API needs to be enabled in Google Cloud Console")
                        break
                    elif "invalid" in error_detail.lower() or "key" in error_detail.lower():
                        print(f"[ERROR] API key issue - switching to fallback")
                        break
                        
                except Exception as e:
                    print(f"[ERROR] Unexpected error for query '{query[:50]}...': {str(e)}")
                    continue
                    
                if len(result['sources']) >= 6:
                    break
            
            if result['sources']:
                result['has_live'] = True
                print(f"[SUCCESS] Google API returned {len(result['sources'])} results")
            else:
                print(f"[WARNING] Google API returned no results - using fallback")
                    
        except ImportError as e:
            print(f"[ERROR] Google API library not installed: {e}")
            print(f"[INFO] Install with: pip install google-api-python-client")
            
        except Exception as e:
            print(f"[ERROR] Google API failed completely: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # THIS SECTION MUST BE OUTSIDE THE IF BLOCK (UNINDENT IT!)
    # If Google API didn't return results, use fallback
    if len(result['sources']) == 0:
        print(f"[INFO] No Google results - using fallback sources")
        result['sources'] = generate_fallback_sources(topic, domain, domain_info)
        result['has_live'] = False
    
    # Remove duplicates
    result['sources'] = remove_duplicate_sources(result['sources'])

    print(f"[INFO] Total sources found: {len(result['sources'])}")

    # ===== FIX 1: AI FRAMEWORK GENERATION =====
    # Check if Google returned garbage (search pages, not articles)
    if result['sources']:
        useful_sources = [s for s in result['sources'] 
                         if s.get('snippet') and len(s.get('snippet', '')) > 100]
        
        if len(useful_sources) < 2:
            print(f"⚠️ Google returned {len(result['sources'])} sources but only {len(useful_sources)} useful")
            print(f"🤖 Switching to AI framework generation...")
            result['sources'] = []
            result['has_live'] = False
    
    # If no useful sources, generate domain-specific frameworks with AI
    if not result['sources'] or len(result['sources']) < 2:
        print(f"🤖 Generating AI frameworks for {domain} / {topic}...")
        
        try:
            framework_prompt = f"""You are a {domain} industry expert specializing in {topic}.

CONTEXT - You are creating frameworks for THIS specific situation:
- Topic: {topic}
- Domain: {domain}
- Generic application

YOUR TASK: Identify 3-5 NAMED frameworks/methodologies that are:
1. Specific to {domain} industry (not generic business frameworks)
2. Actually used by {domain} professionals for {topic}
3. Have documented sources/creators

PRIORITIZE:
- Industry-specific frameworks over generic business models
- Technical/operational frameworks for technical domains
- Behavioral/cultural frameworks for leadership domains
- Recent frameworks (2015+) over outdated ones

AVOID:
- Generic frameworks (SWOT, PESTEL, Porter's Five Forces) UNLESS domain-specific
- Made-up frameworks
- Frameworks from unrelated industries

Return ONLY a JSON array:
[
  {{
    "name": "Exact Framework Name",
    "source": "Creator/Source with year (e.g., 'GSMA, 2022' or 'Osterwalder, 2010')",
    "domain_specific": true,
    "description": "What it does in context of {domain} and {topic} (one sentence)",
    "application": "Specific application to {topic} in {domain} (one sentence with example)",
    "why_not_generic": "Why this is better than generic alternatives for {domain} (one sentence)"
  }}
]

EXAMPLE for Telecom + Strategic Planning:
{{
  "name": "Telecom Revenue Stream Diversification Model",
  "source": "GSMA Intelligence, 2021",
  "domain_specific": true,
  "description": "Framework for telecom operators to shift from declining voice/SMS revenue to data, IoT, and enterprise services",
  "application": "Map current revenue mix, identify declining streams, develop alternative revenue portfolios based on network assets",
  "why_not_generic": "Unlike generic Blue Ocean Strategy, this accounts for spectrum costs, regulatory constraints, and infrastructure leverage specific to telecom"
}}

Return ONLY valid JSON array, no markdown."""

            ai_response = call_groq_with_fallback(
                messages=[
                    {"role": "system", "content": f"You are a {domain} research expert. Return ONLY valid JSON, no markdown."},
                    {"role": "user", "content": framework_prompt}
                ],
                temperature=0.3,
                max_tokens=1200
            )
            
            # Parse JSON
            import re
            clean_json = re.sub(r'```json\s*|\s*```', '', ai_response).strip()
            frameworks = json.loads(clean_json)
            
            print(f"✅ Generated {len(frameworks)} frameworks: {[f['name'] for f in frameworks]}")
            
            # Convert to source format
            ai_sources = []
            for fw in frameworks[:5]:
                ai_sources.append({
                    'site': fw.get('source', f'{domain.title()} Framework'),
                    'title': fw['name'],
                    'snippet': f"{fw['description']} Application: {fw['application']}",
                    'url': f"https://www.google.com/search?q={fw['name'].replace(' ', '+')}"
                })
            
            result['sources'] = ai_sources
            result['has_live'] = True
            result['ai_generated'] = True
            
        except Exception as e:
            print(f"❌ AI framework generation failed: {e}")
            # Fallback to generic
            result['sources'] = generate_fallback_sources(topic, domain, domain_info)
            result['ai_generated'] = False

    # CRITICAL: Always return a valid dict
    return result

def fetch_company_from_google(company_name: str) -> Dict:
    try:
        import requests

        GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
        GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")

        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            print("⚠️ Google API not configured")
            return None

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": f"{company_name} company overview competitors industry",
            "num": 5
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            print("Google API error:", response.text)
            return None
            
        data = response.json()

        items = data.get("items", [])

        if not items:
            return None

        overview = ""
        sources = []

        for item in items:
            overview += f"{item.get('title')}\n{item.get('snippet')}\n\n"
            sources.append(item.get("link"))

        return {
            'has_data': True,
            'overview': overview.strip(),
            'industry': '',
            'size': '',
            'products': '',
            'news': [],
            'competitors': [],
            'market_trends': [],
            'strategic_context': '',
            'sources': sources
        }

    except Exception as e:
        print("Google fallback failed:", e)
        return None
        
def fetch_company_research(company_name: str) -> Dict:
    """Research a company using AI knowledge base"""
    
    if not company_name or len(company_name.strip()) < 2:
        return {
            'has_data': False,
            'overview': '',
            'news': [],
            'competitors': [],
            'industry': '',
            'sources': []
        }
    
    print(f"🔍 AI Research: {company_name}")
    
    try:
        # Use AI to research the company
        research_prompt = f"""Research {company_name} comprehensively and provide SPECIFIC, FACTUAL information.

Return ONLY valid JSON (no markdown, no code blocks, no explanation):

{{
  "overview": "Write 4-5 sentences about {company_name}: what they do, their market position, scale (employees/revenue if known), primary products/services. BE SPECIFIC with numbers if you know them.",
  "industry": "Specific industry sector (e.g., 'Telecommunications', 'Healthcare Technology', 'Automotive Manufacturing')",
  "size": "Company size with specifics if known (e.g., '500M subscribers, $15B revenue' or 'Mid-size, 5,000 employees')",
  "products": "List their main 4-5 products or services with specifics",
  "news": [
    {{"title": "Recent development or initiative from 2024-2025", "summary": "2-3 sentence description with specifics"}},
    {{"title": "Another recent development", "summary": "2-3 sentence description"}},
    {{"title": "Third development or challenge", "summary": "2-3 sentence description"}}
  ],
  "competitors": ["Main competitor 1", "Main competitor 2", "Main competitor 3", "Main competitor 4", "Main competitor 5"],
  "market_trends": [
    "Specific trend affecting {company_name}'s industry in 2024-2026 with data/percentages if possible",
    "Technology or regulatory change impacting their sector with specifics",
    "Customer behavior shift relevant to their business with details"
  ],
  "strategic_context": "2-3 sentences about {company_name}'s current strategic position, challenges, or market dynamics. Include competitive pressures, recent strategic moves, or market position."
}}

For {company_name} specifically, use your knowledge to provide REAL, FACTUAL information.
If {company_name} is a major company you know about (like Airtel, Infosys, Tata, etc.), provide accurate details.
Include specific numbers, market positions, and real competitors."""

        response = call_groq_with_fallback(
            messages=[
                {"role": "system", "content": "You are a business research analyst. Research companies and return comprehensive, factual information in valid JSON format. For well-known companies, provide accurate data with specific numbers. Return ONLY the JSON object, no markdown formatting, no code blocks, no explanation."},
                {"role": "user", "content": research_prompt}
            ],
            temperature=0.2,
            max_tokens=1500
        )
        
        # Parse JSON response
        import re
        
        # Remove any markdown code blocks
        clean_response = re.sub(r'```json\s*|\s*```', '', response).strip()
        
        # Extract JSON object
        json_match = re.search(r'\{.*\}', clean_response, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON found in response")
        
        company_data = json.loads(json_match.group())
        
        # Build comprehensive overview text
        full_overview = f"{company_data.get('overview', '')}\n\n"
        
        if company_data.get('size'):
            full_overview += f"**Company Scale:** {company_data['size']}\n\n"
        
        if company_data.get('products'):
            full_overview += f"**Primary Offerings:** {company_data['products']}\n\n"
        
        if company_data.get('strategic_context'):
            full_overview += f"**Strategic Position:** {company_data['strategic_context']}"
        
        print(f"  ✓ Successfully researched {company_name}")
        print(f"  ✓ Industry: {company_data.get('industry', 'Unknown')}")
        print(f"  ✓ Competitors: {len(company_data.get('competitors', []))}")
        print(f"  ✓ News items: {len(company_data.get('news', []))}")
        print(f"  ✓ Market trends: {len(company_data.get('market_trends', []))}")
        
        return {
            'has_data': True,
            'overview': full_overview.strip(),
            'industry': company_data.get('industry', 'Unknown'),
            'size': company_data.get('size', ''),
            'products': company_data.get('products', ''),
            'news': company_data.get('news', []),
            'competitors': company_data.get('competitors', []),
            'market_trends': company_data.get('market_trends', []),
            'strategic_context': company_data.get('strategic_context', ''),
            'sources': ['AI Knowledge Base - Company Research', 'Industry Analysis']
        }
        
    except json.JSONDecodeError as e:
        print(f"  ✗ JSON parsing failed: {e}")
        print(f"  Response preview: {response[:200]}...")
        return create_minimal_research(company_name)
        
    except Exception as e:
        print(f"  ✗ Research failed: {e}")
        import traceback
        traceback.print_exc()
        # Try Google fallback before minimal research
        print("🔎 Trying Google fallback...")
        google_data = fetch_company_from_google(company_name)

        if google_data:
            return google_data

        return create_minimal_research(company_name)


def create_minimal_research(company_name: str) -> Dict:
    """Create minimal research data as fallback"""
    return {
        'has_data': True,
        'overview': f"{company_name} is an organization in their industry sector. For maximum training effectiveness, please provide specific context about their situation, challenges, and strategic priorities.",
        'industry': 'To be specified',
        'size': 'To be specified',
        'products': 'To be specified',
        'news': [],
        'competitors': [],
        'market_trends': [],
        'strategic_context': '',
        'sources': ['Limited data - please provide context']
    }

def fetch_company_via_google(company_name: str, api_key: str, cse_id: str) -> Dict:
    """Fetch company research using Google Custom Search"""
    
    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        
        print(f"    → Building Google search service...")
        svc = build("customsearch", "v1", developerKey=api_key)
        
        all_snippets = []
        sources = []
        
        # Search 1: Company overview
        queries = [
            f"{company_name} company overview business model",
            f"{company_name} products services industry",
            f"{company_name} competitors market position",
            f"{company_name} news 2025 2026"
        ]
        
        for query in queries:
            try:
                print(f"    → Searching: {query[:50]}...")
                res = svc.cse().list(q=query, cx=cse_id, num=3).execute()
                
                if res.get('items'):
                    for item in res['items']:
                        snippet = item.get('snippet', '')
                        title = item.get('title', '')
                        url = item.get('url', '')
                        
                        if snippet:
                            all_snippets.append(f"**{title}**: {snippet}")
                            sources.append(url)
                        
                    print(f"    ✓ Found {len(res['items'])} results")
                    
            except HttpError as e:
                print(f"    ✗ Query failed: {e}")
                if "rateLimitExceeded" in str(e):
                    print(f"    ⚠️  Rate limit hit - stopping searches")
                    break
                continue
            
            # Limit total results
            if len(all_snippets) >= 8:
                break
        
        if not all_snippets:
            print(f"    ✗ No snippets collected from Google")
            return {'has_data': False}
        
        # Synthesize with AI
        print(f"    → Synthesizing {len(all_snippets)} search results with AI...")
        
        synthesis_prompt = f"""Based on these Google search results about {company_name}, extract structured information:

SEARCH RESULTS:
{chr(10).join(all_snippets[:8])}

Return ONLY valid JSON (no markdown, no code blocks):
{{
  "overview": "3-4 sentence overview of what {company_name} does",
  "industry": "specific industry sector",
  "size": "company size if mentioned",
  "products": "main products/services",
  "news": [
    {{"title": "recent development", "summary": "brief description"}},
    {{"title": "another development", "summary": "brief description"}}
  ],
  "competitors": ["competitor1", "competitor2", "competitor3"],
  "market_trends": ["trend1", "trend2"],
  "strategic_context": "their market position and challenges"
}}"""

        synthesis = call_groq_with_fallback(
            messages=[
                {"role": "system", "content": "Extract structured company data from search results. Return ONLY valid JSON."},
                {"role": "user", "content": synthesis_prompt}
            ],
            temperature=0.2,
            max_tokens=1200
        )
        
        # Parse JSON
        import json
        import re
        
        clean_json = re.sub(r'```json\s*|\s*```', '', synthesis).strip()
        json_match = re.search(r'\{.*\}', clean_json, re.DOTALL)
        
        if not json_match:
            raise ValueError("No JSON in AI response")
        
        company_data = json.loads(json_match.group())
        
        print(f"    ✓ Successfully synthesized Google results")
        
        # Build overview
        full_overview = f"{company_data.get('overview', '')}\n\n"
        if company_data.get('size'):
            full_overview += f"**Size:** {company_data['size']}\n\n"
        if company_data.get('products'):
            full_overview += f"**Products/Services:** {company_data['products']}"
        
        return {
            'has_data': True,
            'overview': full_overview.strip(),
            'industry': company_data.get('industry', ''),
            'news': company_data.get('news', []),
            'competitors': company_data.get('competitors', []),
            'market_trends': company_data.get('market_trends', []),
            'strategic_context': company_data.get('strategic_context', ''),
            'sources': sources[:3]
        }
        
    except ImportError:
        print(f"    ✗ Google API library not installed")
        return {'has_data': False}
    except Exception as e:
        print(f"    ✗ Google search failed: {e}")
        return {'has_data': False}


def fetch_company_via_ai(company_name: str) -> Dict:
    """Fetch company research using AI knowledge base (fallback)"""
    
    print(f"    → Using AI knowledge base...")
    
    try:
        research_prompt = f"""Research {company_name} comprehensively.

Return ONLY valid JSON (no markdown, no code blocks):
{{
  "overview": "3-4 sentences about what {company_name} does, their business, and market position",
  "industry": "specific industry sector",
  "size": "company size estimate",
  "products": "main products or services",
  "news": [
    {{"title": "recent development 1", "summary": "description"}},
    {{"title": "recent development 2", "summary": "description"}}
  ],
  "competitors": ["competitor1", "competitor2", "competitor3", "competitor4"],
  "market_trends": ["trend1 affecting their industry", "trend2 affecting their industry"],
  "strategic_context": "their current strategic position"
}}

Be specific and factual based on your knowledge of {company_name}."""

        response = call_groq_with_fallback(
            messages=[
                {"role": "system", "content": "You research companies and return structured JSON. Return ONLY valid JSON."},
                {"role": "user", "content": research_prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        
        # Parse JSON
        import json
        import re
        
        clean_json = re.sub(r'```json\s*|\s*```', '', response).strip()
        json_match = re.search(r'\{.*\}', clean_json, re.DOTALL)
        
        if not json_match:
            raise ValueError("No JSON in response")
        
        company_data = json.loads(json_match.group())
        
        # Build overview
        full_overview = f"{company_data.get('overview', '')}\n\n"
        if company_data.get('size'):
            full_overview += f"**Size:** {company_data['size']}\n\n"
        if company_data.get('products'):
            full_overview += f"**Products/Services:** {company_data['products']}"
        
        print(f"    ✓ AI research completed")
        
        return {
            'has_data': True,
            'overview': full_overview.strip(),
            'industry': company_data.get('industry', ''),
            'news': company_data.get('news', []),
            'competitors': company_data.get('competitors', []),
            'market_trends': company_data.get('market_trends', []),
            'strategic_context': company_data.get('strategic_context', ''),
            'sources': ['AI Knowledge Base']
        }
        
    except Exception as e:
        print(f"    ✗ AI research failed: {e}")
        return {
            'has_data': False,
            'overview': '',
            'news': [],
            'competitors': [],
            'industry': '',
            'sources': []
        }


def format_company_research(company_name: str, research: Dict) -> str:
    """Format company research into text for AI prompt"""
    
    if not research.get('has_data'):
        return f"\n**Company:** {company_name}\n**Note:** Using user-provided context.\n\n"
    
    output = "\n" + "="*70 + "\n"
    output += f"RESEARCHED DATA FOR {company_name.upper()}\n"
    output += "="*70 + "\n\n"
    
    if research.get('overview'):
        output += f"**Overview:**\n{research['overview']}\n\n"
    
    if research.get('industry'):
        output += f"**Industry:**\n{research['industry']}\n\n"
    
    if research.get('news'):
        output += f"**Recent News:**\n"
        for i, news in enumerate(research['news'][:3], 1):
            output += f"{i}. {news['title']}\n"
        output += "\n"
    
    if research.get('competitors'):
        output += f"**Competitors:**\n"
        output += ", ".join(research['competitors'][:5])
        output += "\n\n"
    
    output += "="*70 + "\n\n"
    
    return output

def analyze_company_context_depth(company_name, company_context):
    """Analyze how detailed the company context is and what's missing"""
    
    if not company_context or len(company_context.strip()) < 50:
        return {
            'depth_score': 0,
            'missing_critical': [
                'Company size (employees, revenue, AUM)',
                'Current challenges or pain points',
                'Competitive pressures or threats',
                'Internal constraints (budget, timeline, politics)',
                'Specific stakeholder concerns'
            ],
            'has_specifics': False
        }
    
    context_lower = company_context.lower()
    
    # Check for specificity indicators
    has_numbers = bool(re.search(r'\d+', company_context))
    has_specific_names = bool(re.search(r'[A-Z][a-z]+ [A-Z][a-z]+', company_context))
    has_constraints = any(word in context_lower for word in ['budget', 'timeline', 'limited', 'constraint', 'can\'t', 'cannot'])
    has_stakeholders = any(word in context_lower for word in ['ceo', 'cfo', 'team', 'manager', 'advisor', 'board'])
    has_challenges = any(word in context_lower for word in ['challenge', 'problem', 'issue', 'struggle', 'concern', 'frustrat'])
    
    depth_score = sum([has_numbers, has_specific_names, has_constraints, has_stakeholders, has_challenges])
    
    missing = []
    if not has_numbers:
        missing.append('Specific metrics (sizes, percentages, amounts)')
    if not has_constraints:
        missing.append('Real constraints (budget, political, technical)')
    if not has_stakeholders:
        missing.append('Named stakeholder roles or factions')
    if not has_challenges:
        missing.append('Concrete challenges or pain points')
    
    return {
        'depth_score': depth_score,
        'missing_critical': missing,
        'has_specifics': depth_score >= 3
    }
# ========== AUDIENCE LEVEL MAPPING ==========

AUD_MAP = {
    "Executive/C-Suite/Senior Leadership": "executive - strategic, skip basics, ROI focus",
    "Manager/Supervisor/Team Lead": "manager - balance strategy+tactics, team focus",
    "Emerging/New/First-Time Leader": "emerging - foundational, clear explanations",
    "Individual Contributor/Specialist": "individual - personal effectiveness, technical"
}


# ========== CONTENT GENERATION FUNCTIONS ==========

def gen_content(prompt, fmt, topic, dur, aud, res, company_name=""):
    """Generate content using Groq with fallback"""
    
    print("🎯 Generating content...")
    # Determine token limit based on format AND duration
    if fmt in ["workshop", "action learning"]:
        if "2 Days" in dur:
            max_tokens = 32000
        elif "1 Day" in dur:
            max_tokens = 24000
        else:  # Half Day
            max_tokens = 16000
    elif "2 Days" in dur or "5" in prompt:
        max_tokens = 20000
    else:
        max_tokens = 8000
    
    print(f"📊 Token limit: {max_tokens} (format={fmt}, duration={dur})")
    
    try:
        # Use the fallback system
        content = call_groq_with_fallback(
            messages=[
                {"role": "system", "content": f'''You are an expert {fmt} designer with deep research capabilities. 

CRITICAL INSTRUCTIONS:
1. Generate ALL modules requested - do NOT stop after one module
2. Do NOT add research sources/footer ANYWHERE in your response
3. Do NOT add "By NEXUS" or any closing remarks
4. Generate ONLY the content requested in the user prompt
5. Fill in ALL placeholders - NEVER leave [Same detailed structure] or [...] brackets
6. Every step, every section must have COMPLETE content written out

Each framework step MUST have:
- Full "What you do:" section with 3 concrete actions
- Full "How to do it:" section with 3 specific methods
- Complete example
- Complete common mistake
- Complete pro tip
- Complete framework with 4+ detailed steps
- "See It in Action: Real Example" case study
- "Your Turn: Practice Exercise" 
- "Tools & Templates Provided" (3 templates)
- "Resources to Go Deeper" (3 videos)

NEVER write [Same detailed structure] - write the ACTUAL structure for each step.

DO NOT ADD:
- Research sources
- Footer with "By NEXUS"
- "Why Topic Matters Now" section
- "Market Context & Trends" section
- "Business Impact" section
- Any header or wrapper content
- Just generate the exact content requested in the user prompt

Use asterisks for ALL bullet points.'''},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=32000
        )
        
        print("✅ Content generated successfully")
        
        # Just return the content as-is, no footer
        return content, time.time(), GROQ_MODEL, "Success"
        
    except Exception as e:
        print(f"❌ Generation error: {e}")
        return "Error generating content", 0, "", "Error"


def clean_module_content(content):
    """Remove AI instructions from generated content"""
    
    # Patterns to remove
    patterns_to_remove = [
        r'⚠️ CRITICAL CHECKPOINT ⚠️.*?(?=\n## MODULE|\n---|\Z)',
        r'={50,}.*?={50,}',
        r'REPEAT THE ABOVE STRUCTURE.*?(?=\n## MODULE|\n---|\Z)',
        r'✓ Did you generate Module \d+\?.*?(?=\n## MODULE|\n---|\Z)',
        r'If ANY module is missing.*?(?=\n## MODULE|\n---|\Z)',
        r'ONLY after ALL \d+ modules.*?(?=\n## MODULE|\n---|\Z)',
        r'REMINDER: FOR 2-DAY TRAINING.*?(?=\n## MODULE|\n---|\Z)',
        r'VERIFICATION BEFORE STOPPING.*?(?=\n## MODULE|\n---|\Z)',
        r'You have now completed Module \d+\..*?(?=\n## MODULE|\n---|\Z)',
        r'You MUST continue with Module \d+\..*?(?=\n## MODULE|\n---|\Z)',
        r'Do NOT stop until ALL \d+ modules are complete\..*?(?=\n## MODULE|\n---|\Z)',
        r'MODULE 1, MODULE 2, MODULE 3, MODULE 4, MODULE 5 - ALL 5 MODULES REQUIRED.*?(?=\n## MODULE|\n---|\Z)',
        r'MODULES 1 THROUGH \d+.*?(?=\n## MODULE|\n---|\Z)',
    ]
    
    import re
    cleaned_content = content
    
    for pattern in patterns_to_remove:
        cleaned_content = re.sub(pattern, '', cleaned_content, flags=re.DOTALL | re.MULTILINE)
    
    # Remove multiple consecutive blank lines
    cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)
    
    return cleaned_content

def gen_synopsis(topic, aud_lvl, fmt, dur, res):
    """Generate instructions instead of synopsis"""
    if dur == "Half Day (3-4 hours)":
        mods = 2
    elif dur == "1 Day (6-7 hours)":
        mods = 3
    else:
        mods = 5
    domain = res.get('domain', 'business')
    
    instructions = f'''# How to Use NEXUS for: {topic}
    
## 📋 What You're About to Generate

**Format:** {fmt}
**Domain:** {domain.title()}
**Audience:** {aud_lvl}
**Duration:** {dur}
**Modules/Sessions:** {mods if fmt == "Training" else (4 if dur=="1 Day (6-7 hours)" else 8) if fmt == "Workshop" else (6 if dur=="1 Day (6-7 hours)" else 12)}

---

## 🚀 Quick Start Guide

### Step 1: Review Your Settings
- Check that the topic, audience level, format, and duration are correct above
- If needed, go back and adjust before generating

### Step 2: Add Company Customization (Optional)
- **Company Name**: Enter the company receiving this training
- **Company Context**: Add specific details (size, industry, challenges, goals)
- This will customize all examples, case studies, and context for that company

### Step 3: Click Generate
- Wait 30-60 seconds while NEXUS:
  - Detects the domain ({domain})
  - Researches authoritative sources
  - Generates complete curriculum
  - Creates facilitator guide
  - Builds participant handout

### Step 4: Review & Unlock
- Review the generated content structure
- Click "Unlock Full Access" to view everything
- All materials will be immediately available

---

## 📦 What You'll Get

### 1. Complete Training Content
'''

    if fmt == "Training":
        instructions += f'''- **{mods} Full Modules** with detailed frameworks
- Context & Challenge sections for each module
- Proven frameworks with step-by-step instructions
- Real-world examples and case studies
- Practice exercises (35 min each)
- Curated video resources (under 3 min each)
- Group dialogue questions
- 30-day implementation plan
'''
    elif fmt == "Workshop":
        sess = 4 if dur=="1 Day (6-7 hours)" else 8
        instructions += f'''- **{sess} Interactive Sessions** with hands-on activities
- Opening activities (15 min each)
- Core content with frameworks (30 min)
- Group activities (30 min)
- Debrief and reflection (15 min)
- Templates and tools for each session
'''
    else:
        wks = 6 if dur=="1 Day (6-7 hours)" else 12
        instructions += f'''- **{wks}-Week Action Learning Journey**
- Challenge selection and framing
- Deep dive and analysis activities
- Solution development process
- Implementation planning
- Weekly 90-min session structure
- Coaching questions for each phase
'''

    instructions += '''
### 2. Facilitator Guide
- Opening messages for each module/session
- Key talking points
- Discussion questions
- Transition statements

### 3. Participant Handout
- Structured note-taking space
- Key concepts summary
- Framework overviews
- Action planning templates

### 4. PowerPoint Export
- AI-ready prompt for Gamma/GenSpark
- Instant PPT generation capability
- Professional design automation

---

## 💡 Pro Tips

**For Best Results:**
1. Be specific with your topic (e.g., "Strategic Planning for Healthcare" vs just "Planning")
2. Add company context for highly customized content
3. Choose audience level carefully - it shapes all frameworks and examples
4. Review the Sample tab to see output quality

**After Generation:**
1. Review all tabs before unlocking
2. Use the PPT Export feature for quick presentations
3. Customize examples with your own company stories
4. Adapt exercises to your specific time constraints

---

'''

    if res.get('has_live') and res.get('sources'):
        instructions += f"## 📚 Research Foundation ({domain.title()} Domain)\n\n"
        instructions += "Your content will be based on authoritative sources including:\n"
        instructions += ", ".join([x['site'] for x in res['sources'][:3]])
        instructions += "\n\n"
    
    instructions += "**Ready? Click the 'Generate' button to create your complete training program!**"
    
    return instructions


def get_audience_description(aud_lvl: str, domain: str) -> str:
    """Get audience description based on level and domain"""
    
    if domain in ['medical']:
        aud_map = {
            "Executive": "healthcare executives - strategic, policy focus, ROI",
            "Manager": "clinical managers - workflow, quality, team coordination",
            "Emerging": "residents/fellows - evidence-based, protocols, exam prep",
            "Individual": "practicing clinicians - advanced techniques, patient care"
        }
    elif domain in ['engineering', 'automotive', 'manufacturing', 'construction']:
        aud_map = {
            "Executive": "engineering leaders - innovation, technical strategy",
            "Manager": "technical managers - project delivery, team guidance",
            "Emerging": "entry-level engineers - fundamentals, safety, standards",
            "Individual": "senior engineers - advanced techniques, optimization"
        }
    elif domain in ['it_software']:
        aud_map = {
            "Executive": "tech executives - digital transformation, architecture",
            "Manager": "engineering managers - agile, delivery, team velocity",
            "Emerging": "junior developers - coding basics, best practices",
            "Individual": "senior developers - system design, performance"
        }
    elif domain in ['finance']:
        aud_map = {
            "Executive": "finance executives - strategic capital allocation, M&A",
            "Manager": "finance managers - budgeting, reporting, controls",
            "Emerging": "analysts - financial modeling, valuation basics",
            "Individual": "professionals - specialized analysis, compliance"
        }
    elif domain in ['legal']:
        aud_map = {
            "Executive": "partners/GCs - firm strategy, risk management",
            "Manager": "practice managers - team coordination, client service",
            "Emerging": "associates - legal research, case preparation",
            "Individual": "practitioners - specialized practice areas"
        }
    elif domain in ['education']:
        aud_map = {
            "Executive": "administrators - institutional strategy, policy",
            "Manager": "department heads - curriculum, faculty development",
            "Emerging": "new teachers - classroom management, lesson planning",
            "Individual": "experienced educators - advanced pedagogy"
        }
    elif domain in ['hospitality']:
        aud_map = {
            "Executive": "hospitality executives - brand strategy, operations",
            "Manager": "managers - service excellence, team leadership",
            "Emerging": "supervisors - guest service, shift management",
            "Individual": "professionals - specialized roles, expertise"
        }
    else:  # Business default
        aud_map = {
            "Executive": "executive - strategic, skip basics, ROI focus",
            "Manager": "manager - balance strategy+tactics, team focus",
            "Emerging": "emerging - foundational, clear explanations",
            "Individual": "individual - personal effectiveness, technical"
        }
    
    # Match audience level
    for key, desc in aud_map.items():
        if key.lower() in aud_lvl.lower():
            return desc
    
    return f"tailor for {aud_lvl}"


def get_framework_guidance(topic: str, aud_lvl: str, domain: str, num_modules: int) -> str:
    """Generate domain-specific framework guidance"""
    
    if domain in ['medical']:
        if "Executive" in aud_lvl:
            return f"FRAMEWORKS FOR HEALTHCARE EXECUTIVES ({num_modules} modules): Strategic healthcare transformation, quality improvement systems, clinical outcomes optimization, regulatory compliance, and organizational excellence. Focus on evidence-based leadership and population health."
        elif "Manager" in aud_lvl:
            return f"FRAMEWORKS FOR CLINICAL MANAGERS ({num_modules} modules): Workflow optimization, team coordination, quality metrics, patient safety protocols, resource management, and clinical effectiveness. Focus on operational excellence."
        else:
            return f"FRAMEWORKS FOR CLINICAL TRAINING ({num_modules} modules): Evidence-based diagnostic protocols, treatment algorithms, patient safety systems, clinical decision-making frameworks, and outcome measurement. Emphasis on best practices and standards of care."
    
    elif domain in ['engineering', 'automotive', 'manufacturing', 'construction']:
        if "Executive" in aud_lvl:
            return f"FRAMEWORKS FOR ENGINEERING LEADERS ({num_modules} modules): Technical innovation strategy, R&D management, product development lifecycle, quality systems implementation, and engineering excellence. Focus on competitive technical advantage."
        elif "Manager" in aud_lvl:
            return f"FRAMEWORKS FOR TECHNICAL MANAGERS ({num_modules} modules): Design reviews, technical planning, quality assurance, team collaboration, delivery management, and engineering execution. Focus on project success."
        else:
            return f"FRAMEWORKS FOR TECHNICAL TRAINING ({num_modules} modules): Diagnostic procedures, systematic troubleshooting, safety protocols, technical standards, quality control, and practical skills development. Emphasis on certification readiness."
    
    elif domain == 'it_software':
        if "Executive" in aud_lvl:
            return f"FRAMEWORKS FOR TECH EXECUTIVES ({num_modules} modules): Digital transformation strategy, technology architecture, innovation pipelines, scalability planning, and technical strategy. Focus on competitive technology advantage."
        elif "Manager" in aud_lvl:
            return f"FRAMEWORKS FOR ENGINEERING MANAGERS ({num_modules} modules): Agile methodologies, sprint planning, technical debt management, team velocity optimization, code quality, and delivery excellence. Focus on engineering productivity."
        else:
            return f"FRAMEWORKS FOR SOFTWARE DEVELOPMENT ({num_modules} modules): Design patterns, coding standards, testing strategies, debugging techniques, performance optimization, and software craftsmanship. Emphasis on clean code."
    
    elif domain == 'finance':
        return f"FRAMEWORKS FOR FINANCIAL PROFESSIONALS ({num_modules} modules): Financial modeling, risk assessment, portfolio management, regulatory compliance, investment analysis, and data-driven decision making. Emphasis on analytical rigor."
    
    elif domain == 'legal':
        return f"FRAMEWORKS FOR LEGAL PROFESSIONALS ({num_modules} modules): Legal research methodologies, case analysis, client counseling, ethical considerations, professional practice standards, and critical thinking. Emphasis on professional judgment."
    
    elif domain == 'education':
        return f"FRAMEWORKS FOR EDUCATORS ({num_modules} modules): Instructional design, learning assessment, classroom management, differentiation strategies, student engagement, and evidence-based teaching practices. Emphasis on learning outcomes."
    
    elif domain == 'sales_marketing':
        return f"FRAMEWORKS FOR SALES & MARKETING ({num_modules} modules): Customer insights, market segmentation, campaign design, sales methodology, performance metrics, and customer-centric approaches. Emphasis on revenue growth."
    
    elif domain == 'hospitality':
        return f"FRAMEWORKS FOR HOSPITALITY PROFESSIONALS ({num_modules} modules): Guest service excellence, operational efficiency, team leadership, quality standards, revenue management, and customer experience. Emphasis on service delivery."
    
    else:  # Business default
        if "Executive" in aud_lvl:
            return f"FRAMEWORKS FOR EXECUTIVES ({num_modules} modules): Strategic planning, competitive analysis, opportunity creation, portfolio prioritization, market positioning, growth strategy, and performance management. Focus on strategic ROI."
        elif "Manager" in aud_lvl:
            return f"FRAMEWORKS FOR MANAGERS ({num_modules} modules): Leadership frameworks, execution discipline, goal alignment, team development, delegation mastery, and performance management. Focus on tactical execution."
        elif "Emerging" in aud_lvl:
            return f"FRAMEWORKS FOR EMERGING LEADERS ({num_modules} modules): Team dynamics, basic delegation, goal setting, constructive feedback, personal prioritization, and foundational leadership. Focus on core skills."
        else:
            return f"FRAMEWORKS FOR INDIVIDUAL CONTRIBUTORS ({num_modules} modules): Personal effectiveness, prioritization, workflow management, continuous learning, structured communication, and self-assessment. Focus on productivity."


AUD_MAP = {
    "Executive/C-Suite/Senior Leadership": "executive - strategic, skip basics, ROI focus",
    "Manager/Supervisor/Team Lead": "manager - balance strategy+tactics, team focus",
    "Emerging/New/First-Time Leader": "emerging - foundational, clear explanations",
    "Individual Contributor/Specialist": "individual - personal effectiveness, technical"
}
# NEXUS Learning Generator - Part 3 (Content Generation with Enhanced Company Customization)

def build_deep_contextualization_prompt(company_name, company_context, context_analysis, topic, domain):
    """Build deep contextualization instructions for training"""
    
    prompt = f"""
{'='*70}
🎯 CRITICAL: DEEP CONTEXTUALIZATION REQUIREMENTS (ALL DOMAINS)
{'='*70}

MANDATORY APPROACH FOR EVERY MODULE:

1. **START WITH REAL TENSION/TRADE-OFF:**
   Instead of: "In this module, you'll learn {topic}"
   Write: "You're sitting in a conference room with 3 executives who violently disagree:
   - CFO wants to cut costs 20%
   - Sales wants to hire 50 people
   - Operations says systems will collapse if you do either
   
   Welcome to {topic}. It's about choosing what NOT to do."

2. **APPLY FRAMEWORKS TO ACTUAL DILEMMAS:**
   Use real scenarios from {company_name if company_name else 'this organization'} facing {topic} challenges.

3. **FORCE SPECIFIC CHOICES:**
   Every module must include ONE exercise where participants choose between 2-3 paths:
   - Each path has clear trade-offs
   - No "right" answer
   - Participants must DEFEND their choice with framework analysis

4. **USE PEER CASE STUDIES, NOT ASPIRATIONAL ONES:**
   DO NOT USE: Google, Netflix, Amazon (unless relevant to context)
   
   USE: Companies at similar scale/stage facing similar challenges
   - If startup → other startups
   - If traditional company → other traditional companies disrupted
   - If regional player → other regional players

5. **VERIFICATION CHECKLIST - Before completing each module:**
   ☐ Does the module start with a realistic tension/dilemma?
   ☐ Are frameworks APPLIED to scenarios (not just explained)?
   ☐ Do exercises force trade-off decisions?
   ☐ Are case studies from peer companies (not aspirational)?
   ☐ Are constraints explicitly acknowledged?

⚠️ IF MODULE FEELS GENERIC, IT'S WRONG. Rewrite with more specificity.

{'='*70}
"""
    return prompt
def build_context_warning_prompt(company_name, context_analysis, domain):
    """Build context quality warning aligned with deep contextualization standards"""

    if not context_analysis:
        return ""

    depth_score = context_analysis.get("depth_score", 0)
    has_specifics = context_analysis.get("has_specifics", False)
    missing = context_analysis.get("missing", [])

    # Only trigger when context is weak
    if depth_score >= 4 and has_specifics:
        return ""

    missing_items = "\n".join([f"- {m}" for m in missing]) if missing else "- No concrete operational details provided"

    prompt = f"""
{'='*70}
⚠️ CONTEXT QUALITY ALERT — DEEP CONTEXTUALIZATION AT RISK
{'='*70}
The context provided for **{company_name or 'this organization'}** is insufficient
to meet the Deep Contextualization standards required for this training.

📊 **Context Quality Snapshot**
- Depth Score: {depth_score}/6
- Has Specifics: {has_specifics}
- Domain Detected: {domain}

❌ **Critical Gaps Identified**
{missing_items}

🚫 WHAT THIS MEANS:
- Real tensions and trade-offs may feel generic
- Scenarios risk sounding theoretical instead of lived
- Exercises may lack meaningful constraints
- Case studies may drift toward abstraction

✅ TO UNLOCK HIGH-FIDELITY TRAINING, ADD:
1. **Real constraints**
   (budget limits, political realities, regulatory pressure, technical debt)
2. **Concrete pain points**
   (missed targets, failures, bottlenecks, internal conflicts)
3. **Decision pressure**
   (what leadership is currently debating or avoiding)
4. **Success metrics**
   (KPIs, OKRs, incentives, or consequences)

⚠️ THE PROGRAM WILL STILL BE GENERATED.
However, without these details, depth and realism will be compromised.

➡️ Rule of thumb:
**If a senior leader at {company_name or 'this organization'} wouldn’t argue with the scenario — it’s not specific enough.**
{'='*70}
"""

    return prompt    

def gen_training(topic, aud, dur, res, aud_lvl, company_name="", company_context="", delivery_mode="In-Person"):
    generation_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    # Determine number of modules based on duration
    if dur == "Half Day (3-4 hours)":
        mods = 2
        max_tokens = 8000
    elif dur == "1 Day (6-7 hours)":
        mods = 3
        max_tokens = 8000
    else:  # 2 Days
        mods = 5
        max_tokens = 16000  # Increase for more modules
    
    domain = res.get('domain', 'business')

   # Build research context with MANDATORY instructions
    rctx = ""
    research_frameworks = ""
    
    if res.get('has_live') and res.get('sources'):
        rctx = f"## RESEARCH SOURCES - YOU MUST USE THESE\n\n"
        rctx += f"The following sources contain SPECIFIC frameworks, data, and examples for {topic}.\n"
        rctx += f"YOU MUST extract and apply concepts from these sources - NOT generic advice.\n\n"
        
        for i, s in enumerate(res['sources'][:3], 1):
            site = s.get('site', 'Source')
            snippet = s.get('snippet', '')[:200]
            rctx += f"**Source {i}: {site}**\n{snippet}\n\n"
        
        research_frameworks = f"""
CRITICAL RESEARCH REQUIREMENTS:

1. **EXTRACT SPECIFIC FRAMEWORKS** from the sources above:
   - If Harvard Business Review is cited, use THEIR specific frameworks (e.g., "Porter's Five Forces", "Blue Ocean Strategy")
   - If McKinsey is cited, use THEIR methodologies (e.g., "7S Framework", "Three Horizons")
   - If domain-specific sources cited, use THEIR technical standards/protocols

2. **USE REAL DATA** from the sources:
   - Quote statistics with source attribution: "(Source: McKinsey, 2024)"
   - Reference specific studies or research mentioned
   - Use percentages, numbers, and metrics from the sources

3. **CITE EXAMPLES** from the sources:
   - If a source mentions a company case study, USE IT
   - If a source describes a specific technique, EXPLAIN IT
   - Don't invent examples when sources provide real ones

4. **FORBIDDEN:**
   - ❌ Generic frameworks not mentioned in sources
   - ❌ Made-up statistics or percentages
   - ❌ Vague "research shows" without source
   - ❌ Ignoring the research and using your general knowledge

If sources mention specific frameworks by name, YOU MUST use those exact frameworks.
"""
    else:
        rctx = f"RESEARCH: No live sources available. Use authoritative {domain} knowledge and cite well-known frameworks in the field.\n"
        research_frameworks = f"""
Since no specific research sources are available, you MUST:
1. Use well-established frameworks from {domain} field (cite by name)
2. Reference authoritative sources by name (e.g., "According to [authority in {domain}]...")
3. Use realistic data ranges typical for {domain}
4. Avoid generic business advice - stay domain-specific to {domain}
"""
    # ========== COMPANY RESEARCH (NEW) ==========
    company_research_text = ""
    
    if company_name and company_name.strip():
        print(f"\n{'='*60}")
        print(f"🔍 COMPANY RESEARCH: {company_name}")
        print(f"{'='*60}")
        
        company_research = fetch_company_research(company_name.strip())
        company_research_text = format_company_research(company_name, company_research)
        
        if company_research.get('has_data'):
            print(f"✅ Successfully researched {company_name}")
        else:
            print(f"⚠️ No research data for {company_name} - using user context only")
        
        print(f"{'='*60}\n")
    # =============================================    

    print("📚 Checking past learnings...")
    past_feedback = feedback_system.get_learnings_for_topic(topic)
    
    past_learnings = ""
    if past_feedback:
        past_learnings = "\n\nLEARNINGS FROM PAST USER FEEDBACK:\n"
        for rating, worked, needs_improvement in past_feedback:
            if worked:
                past_learnings += f"- What worked well (Rating {rating}/5): {worked}\n"
            if needs_improvement:
                past_learnings += f"- What to avoid: {needs_improvement}\n"

    lvl = get_audience_description(aud_lvl, domain)
    framework_guidance = get_framework_guidance(topic, aud_lvl, domain, mods)
    # Analyze context quality
    context_analysis = analyze_company_context_depth(company_name, company_context)
    
    print(f"\n📊 Context Quality Check:")
    print(f"  Depth Score: {context_analysis['depth_score']}/6")
    print(f"  Has Specifics: {context_analysis['has_specifics']}")
    if context_analysis['missing_critical']:
        print(f"  Missing: {', '.join(context_analysis['missing_critical'][:3])}")

    # Company info - YOUR ORIGINAL CODE
    company_info = ""
    if company_name or company_context:
        company_info = "\n\n" + "="*70 + "\n"
        company_info += "COMPANY CUSTOMIZATION\n"
        company_info += "="*70 + "\n\n"
    
        if past_learnings:
            company_info += "**LEARNINGS FROM PAST FEEDBACK:**\n"
            company_info += past_learnings + "\n\n"
    
    # === CRITICAL: PREVENT VERBATIM COPYING ===
        if company_name:
            if company_research_text:
                # We have research - use it!
                company_info += company_research_text
                company_info += "\n\n**USER-PROVIDED CONTEXT (DO NOT COPY):**\n"
                if company_context:
                    company_info += f"{company_context}\n\n"
                    company_info += "⚠️ **CRITICAL INSTRUCTION:**\n"
                    company_info += "1. DO NOT copy the user context above word-for-word\n"
                    company_info += "2. SYNTHESIZE research data + user context into NEW insights\n"
                    company_info += "3. ADD market trends, competitive dynamics, financial context\n"
                    company_info += "4. TRANSFORM generic statements into specific analysis\n\n"
        else:
            # No research - but still don't copy verbatim
            company_info += f"**TARGET COMPANY:** {company_name}\n\n"
            if company_context:
                company_info += "**USER-PROVIDED CONTEXT (DO NOT COPY VERBATIM):**\n"
                company_info += f"{company_context}\n\n"
                company_info += "⚠️ **CRITICAL INSTRUCTION:**\n"
                company_info += "You MUST transform this context, not copy it:\n"
                company_info += "1. Add financial/market context for the telecom industry\n"
                company_info += "2. Reference specific competitive threats (Jio, Vi, etc.)\n"
                company_info += "3. Analyze WHY this leadership team conflict exists (market pressure? strategic pivot?)\n"
                company_info += "4. Connect to recent industry developments (5G, ARPU decline, spectrum auctions)\n"
                company_info += "5. Make it insightful, not regurgitated\n\n"
    else:
        company_info += f"**TARGET COMPANY:** {company_name}\n"
        company_info += f"(No research data available - use user context)\n\n"
        company_info += f"You MUST research and integrate the following about {company_name}:\n\n"
        company_info += f"1. INDUSTRY & BUSINESS MODEL:\n"
        company_info += f"   - What industry/sector does {company_name} operate in?\n"
        company_info += f"   - What is their primary business model and revenue streams?\n"
        company_info += f"   - Company size (employees, revenue, market cap if public)\n"
        company_info += f"   - Key products/services they offer\n\n"
            
        company_info += f"2. RECENT NEWS & DEVELOPMENTS:\n"
        company_info += f"   - Recent announcements, launches, or initiatives from {company_name}\n"
        company_info += f"   - Any challenges or opportunities mentioned in news\n"
        company_info += f"   - Strategic direction or transformation efforts\n"
        company_info += f"   - Recent leadership changes or organizational shifts\n\n"
            
        company_info += f"3. COMPETITIVE LANDSCAPE:\n"
        company_info += f"   - Who are {company_name}'s main competitors?\n"
        company_info += f"   - Market position and competitive advantages\n"
        company_info += f"   - Industry trends affecting {company_name}\n"
        company_info += f"   - How competitors are addressing similar challenges\n\n"
            
        company_info += f"4. MARKET TRENDS SPECIFIC TO {company_name}:\n"
        company_info += f"   - Industry-specific trends affecting their sector\n"
        company_info += f"   - Technology disruptions in their market\n"
        company_info += f"   - Regulatory or policy changes impacting them\n"
        company_info += f"   - Customer/market shifts relevant to their business\n\n"
        
    if company_context:
        company_info += f"ADDITIONAL CONTEXT PROVIDED:\n{company_context}\n\n"
        company_info += f"You MUST synthesize this context with your research to create highly relevant content.\n\n"
        
        company_info += f"\nHOW TO USE THIS INFORMATION:\n\n"
        company_info += f"A. MARKET CONTEXT & TRENDS Section:\n"
        company_info += f"   - DO NOT use generic statistics\n"
        company_info += f"   - USE statistics and trends SPECIFIC to {company_name if company_name else 'their'} industry\n"
        company_info += f"   - CONNECT trends directly to {company_name if company_name else 'their company'} situation\n"
        company_info += f"   - Example: Instead of 'Companies struggle with X', write '{company_name if company_name else 'Companies in [their industry]'} faces pressure from Y trend'\n\n"
        
        company_info += f"B. BUSINESS IMPACT Section:\n"
        company_info += f"   - QUANTIFY impact using metrics relevant to {company_name if company_name else 'their'} business model\n"
        company_info += f"   - Reference {company_name if company_name else 'their'} specific challenges from context/research\n"
        company_info += f"   - Use industry benchmarks for {company_name if company_name else 'their'} sector\n"
        company_info += f"   - Connect to their revenue model, customer base, or operational metrics\n\n"
        
        company_info += f"C. WHY NOW Section:\n"
        company_info += f"   - Reference RECENT developments affecting {company_name if company_name else 'this company'}\n"
        company_info += f"   - Connect urgency to {company_name if company_name else 'their'} strategic priorities\n"
        company_info += f"   - Mention competitor moves or market shifts creating urgency\n\n"
        
        company_info += f"D. CONTEXT & CHALLENGE in Each Module:\n"
        company_info += f"   - DO NOT copy-paste the company context verbatim\n"
        company_info += f"   - TRANSFORM it: Add analysis, connect to module topic, provide insights\n"
        company_info += f"   - Make it specific: 'As a {company_name if company_name else '[industry type]'} company facing [specific challenge from context], your teams are experiencing...'\n"
        company_info += f"   - Add market intelligence: Reference what competitors or industry leaders are doing\n\n"
        
        company_info += f"E. COST OF STANDING STILL Section:\n"
        company_info += f"   - Connect directly to '{topic}' for {company_name if company_name else 'this company'}\n"
        company_info += f"   - Calculate opportunity cost in their business terms (revenue, market share, efficiency)\n"
        company_info += f"   - Reference what {company_name if company_name else 'their'} competitors are doing differently\n"
        company_info += f"   - Use industry-specific metrics and timeframes\n"
        company_info += f"   - Example: 'For a company like {company_name if company_name else '[their type]'}, delaying {topic} means...'\n\n"
        
        company_info += f"F. EXAMPLES Throughout:\n"
        company_info += f"   ⚠️ CRITICAL RULE: NEVER use {company_name if company_name else 'the target company'} in any 'See It in Action' case studies or framework examples\n"
        company_info += f"   - {company_name if company_name else 'They'} are the AUDIENCE, not the example\n"
        company_info += f"   - ALWAYS use their competitors, industry peers, or similar companies instead\n"
        company_info += f"   - Research and name specific competitors of {company_name if company_name else 'this company'} to use in examples\n"
        company_info += f"   - Make case studies relevant to their sector and scale but use OTHER companies\n\n"
        
        company_info += f"CRITICAL: Every section must feel like it was custom-built for {company_name if company_name else 'this specific company'}, not generic content with the company name dropped in.\n\n"
    # Analyze context depth and add warnings if shallow
    context_analysis = analyze_company_context_depth(company_name, company_context)
    
    if not context_analysis['has_specifics'] and (company_name or company_context):
        company_info += f"""
{'='*70}
EXAMPLES - LEARN FROM THESE BEFORE GENERATING
{'='*70}

EXAMPLE OF 10/10 MODULE (Company-Specific):

## MODULE 1: Breaking Free from the Voice Revenue Trap

**Duration:** 90 min

**Context & Challenge:**
Airtel generates 65% of revenue from voice/SMS services declining at 12% annually. 
Competitors like Jio offer free voice, forcing Airtel into a race to zero. Meanwhile, 
Airtel's 500M subscriber base and pan-India 4G network are underutilized assets 
that could generate IoT, enterprise, and digital service revenue.

**The Real Problem:**
Leadership is optimizing a dying business (better voice quality, cheaper SMS) instead 
of leveraging network assets for new revenue streams. This is like Kodak perfecting 
film while digital cameras emerged.

**Framework: Network Asset Monetization Framework (TM Forum, 2020)**

This framework helps telecom operators shift from "connectivity provider" to 
"digital platform operator" by mapping network capabilities (coverage, data, APIs) 
to revenue opportunities (IoT, enterprise solutions, fintech).

**Step 1: Audit Your Stranded Assets**
What you do:
- List your network capabilities beyond connectivity (geographic reach, customer data, billing systems)
- For Airtel: 500M subscribers, payment infrastructure, pan-India distribution
- Calculate the "opportunity cost" of using these only for voice/SMS

[continues with Airtel-specific details in EVERY step]

---

EXAMPLE OF 3/10 MODULE (Generic):

## MODULE 1: Strategic Planning Basics

**Context & Challenge:**
Companies need to plan strategically to compete effectively in the market.

**Framework: SWOT Analysis**

SWOT helps you identify strengths, weaknesses, opportunities, and threats.

**Step 1: Identify Strengths**
What you do:
- List your company's strengths
- Think about what you do well
- Write them down

[This could apply to ANY company - FAILS the test]

---

YOUR TASK: Generate modules like the 10/10 example, NOT the 3/10 example.

CRITICAL DIFFERENCES:
- 10/10: Uses company's ACTUAL numbers (65% voice revenue, 12% decline)
- 3/10: Uses vague statements ("need to compete")
- 10/10: Names real competitors (Jio)
- 3/10: Says "competitors" generically
- 10/10: Framework is industry-specific (Network Asset Monetization)
- 3/10: Framework is generic (SWOT)
- 10/10: Steps reference company's actual situation in each action
- 3/10: Steps are fill-in-the-blank templates

{'='*70}

NOW GENERATE THE {mods} MODULES FOLLOWING THE 10/10 EXAMPLE PATTERN:

The user provided limited context about {company_name if company_name else 'their company'}.

MISSING CRITICAL INFORMATION:
"""
        for missing_item in context_analysis['missing_critical']:
            company_info += f"• {missing_item}\n"
        
        company_info += f"""

YOU MUST DO THE FOLLOWING:

1. **START each module with a CONTEXT PROMPT:**
   "⚠️ To maximize training effectiveness, we need more context about {company_name if company_name else 'your organization'}:
   - [List 3-4 specific questions based on what's missing above]
   
   For now, we'll use generic examples, but please provide this info to get fully customized content."

2. **CREATE REALISTIC SCENARIOS** based on the limited info:
   - Use the domain ({domain}) to infer likely challenges
   - Create plausible stakeholder conflicts typical in {domain}
   - Build hypothetical but realistic scenarios

3. **ASK DISCOVERY QUESTIONS** in exercises:
   - "Before we apply this framework, what is YOUR company's actual situation regarding..."
   - Force participants to provide the missing context during the training

4. **PROVIDE CONDITIONAL EXAMPLES:**
   - "If you're facing X situation (common in {domain}), use this approach..."
   - "If you're facing Y situation instead, use this alternative..."

DO NOT proceed as if you have full context when you don't.

{'='*70}

"""
    # Technical training requirements for engineering/manufacturing domains
    if domain in ['engineering', 'manufacturing', 'automotive', 'construction']:
        company_info += f"""
{'='*70}
⚙️ CRITICAL TECHNICAL TRAINING REQUIREMENTS
{'='*70}

For technical/manufacturing training, you MUST:

1. **USE ACTUAL EQUIPMENT/PROCESSES:**
   - Reference SPECIFIC equipment models from context (e.g., "MTS Criterion Model 43")
   - Use EXACT SOPs from context (e.g., "SOP-QC-023 Section 4.2")
   - NOT generic terms like "tensile testing machine" or "follow procedures"

2. **USE REAL OPERATING PRACTICES:**
   - Base examples on ACTUAL scenarios from their shop floor
   - Use THEIR calibration schedules, maintenance routines
   - Reference THEIR quality gates and checkpoints

3. **USE ACTUAL METRICS:**
   - NOT illustrative metrics like "aim for good results"
   - USE their real targets: "Reduce 15% scrap to <5%", "Achieve Cpk ≥ 1.33"
   - Quote their actual acceptance criteria from context

4. **REAL-USE SCENARIOS:**
   Instead of: "Imagine testing a sample..."
   Write: "Using your MTS Model 43, testing automotive-grade steel per ASTM E8..."
   
   Instead of: "Calculate tensile strength..."
   Write: "Per SOP-QC-023 Section 4.2, enter load values into LabVIEW software..."

5. **MINIMAL EXTERNAL EXAMPLES:**
   - PRIMARY: Their equipment, their processes, their scenarios
   - SECONDARY: Industry peers only when directly comparable
   - AVOID: Generic case studies from unrelated companies

VERIFICATION CHECKLIST - Before completing each module:
☐ Equipment mentioned by actual model/name from context
☐ Procedures reference actual SOP numbers
☐ Standards cite specific ASTM/ISO from context
☐ Metrics use real targets (Cpk, defect rates, etc.)
☐ Examples based on actual operational scenarios
☐ Minimal generic/"illustrative" content

⚠️ If context lacks details, OUTPUT THIS WARNING:
"For maximum training effectiveness, please provide: [specific equipment models, SOP numbers, target metrics, common defects]"

{'='*70}

"""
# Behavioral/Leadership training requirements
    if domain in ['business', 'sales_marketing', 'education', 'legal', 'finance', 'hospitality']:
        company_info += f"""
{'='*70}
🧠 CRITICAL BEHAVIORAL/LEADERSHIP TRAINING REQUIREMENTS
{'='*70}

For behavioral/soft skills training, you MUST:

1. **USE ACTUAL ORGANIZATIONAL CULTURE:**
   - Reference SPECIFIC cultural dynamics from context
   - NOT generic "build trust" → "In your command-and-control culture where trust is earned through technical expertise, transparency means..."
   - Quote their actual decision-making processes, meeting culture, communication norms

2. **USE REAL SCENARIOS FROM THEIR ORGANIZATION:**
   - Base ALL examples on ACTUAL situations from context
   - NOT "imagine a difficult conversation" → "When Sales promises features Engineering can't deliver (per context), use this approach..."
   - Reference their specific dysfunctional patterns, recurring conflicts

3. **ADDRESS ACTUAL LEADERSHIP CHALLENGES:**
   - NOT generic "how to give feedback" → "When giving feedback to 15-year veterans who resist change (per your culture)..."
   - Use THEIR pressure points, daily frustrations, difficult situations
   - Acknowledge THEIR constraints (e.g., "Given your 6-hour meeting days...")

4. **CONTEXTUALIZE EVERY FRAMEWORK:**
   - Framework steps → Applied to THEIR specific culture/dynamics
   - Practice exercises → Using THEIR actual scenarios from context
   - Role plays → Based on THEIR real conversations/conflicts
   - Examples → From organizations with SIMILAR culture (not Google/Netflix unless relevant)

5. **REAL DIALOGUE & LANGUAGE:**
   Instead of: "Use active listening..."
   Write: "In your weekly standup where engineers interrupt constantly, try: [pause 3 seconds], 'Let me make sure I understand. You're saying the API latency is caused by...'"
   
   Instead of: "Provide constructive feedback..."
   Write: "When reviewing code where developers get defensive (per your culture), open with: 'Your error handling is solid. I have a concern about scalability...'"

6. **MINIMAL EXTERNAL EXAMPLES:**
   - PRIMARY: Their culture, their scenarios, their dynamics
   - SECONDARY: Companies with similar culture (e.g., other startups, other manufacturing-heritage firms)
   - AVOID: Google/Netflix examples unless culture explicitly matches

VERIFICATION CHECKLIST - Before completing each module:
☐ Cultural dynamics mentioned specifically from context
☐ Examples based on actual scenarios described
☐ Frameworks adapted to their decision-making/communication style
☐ Practice exercises use their real situations
☐ Language/dialogue matches their organizational style
☐ Minimal generic self-help content

⚠️ If context lacks cultural details, OUTPUT THIS WARNING:
"For maximum training effectiveness, please provide: [culture type, current behavioral challenges, specific scenarios leaders face]"

{'='*70}

"""
    # Add deep contextualization requirements
    company_info += f"""
{'='*70}
🎯 CRITICAL: DEEP CONTEXTUALIZATION REQUIREMENTS (ALL DOMAINS)
{'='*70}

MANDATORY APPROACH FOR EVERY MODULE:

1. **START WITH REAL TENSION/TRADE-OFF:**
   Instead of: "In this module, you'll learn strategic planning"
   Write: "You're sitting in a conference room with 3 executives who violently disagree:
   - CFO wants to cut costs 20%
   - Sales wants to hire 50 people
   - Operations says systems will collapse if you do either
   
   Welcome to strategic planning. It's about choosing what NOT to do."

2. **APPLY FRAMEWORKS TO ACTUAL DILEMMAS:**
   Instead of: "Step 1: Identify Strengths using SWOT"
   Write: "Your company's biggest strength is also your biggest weakness.
   
   {company_name if company_name else 'Your organization'}'s veteran team (avg 15 years tenure) knows every client personally.
   Competitors with junior staff + CRM software are faster and cheaper.
   
   SWOT Question: Is 'veteran expertise' plotted as STRENGTH or WEAKNESS?
   Answer: BOTH. That's why strategic planning is hard."

3. **FORCE SPECIFIC CHOICES:**
   Every module must include ONE exercise where participants choose between 2-3 paths:
   - Each path has clear trade-offs
   - No "right" answer
   - Participants must DEFEND their choice with framework analysis

4. **USE PEER CASE STUDIES, NOT ASPIRATIONAL ONES:**
   DO NOT USE: Google, Netflix, Amazon (unless relevant to user's context)
   
   USE: Companies at similar scale/stage facing similar challenges
   - If startup → other startups
   - If traditional company → other traditional companies disrupted
   - If regional player → other regional players
   
   NAME THEM: "ABC Corp (similar {domain} company) faced this exact choice..."

5. **MAKE EXERCISES SCENARIO-BASED:**
   Instead of: "Complete SWOT analysis for your company"
   Write: "THE SCENARIO:
   
   Monday morning. You get three emails:
   1. Biggest client (20% of revenue): 'We're switching to [competitor] unless you match their pricing'
   2. CFO: 'We need to cut $2M from budget this quarter'
   3. Star employee: 'I got an offer from [competitor] for 40% more. Counter?'
   
   You have $2M budget and 30 days.
   
   EXERCISE: Use SWOT to decide which fire to fight first and WHY."

6. **INCLUDE REAL CONSTRAINTS:**
   Every strategic decision must acknowledge:
   - Budget limits (can't do everything)
   - Time limits (can't wait for perfect info)
   - Political limits (stakeholders disagree)
   - Technical limits (systems/skills gaps)

7. **VERIFICATION CHECKLIST - Before completing each module:**
   ☐ Does the module start with a realistic tension/dilemma?
   ☐ Are frameworks APPLIED to scenarios (not just explained)?
   ☐ Do exercises force trade-off decisions?
   ☐ Are case studies from peer companies (not aspirational)?
   ☐ Are constraints explicitly acknowledged?
   ☐ Could this module be used by ANY company or is it specific?

⚠️ IF MODULE FEELS GENERIC, IT'S WRONG. Rewrite with more specificity.

{'='*70}

"""
    # Add context-based prompting
    if company_name or company_context:
        if not context_analysis['has_specifics']:
            # User gave shallow context - add adaptive training instructions
            company_info += build_context_warning_prompt(company_name, context_analysis, domain)
        
        # Add deep contextualization for ALL training
        company_info += build_deep_contextualization_prompt(
            company_name, 
            company_context, 
            context_analysis, 
            domain, 
            topic
        )
    delivery_instructions = ""
    if delivery_mode == "Virtual (Online)":
        delivery_instructions = f"""
VIRTUAL DELIVERY MODE - CRITICAL ADAPTATIONS:

All exercises and activities MUST be adapted for online/virtual delivery:

**Exercise Design for Virtual:**
- Use digital collaboration tools: Miro, Mural, Google Jamboard, Mentimeter, Padlet
- Include breakout room instructions (Zoom/Teams)
- Provide poll/chat engagement prompts
- Design for screen sharing and digital whiteboards
- Keep individual activities 10-15 min max (shorter attention spans online)
- Build in energizers every 45-60 minutes
- Use asynchronous pre-work when appropriate

**Virtual-Specific Templates:**
- Google Docs/Sheets templates (shareable links)
- Miro board templates
- Digital worksheet links
- Online poll tools (Mentimeter, Slido)

**Engagement Strategies:**
- Chat waterfalls (everyone types, posts on "go")
- Emoji reactions for quick feedback
- Virtual hand raising
- Breakout rooms for small group work (specify 3-4 people)
- Gallery view for show-and-tell

**Time Management:**
- Plan for tech setup time (5 min at start)
- Shorter segments (max 20 min presentation)
- More frequent breaks (10 min every hour)
- Buffer time for technical issues

**Examples Must Include:**
- "In breakout rooms of 3-4 people on Zoom..."
- "Using the Miro board template, individually drag and drop..."
- "Type your answer in chat, but don't hit send until facilitator says go..."
- "Share your screen to show your work..."
"""
    elif delivery_mode == "Hybrid":
        delivery_instructions = f"""
HYBRID DELIVERY MODE - CRITICAL ADAPTATIONS:

Design activities that work for BOTH in-person and remote participants:

**Hybrid Exercise Design:**
- ALL activities must work in both formats simultaneously
- Provide physical worksheets AND digital versions
- In-person participants use shared screens for virtual teammates
- Virtual participants see in-room activities via camera
- Assign "room ambassadors" to ensure virtual inclusion

**Hybrid-Specific Considerations:**
- Microphones for in-room discussions (virtual can hear)
- Hybrid breakouts: mix virtual + in-person in same groups
- Use digital tools as primary (Miro/Mentimeter) so all can participate equally
- Camera angles that show room whiteboards
- In-room participants share laptops with virtual participants

**Best Practices:**
- Always check "can virtual participants see/hear this?"
- Rotate who speaks first (in-room vs virtual)
- Use digital tools as the primary interface
- Assign in-room "virtual ambassadors"
"""
    else:  # In-Person
        delivery_instructions = f"""
IN-PERSON DELIVERY MODE:

Design for face-to-face, physical classroom environment:

**In-Person Exercise Design:**
- Physical materials: flip charts, post-its, markers, handouts
- Room movement: stand up, rotate tables, gallery walks
- Tactile activities: building with blocks, creating posters
- Table groups of 4-6 people for discussions
- Full room energy: music, physical energizers

**In-Person Templates:**
- Printed worksheets and handouts
- Flip chart templates
- Post-it note activities
- Physical card sorting exercises

**Engagement Strategies:**
- Table group discussions
- Pair-and-share activities
- Gallery walks (rotate to view other groups' work)
- Popcorn sharing (randomly call on people)
- Physical movement activities

**Examples Must Include:**
- "At your tables in groups of 4-6..."
- "Write on post-it notes and place on the flip chart..."
- "Walk around the room to view other groups' posters..."
- "Find a partner and discuss for 5 minutes..."
"""

    # DEFINE ALL GUIDANCE VARIABLES BEFORE PROMPT
    context_guidance = ""
    if company_name or company_context:
        context_guidance = f"[RESEARCH AND SYNTHESIZE: Based on {company_name} being a {company_context}, describe their current situation. DO NOT copy-paste. Add market analysis, industry trends, competitive pressures. Make it insightful, not regurgitated.]"
    else:
        context_guidance = "Where they are right now - e.g., Facing pressure to deliver faster with fewer resources"
    
    challenge_guidance = ""
    if company_name:
        challenge_guidance = f"[SPECIFIC TO {company_name}: What is the exact problem they face related to {topic}? Reference their industry, scale, and situation. Be specific about what keeps their leaders up at night.]"
    else:
        challenge_guidance = "The specific problem keeping them up at night"
    
    landscape_guidance = ""
    if company_name:
        landscape_guidance = f"[FOR {company_name} SPECIFICALLY: What has changed in their industry/market in the last 12-24 months? Reference competitor moves, technology shifts, regulatory changes, or customer behavior changes affecting them. 2-3 sentences with real market intelligence.]"
    else:
        landscape_guidance = "2-3 sentences about what is different in their world"
    
    cost_guidance = ""
    if company_name:
        cost_guidance = f"""* [QUANTIFIED FOR {company_name}]: If they delay action on {topic}, what is the financial/market/competitive cost? Use their revenue scale, market position, and industry benchmarks. Example: 'For a company at {company_name}'s scale, a 6-month delay in {topic} could mean $X in lost revenue or Y% market share erosion'
* [COMPETITIVE THREAT]: Name 2-3 competitors or industry peers who are already advancing on {topic} - what advantage are they gaining?
* [OPPORTUNITY COST]: What strategic opportunities become inaccessible if {company_name} doesn't develop capability in {topic}? Reference market trends in their sector."""
    else:
        cost_guidance = """* Specific consequence 1 with data/example
* Specific consequence 2 with data/example
* What competitors/peers are doing that they are not"""
    
    opportunity_guidance = ""
    if company_name:
        opportunity_guidance = f"[FOR {company_name}]: 1-2 sentences about what competitive advantage or market position becomes possible when they master {topic}. Connect to their strategic goals or growth plans if mentioned in context."
    else:
        opportunity_guidance = "1-2 sentences about what becomes possible when they master this"
    
    example_guidance = ""
    if company_name:
        example_guidance = f"Quick scenario showing this step in context of {company_name}'s industry"
    else:
        example_guidance = "Quick real scenario showing this step"
    
    real_example_guidance = ""
    if company_name:
        real_example_guidance = f"""DO NOT use {company_name} itself as the example.
    
        Instead, use a DIFFERENT company that is:
        - In the SAME industry as {company_name}
        - Similar scale/size to {company_name}
        - Has publicly known initiatives related to this topic
    
        Examples of similar companies to research:
        - If {company_name} is in manufacturing: Use Siemens, GE, Bosch, or similar
        - If {company_name} is in healthcare: Use Cleveland Clinic, Johns Hopkins, Mayo Clinic
        - If {company_name} is in IT/software: Use Microsoft, Google, Adobe, or similar
        - If {company_name} is in automotive: Use Toyota, BMW, Tesla, or similar
        
        Your example company should be recognizable and have documented case studies available."""
    else:
        real_example_guidance = "Use a well-known company with documented success in this area. Choose from Fortune 500 or industry leaders with public case studies."
    
    industry_guidance = ""
    if company_name:
        industry_guidance = f"[{company_name}'s industry or similar]"
    else:
        industry_guidance = "Industry"
    
    exercise_guidance = ""
    if company_name:
        exercise_guidance = f"How this exercise applies directly to challenges at {company_name}"
    else:
        exercise_guidance = "How this exercise mirrors real work"

    if company_name:
        company_specific_block = f"""
YOU MUST BUILD THIS ENTIRE TRAINING AROUND {company_name.upper()}'S ACTUAL SITUATION.

THEIR SPECIFIC CONTEXT (from research + user):
{company_research_text if company_research_text else "User-provided context only"}

MANDATORY REQUIREMENTS FOR EVERY MODULE:

1. **MODULE MUST START with {company_name}'s specific challenge**
   - NOT: "Companies struggle with strategic planning"
   - YES: "{company_name} faces a $100M revenue decline from traditional telecom services while competitors like Jio gain 15M subscribers through aggressive pricing"

2. **FRAMEWORKS MUST ADDRESS {company_name}'s situation**
   - Extract frameworks from research sources above
   - Show how framework specifically helps {company_name}
   - Use {company_name}'s actual numbers/competitors in examples

3. **EXAMPLES MUST USE {company_name}'s industry peers**
   - NOT: Generic "Company X did Y"
   - YES: "{company_research.get('competitors', ['Industry peer'])[0] if company_research.get('competitors') else 'An industry peer'} used [framework] to address [similar challenge]"

4. **EXERCISES MUST APPLY TO {company_name}'s real work**
   - Use their actual challenges from context
   - Reference their competitors, products, constraints
   - Make it impossible to complete without {company_name}-specific knowledge

VERIFICATION: After writing each module, ask:
- Could this module be used for a different company? (If YES, you failed)
- Does it reference {company_name}'s specific situation? (If NO, you failed)
- Would {company_name}'s leaders recognize their challenges? (If NO, you failed)
"""
    else:
        company_specific_block = """
NO COMPANY SPECIFIED - Use general examples but:
- Make scenarios realistic and detailed
- Use specific numbers and contexts
- Reference real industry challenges
"""

    # NOW DEFINE intro_prompt HERE - RIGHT AFTER ALL GUIDANCE VARIABLES
    intro_prompt = f'''You are creating comprehensive training content on "{topic}" for {aud_lvl}.

DOMAIN: {domain}
AUDIENCE: {aud_lvl} ({lvl})
MODULES: {mods}
DURATION: {dur}
DELIVERY MODE: {delivery_mode}

{rctx}

{research_frameworks}

{delivery_instructions}

GENERATE ONLY THE INTRODUCTION SECTIONS - DO NOT GENERATE MODULES YET:
DO NOT ADD research sources, footers, headers, or "By NEXUS" anywhere.
CRITICAL: You MUST start EVERY response with this EXACT format:
## Why Topic Matters Now

**Market Context & Trends:**
* Statistic with percentage (Source: McKinsey/HBR/Gartner).
* Data point about impact (Source: Research firm).
* Comparison with percentage (Source: Watson Wyatt/BCG).

**Business Impact:**
* Productivity stat with percentage (Source: McKinsey/Bain).
* Employee stat with percentage (Source: Gallup/Deloitte).
* Financial performance stat (Source: Watson Wyatt/PwC).

**Why Now:**
* Recent trend making topic urgent (Source: HBR/McKinsey).
* Technology changes requiring adaptation (Source: McKinsey/Gartner).
* Workforce changes (Source: Gallup/Deloitte).

Then provide all modules with complete format. Then end with 30-Day Implementation Plan and Success Metrics.

## {topic}: What It Is

**Definition:**
[Write 2-3 sentences defining "{topic}" clearly. This must be actual content, not a placeholder.]

**Business Outcomes - Why This Matters:**
When leaders master {topic}, three things change:
* **Decisions:** [Explain specifically what decisions improve and how]
* **Behaviors:** [Explain specifically what behaviors must change]
* **Mistakes:** [Explain specifically what costly mistakes will reduce]

---

## 1. CONTEXT SETTING

{f"**About {company_name}:**" if company_name else "**Your Organization:**"}
{company_context if company_context else "[Write 2-3 sentences describing the organizations current situation based on their industry and challenges]"}

**Market Reality:**
[Write three specific, researched statistics with credible sources:]
* [Industry statistic with percentage] (Source: McKinsey/HBR/Gartner)
* [Impact data point with numbers] (Source: Research firm)
* [Competitive comparison with data] (Source: Watson Wyatt/BCG)

**Where You Are Right Now:**
{context_guidance}

{'='*70}
CRITICAL INSTRUCTION - COMPANY CHALLENGE MANDATE
{'='*70}

    {company_specific_block}
{'='*70}

---

## 2. PROBLEM FRAMING 

**What's Really Broken:**
{landscape_guidance}

**Why Traditional Approaches Fail:**
[Write three specific approaches that fail:]
* [Common approach 1 that looks right but does not work - explain why]
* [Common approach 2 that seems logical but fails - explain why]
* [Common approach 3 that's comfortable but costly - explain why]

**The Cost of Standing Still:**
{cost_guidance}

**The Hidden Cost:**
{challenge_guidance}

---

STOP HERE. Generate only these introduction sections with complete content.
DO NOT add research sources, footers, "By NEXUS", or any wrapper content.'''

    print("🔄 Generating introduction...")
    intro_content = gen_content(intro_prompt, "training", topic, dur, aud_lvl, res, company_name)
    if isinstance(intro_content, tuple):
        intro_content = intro_content[0]    
    
    print(f"🔄 Generating ALL {mods} modules...")
    
    all_modules_prompt = f'''You are generating ALL {mods} COMPLETE modules for training on "{topic}" for {aud_lvl}.
CRITICAL CONTEXTUALIZATION RULES:

1. **NO GENERIC EXERCISES:**
   ❌ "Identify your company's strengths"
   ✅ "Your competitor just launched a feature you've been planning for 6 months. Do you:
       A) Rush yours to market (risk bugs)
       B) Delay to perfect it (risk losing clients)
       C) Pivot to different feature (risk wasted work)
       Choose and defend using SWOT"

2. **FRAMEWORKS MUST SOLVE REAL PROBLEMS:**
   ❌ "SWOT helps you identify strengths, weaknesses, opportunities, threats"
   ✅ "SWOT reveals the brutal truth: your strength IS your weakness.
       
       Example: {company_name if company_name else 'Company X'}'s deep client relationships 
       (Strength) require senior advisors (Expensive = Weakness) who resist automation 
       (Threat from low-cost competitors) but could become premium positioning (Opportunity).
       
       SWOT doesn't give answers. It reveals trade-offs."

3. **CASE STUDIES MUST BE PEER COMPANIES:**
   ❌ "See It in Action: Google's approach to strategic planning"
   ✅ "See It in Action: Regional Bank XYZ (similar to {company_name if company_name else 'you'})
       
       Challenge: Fintech startups offering 3% savings rates vs their 0.5%
       
       Their SWOT revealed:
       - Strength: 50-year local reputation, relationship banking
       - Weakness: Legacy tech stack, slow decision-making
       - Opportunity: Elderly clients who distrust fintechs
       - Threat: Their own kids banking with Chime/SoFi
       
       Decision: Didn't compete on rates. Doubled down on 'sleep well at night' 
       positioning for 50+ customers. Let go of millennial market.
       
       Result: Lost 30% of accounts but grew deposits 15% (older = wealthier)"

4. **EVERY MODULE NEEDS A 'FORK IN THE ROAD' MOMENT:**
   Include ONE major decision point where two reasonable executives would disagree:
   - Framed as "Path A vs Path B"
   - Each path has pros/cons
   - Framework helps analyze, not decide
   - Participants must choose and defend

5. **EXERCISES ARE SIMULATIONS, NOT WORKSHEETS:**
   ❌ "Complete this SWOT template"
   ✅ "SIMULATION: You're in Q4 planning meeting.
       
       Sales Leader: 'We need to expand to Enterprise segment - huge deals!'
       Product Leader: 'Our platform can't handle Enterprise scale - will crash'
       Finance Leader: 'Enterprise requires 18-month sales cycles - we'll run out of cash'
       
       You have 60 minutes and a whiteboard.
       
       Task: Use SWOT to map the situation and recommend ONE path forward.
       Deliver a 2-minute pitch to CEO (your group presents to room)"

6. **MAKE EVERY SECTION CONVERSATIONAL & DIRECT:**
   ❌ "Strategic planning enables organizations to achieve competitive advantage"
   ✅ "Let's be honest: Most strategic plans are bullshit.
       
       They're 50-page decks that executives present once and never look at again.
       
       Why? Because they avoid hard trade-offs.
       
       Real strategic planning is saying NO to good ideas so you can say YES 
       to great ones. It's choosing what to kill, not just what to build."

NOW GENERATE THE {mods} MODULES FOLLOWING THESE RULES:

CRITICAL MODULE COUNT REQUIREMENTS:
- Half Day (3-4 hours) = EXACTLY 2 modules
- 1 Day (6-7 hours) = EXACTLY 3 modules
- 2 Days (12-14 hours) = EXACTLY 5 modules

YOUR TASK: Generate EXACTLY {mods} modules - NOT {mods-1}, NOT {mods+1}, EXACTLY {mods}

STOP AFTER MODULE {mods} - DO NOT GENERATE MODULE {mods+1}

DOMAIN: {domain}
AUDIENCE: {aud_lvl} ({lvl})
DELIVERY MODE: {delivery_mode}

{delivery_instructions}

{company_info}

FOR EACH OF THE {mods} MODULES, USE THIS COMPLETE STRUCTURE:

## MODULE [NUMBER]: [Create a specific, action-oriented title]

**Duration:** 90 min

### What You Will Walk Away With
By the end of this module:
1. [Specific outcome 1 - What they will be able to DO differently Monday morning]
2. [Specific outcome 2 - What they will be able to DO differently Monday morning]
3. [Specific outcome 3 - What they will be able to DO differently Monday morning]

NOT theory. NOT concepts. ACTIONS to take Monday morning.

---

**Myths vs Reality:**
* **Myth:** [Common belief people have]
* **Reality:** [What is actually true, with a specific example]


---

### The Core Framework

Present a complete 4-step framework for {topic}. For each step:
- Name it clearly
- Explain why it matters  
- Show exactly what actions to take
- Provide methods for doing it
- Give a real example
- Note common mistakes
- Share pro tips

Write it in a clear, structured format with headers and bullet points. Each step should be substantially different from the others.

---

### MANDATORY SECTION - See It in Action: Real Example

 CRITICAL: {f"DO NOT use {company_name}. Use a competitor or peer company." if company_name else "Use a well-known company."}

**Company:** [Specific company name - NOT {company_name if company_name else 'the target'}]

**Industry:** [{industry_guidance}]

**Challenge:** [2-3 sentences with context]

**What They Did:**

**Step 1:** [2-3 sentences with specific details]

**Step 2:** [2-3 sentences with specific details]

**Step 3:** [2-3 sentences with specific details]

**Step 4:** [2-3 sentences with specific details]

**What Changed:**
* [Measurable result 1 with numbers and timeframe]
* [Measurable result 2 with numbers and timeframe]
* [Measurable result 3 with numbers and timeframe]

**The Key Insight:**
[2-3 sentences about the critical success factor]

---

### MANDATORY SECTION - Your Turn: Practice Exercise

**What You Will Create:** [Name the deliverable]

**Why This Matters:** {exercise_guidance}

**Instructions (35 min):**

**Individual Work (15 min):**
1. [Specific step with expected output]
2. [Specific step with expected output]
3. [Specific step with expected output]

**Small Group Discussion (10 min):**
- Share your deliverable
- Give and receive feedback
- Discuss challenges

**Refinement (10 min):**
- Revise based on feedback
- Finalize deliverable
- Prepare to share

---

### MANDATORY SECTION - Tools & Templates Provided

**Template 1: [Specific Template Name]**
- Find it: Google search "{topic} [template name] template"

**Template 2: [Specific Worksheet Name]**
- Find it: Google search "{topic} [worksheet name]"

**Template 3: [Specific Tool Name]**
- Find it: Google search "[framework name] tool template"

---

### MANDATORY SECTION - Resources to Go Deeper

**Video 1: [{topic} Framework Explained]** (Under 3 min)
- YouTube search: "{topic} [framework name] explained"
- Look for videos from: HBR, McKinsey, thought leaders

**Video 2: [Real Application of {topic}]** (Under 3 min)
- YouTube search: "{topic} case study"
- Look for videos from: Industry channels, business schools

**Video 3: [Common {topic} Pitfalls]** (Under 3 min)
- YouTube search: "{topic} mistakes to avoid"
- Look for videos from: Experts, consultants

---

### One Bold Closing Thought

[Provocative statement that reframes the module content]

**Next Step:**
[ONE specific action for the next 48 hours]

---
Generate exactly {mods} modules as specified above. Each module should be complete with all sections.
''' 

    modules_content = gen_content(all_modules_prompt, "training", topic, dur, aud_lvl, res, company_name)
    if isinstance(modules_content, tuple):
        modules_content = modules_content[0]
    
    # Generate final sections
    print("🔄 Generating implementation roadmap and metrics...")
    final_prompt = f'''Generate the final sections for a {mods}-module training on "{topic}":

## 30-Day Implementation Roadmap

**Week 1: [Focus Area from Module 1]**
- Day 1-2: [Specific actions from Module 1]
- Day 3-4: [Specific actions from Module 1]
- Day 5: [Specific milestone to achieve]

**Week 2: [Focus Area from Module 2]**
- Day 8-10: [Specific actions from Module 2]
- Day 11-12: [Specific actions from Module 2]
- Day 14: [Specific milestone to achieve]

**Week 3: [Focus Area from Module 3]**
- Day 15-17: [Specific actions from Module 3]
- Day 18-19: [Specific actions from Module 3]
- Day 21: [Specific milestone to achieve]

**Week 4: [Focus Area - Integration]**
- Day 22-24: [Integration actions across all modules]
- Day 25-26: [Refinement actions]
- Day 28-30: [Final milestone and measurement]

---

## Success Metrics

**90-Day Outcomes:**
* [Specific measurable outcome 1 - include target numbers]
* [Specific measurable outcome 2 - include target numbers]
* [Specific measurable outcome 3 - include target numbers]

**6-Month Outcomes:**
* [Specific measurable outcome 1 - include target numbers]
* [Specific measurable outcome 2 - include target numbers]
* [Specific measurable outcome 3 - include target numbers]

Fill in ALL placeholders with actual, specific content for {topic}.'''

    final_sections = gen_content(final_prompt, "training", topic, dur, aud_lvl, res, company_name)
    if isinstance(final_sections, tuple):
        final_sections = final_sections[0]
    
    # Combine everything
    content = intro_content + "\n\n---\n\n" + modules_content + "\n\n---\n\n" + final_sections
    
    # DEBUG: Check sources
    print(f"\n🔍 DEBUG: Sources data:")
    print(f"  has_live: {res.get('has_live')}")
    print(f"  sources count: {len(res.get('sources', []))}")
    if res.get('sources'):
        for i, s in enumerate(res.get('sources', [])[:3], 1):
            print(f"  Source {i}: site={s.get('site')}, url={s.get('url')}, title={s.get('title')}")
    
   # Add research sources at the very end
    domain = res.get('domain', 'business')
    footer = f"\n\n---\n\n## Research Sources\n\n"
    footer += f"**Based on {domain.title()} domain research:**\n\n"
    
    sources = res.get('sources', [])
    
    if sources:
        for s in sources[:5]:
            site = s.get('site', 'Research Source')
            title = s.get('title', f'{topic} Resources')
            url = s.get('url', '')
            
            # Format: Site: Title \n Link: URL
            footer += f"**{site}**: {title}\n"
            if url:
                footer += f"Link: {url}\n"
            footer += "\n"
    else:
        # Fallback if no sources
        footer += f"Explore these authoritative {domain} sources for '{topic}':\n\n"
        footer += f"1. Search academic databases and professional journals\n"
        footer += f"2. Review industry associations and standards bodies\n"
        footer += f"3. Consult leading practitioners and thought leaders\n\n"
    
    footer += f"*Training synthesizes insights from {domain} best practices and research*\n"
    footer += f"\n\n---\n\n*By NEXUS*"
    
    # Now add header and footer
    final_content = f"# {topic} - Training\n**Generated:** {datetime.now().strftime('%Y-%m-%d')}\n**Audience:** {aud}\n**Duration:** {dur}\n**Domain:** {domain.title()}\n\n---\n\n{content}\n{footer}"
    content = final_content
    
    # Store metadata
    frameworks_used = ["Framework 1", "Framework 2", "Framework 3"]
    eval_score = 4.0    
    feedback_system.store_generation_metadata(
        generation_id, 
        topic, 
        company_name or "N/A", 
        aud_lvl, 
        dur, 
        frameworks_used, 
        eval_score
    )

    print(f"\n✅ Training generated! Generation ID: {generation_id}")
    print(f"⏱️  Time taken: {time.time() - start_time:.2f} seconds")

    return content, generation_id
    
def gen_workshop(topic, aud, dur, res, company_name="", company_context="", delivery_mode="In-Person"):
    # Generate unique ID for this workshop
    generation_id = str(uuid.uuid4())[:8]
    print(f"🆔 Workshop Generation ID: {generation_id}")
    
    # Workshop sessions: 2 per half day, 4 per full day, 8 for 2 days
    if dur == "Half Day (3-4 hours)":
        num_modules = 2  # 2 sessions @ 90 min each = 3 hours
    elif dur == "1 Day (6-7 hours)":
        num_modules = 4  # 4 sessions @ 90 min each = 6 hours
    else:  # 2 Days
        num_modules = 8  # 8 sessions @ 90 min each = 12 hours
    
    domain = res.get('domain', 'business')
    # ADD COMPANY RESEARCH HERE
    company_research_text = ""
    if company_name and company_name.strip():
        company_research = fetch_company_research(company_name.strip())
        company_research_text = format_company_research(company_name, company_research)
    mods = num_modules
    
    # Build research context with MANDATORY instructions
    rctx = ""
    research_frameworks = ""
    
    if res.get('has_live') and res.get('sources'):
        rctx = f"## RESEARCH SOURCES - YOU MUST USE THESE\n\n"
        rctx += f"The following sources contain SPECIFIC frameworks, data, and examples for {topic}.\n"
        rctx += f"YOU MUST extract and apply concepts from these sources - NOT generic advice.\n\n"
        
        for i, s in enumerate(res['sources'][:3], 1):
            site = s.get('site', 'Source')
            snippet = s.get('snippet', '')[:200]
            rctx += f"**Source {i}: {site}**\n{snippet}\n\n"
        
        research_frameworks = f"""
CRITICAL RESEARCH REQUIREMENTS:

1. **EXTRACT SPECIFIC FRAMEWORKS** from the sources above:
   - If Harvard Business Review is cited, use THEIR specific frameworks (e.g., "Porter's Five Forces", "Blue Ocean Strategy")
   - If McKinsey is cited, use THEIR methodologies (e.g., "7S Framework", "Three Horizons")
   - If domain-specific sources cited, use THEIR technical standards/protocols

2. **USE REAL DATA** from the sources:
   - Quote statistics with source attribution: "(Source: McKinsey, 2024)"
   - Reference specific studies or research mentioned
   - Use percentages, numbers, and metrics from the sources

3. **CITE EXAMPLES** from the sources:
   - If a source mentions a company case study, USE IT
   - If a source describes a specific technique, EXPLAIN IT
   - Don't invent examples when sources provide real ones

4. **FORBIDDEN:**
   - ❌ Generic frameworks not mentioned in sources
   - ❌ Made-up statistics or percentages
   - ❌ Vague "research shows" without source
   - ❌ Ignoring the research and using your general knowledge

If sources mention specific frameworks by name, YOU MUST use those exact frameworks.
"""
    else:
        rctx = f"RESEARCH: No live sources available. Use authoritative {domain} knowledge and cite well-known frameworks in the field.\n"
        research_frameworks = f"""
Since no specific research sources are available, you MUST:
1. Use well-established frameworks from {domain} field (cite by name)
2. Reference authoritative sources by name (e.g., "According to [authority in {domain}]...")
3. Use realistic data ranges typical for {domain}
4. Avoid generic business advice - stay domain-specific to {domain}
"""

    # Enhanced company customization
    company_info = ""
    if company_name or company_context:
        company_info = "\n\nCOMPANY CUSTOMIZATION:\n"
        if company_name:
            company_info += f"Company: {company_name}\n"
        if company_context:
            company_info += f"Context: {company_context}\n"
        company_info += "Customize all scenarios and examples for this company.\n\n"

    example_guidance = ""
    if company_name:
        example_guidance = f"Quick scenario from a company SIMILAR to {company_name} (same industry/scale) - NOT {company_name} itself"
    else:
        example_guidance = "Quick real scenario showing this step"
    
    real_example_guidance = ""
    if company_name:
        real_example_guidance = f" DO NOT USE {company_name} - Use a competitor, peer company, or similar organization in {company_name}'s industry"
    else:
        real_example_guidance = "Real or realistic company name"
    
    industry_guidance = ""
    if company_name:
        industry_guidance = f"[{company_name}'s industry or similar]"
    else:
        industry_guidance = "Industry"
    
    exercise_guidance = ""
    if company_name:
        exercise_guidance = f"How this exercise applies directly to challenges at {company_name}"
    else:
        exercise_guidance = "How this exercise mirrors real work"

    prompt = f'''Create comprehensive interactive workshop on "{topic}" for {aud}. 
DOMAIN: {domain}
DURATION: {dur} ({num_modules} modules)
DELIVERY MODE: {delivery_mode}
RESEARCH: {rctx}
{company_info}

{"VIRTUAL DELIVERY: All activities must use digital tools (Miro, Zoom breakouts, Mentimeter polls, chat exercises). No physical materials." if delivery_mode == "Virtual (Online)" else ""}
{"HYBRID DELIVERY: Activities must work for both in-person and remote participants simultaneously. Use digital tools as primary interface." if delivery_mode == "Hybrid" else ""}
{"IN-PERSON DELIVERY: Use physical materials, room movement, flip charts, and table group activities." if delivery_mode == "In-Person" else ""}

CRITICAL: Generate ALL {num_modules} complete hour-by-hour sections.

===== START WITH INTRODUCTION =====
CRITICAL: You MUST start EVERY response with this EXACT format:
## Why Topic Matters Now

**Market Context & Trends:**
* Statistic with percentage (Source: McKinsey/HBR/Gartner).
* Data point about impact (Source: Research firm).
* Comparison with percentage (Source: Watson Wyatt/BCG).

**Business Impact:**
* Productivity stat with percentage (Source: McKinsey/Bain).
* Employee stat with percentage (Source: Gallup/Deloitte).
* Financial performance stat (Source: Watson Wyatt/PwC).

**Why Now:**
* Recent trend making topic urgent (Source: HBR/McKinsey).
* Technology changes requiring adaptation (Source: McKinsey/Gartner).
* Workforce changes (Source: Gallup/Deloitte).

Then provide all modules with complete format. Then end with 30-Day Implementation Plan and Success Metrics.

## {topic}: What It Is

**Definition:**
[Write 2-3 sentences defining "{topic}" clearly for workshop participants.]

{f"""**Workshop Context:**
This workshop is designed for {company_name}.
**Company Background:** {company_context}
""" if company_name or company_context else ''}

**Why This Workshop Matters:**
When participants master {topic}, three things change:
* **Decisions:** [Explain specifically what decisions improve]
* **Behaviors:** [Explain specifically what behaviors change]
* **Results:** [Explain specifically what results improve]

---

## Why Now: The Urgency

**Market Context:**
* [Industry trend statistic] (Source: McKinsey/HBR)
* [Impact data point] (Source: Research firm)
* [Competitive pressure point] (Source: BCG/Gartner)

**Business Impact:**
* [Productivity/efficiency metric]
* [Employee/team performance metric]
* [Financial/operational metric]

**Whats Changed:**
[2-3 sentences about what has shifted in the last 12-24 months that makes this workshop critical now]

**The Cost of Inaction:**
* [Specific consequence 1 with data]
* [Specific consequence 2 with data]
* [What competitors/peers are doing differently]

---

===== STRUCTURE FOR EACH MODULE =====

## MODULE [NUMBER]: [CLEAR THEME/FOCUS]

**Learning Objectives for This Module:**
- Specific skill/capability 1 participants will gain
- Specific skill/capability 2 participants will gain
- Specific skill/capability 3 participants will gain

---

### Welcome & Energizer (10 minutes)

**Interactive Opening:**
* Poll Question 1: [Specific engaging question related to hours theme]
* Poll Question 2: [Related follow-up question]
* Quick Activity: [2-3 minute networking or discussion prompt]

**Purpose:** [Why this energizer sets up the hours learning]

---
### Conceptual Input: [FRAMEWORK/CONCEPT NAME] (20 minutes)

**Interactive Presentation with Engagement:**

**The [Framework Name] for {domain}:**

**Component 1: [Framework Name] - [Specific Application to {topic}]**

**What is [Framework Name]:**
[2-3 sentences explaining the framework itself - what it is, its core purpose, its key elements]

**Why its specifically helpful for {topic}:**
[2-3 sentences explaining how this framework uniquely addresses the challenges in {topic}]

**What you do:**
- [Concrete action using this framework]
- [Concrete action using this framework]  
- [Concrete action using this framework]

**How to do it:**
- [Specific method]
- [Specific method]
- [Specific method]

**Example:** {example_guidance}

---

**Component 2: [Framework Name] - [Specific Application to {topic}]**

**What is [Framework Name]:**
[2-3 sentences explaining the framework itself]

**Why its specifically helpful for {topic}:**
[2-3 sentences explaining how this framework addresses {topic} challenges]

**What you do:**
- [Concrete action using this framework]
- [Concrete action using this framework]
- [Concrete action using this framework]

**How to do it:**
- [Specific method]
- [Specific method]
- [Specific method]

**Example:** {example_guidance}

---

**Component 3: [Framework Name] - [Specific Application to {topic}]**

**What is [Framework Name]:**
[2-3 sentences explaining the framework itself]

**Why its specifically helpful for {topic}:**
[2-3 sentences explaining how this framework addresses {topic} challenges]

**What you do:**
- [Concrete action using this framework]
- [Concrete action using this framework]
- [Concrete action using this framework]

**How to do it:**
- [Specific method]
- [Specific method]
- [Specific method]

**Example:** {example_guidance}

---

**Component 4: [Framework Name] - [Specific Application to {topic}]**

**What is [Framework Name]:**
[2-3 sentences explaining the framework itself]

**Why its specifically helpful for {topic}:**
[2-3 sentences explaining how this framework addresses {topic} challenges]

**What you do:**
- [Concrete action using this framework]
- [Concrete action using this framework]
- [Concrete action using this framework]

**How to do it:**
- [Specific method]
- [Specific method]
- [Specific method]

**Example:** {example_guidance}

---

**Visual Aid:** [Describe Two by Two matrix, pyramid, cycle diagram, or other visual that helps understand these frameworks]
```
**Chat/Poll Exercise:**
"[Specific question participants answer in chat about applying one of these frameworks]"
Facilitator action: [Clusters responses into themes, highlights patterns, identifies outliers]

**Real Example:**
{"[Brief 2-3 sentence example from a competitor or peer company in " + company_name + "'s industry showing one of these frameworks in action]" if company_name else "[Brief 2-3 sentence example from " + domain + " showing framework in action]"}

---
### Activity 1: [DESCRIPTIVE ACTIVITY NAME] (35 minutes)

**Scenario Launch (5 min):**

[Write 2-3 detailed paragraphs describing a realistic scenario/challenge in {domain}. Include:
- Specific situation participants will work on
- Context and background details
- Key stakeholders involved
- The challenge or decision to be made
- Why this matters in real work]

{f"Make scenario relevant to {company_name} if possible" if company_name else f"Use {domain}-specific context"}

**Breakout Room Activity (20 min):**

Groups of 4-5 work in breakout rooms using [specific tool: Miro board/Google Jamboard/shared doc]:

Tasks to complete:
* Task 1: [Specific action with clear instructions]
* Task 2: [Specific action with clear instructions]
* Task 3: [Specific action with clear instructions]
* Task 4: [Specific action with clear instructions]

**Deliverable:** [Exactly what groups create - framework filled out, decision matrix, action plan, etc.]

**Template/Tool Provided:**
- Template Name: [Specific template name]
- What it contains: [Description of template structure]
- Access: Google search "[specific search term for template]"

**Gallery Walk & Debrief (10 min):**

* How outputs shared: [Screen share rotation, Miro board gallery view, etc.]
* Facilitator highlights: [2-3 specific patterns to look for across groups]
* Key questions to ask:
  - Question 1 about their approach
  - Question 2 about challenges faced
  - Question 3 about insights gained
* Bridge: [How this connects to next concept/framework]

---


### Activity 2: [SECOND ACTIVITY NAME] (25 minutes)

**Live Collaborative Activity on [Tool Name]:**

**Phase 1: [Activity Phase Name] (8 min)**

Instructions:
[What participants do individually or in groups]
* Specific action 1
* Specific action 2
* What they document or create

**Tool/Template:** [Specific template name and how to use it]

**Phase 2: [Second Phase Name] (10 min)**

Instructions:
[What happens next - building on Phase 1]
* Specific action 1
* Specific action 2
* How outputs are captured or shared
* What criteria they use

**Phase 3: [Third Phase Name] (7 min)**

Instructions:
[Synthesis, decision-making, or prioritization activity]
* What groups finalize or decide
* How they prepare to share
* Final deliverable

**Debrief (Remainder - approx 7 min):**

Discussion questions:
* [Question 1 connecting activity to real work challenges]
* [Question 2 about insights or surprises]
* [Question 3 about application]

Key insights facilitator emphasizes:
* Insight 1 about common patterns
* Insight 2 about best practices
* Insight 3 connecting to real work

Connection to real work: [How this activity mirrors actual {domain} challenges they face]

---

### BREAK (10 minutes)

**Energizer on Return:**
[Quick 1-2 minute poll, question, or stretch activity to re-engage participants]

---

===== END OF MODULE STRUCTURE =====

TIMING REQUIREMENTS:
- Each module is 90 minutes total
- All activities within module must add up to 90 minutes
- Include 2-3 min transition time between activities
- Include 10-minute break at end of each module

ACTIVITY REQUIREMENTS:
- NO straight lecture longer than 20 minutes
- Every Module needs minimum 2 hands-on activities
- Mix individual work, breakout groups (4-5 people), full group discussion
- Use specific collaboration tools: Miro, Mural, Google Jamboard, Mentimeter, Padlet
- Each activity has clear deliverable participants create

SCENARIO REQUIREMENTS:
- Base all scenarios on realistic {domain} challenges
- Include enough detail that participants can role-play or work the scenario
- {"Reference " + company_name + " industry/situation when creating scenarios" if company_name else "Make scenarios industry-specific for " + domain}
- Scenarios should feel like real situations participants face at work

TEMPLATE REQUIREMENTS:
- Name exact template (not generic "worksheet")
- Provide Google search term to find template online
- Describe whats on the template (columns, sections, prompts)
- Templates match activity deliverables

PROGRESSION ACROSS MODULES:

{"DAY 1 (Modules 1-4): Module 1: Foundation & context setting, Module 2: Core framework introduction, Module 3: Framework application & practice, Module 4: Day 1 synthesis. DAY 2 (Modules 5-8): Module 5: Advanced application, Module 6: Complex scenarios, Module 7: Real-world case studies, Module 8: Action planning & close" if dur == "2 Days (12-14 hours)" else "Module 1: Foundation & environmental context, Module 2: Core frameworks introduction, Module 3: Framework application & practice, Module 4: Real-world application & action planning"}

ELEMENTS REQUIRED IN EVERY Module:
1. Learning objectives (3 specific skills)
2. Welcome & energizer with polls (10 min)
3. Activity 1 with scenario, breakout, debrief (30-40 min)
4. Conceptual input with framework (15-20 min)
5. Activity 2 with phases and debrief (20-30 min)
6. Break with re-energizer (10 min)
7. At least 2 poll/chat interactions
8. At least 1 breakout room activity (15-25 min)
9. Debrief after each activity (5-10 min)
10. Named templates with Google search terms
11. Real examples {"from " + company_name + " industry" if company_name else "from " + domain}

END WORKSHOP WITH:

## WORKSHOP CLOSE & ACTION PLANNING (Final 30 minutes)

**Individual Reflection (10 min):**
Participants write:
* Whats your #1 insight from this workshop?
* What will you do differently starting Monday morning?
* Whats one thing you will stop doing?
* Whats one thing you will start doing?

**Action Plan Creation (15 min):**

Using 30-Day Action Plan template, participants document:

**Week 1 Actions:**
* Specific action 1
* Specific action 2
* Who to involve

**Week 2 Actions:**
* Specific action 1
* Specific action 2
* Resources needed

**Week 3 Actions:**
* Specific action 1
* Specific action 2
* Success metrics

**Week 4 Actions:**
* Review and adjust
* Celebrate wins
* Plan next phase

**First 48-Hour Commitment:**
* One specific action to take within 48 hours

**Accountability Partner:** [Name and contact]

**Group Share & Close (5 min):**
* Popcorn style: Each person shares their 48-hour commitment (one sentence each)
* Facilitator closing remarks on key themes from workshop
* Post-workshop resources and follow-up plan

---

REMEMBER: This is a WORKSHOP format - highly interactive, not lecture-based.

Target time allocation per Module:
- 40% DOING (hands-on activities, exercises, creating deliverables)
- 30% DISCUSSING (debriefs, dialogue, sharing insights)
- 30% LEARNING (frameworks, concepts, examples)

Make every module engaging, interactive, and immediately applicable to real work in {domain}.

Generate ALL {num_modules} modules following this exact structure with complete detail for each module.'''

    # Generate content
    content = gen_content(prompt, "workshop", topic, dur, aud, res)
    if isinstance(content, tuple):
        content = content[0]
    
   # Add research sources at the very end
    domain = res.get('domain', 'business')
    footer = f"\n\n---\n\n## Research Sources\n\n"
    footer += f"**Based on {domain.title()} domain research:**\n\n"

    sources = res.get('sources', [])

    if sources:
        for s in sources[:5]:
            site = s.get('site', 'Research Source')
            title = s.get('title', f'{topic} Resources')
            url = s.get('url', '')
        
            footer += f"**{site}**: {title}\n"
            if url:
                footer += f"Link: {url}\n"
                footer += "\n"
    else:
        footer += f"Explore these authoritative {domain} sources for '{topic}':\n\n"
        footer += f"1. Search academic databases and professional journals\n"
        footer += f"2. Review industry associations and standards bodies\n"
        footer += f"3. Consult leading practitioners and thought leaders\n\n"

    footer += f"*Training synthesizes insights from {domain} best practices and research*\n"
    footer += f"\n\n---\n\n*By NEXUS*"

# Create final content with header and footer
    final_content = f"# {topic} - Workshop\n**Generated:** {datetime.now().strftime('%Y-%m-%d')}\n**Audience:** {aud}\n**Duration:** {dur}\n**Domain:** {domain.title()}\n\n---\n\n{content}\n{footer}"

    feedback_system.store_generation_metadata(generation_id, topic, company_name or "N/A", aud, dur, ["Workshop Framework"], 4.0)
    print(f"\n✅ Workshop generated! Generation ID: {generation_id}")

    return final_content, generation_id
def gen_action(topic, aud, dur, res, company_name="", company_context="", delivery_mode="In-Person"):
    generation_id = str(uuid.uuid4())[:8]
    print(f"🆔 Action Learning Generation ID: {generation_id}")
    
    # Action Learning: 6 weeks for 1 day, 12 weeks for 2 days
    if dur == "Half Day (3-4 hours)":
        wks = 4
    elif dur == "1 Day (6-7 hours)":
        wks = 6
    else:  # 2 Days
        wks = 12
    
    domain = res.get('domain', 'business')
    
    # ADD COMPANY RESEARCH HERE
    company_research_text = ""
    if company_name and company_name.strip():
        company_research = fetch_company_research(company_name.strip())
        company_research_text = format_company_research(company_name, company_research)

    # Build research context with MANDATORY instructions
    rctx = ""
    research_frameworks = ""
    
    if res.get('has_live') and res.get('sources'):
        rctx = f"## RESEARCH SOURCES - YOU MUST USE THESE\n\n"
        rctx += f"The following sources contain SPECIFIC frameworks, data, and examples for {topic}.\n"
        rctx += f"YOU MUST extract and apply concepts from these sources - NOT generic advice.\n\n"
        
        for i, s in enumerate(res['sources'][:3], 1):
            site = s.get('site', 'Source')
            snippet = s.get('snippet', '')[:200]
            rctx += f"**Source {i}: {site}**\n{snippet}\n\n"
        
        research_frameworks = f"""
CRITICAL RESEARCH REQUIREMENTS:

1. **EXTRACT SPECIFIC FRAMEWORKS** from the sources above:
   - If Harvard Business Review is cited, use THEIR specific frameworks (e.g., "Porter's Five Forces", "Blue Ocean Strategy")
   - If McKinsey is cited, use THEIR methodologies (e.g., "7S Framework", "Three Horizons")
   - If domain-specific sources cited, use THEIR technical standards/protocols

2. **USE REAL DATA** from the sources:
   - Quote statistics with source attribution: "(Source: McKinsey, 2024)"
   - Reference specific studies or research mentioned
   - Use percentages, numbers, and metrics from the sources

3. **CITE EXAMPLES** from the sources:
   - If a source mentions a company case study, USE IT
   - If a source describes a specific technique, EXPLAIN IT
   - Don't invent examples when sources provide real ones

4. **FORBIDDEN:**
   - ❌ Generic frameworks not mentioned in sources
   - ❌ Made-up statistics or percentages
   - ❌ Vague "research shows" without source
   - ❌ Ignoring the research and using your general knowledge

If sources mention specific frameworks by name, YOU MUST use those exact frameworks.
"""
    else:
        rctx = f"RESEARCH: No live sources available. Use authoritative {domain} knowledge and cite well-known frameworks in the field.\n"
        research_frameworks = f"""
Since no specific research sources are available, you MUST:
1. Use well-established frameworks from {domain} field (cite by name)
2. Reference authoritative sources by name (e.g., "According to [authority in {domain}]...")
3. Use realistic data ranges typical for {domain}
4. Avoid generic business advice - stay domain-specific to {domain}
"""

    company_info = ""
    if company_name or company_context:
        company_info = f"\n\nCOMPANY CUSTOMIZATION: For {company_name if company_name else 'this company'}\n"
        if company_context:
            company_info += f"Context: {company_context}\n"
        company_info += f"\nCRITICAL: Customize ALL activities with company-specific details.\n\n"
    
    mid_point = wks // 2
    
    # CRITICAL: Different prompt structure from Workshop/Training
    prompt = f"""You are creating a {wks}-week ACTION LEARNING program (NOT a workshop, NOT a training course).

CRITICAL DIFFERENCES FROM WORKSHOPS:
- This is NOT a series of sessions with activities
- This IS a structured journey where participants work on REAL business problems
- Participants spend WEEKS (not hours) on actual work challenges
- Each week has real-world application, not classroom exercises
- Focus is on DOING and REFLECTING, not learning frameworks

FORMAT: Action Learning Program
DOMAIN: {domain}
DURATION: {wks} weeks
RESEARCH: {rctx}
{company_info}

YOUR TASK: Create a {wks}-week action learning journey where participants:
1. Select a REAL business challenge related to {topic}
2. Research and analyze it over {wks} weeks
3. Develop solutions through peer coaching
4. Present recommendations to leadership

STRUCTURE YOUR RESPONSE EXACTLY LIKE THIS:

---

# {topic} - Action Learning Program

**Duration:** {wks} Weeks  
**Format:** Action Learning Sets (Weekly 90-min sessions)  
**Focus:** Solving real {topic} challenges in your organization

---

## What is Action Learning?

Action Learning is a structured process where small teams work on real business challenges over {wks} weeks, meeting weekly to:
- Share progress on their individual challenges
- Coach each other through powerful questions
- Apply {topic} concepts to actual work
- Develop solutions they can implement immediately

**This is NOT a training course.** You won't sit through lectures. You'll work on an actual {topic} challenge from your job and get peer coaching every week.

---

## Program Overview

**Duration:** {wks} weeks (one 90-minute session per week)

**Team Structure:**
- 4-6 participants per action learning set
- Each person works on their own real {topic} challenge
- Facilitator guides the process (doesn't provide answers)

**What You'll Work On:**
A real business challenge related to {topic} that:
- Is within your sphere of influence
- Can show progress in {wks} weeks
- Matters to your organization
- Involves {topic} skills/knowledge

**Weekly Commitment:**
- 90-minute action learning set meeting
- 2-3 hours of work on your challenge between sessions
- Brief pre-work (readings, reflection) as assigned

---

## Weekly Structure

Each 90-minute session follows this format:

**Check-In (15 minutes):**
- Progress updates from each participant
- Obstacles encountered since last session
- Insights or breakthroughs

**Focused Coaching (45 minutes):**
- Deep dive on 1-2 participants' challenges
- Peers ask powerful questions (not advice-giving)
- Explore assumptions and reframe problems

**Action Planning (20 minutes):**
- Each person commits to specific next steps
- Identify resource needs and support
- Set accountability for next session

**Reflection (10 minutes):**
- What did you learn today?
- How does this apply to your challenge?
- What will you do differently?

---

## The {wks}-Week Journey

### PHASE 1: Weeks 1-{mid_point} — Challenge Selection & Deep Analysis

**Week 1: Challenge Identification**

**What You'll Do:**
- Identify 2-3 potential {topic} challenges from your work
- Evaluate each against selection criteria (impact, feasibility, learning)
- Share with set and get feedback on which to pursue

**Session Focus:**
- Present your challenge options to the set
- Receive coaching questions to clarify and refine
- Select ONE challenge to work on for {wks} weeks

**Between Sessions:**
- Draft your challenge statement (one clear sentence)
- Map stakeholders affected by this challenge
- Gather baseline data on current state

**Deliverable:** One-page Challenge Charter (problem, scope, success criteria)

---

**Week 2: Stakeholder Analysis**

**What You'll Do:**
- Interview 3-5 stakeholders about the challenge
- Map their perspectives, needs, and concerns
- Identify hidden dynamics or political considerations

**Session Focus:**
- Share what you learned from stakeholders
- Get coached on: "What aren't they telling you?" "Who's missing from your map?"
- Explore power dynamics and influence patterns

**Between Sessions:**
- Conduct additional stakeholder conversations
- Document conflicting viewpoints
- Identify decision-makers and blockers

**Deliverable:** Stakeholder Map with insights and influence assessment

---

**Week 3: Root Cause Analysis**

**What You'll Do:**
- Gather data on your challenge (metrics, evidence, patterns)
- Apply root cause analysis (5 Whys, Fishbone, etc.)
- Distinguish symptoms from underlying causes

**Session Focus:**
- Present your root cause hypothesis
- Get challenged: "How do you know?" "What assumptions are you making?"
- Peer coaching helps you dig deeper

**Between Sessions:**
- Test your root cause hypothesis with data
- Challenge your own assumptions
- Identify what you still don't know

**Deliverable:** Root Cause Analysis Report with evidence

---

**Week {mid_point}: Hypothesis Testing**

**What You'll Do:**
- Develop 2-3 hypotheses about what might solve the challenge
- Design small experiments to test each hypothesis
- Run quick tests (pilot, prototype, or inquiry)

**Session Focus:**
- Share your hypotheses and test designs
- Get coached on: "What's the riskiest assumption?" "How can you test cheaply?"
- Refine your experimental approach

**Between Sessions:**
- Run your experiments
- Collect feedback and data
- Document what worked and what didn't

**Deliverable:** Experiment Results Summary

---

### PHASE 2: Weeks {mid_point+1}-{wks-1} — Solution Development & Testing

**Week {mid_point+1}: Solution Design**

**What You'll Do:**
- Based on your experiments, design 2-3 solution approaches
- Evaluate each against feasibility, impact, and resources
- Get peer input on blind spots and risks

**Session Focus:**
- Present your solution options
- Get coached on trade-offs and unintended consequences
- Pressure-test your assumptions

**Between Sessions:**
- Refine your preferred solution
- Identify resources and support needed
- Map implementation steps

**Deliverable:** Solution Proposal (2-3 pages)

---

**Week {mid_point+2}: Pilot Planning**

**What You'll Do:**
- Design a small-scale pilot of your solution
- Identify success metrics and feedback mechanisms
- Plan rollout timeline and resources

**Session Focus:**
- Share your pilot design
- Get coached on: "What could go wrong?" "How will you know it's working?"
- Refine success criteria

**Between Sessions:**
- Secure approval and resources for pilot
- Recruit participants or test group
- Prepare pilot materials and process

**Deliverable:** Pilot Implementation Plan

---

**Week {wks-1}: Pilot Results & Iteration**

**What You'll Do:**
- Run your pilot and collect data
- Gather qualitative feedback from participants
- Assess what worked, what didn't, and why

**Session Focus:**
- Share pilot results (successes and failures)
- Get coached on: "What surprised you?" "What would you change?"
- Plan iterations based on learning

**Between Sessions:**
- Iterate on your solution based on pilot feedback
- Prepare for final presentation to leadership
- Document your learning journey

**Deliverable:** Pilot Results Report with recommendations

---

### PHASE 3: Week {wks} — Final Presentation & Action Planning

**Week {wks}: Leadership Presentation & Next Steps**

**What You'll Do:**
- Present your challenge, analysis, solution, and pilot results
- Make recommendations to leadership or stakeholders
- Commit to next 90 days of implementation

**Session Focus:**
- Practice presentations with peer feedback
- Final coaching on messaging and influence
- Celebrate learning and progress

**Final Deliverable:**
- 10-minute presentation to leadership
- Implementation roadmap for next 90 days
- Reflection on personal learning and growth

---

## Success Criteria

**Process Measures:**
- Attendance and engagement in weekly sessions
- Quality of peer coaching (asking vs. telling)
- Depth of reflection and insight

**Outcome Measures:**
- Progress on real challenge (baseline → pilot results)
- Quality of analysis and solution design
- Leadership buy-in and support for implementation

**Learning Measures:**
- Growth in {topic} capabilities
- Application of action learning principles
- Confidence in tackling complex challenges

---

## Facilitator Role

**The facilitator is NOT a teacher or expert.** The facilitator:
- Holds the space for peer coaching
- Asks powerful questions to deepen thinking
- Ensures everyone gets airtime and support
- Protects the action learning process
- Does NOT give advice or answers

---

## Resources & Support

**Action Learning Methodology:**
- Questioning techniques for peer coaching
- Reflection frameworks and templates
- Challenge selection criteria
- Progress tracking tools

**{topic} Resources:**
- Curated reading list on {topic}
- Case studies of similar challenges
- Tools and templates for analysis
- Expert contacts (optional consultations)

---

## 90-Day Post-Program Implementation

After the {wks}-week program, participants commit to:

**Months 1-3:**
- Implement refined solution at scale
- Track success metrics weekly
- Monthly check-ins with action learning set
- Adjust based on real-world feedback

**Sustainability:**
- Build solution into standard operating procedures
- Train others on new approach
- Document lessons learned
- Identify next challenge to tackle

---

*This is an ACTION LEARNING program, not a workshop. Expect to DO real work, not complete exercises.*"""

    content = gen_content(prompt, "action learning", topic, dur, aud, res, company_name)
    if isinstance(content, tuple):
        content = content[0]
    
    # Add footer
    domain = res.get('domain', 'business')
    footer = f"\n\n---\n\n## Research Sources\n\n"
    footer += f"**Based on {domain.title()} domain research:**\n\n"
    
    sources = res.get('sources', [])
    
    if sources:
        for s in sources[:5]:
            site = s.get('site', 'Research Source')
            title = s.get('title', f'{topic} Resources')
            url = s.get('url', '')
            
            footer += f"**{site}**: {title}\n"
            if url:
                footer += f"Link: {url}\n"
            footer += "\n"
    else:
        footer += f"Explore these authoritative {domain} sources for '{topic}':\n\n"
        footer += f"1. Search academic databases and professional journals\n"
        footer += f"2. Review industry associations and standards bodies\n"
        footer += f"3. Consult leading practitioners and thought leaders\n\n"
    
    footer += f"*Training synthesizes insights from {domain} best practices and research*\n"
    footer += f"\n\n---\n\n*By NEXUS*"

    final_content = f"# {topic} - Action Learning\n**Generated:** {datetime.now().strftime('%Y-%m-%d')}\n**Audience:** {aud}\n**Duration:** {dur}\n**Domain:** {domain.title()}\n\n---\n\n{content}\n{footer}"

    feedback_system.store_generation_metadata(generation_id, topic, company_name or "N/A", aud, dur, ["Action Learning Framework"], 4.0)
    print(f"\n✅ Action Learning generated! Generation ID: {generation_id}")

    return final_content, generation_id

def gen_facil(fmt, topic, content):
    """Generate facilitator talking points aligned with actual modules"""
    # Extract module titles from content
    import re
    module_pattern = r'## MODULE (\d+): (.+?)(?=\n|$)'
    session_pattern = r'## SESSION (\d+): (.+?)(?=\n|$)'
    
    modules = []
    
    # Try to find modules
    module_matches = re.findall(module_pattern, content, re.MULTILINE)
    if module_matches:
        modules = [(int(num), title.strip()) for num, title in module_matches]
    else:
        # Try sessions for workshops
        session_matches = re.findall(session_pattern, content, re.MULTILINE)
        if session_matches:
            modules = [(int(num), title.strip()) for num, title in session_matches]

    if not modules:
        # Last resort: extract any ## heading as a module
        heading_matches = re.findall(r'^## (.+?)(?=\n|$)', content, re.MULTILINE)
        if heading_matches:
            modules = [(i+1, h.strip()) for i, h in enumerate(heading_matches[:8])]
        else:
            print("⚠️ No modules found in content, using fallback")
            return generate_fallback_facil(fmt, topic)

    print(f"✅ Found {len(modules)} modules for facilitator guide")

    facil_prompt = f'Create facilitator talking points for "{topic}" {fmt}.\n\nThe training has {len(modules)} modules with these EXACT titles:\n'
    for num, title in modules:
        facil_prompt += f"\n{num}. {title}"

    facil_prompt += f'''

For EACH module above, create:

## MODULE [num]: [title]

**Opening Message (2-3 sentences):**
Welcoming statement that sets up the module purpose and connects to participants real work.

**Key Talking Points (4-5 bullets):**
* Core concept 1 with brief explanation
* Core concept 2 with brief explanation
* Framework or tool name and its value
* Common pitfall to avoid
* Success indicator or outcome

**Discussion Questions to Ask:**
* Open-ended question about their current challenges
* Question that prompts reflection on past experiences
* Question that connects framework to their work context

**Transition to Next Module:**
1-2 sentences bridging to the next topic.

---

Generate talking points for ALL {len(modules)} modules using their exact titles above.
Keep it concise - facilitator needs quick reference, not full content.'''

    try:
        facilitator_content = call_groq_with_fallback(
            messages=[
                {"role": "system", "content": "You create concise, practical facilitator talking points that align exactly with the training modules provided."},
                {"role": "user", "content": facil_prompt}
            ],
            temperature=0.4,
            max_tokens=6000
        )
        return f"# FACILITATOR GUIDE: {topic}\n\n**Format:** {fmt}\n**Modules:** {len(modules)}\n\n---\n\n{facilitator_content}"
    except Exception as e:
        print(f"❌ Facilitator generation failed: {e}")
        return generate_fallback_facil(fmt, topic, modules)


def generate_fallback_facil(fmt, topic, modules=None):
    """Generate fallback facilitator content"""
    if not modules:
        modules = [(1, "Foundation"), (2, "Application"), (3, "Integration")]

    output = f"# FACILITATOR GUIDE: {topic}\n\n**Format:** {fmt}\n\n---\n\n"
    for num, title in modules:
        output += f"## MODULE {num}: {title}\n\n"
        output += f"**Opening Message:**\nWelcome to Module {num} on {title}. This module builds on our previous work and focuses on practical application of {topic}.\n\n"
        output += f"**Key Talking Points:**\n* {title} is critical for {topic} success\n* The framework we will explore has been proven across industries\n* Participants will leave with actionable tools\n* Common challenges include implementation barriers\n* Success requires both understanding and practice\n\n"
        output += f"**Discussion Questions:**\n* What challenges have you faced related to {title.lower()}?\n* How does this connect to your current priorities?\n* What would success look like in your context?\n\n"
        output += f"**Transition:**\n{'Now that we understand ' + title.lower() + ', lets move to Module ' + str(num+1) if num < len(modules) else 'This completes our learning journey - time to commit to action.'}\n\n---\n\n"
    return output


def gen_handout(fmt, topic, content):
    """Generate participant handout aligned with actual modules"""
    # Extract module titles from content
    import re
    module_pattern = r'## MODULE (\d+): (.+?)(?=\n|$)'
    session_pattern = r'## SESSION (\d+): (.+?)(?=\n|$)'
    
    modules = []
    
    # Try to find modules
    module_matches = re.findall(module_pattern, content, re.MULTILINE)
    if module_matches:
        modules = [(int(num), title.strip()) for num, title in module_matches]
    else:
        # Try sessions
        session_matches = re.findall(session_pattern, content, re.MULTILINE)
        if session_matches:
            modules = [(int(num), title.strip()) for num, title in session_matches]

    if not modules:
        heading_matches = re.findall(r'^## (.+?)(?=\n|$)', content, re.MULTILINE)
        if heading_matches:
            modules = [(i+1, h.strip()) for i, h in enumerate(heading_matches[:8])]
        else:
            print("⚠️ No modules found for handout, using fallback")
            return generate_fallback_handout(fmt, topic)

    print(f"✅ Found {len(modules)} modules for participant handout")

    handout_prompt = f'Create a participant handout for "{topic}" {fmt}.\n\nThe training has {len(modules)} modules with these EXACT titles:\n'
    for num, title in modules:
        handout_prompt += f"\n{num}. {title}"

    handout_prompt += f'''

Create a clean, print-ready handout with this structure for EACH module:

## MODULE [num]: [EXACT TITLE]

**Key Concepts:**
- Concept 1 from this module
- Concept 2 from this module
- Concept 3 from this module

**Framework Overview:**
1-2 sentence description of the main framework or tool covered in this module.

**My Key Takeaway:**
___________________________________________________________________________

**My Action Item:**
___________________________________________________________________________

**Your Notes:**
___________________________________________________________________________
___________________________________________________________________________
___________________________________________________________________________

---

Generate this format for ALL {len(modules)} modules using their exact titles.
Keep it concise - this is for participants to take notes during the session.'''

    try:
        handout_content = call_groq_with_fallback(
            messages=[
                {"role": "system", "content": "You create clean, structured participant handouts that match the training modules exactly."},
                {"role": "user", "content": handout_prompt}
            ],
            temperature=0.3,
            max_tokens=5000
        )
        topic_upper = topic.upper()
        return f"# {topic_upper} - PARTICIPANT GUIDE\n\n**Format:** {fmt}\n**Modules:** {len(modules)}\n\n---\n\n{handout_content}"
    except Exception as e:
        print(f"❌ Handout generation failed: {e}")
        return generate_fallback_handout(fmt, topic, modules)


def generate_fallback_handout(fmt, topic, modules=None):
    """Generate fallback handout content"""
    if not modules:
        modules = [(1, "Foundation"), (2, "Application"), (3, "Integration")]

    topic_upper = topic.upper()
    output = f"# {topic_upper} - PARTICIPANT GUIDE\n\n**Format:** {fmt}\n\n---\n\n"
    for num, title in modules:
        output += f"## MODULE {num}: {title}\n\n"
        output += f"**Key Concepts:**\n- Core concept related to {title.lower()}\n- Framework or tool for {title.lower()}\n- Best practices for implementation\n\n"
        output += f"**Framework Overview:**\nThis module covers the essential framework for {title.lower()} in the context of {topic}.\n\n"
        output += f"**My Key Takeaway:**\n___________________________________________________________________________\n\n"
        output += f"**My Action Item:**\n___________________________________________________________________________\n\n"
        output += f"**Your Notes:**\n___________________________________________________________________________\n___________________________________________________________________________\n___________________________________________________________________________\n\n---\n\n"
    return output
    
def prepare_ppt_text(content, topic):
    """Prepare PowerPoint export instructions and AI prompt"""
    if not content or content == "Generate & unlock..." or "LOCKED" in content:
        return "Please generate and unlock content first!", ""
    # Validate content
    if not isinstance(content, str):
        print(f" WARNING: content is not a string, it's {type(content)}")
        return "Error: Invalid content format", ""
    
    lines = content.split('\n')
    module_info = []
    
    for i, line in enumerate(lines):
        if '**Generated:**' in line or '**Audience:**' in line or '**Duration:**' in line:
            continue
        if line.startswith('# MODULE') or line.startswith('## SESSION'):
            module_info.append(line.strip())
        elif '**The ' in line and 'Framework**' in line:
            module_info.append('  ' + line.strip())
    
    ppt_prompt = f'''Create a professional presentation on: {topic}

Structure the presentation to cover these key areas:

{chr(10).join(module_info[:30])}

Please create comprehensive slides that:
- Start with a compelling title slide
- Include an overview of why this topic matters now
- Cover each module/section with clear explanations
- Use bullet points and visuals for frameworks
- Add real-world examples and case studies
- End with implementation steps and key takeaways

Make it executive-ready, visually engaging, and actionable.'''
    
    instructions = f'''# Ready to Create Your Presentation!

**Topic:** {topic}

---

## Option 1: Download Full Content

**Download the complete training content to create slides manually**

### Steps:
1. Click **"Download Content"** button below (in Content tab)
2. Copy sections you want to include in your presentation
3. Paste into PowerPoint, Google Slides, or Keynote
4. Format and design slides manually

**Best for:** Full control over design and layout

---


## Option 2: AI-Generated PPT 

**Use Gamma AI or GenSpark AI to automatically create your presentation**

### Steps:
1. **Copy the AI prompt** from the "AI Prompt for Gamma/GenSpark" box below
2. **Click** "Open Gamma AI" or "Open GenSpark AI" button
3. **Sign in** with your account credentials
4. **Paste** the prompt into the AI chat/input field
5. **Generate** - Let AI create your presentation in minutes!

**Why use AI tools?**
- Professional design automatically applied
- Visual layouts and graphics included
- Faster than manual creation
- Modern, engaging slide formats
**Choose your preferred option below**
'''
    
    return instructions, ppt_prompt


def unlock(sess):
    """Unlock full access to generated content"""
    if not sess or sess not in payment_state:
        return "Generate first", "No content", "No content", "Generate first", "Generate first", ""
    
    payment_state[sess]['paid'] = True
    save_state()

    
    ppt_inst, ppt_txt = prepare_ppt_text(
        payment_state[sess]['content'], 
        payment_state[sess]['topic']
    )
    
    return (
        payment_state[sess]['content'],
        payment_state[sess]['facil'],
        payment_state[sess]['handout'],
        "UNLOCKED!",
        ppt_inst,
        ppt_txt
    )

# Load saved state on startup
print("Loading saved state...")
load_state()
print(f"Loaded {len(payment_state)} existing sessions")
print(f"Supported domains: {', '.join(DomainDetector.get_all_domains())}")
if not DATA_DIR.exists():
    print(f" WARNING: DATA_DIR doesn't exist, creating: {DATA_DIR}")
    DATA_DIR.mkdir(exist_ok=True)

# Verify database exists
db_path = DATA_DIR / 'nexus_feedback.db'
if db_path.exists():
    print(f"✅ Database file found: {db_path}")
else:
    print(f" Database file NOT found: {db_path}")

    # NEXUS Learning Generator - Part 4 (Utility Functions)
import json
from pathlib import Path


def create_prog(topic, fmt, dur, aud_lvl, company_name, company_context, delivery_mode, sess, progress=None):
    """Main function to create training program"""
    if not topic: 
        return (
            "Enter topic", "Locked", "Locked", "Locked", "Waiting", 
            False, None, "Generate first", "",
            None, None, None, True, False
        )
    
    try:
        start = time.time()
        sid = gen_session_id()
        
        progress(0.05, desc="Detecting domain...")
        res = fetch_research(topic)
        
        # Safety check
        if res is None:
            print(" WARNING: fetch_research returned None!")
            res = {
                'sources': [],
                'has_live': False,
                'domain': 'business'
            }
        
        domain = res.get('domain', 'business')
        
        # Research company if provided
        company_research_status = ""
        if company_name and company_name.strip():
            progress(0.15, desc=f"Researching {company_name}...")
            company_research = fetch_company_research(company_name.strip())
            if company_research.get('has_data'):
                company_research_status = f"\n✅ Company researched: {company_name}"
                print(f"✅ Found data for {company_name}")
            else:
                company_research_status = f"\n Company: {company_name} (context only)"
        
        progress(0.25, desc=f"Creating {domain} instructions...")
        # NEW: Generate company-specific frameworks
        if company_research.get('has_data') and res.get('domain'):
            print(f"🎯 Generating frameworks tailored to {company_name}...")
            
            try:
                company_framework_prompt = f"""You are a {res['domain']} industry analyst specializing in {topic}.

COMPANY CONTEXT:
- Name: {company_name}
- Industry: {company_research.get('industry', 'Unknown')}
- Size: {company_research.get('size', 'Unknown')}
- Key Products: {company_research.get('products', 'Unknown')[:200]}
- Recent Challenges: {', '.join([n.get('title', '') for n in company_research.get('news', [])[:3]])}
- Competitors: {', '.join(company_research.get('competitors', [])[:5])}

YOUR TASK: Generate 3-5 frameworks/methodologies specifically relevant to {company_name}'s situation with {topic}.

These must be:
1. NAMED frameworks actually used in {res['domain']} industry
2. Directly applicable to {company_name}'s challenges/context above
3. More specific than generic business frameworks

Return ONLY valid JSON array:
[
  {{
    "name": "Framework Name",
    "source": "Creator/Source with year",
    "why_relevant_to_company": "Why this framework specifically helps {company_name} with their situation (1 sentence)",
    "description": "What it does (1 sentence)",
    "application_to_company": "How {company_name} can apply this given their {company_research.get('industry', 'industry')} context (1 sentence)",
    "addresses_challenge": "Which of {company_name}'s challenges this solves (1 sentence)"
  }}
]

Example for telecom company facing OTT competition:
{{
  "name": "Network-Based Service Platform Strategy",
  "source": "TM Forum, 2020",
  "why_relevant_to_company": "Directly addresses revenue decline from OTT services by leveraging network infrastructure assets",
  "description": "Framework for telecom operators to create platform businesses using network capabilities (APIs, data, connectivity)",
  "application_to_company": "Transform from connectivity provider to platform operator enabling IoT, enterprise solutions, and digital services",
  "addresses_challenge": "Counters revenue loss to WhatsApp/Zoom by monetizing network capabilities they can't replicate"
}}

Return ONLY valid JSON, no markdown."""

                company_frameworks_response = call_groq_with_fallback(
                    messages=[
                        {"role": "system", "content": f"You are a {res['domain']} strategy expert. Return ONLY valid JSON."},
                        {"role": "user", "content": company_framework_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1500
                )
                
                import re
                clean_json = re.sub(r'```json\s*|\s*```', '', company_frameworks_response).strip()
                company_frameworks = json.loads(clean_json)
                
                # Add company frameworks to research sources
                for fw in company_frameworks[:5]:
                    res['sources'].append({
                        'site': f"{fw['source']} (Tailored for {company_name})",
                        'title': fw['name'],
                        'snippet': f"{fw['description']} RELEVANCE TO {company_name.upper()}: {fw['why_relevant_to_company']} APPLICATION: {fw['application_to_company']}",
                        'url': f"https://www.google.com/search?q={fw['name'].replace(' ', '+')}"
                    })
                
                print(f"✅ Added {len(company_frameworks)} company-specific frameworks")
                
            except Exception as e:
                print(f"⚠️ Company framework generation failed: {e}")
                # Continue with generic frameworks
        
        syn = gen_synopsis(topic, aud_lvl, fmt, dur, res)
        # Enhance synopsis with context warnings if needed
        context_analysis = analyze_company_context_depth(company_name, company_context)
        
        if not context_analysis['has_specifics'] and (company_name or company_context):
            syn += f"\n\n---\n\n##  IMPORTANT: Enhance Your Context\n\n"
            syn += f"To get the most specific, applicable training, please provide:\n\n"
            for missing in context_analysis['missing_critical']:
                syn += f"• {missing}\n"
            syn += f"\n**Use the '✨ Enhance My Prompt' button to add this detail!**\n"
        
        progress(0.4, desc=f"Generating {fmt} for {domain}...")
        
        # Generate content based on format
        if fmt=="Training": 
            result = gen_training(topic, aud_lvl, dur, res, aud_lvl, company_name, company_context, delivery_mode)
            
            if result is None:
                print("❌ ERROR: gen_training returned None!")
                return (
                "Error: Training generation failed", "Error", "Error", "Error", "Error generating training", 
                False, sid, "Error", "",
                None, None, None, True, False
            )
            
            if isinstance(result, tuple) and len(result) >= 2:
                cont, generation_id = result[0], result[1]
            else:
                cont = str(result) if result else "Error"
                generation_id = str(uuid.uuid4())[:8]
            
            if cont is None:
                cont = "Error: Content generation returned None"
            
            gt, mod, stat = time.time(), GROQ_MODEL, "Success"
        
        elif fmt=="Workshop": 
            result = gen_workshop(topic, aud_lvl, dur, res, company_name, company_context, delivery_mode)
            
            # Safety check
            if result is None:
                print("❌ ERROR: gen_workshop returned None!")
                return (
                    "Error: Workshop generation failed", "Error", "Error", "Error", "Error generating workshop", 
                    False, sid, "Error", "",
                    None, None, None, True, False
                )
            
            cont = result[0] if isinstance(result, tuple) else result
            
            # Validate content
            if cont is None:
                print("❌ ERROR: cont is None after gen_workshop!")
                cont = "Error: Content generation returned None"
            
            generation_id = str(uuid.uuid4())[:8]
            gt, mod, stat = time.time(), GROQ_MODEL, "Success"
        
        else:  # Action Learning
            result = gen_action(topic, aud_lvl, dur, res, company_name, company_context, delivery_mode)
            
            # Safety check
            if result is None:
                print("❌ ERROR: gen_action returned None!")
                return (
                    "Error: Action Learning generation failed", "Error", "Error", "Error", "Error generating action learning", 
                    False, sid, "Error", "",
                    None, None, None, True, False
                )
            
            cont = result[0] if isinstance(result, tuple) else result
            
            # Validate content
            if cont is None:
                print("❌ ERROR: cont is None after gen_action!")
                cont = "Error: Content generation returned None"
            
            generation_id = str(uuid.uuid4())[:8]
            gt, mod, stat = time.time(), GROQ_MODEL, "Success"
        
        # One final safety check before calling gen_facil
        if cont is None or not isinstance(cont, str):
            print(f"❌ CRITICAL: cont is invalid before gen_facil! Type: {type(cont)}, Value: {cont}")
            cont = "Error: Invalid content generated"
        
        if stat=="Error": 
            return (
                syn, "Failed", "Failed", "Failed", "Error", 
                False, sid, "Error", "",
                None, None, None, True, False
            )
        
        progress(0.7, desc="Creating facilitator guide...")
        fac = gen_facil(fmt, topic, cont)
        
        progress(0.9, desc="Creating participant handout...")
        hand = gen_handout(fmt, topic, cont)
        
        tot = time.time() - start
        progress(1.0, desc="Done!")
        
        # Store generation_id in payment state
        if not generation_id:
            print(" WARNING: generation_id is None or empty!")
            generation_id = str(uuid.uuid4())[:8]
            print(f"✅ Generated fallback ID: {generation_id}")
        
        payment_state[sid] = {
            'content': cont, 
            'facil': fac, 
            'handout': hand, 
            'topic': topic,
            'format': fmt,
            'audience': aud_lvl,
            'duration': dur,
            'domain': domain,
            'paid': False,
            'generation_id': generation_id
        }
        save_state()
        
        lock = f"# LOCKED\n\nFull {fmt.lower()} after unlock.\n\nClick Unlock."
        
        # Calculate modules based on duration
        if dur == "Half Day (3-4 hours)":
            mods = 2
        elif dur == "1 Day (6-7 hours)":
            mods = 3 if fmt == "Training" else 4
        else:
            mods = 5 if fmt == "Training" else 8
        
        stat_msg = f"""✅ GENERATION COMPLETE!

Time: {tot:.1f}s
Topic: {topic}
Domain: {domain.title()}
Audience: {aud_lvl}
Format: {fmt}
Modules: {mods}"""
        
        # Add company research status
        if company_name:
            if company_research_status:
                stat_msg += company_research_status
            else:
                stat_msg += f"\nCompany: {company_name} (user context)"
        
        stat_msg += "\n\n🔓 Click 'Unlock Full Access' to view!"
        
        return (
            syn, lock, lock, lock, stat_msg, 
            True, sid, "Generate and unlock to export", "",
            generation_id, topic, company_name, 
            False, True
        )
        
    except Exception as e:
        print(f"Error in create_prog: {e}")
        import traceback
        traceback.print_exc()
        return (
            str(e), "Error", "Error", "Error", "Error", 
            False, None, "Error", "",
            None, None, None, True, False
        )

    # Load saved state on startup
print("Loading saved state...")
load_state()
print(f"Loaded {len(payment_state)} existing sessions")
print(f"Supported domains: {', '.join(DomainDetector.get_all_domains())}")

def generate_with_feedback(topic, audience, duration, aud_lvl, company_name, company_context):
    """Generate training and return content + generation ID for feedback"""
    
    # Your existing research/generation logic
    res = {"domain": "business", "has_live": False, "sources": []}  # Adjust based on your logic
    
    # Generate training
    training_content, generation_id = gen_training(
        topic, audience, duration, res, aud_lvl, company_name, company_context
    )
    
    # Extract just the content part if gen_content returns tuple
    if isinstance(training_content, tuple):
        training_content = training_content[0]
    
    # Return content and make feedback section visible
    return (
        training_content,  # Display content
        generation_id,  # Store generation ID
        True,  # Show feedback section
        topic,  # Store topic for feedback
        company_name  # Store company name for feedback
    )

    return content, generation_id  # At end of gen_training
# ========== FEEDBACK FUNCTIONS ==========
# Add these after create_prog function (around line 2750)

def submit_feedback_handler(generation_id, topic, company_name, rating, what_worked, 
                            what_needs_improvement, suggestions, would_use_again):
    """Handle feedback submission"""
    
    print(f"🐛 DEBUG: generation_id={generation_id}, topic={topic}")
    
    if not generation_id:
        return "❌ No generation ID found. Please generate training first.", get_feedback_stats_display()
    
    # Submit feedback
    thank_you_msg = feedback_system.submit_feedback(
        generation_id,
        topic or "Unknown",
        company_name or "N/A",
        int(rating),
        what_worked,
        what_needs_improvement,
        suggestions,
        would_use_again
    )
    
    # Force database commit
    feedback_system.db.commit()
    
    # Return BOTH the thank you message AND updated stats
    return thank_you_msg, get_feedback_stats_display()


def debug_check_feedback():
    """Debug function to check feedback in database"""
    try:
        cursor = feedback_system.db.execute('SELECT COUNT(*) FROM feedback')
        count = cursor.fetchone()[0]
        print(f"📊 Total feedback entries in database: {count}")
        
        if count > 0:
            cursor = feedback_system.db.execute('''
                SELECT generation_id, topic, rating, timestamp 
                FROM feedback 
                ORDER BY timestamp DESC 
                LIMIT 5
            ''')
            print("📝 Recent feedback:")
            for row in cursor.fetchall():
                print(f"  - {row[1]} (Rating: {row[2]}/5) - {row[3]}")
        
        return f"Database has {count} feedback entries"
    except Exception as e:
        return f"Error checking database: {e}"


def get_feedback_stats_display():
    """Get feedback statistics for display"""
    try:
        # Check if database is initialized
        if feedback_system.db is None:
            return """
## Database Not Initialized

The feedback database hasn't been initialized yet.

Please restart the application to initialize the database.
"""
        
        # Force a fresh query
        cursor = feedback_system.db.execute('''
            SELECT 
                COUNT(*) as total_feedback,
                AVG(rating) as avg_rating,
                SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) as positive_count,
                SUM(CASE WHEN would_use_again = 1 THEN 1 ELSE 0 END) as would_use_again_count
            FROM feedback
        ''')
        stats = cursor.fetchone()
        
        print(f"📊 Analytics query result: {stats}")
        
        if stats and stats[0] > 0:
            return f"""
## Overall Statistics

- **Total Feedback Received:** {stats[0]}
- **Average Rating:** {stats[1]:.2f}/5 ⭐
- **Positive Ratings (4-5):** {stats[2]} ({stats[2]/stats[0]*100:.1f}%)
- **Would Use Again:** {stats[3]} ({stats[3]/stats[0]*100:.1f}%)

*Keep the feedback coming! Every response makes Nexus better.*

*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        return f"""
## No Feedback Yet

Be the first to provide feedback!

1. Generate training content
2. Go to the Feedback tab
3. Fill out the form
4. Submit

*Database checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
    except Exception as e:
        return f"Error loading stats: {str(e)}\n\nDatabase path: {feedback_system.db_path}"

    # ADD THESE LINES FOR FEEDBACK SYSTEM
    generation_id_state = gr.State(None)
    topic_state = gr.State(None)
    company_state = gr.State(None)
    domain_state = gr.State(None) 
    enhanced_topic_stored = gr.State("")
    enhanced_context_stored = gr.State("")
    
    with gr.Row():
        with gr.Column(scale=2):
            topic = gr.Textbox(
                label="Purpose of Training", 
                placeholder="e.g., Strategic Planning, Ophthalmology for Residents, Car Engine Diagnostics, Python Programming, etc.",
                info="Works for ANY professional topic - business, medical, technical, or specialized fields"
            )
            
            company_name = gr.Textbox(
                label="Company Name (Optional)",
                placeholder="e.g., Tata Steel, Apollo Hospitals, Infosys",
                info="Company receiving this training - we'll research and customize content"
            )
            company_context = gr.Textbox(
    label="Company Context (CRITICAL for Quality - Be VERY Specific)",
    placeholder="""❌ BAD: "Telecom company facing competition"

✅ GOOD: "Airtel: 500M subscribers, lost 15M to Jio in 2023 due to pricing. 
CEO Gopal Vittal pushing ₹50K crore 5G investment. CFO wants 15% cost cuts. 
Network ops resists change. Comms are siloed - Finance/Marketing/Network don't talk. 
Recent fail: Launched pricing without telling customer service = 10M complaints."

INCLUDE (the more specific, the better):
📊 Numbers: Employees, revenue, market share, specific metrics
👥 Stakeholders: Who disagrees with whom? Named roles/people
💰 Constraints: Budget limits, political dynamics, what you CAN'T do
⚡ Recent events: What happened that prompted this training?
🎯 Specific problem: Not just "need better communication" but "Finance launched 
   new pricing without telling customer service, caused 10M complaints"

Without this detail, you get GENERIC training. 
With this detail, you get HYPER-SPECIFIC training worth 10x more.""",
    lines=8,
    info="⚠️ QUALITY TIP: More detail = Better training. Aim for 100+ words with numbers, names, real scenarios"
        )
            
        
            
            aud_lvl = gr.Radio(
                label="Audience Level",
                choices=["Executive/C-Suite/Senior Leadership", "Manager/Supervisor/Team Lead", "Emerging/New/First-Time Leader", "Individual Contributor/Specialist"],
                value="Executive/C-Suite/Senior Leadership"
            )
            with gr.Row():
                fmt = gr.Radio(label="Format", choices=["Training", "Workshop", "Action Learning"], value="Training")
                dur = gr.Radio(
                    label="Duration", 
                    choices=["Half Day (3-4 hours)", "1 Day (6-7 hours)", "2 Days (12-14 hours)"], 
                    value="1 Day (6-7 hours)"
                )

            with gr.Row():
                delivery_mode = gr.Dropdown(
                    label="Delivery Mode",
                    choices=["In-Person", "Virtual (Online)", "Hybrid"],
                    value="In-Person",
                    info="Adjusts exercises and activities for the delivery format"
                )
            
            # ADD ENHANCEMENT BUTTON HERE
           # Find this section in your code (around line 3000):
# This is where you have your input fields

            # ADD ENHANCEMENT BUTTON ROW
            with gr.Row():
                btn_gen = gr.Button("Generate", variant="primary", size="lg")
        
        with gr.Column(scale=1):
            status = gr.Textbox(
                label="Status", 
                lines=15, 
                interactive=False,
                value="""Ready! 

Universal Domain Support:
- Business & Leadership
- Medical & Healthcare
- Engineering & Technical
- IT & Software
- Finance & Accounting
- Legal & Compliance
- Education & Training
- Manufacturing & Operations
- Sales & Marketing
- Hospitality & Service
- Travel & Tourism
- Construction & Trades
- Any professional topic!

Formats:
- Training (3-5 modules)
- Workshop (4-8 sessions)
- Action Learning (6-12 wks)

Enter topic & Generate!"""
            )
            btn_unlock = gr.Button("Unlock Full Access", variant="secondary", size="lg", visible=False)
      

    # ===== SMART CONTEXT POPUP =====
    pending_inputs = gr.State({})
    detected_domain = gr.State("")

    with gr.Column(visible=False) as smart_context_form:
        gr.HTML("""
            <div style='background: linear-gradient(135deg, #667eea, #764ba2); 
                        padding: 20px; border-radius: 12px; color: white; margin-bottom: 15px;'>
                <h3 style='margin: 0; font-size: 1.4em;'>✨ Quick Context Check</h3>
                <p style='margin: 8px 0 0; opacity: 0.9;'>Answer 2-3 quick questions to make your training hyper-specific</p>
            </div>
        """)

        q_challenges = gr.Textbox(
            label="🎯 What specific challenges should this training address?",
            placeholder="e.g. 'Team leads don't give feedback', 'Scrap rate too high', 'Departments don't collaborate'",
            lines=2,
            info="Be specific about the ACTUAL problem, not the symptom"
        )

        with gr.Column(visible=False) as technical_section:
            gr.HTML("""
                <div style='background: #f0f4ff; padding: 12px; border-radius: 8px; 
                            border-left: 4px solid #667eea; margin: 10px 0;'>
                    <b>⚙️ Technical Training Detected</b> — Add equipment/process details for maximum relevance
                </div>
            """)
            q_tech_popup = gr.Textbox(
                label="⚙️ Equipment, Standards & Metrics",
                placeholder="""Equipment: "MTS Criterion Model 43 tensile tester"
Standards: "ASTM E8, ISO 6892-1, SOP-QC-023"
Current metrics: "15% scrap rate, Cpk = 0.98"
Targets: "Target <5% scrap, Cpk ≥ 1.33"
Common issues: "Grip slippage at >50kN" """,
                lines=4,
                info="Specific equipment models, SOP numbers, real metrics make training directly applicable"
            )

        with gr.Column(visible=False) as behavioral_section:
            gr.HTML("""
                <div style='background: #fff3f0; padding: 12px; border-radius: 8px; 
                            border-left: 4px solid #ff6b35; margin: 10px 0;'>
                    <b>🧠 Leadership/Behavioral Training Detected</b> — Add culture details for maximum relevance
                </div>
            """)
            q_behav_popup = gr.Textbox(
                label="🧠 Culture, Dynamics & Real Scenarios",
                placeholder="""Culture: "Command-and-control, heroic firefighting celebrated"
Dynamics: "CFO and CMO don't talk, decisions made in WhatsApp"
Pain points: "Managers promoted from technical roles, no people training"
Real situation: "CEO wants better comms but real problem is strategy disagreement" """,
                lines=4,
                info="Be honest about dysfunction. Real culture details = Real training relevance"
            )

        q_outcomes = gr.Textbox(
            label="🎯 What should participants DO differently after training?",
            placeholder="e.g. 'Run effective standups in <15 min', 'Reduce scrap rate to <5%', 'Make decisions without 50-person email chains'",
            lines=2,
            info="Focus on concrete actions and measurable outcomes"
        )

        with gr.Row():
            btn_skip = gr.Button("⏭️ Skip — Generate Now", size="md", variant="secondary")
            btn_submit_context = gr.Button("🚀 Generate with Context", variant="primary", size="md") 
    
    
    with gr.Tabs():
        with gr.Tab("Instructions"):
            syn_out = gr.Markdown("""# How to Use NEXUS

    
## YOUR FEEDBACK, IN THE FEEDBACK SECTION, WOULD HELP ME LEARN TO SERVE YOU BETTER
  
            
## 📋 Quick Start Guide

### Step 1: Enter Your Topic
Enter any professional topic in the "Purpose of Training" field above.

Examples:
- Strategic Planning
- Ophthalmology for Residents  
- Car Engine Diagnostics
- Python Programming
- Leadership Development
- Any professional topic!

### Step 2: Add Company Details (Optional)
- **Company Name**: Enter the company receiving this training
- **Company Context**: Add specific details about their situation

This will customize all content specifically for that company with:
- Industry-specific market trends
- Company-relevant metrics and examples
- Tailored challenges and opportunities

### Step 3: Select Settings
- **Audience Level**: Choose the leadership/skill level
- **Format**: Training (modules), Workshop (sessions), or Action Learning (weeks)
- **Duration**: 1 Day (3 modules/4 sessions) or 2 Days (5 modules/8 sessions)

### Step 4: Generate & Review
1. Click **"Generate"** button
2. Wait 30-60 seconds while NEXUS creates your content
3. Review this tab - it will update with detailed instructions
4. Click **"Unlock Full Access"** to view all materials

---

## 📦 What You'll Get

✅ Complete training content with frameworks and examples  
✅ Facilitator guide with talking points  
✅ Participant handout with note-taking space  
✅ PowerPoint export ready for AI generation  

---

**Check the "Sample" tab to see complete example output!**

**Ready? Fill in your topic above and click Generate!**
""")
        
        with gr.Tab("Content"):
            cont_out = gr.Markdown("Generate & unlock to view full content...")
        
        with gr.Tab("Facilitator"):
            fac_out = gr.Markdown("Generate & unlock to view facilitator guide...")
        
        with gr.Tab("Handout"):
            hand_out = gr.Markdown("Generate & unlock to view participant handout...")
        
        with gr.Tab("PPT Export"):
            ppt_instructions = gr.Markdown("Generate and unlock content first to export to PPT")
            ppt_text = gr.Textbox(
                label="AI Prompt for Gamma/GenSpark",
                lines=20,
                placeholder="Your AI prompt will appear here after unlocking...",
                interactive=True
            )
            with gr.Row():
                gr.HTML('<a href="https://gamma.app" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #667eea; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; margin: 5px;">Open Gamma AI</a>')
                gr.HTML('<a href="https://www.genspark.ai" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #667eea; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; margin: 5px;">Open GenSpark AI</a>')
            gr.Markdown("""
### How to Use:
1. **Copy the prompt** from the text box above
2. **Click** one of the blue buttons to open Gamma AI or GenSpark AI
3. **Paste** the prompt and generate your presentation
4. **Download** your professional PPT in minutes!
""")
        
        with gr.Tab("Sample"):
            gr.Markdown("""# Sample Output - Strategic Planning Training

## Why Strategic Planning Matters Now

**Market Context & Trends:**
* 85 Percent of organizations lack an effective strategic planning process (Source: Harvard Business Review)
* Companies with formal strategic planning are 12 Percent more profitable (Source: McKinsey & Company)
* Only 23 Percentof organizations successfully execute their strategy (Source: BCG)
* Strategic planning market growing at 11 Percent annually, reaching $8.2B by 2028 (Source: MarketsandMarkets)
* 76 Percent of executives view strategic planning as critical for competitive advantage (Source: Deloitte)

**Business Impact:**
* Organizations with effective planning see 30 Percent higher productivity (Source: Bain & Company)
* 67 Percent of high-performing companies attribute success to strategic clarity (Source: McKinsey)
* Companies with strategic alignment report 2.5x higher revenue growth (Source: MIT Sloan)
* Strategic planning reduces resource waste by 40 Percent (Source: Harvard Business Review)

**Why Now:**
* Market volatility requires adaptive strategic approaches (Source: BCG)
* Digital transformation demands integrated strategic frameworks (Source: Gartner)
* Remote work necessitates new planning methodologies (Source: McKinsey)
* Economic uncertainty creates strategic planning urgency (Source: Harvard Business Review)

---

## Context & Challenge

**Context:**
Organizations are facing unprecedented market volatility and competitive pressure requiring faster, more adaptive strategic responses.

**Challenge:**
How do you create a strategic plan that's both visionary and executable when the future seems increasingly unpredictable?

**The Landscape Has Changed:**
In the past 24 months, strategic planning cycles have shortened from annual to quarterly in 60 Percent of organizations, and agile strategy frameworks have become the new standard.

**The Cost of Standing Still:**
* Organizations without clear strategy lose 25 Percent efficiency annually
* Competitors with adaptive strategies capture market share at 3x rate
* Strategic drift costs Fortune 500 companies average $50M per year

**The Opportunity:**
When you master strategic planning, you create organizational alignment, faster decision-making, and sustainable competitive advantage.

---

## MODULE 1: Foundation of Strategic Thinking

**Duration:** 90 min

### What You Will Walk Away With

By the end of this module:

1. **Apply** the Strategic Canvas framework to map your competitive position
2. **Create** a compelling strategic vision that drives action
3. **Build** strategic priorities using the Impact-Effort matrix

NOT theory. NOT concepts. ACTIONS to take Monday morning.

---

### Patterns We See

**Common Patterns:**
1. Creating 50-page strategic plans that nobody reads or implements
2. Setting vague goals like "increase market share" without clear metrics
3. Planning in isolation without stakeholder input or buy-in

**Myths vs Reality:**
* **Myth:** Strategic planning is only for executives
*  **Reality:** The best strategies involve input from all organizational levels, as front-line employees often see market shifts first



**The Hidden Cost:**
Without effective strategic planning, organizations waste approximately 30 Percent of leadership time on misaligned initiatives, equivalent to $250K+ annually in a 50-person company.

---

### The Core Frameworks

#### Framework 1: Strategic Canvas (Blue Ocean Strategy)

**What It Is (In Plain Language):**
A visual tool that maps how your organization competes compared to others, helping you find unique positioning and avoid head-to-head competition.

**Why It Works:**
Instead of competing on the same factors as everyone else, you identify what to eliminate, reduce, raise, and create to differentiate.

**The Framework in Action:**

CRITICAL: This section shows DETAILED step-by-step implementation with multiple actions per step.

**Step 1: MAP - Identify Key Competition Factors**

You begin by listing 8-12 factors that truly define how companies compete in your industry. This isnt about what you think matters—its about what customers actually care about and what competitors emphasize. You are looking for the complete picture of the competitive landscape.

- **Action:** Survey 10-15 customers asking "What factors do you consider when choosing a provider in our industry?"
- **Action:** Visit 3-5 competitor websites and note what they emphasize in their marketing
- **Action:** List out every factor, even if it seems obvious (price, speed, expertise, relationship, results, etc.)
- **Example:** For a consulting firm, factors might include: price per hour, years of experience, industry specialization, response time, methodology/tools, relationship quality, results guarantee, geographic reach
- **Common Mistake:** Listing only factors where you are strong, rather than all factors that define the industry
- **Pro Tip:** Ask front-line sales teams what objections they hear most—those reveal the real competitive factors

**Step 2: [ACTION VERB] - [What This Accomplishes]**

[Write 2-3 sentences explaining WHY this step matters and what specifically gets done]

**What you do:**
- [Write a concrete action with specific deliverable - DO NOT copy from Step 1]
- [Write a different concrete action with specific deliverable]
- [Write a third concrete action with specific deliverable]

**How to do it:**
- [Write a specific method/approach for THIS step]
- [Write another specific method/approach for THIS step]
- [Write a third specific method/approach for THIS step]

**Example:** {example_guidance}

**Common Mistake:** [Write what people typically do wrong in THIS SPECIFIC step]

**Pro Tip:** [Write how to excel at THIS SPECIFIC step]

---

**Step 3: [ACTION VERB] - [What This Accomplishes]**

[Write 2-3 sentences explaining WHY this step matters - DIFFERENT from Steps 1 and 2]

**What you do:**
- [Write a UNIQUE concrete action for Step 3]
- [Write another UNIQUE concrete action for Step 3]
- [Write a third UNIQUE concrete action for Step 3]

**How to do it:**
- [Write a specific method for Step 3]
- [Write another specific method for Step 3]
- [Write a third specific method for Step 3]

**Example:** {example_guidance}

**Common Mistake:** [Write what people do wrong in Step 3 specifically]

**Pro Tip:** [Write how to excel at Step 3 specifically]

---

**Step 4: [ACTION VERB] - [What This Accomplishes]**

[Write 2-3 sentences explaining WHY Step 4 matters - DIFFERENT from previous steps]

**What you do:**
- [Write a UNIQUE concrete action for Step 4]
- [Write another UNIQUE concrete action for Step 4]
- [Write a third UNIQUE concrete action for Step 4]

**How to do it:**
- [Write a specific method for Step 4]
- [Write another specific method for Step 4]
- [Write a third specific method for Step 4]

**Example:** {example_guidance}

**Common Mistake:** [Write what people do wrong in Step 4]

**Pro Tip:** [Write how to excel at Step 4]

**How Long This Takes:**
2-3 facilitated sessions (3 hours each) over two weeks

**What Success Looks Like:**
You have a visual canvas showing a unique competitive position, a positioning statement that makes competitors approach seem outdated, and buy-in from leadership on which factors to eliminate/reduce/raise/create.

---

### See It in Action: Real Example

**Company:** Cirque du Soleil
**Industry:** Entertainment
**Challenge:** The circus industry was in decline with rising costs (animals, star performers, multiple venues), growing concerns about animal welfare, and intense competition from other entertainment options like movies, sports, and theme parks. Traditional circuses were stuck competing on the same factors—bigger animals, more famous performers, lower prices.

**What They Did:**

Step 1: They mapped the circus industrys competition factors: star performers, animal acts, thrill/danger, humor, multiple shows simultaneously, venue quality, ticket price, artistic music/dance, theme/story.

Step 2: They charted Ringling Bros, smaller regional circuses, and other entertainment options—all clustered around similar factors.

Step 3: Applied ERRC Grid:
- **ELIMINATED:** Animal acts (cost, ethics), star performers (egos, cost), multiple venue shows (complexity)
- **REDUCED:** Humor and slapstick, thrill/danger elements
- **RAISED:** Unique venues (custom-built theaters), artistic quality of music and dance
- **CREATED:** Theatrical themes and storylines, refined environment for adults, artistic production value

Step 4: Created "Cirque du Soleil" category—not a circus, not theater, not ballet—something entirely new.

**What Changed:**
* Created an entirely new "artistic circus" market category with no direct competition
* Achieved 22 times revenue growth in just 10 years
* Commanded premium pricing 10x higher than traditional circuses
* Attracted adult audience who would never attend a traditional circus
* Eliminated 70 Percent of traditional circus costs while raising revenues dramatically

**The Key Insight:**
Competing to be the "best circus" meant fighting over a shrinking pie in a declining industry. Creating a new category—sophisticated artistic entertainment that happens to involve circus skills—meant owning a blue ocean with no competition. They stopped fighting Ringling Bros and started attracting theater and Vegas show audiences instead.

---

### Your Turn: Practice Exercise

**What You Will Create:** Your organizations Strategic Canvas showing current position vs. 2 competitors, plus your future differentiated position

**Why This Matters:** This exercise forces you to confront whether you are truly differentiated or just "better" at the same things as competitors. Most leaders discover they are in red ocean competition and need bold repositioning.

**Instructions (35 min):**

**Individual Work (15 min):**
1. List 8-10 competition factors in your industry (what customers consider when choosing)
2. Rate yourself and 2 competitors on each factor (1-10 scale) and plot on simple graph
3. Apply ERRC Grid: What will you eliminate, reduce, raise, create? Be bold—safe answers dont differentiate

**Small Group Discussion (10 min):**
- Share your current canvas—do you cluster with competitors?
- Share your ERRC decisions—are they bold enough to create visual differentiation?
- Give feedback: "Your eliminate/create decisions need to be bolder" or "Thats differentiated but might alienate core customers"

**Refinement (10 min):**
- Revise your ERRC Grid based on feedback—push yourself to be bolder
- Draw your new strategic curve—it should look distinctly different in shape
- Write your positioning statement: "We are the only _____ that _____"

**Tools Provided:**
- Search "Strategic Canvas Template" on Google - blank graph for mapping competition factors
- Search "ERRC Grid Worksheet" on Google - four-quadrant template for eliminate/reduce/raise/create
- Search "Positioning Statement Template" on Google - fill-in format for unique positioning

**Find Templates Online:**
- Google Search: "strategic canvas template blue ocean"
- Google Search: "ERRC grid worksheet blue ocean strategy"
- Google Search: "blue ocean strategy positioning statement template"

---

### Resources to Go Deeper

**Video 1: Blue Ocean Strategy Explained with Examples** (Under 3 min)
- YouTube search: "blue ocean strategy explained 3 minutes"
- Recommended channels: Harvard Business Review, Blue Ocean Strategy Official, TED-Ed
- What you will learn: Quick overview of blue ocean vs red ocean with visual examples of companies who succeeded

**Video 2: Cirque du Soleil Blue Ocean Case Study** (Under 3 min)
- YouTube search: "cirque du soleil blue ocean strategy case study"
- Recommended channels: Case Study Channel, Business Strategy Hub, Strategy Simplified
- What you will learn: Detailed breakdown of how Cirque applied ERRC grid to transform the circus industry

**Video 3: Common Strategic Canvas Mistakes to Avoid** (Under 3 min)
- YouTube search: "strategic canvas mistakes to avoid"
- Recommended channels: Strategy experts, business school channels, consulting firms
- What you will learn: Why most strategic canvases fail to differentiate and how to create bold positioning

---

### Group Dialogue

**Opening Question (10 min):**
Think about a time when you competed head-to-head with others on the same factors. What did that competition feel like? What was the cost of competing that way?

**Closing Question (10 min):**
Looking at your Strategic Canvas, whats the ONE factor you could eliminate or create that would make your competitors approach seem outdated? Whats stopping you?

---

### One Bold Closing Thought

**Most strategies fail because they try to be "better" rather than "different." Better means endless competition. Different means you are playing a game only you can win.**

**Next Step:**
In the next 48 hours, interview 3 customers and ask: "If we eliminated [factor from your ERRC], would you still buy from us?" Their answer tells you if you are ready for blue ocean.

---

*[Modules 2-3 would follow this same comprehensive structure with elaborate frameworks, templates, and video resources]*

---

## 30-Day Implementation Plan

**Week 1: Foundation & Assessment**
- Day 1-2: Complete Strategic Canvas with leadership team
- Day 3-4: Validate ERRC decisions with customer interviews
- Day 5: Finalize positioning statement and communication

**Week 2: Vision & Priorities**
- Day 8-10: Develop strategic vision and communication cascade
- Day 11-12: Define strategic priorities using Impact-Effort matrix
- Day 14: Present to organization and gather feedback

**Week 3: Initiative Design**
- Day 15-17: Create strategic initiatives with clear owners and metrics
- Day 18-19: Develop resource allocation plan and budget
- Day 21: Conduct initiative review and alignment session

**Week 4: Launch & Execution**
- Day 22-24: Launch communication plan across organization
- Day 25-26: Begin execution of first-wave initiatives
- Day 28-30: Establish monitoring cadence and success metrics tracking

---

## Success Metrics

**90-Day Outcomes:**
* Leadership alignment score increases from baseline to 85 Percent
* 75 Percent of employees can articulate strategy in one sentence
* Strategic decision-making speed improves by 40 Percent

**6-Month Outcomes:**
* 80 Percent of strategic priorities on track or completed
* Measurable impact on revenue/profit (5-10 Percent improvement)
* Market position shift reflected in customer perception surveys
* Employee engagement with strategy at 80 Percent

---

*This is an abbreviated sample showing the complete structure you will receive. Your generated training will include ALL modules with this level of detail, including elaborate framework steps, template search prompts, and curated video resources under 3 minutes.*
""")
        
        with gr.Tab("About Creator"):
            gr.Markdown("""# About the Creator

## Your Professional Thought Partner

**Ashish Mehra** is an ICF Level 2 certified transformational coach and leadership trainer with 1,000+ hours of coaching experience, working with CEOs and senior leaders across India, Canada, Singapore, and Africa. He blends deep coaching expertise with hands-on leadership experience from global organisations to drive measurable change in mindset, performance, and business impact.

---

## Credentials & Experience

- **INSEAD Alumnus**
- **ICF Level 2 Certified Coach**
- **3 decades of experience** working in blue-chip companies:
  - Xerox
  - Airtel
  - Singtel
  - Hitachi
- **Trained by Centre for Creative Leadership**

---

## Why NEXUS?

I created NEXUS to solve a problem I faced repeatedly: **spending long hours creating and preparing bespoke training content.**

After 5 years of manually creating training programs, I realized:

- Traditional design takes 40-80 hours per program
- Research is scattered across multiple sources
- Frameworks arent adapted for different audiences
- Quality varies based on designer availability

**NEXUS combines:**

- My expertise in understanding behaviours and leadership
- Research from top institutions (HBR, McKinsey, Stanford)
- AI-powered content generation
- Proven pedagogical frameworks

---

## My Approach

My methodology blends deep inner clarity with sharp business relevance—helping leaders align who they are with how they lead. I work at the intersection of mindset, behaviour, and strategy, using powerful inquiry and real-world experiments to create shifts that are both human and measurable.

---

## Connect With Me

**Email:** ashish.mehra@interfaceinc.co.in

**LinkedIn:** [linkedin.com/in/asmehra](https://www.linkedin.com/in/asmehra)

**Website:** [interfaceinc.co.in](https://interfaceinc.co.in/)

---

*NEXUS represents the convergence of deep human insight and cutting-edge technology—transforming how we develop leaders and build high-performing organizations.*
""")
            
        # ADD THIS NEW FEEDBACK TAB
        with gr.Tab("📊 Feedback"):
            gr.Markdown("### Help Us Improve NEXUS!")
            gr.Markdown("*Your feedback makes NEXUS smarter for everyone*")
            
            with gr.Group() as feedback_form:
                feedback_notice = gr.Markdown("**Generate training first to provide feedback**", visible=True)
                
                with gr.Column(visible=False) as feedback_inputs:
                    rating_input = gr.Slider(
                        minimum=1,
                        maximum=5,
                        step=1,
                        value=3,
                        label="⭐ Overall Rating (1-5 stars)",
                        info="How useful was this training?"
                    )
                    
                    what_worked_input = gr.Textbox(
                        label="✅ What worked well?",
                        placeholder="e.g., Great examples, clear frameworks, relevant to our industry...",
                        lines=3
                    )
                    
                    what_needs_improvement_input = gr.Textbox(
                        label="🔧 What needs improvement?",
                        placeholder="e.g., Too generic, missing specific examples, frameworks not relevant...",
                        lines=3
                    )
                    
                    suggestions_input = gr.Textbox(
                        label="💡 Suggestions for next time?",
                        placeholder="e.g., Add more case studies, include templates, focus on implementation...",
                        lines=3
                    )
                    
                    would_use_again_input = gr.Checkbox(
                        label="✓ I would use this training material",
                        value=True
                    )
                    
                    submit_feedback_btn = gr.Button("Submit Feedback 🚀", variant="primary")
                
                feedback_response = gr.Markdown()
        
        with gr.Tab("📈 Analytics"):
            gr.Markdown("### Community Feedback Statistics")
            stats_display = gr.Markdown(value="Loading statistics...")
            refresh_stats_btn = gr.Button("🔄 Refresh Statistics")
            debug_btn = gr.Button("🔍 Debug: Check Database", variant="secondary")
            debug_output = gr.Markdown()
    
    # ===== SMART POPUP HANDLERS =====

def on_generate_clicked(topic_val, company_name_val, company_context_val, fmt_val, dur_val, aud_lvl_val, delivery_mode_val, sid_val):
    if not topic_val or not topic_val.strip():
        return (
            False,
            False,
            False,
            {},
            "",
            "⚠️ Please enter a topic first!"
        )

    domain, _ = DomainDetector.detect_domain(topic_val)

    technical_domains = ['engineering', 'manufacturing', 'automotive', 'construction']
    behavioral_domains = ['business', 'sales_marketing', 'education', 'legal', 'finance', 'hospitality']

    stored = {
        'topic': topic_val,
        'company_name': company_name_val,
        'company_context': company_context_val,
        'fmt': fmt_val,
        'dur': dur_val,
        'aud_lvl': aud_lvl_val,
        'delivery_mode': delivery_mode_val,
        'sid': sid_val
    }

    print(f"[UI] Domain detected: {domain}")

    return (
        True,                          # smart_context_form
        domain in technical_domains,   # technical_section
        domain in behavioral_domains,  # behavioral_section
        stored,                                           # pending_inputs
        domain,                                           # detected_domain
        f"📊 Domain: {domain.title()} — answer questions below or skip"  # status
    )

def on_submit_context(q_challenges_val, q_tech_val, q_behav_val, q_outcomes_val, pending, sid_val):
    """Step 2a: Merge popup answers as MANDATORY requirements, then generate"""
    ctx = pending.get('company_context', '') or ''
    
    # Build mandatory requirements section
    mandatory_requirements = "\n\n" + "="*70 + "\n"
    mandatory_requirements += "MANDATORY: USER-SPECIFIED REQUIREMENTS\n"
    mandatory_requirements += "="*70 + "\n\n"
    mandatory_requirements += "The user provided SPECIFIC requirements. YOU MUST address ALL of these:\n\n"

    if q_challenges_val and q_challenges_val.strip():
        mandatory_requirements += f"**CHALLENGE TO SOLVE:**\n{q_challenges_val}\n\n"
        mandatory_requirements += f"→ MODULE 1 MUST start by addressing this exact challenge\n"
        mandatory_requirements += f"→ Framework in Module 1 MUST solve this (not generic planning)\n"
        mandatory_requirements += f"→ Exercise in Module 1 MUST use this as the scenario\n\n"
    
    if q_tech_val and q_tech_val.strip():
        mandatory_requirements += f"**TECHNICAL CONTEXT (MUST USE IN EXAMPLES):**\n{q_tech_val}\n\n"
        mandatory_requirements += f"→ Reference SPECIFIC equipment models mentioned above\n"
        mandatory_requirements += f"→ Use ACTUAL SOP numbers in procedures\n"
        mandatory_requirements += f"→ Apply REAL metrics/targets in examples\n"
        mandatory_requirements += f"→ Base scenarios on ACTUAL operational issues listed\n\n"
    
    if q_behav_val and q_behav_val.strip():
        mandatory_requirements += f"**CULTURAL CONTEXT (MUST USE IN SCENARIOS):**\n{q_behav_val}\n\n"
        mandatory_requirements += f"→ Start Module 1 with the ACTUAL dysfunction described\n"
        mandatory_requirements += f"→ Role-play exercises MUST use this culture dynamic\n"
        mandatory_requirements += f"→ Examples MUST reflect this organizational reality\n"
        mandatory_requirements += f"→ Avoid generic 'build trust' - address THIS culture\n\n"
    
    if q_outcomes_val and q_outcomes_val.strip():
        mandatory_requirements += f"**SUCCESS CRITERIA (MUST BE MODULE OUTCOMES):**\n{q_outcomes_val}\n\n"
        mandatory_requirements += f"→ Each module outcome MUST connect to these results\n"
        mandatory_requirements += f"→ Exercises MUST produce deliverables that achieve these\n"
        mandatory_requirements += f"→ 30-Day Plan MUST have milestones for these outcomes\n\n"
    
    mandatory_requirements += "="*70 + "\n"
    mandatory_requirements += "VERIFICATION: If modules don't directly address the above, you FAILED.\n"
    mandatory_requirements += "="*70 + "\n\n"
    
    # Append to context
    ctx += mandatory_requirements
    pending['company_context'] = ctx.strip()
    
    return create_prog(
        pending['topic'], pending['fmt'], pending['dur'], pending['aud_lvl'],
        pending.get('company_name',''), pending['company_context'],
        pending.get('delivery_mode','In-Person'), sid_val
    )

def on_skip_context(pending, sid_val):
    """Skip context questions and generate with existing context"""
    return create_prog(
        pending['topic'], pending['fmt'], pending['dur'], pending['aud_lvl'],
        pending.get('company_name',''), pending.get('company_context',''),
        pending.get('delivery_mode','In-Person'), sid_val
    )

# Wire up button handlers
    btn_gen.click(
        fn=on_generate_clicked,
        inputs=[topic, company_name, company_context, fmt, dur, aud_lvl, delivery_mode, sid],
        outputs=[smart_context_form, technical_section, behavioral_section, pending_inputs, detected_domain, status]
    )

    btn_submit_context.click(
        fn=on_submit_context,
        inputs=[q_challenges, q_tech_popup, q_behav_popup, q_outcomes, pending_inputs, sid],
        outputs=[syn_out, cont_out, fac_out, hand_out, status, btn_unlock, sid, ppt_instructions, ppt_text,
                 generation_id_state, topic_state, company_state, feedback_notice, feedback_inputs]
    )

    btn_skip.click(
        fn=on_skip_context,
        inputs=[pending_inputs, sid],
        outputs=[syn_out, cont_out, fac_out, hand_out, status, btn_unlock, sid, ppt_instructions, ppt_text,
                 generation_id_state, topic_state, company_state, feedback_notice, feedback_inputs]
    )
    # ADD THIS - Connect unlock button
    btn_unlock.click(
        fn=unlock,
        inputs=[sid],
        outputs=[cont_out, fac_out, hand_out, status, ppt_instructions, ppt_text]
    )
    # Load stats when app starts
    demo.load(fn=get_feedback_stats_display, outputs=stats_display)

# ========== LAUNCH APPLICATION ==========

if __name__ == "__main__":
    print("=" * 60)
    print("NEXUS Learning Generator - Universal Domain Support")
    print("Starting Gradio interface...")
    print("=" * 60)
    
    try:
        demo.queue()
        demo.launch(
            server_name="0.0.0.0",
            server_port=7860,
            show_error=True,
            share=False,
            debug=True
        )
        print("✅ NEXUS is running successfully!")
    except Exception as e:
        print(f"❌ Launch error: {e}")
        import traceback
        traceback.print_exc()
        raise
