"""
🥋 AI Karate Test Generator with Claude AI
===========================================
Uses Claude API to generate intelligent Karate tests
based on your existing feature files and prompts.
"""

import streamlit as st
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
import random

# Try to import anthropic
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# Try to import requests for API calls
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class TransactionTemplate:
    id: str
    name: str
    description: str
    category: str
    card_network: str
    message_type: str
    processing_code: str
    fields: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    icon: str = "💳"
    
    def to_dict(self):
        return asdict(self)

@dataclass
class ResponseCode:
    code: str
    message: str
    category: str
    trigger_field: str = ""
    trigger_value: str = ""

@dataclass 
class SQLTable:
    name: str
    description: str
    columns: Dict[str, Dict[str, str]] = field(default_factory=dict)
    key_columns: List[str] = field(default_factory=list)

# ============================================================================
# KNOWLEDGE BASE
# ============================================================================

class KnowledgeBase:
    def __init__(self):
        self.templates: Dict[str, TransactionTemplate] = {}
        self.response_codes: Dict[str, ResponseCode] = {}
        self.sql_tables: Dict[str, SQLTable] = {}
        self.learned_features: List[Dict] = []
        self.learned_patterns: List[str] = []
        self._load_defaults()
    
    def _load_defaults(self):
        templates = [
            TransactionTemplate("visa_purchase_0100", "fwd_visasig_direct_purchase_0100", "Visa Signature Purchase", "purchase", "visa", "0100", "000000",
                {"DMTI": "0100", "DE2": "4144779500060809", "DE3": "000000", "DE4": "000000000700", "DE11": "{stan}", "DE14": "2512", "DE37": "{rrn}", "DE41": "TERMID01", "DE42": "MERCHANT01"},
                ["visa", "purchase", "signature"], "💳"),
            TransactionTemplate("mastercard_purchase_0100", "fwd_mastercard_purchase_0100", "MasterCard Purchase", "purchase", "mastercard", "0100", "000000",
                {"DMTI": "0100", "DE2": "5500000000000004", "DE3": "000000", "DE4": "000000001000", "DE11": "{stan}", "DE14": "2512", "DE37": "{rrn}", "DE41": "TERMID02"},
                ["mastercard", "purchase"], "💳"),
            TransactionTemplate("visa_atm_0100", "fwd_visa_atm_withdrawal_0100", "Visa ATM Withdrawal", "withdrawal", "visa", "0100", "010000",
                {"DMTI": "0100", "DE2": "4111111111111111", "DE3": "010000", "DE4": "000000005000", "DE11": "{stan}", "DE37": "{rrn}", "DE41": "ATM00001"},
                ["visa", "atm", "withdrawal"], "🏧"),
            TransactionTemplate("visa_refund_0100", "fwd_visa_refund_0100", "Visa Refund", "refund", "visa", "0100", "200000",
                {"DMTI": "0100", "DE2": "4144779500060809", "DE3": "200000", "DE4": "000000000500", "DE11": "{stan}", "DE37": "{rrn}", "DE41": "TERMID01"},
                ["visa", "refund"], "↩️"),
            TransactionTemplate("visa_reversal_0400", "fwd_visa_reversal_0400", "Visa Reversal", "reversal", "visa", "0400", "000000",
                {"DMTI": "0400", "DE2": "4144779500060809", "DE3": "000000", "DE4": "000000000700", "DE11": "{stan}", "DE37": "{rrn}", "DE90": "{original}"},
                ["visa", "reversal"], "🔄"),
            TransactionTemplate("visa_balance_0100", "fwd_visa_balance_inquiry_0100", "Visa Balance Inquiry", "balance", "visa", "0100", "310000",
                {"DMTI": "0100", "DE2": "4144779500060809", "DE3": "310000", "DE4": "000000000000", "DE11": "{stan}", "DE37": "{rrn}"},
                ["visa", "balance", "inquiry"], "💰"),
        ]
        for t in templates:
            self.templates[t.id] = t
        
        codes = [
            ResponseCode("00", "Approved", "approved"),
            ResponseCode("01", "Refer to Issuer", "declined"),
            ResponseCode("05", "Do Not Honor", "declined", "DE2", "4111111111111114"),
            ResponseCode("14", "Invalid Card", "declined", "DE2", "1234567890123456"),
            ResponseCode("51", "Insufficient Funds", "declined", "DE4", "999999999999"),
            ResponseCode("54", "Expired Card", "declined", "DE14", "2001"),
            ResponseCode("55", "Invalid PIN", "declined"),
            ResponseCode("61", "Exceeds Limit", "declined", "DE4", "500000000000"),
            ResponseCode("62", "Restricted Card", "declined", "DE2", "4111111111111113"),
        ]
        for rc in codes:
            self.response_codes[rc.code] = rc
        
        self.sql_tables["PPH_TRAN"] = SQLTable("PPH_TRAN", "Payment Hub Transaction",
            {"TRAN_ID": {"type": "VARCHAR2(36)", "desc": "UUID"}, "TXN_STATUS": {"type": "VARCHAR2(20)", "desc": "Status"},
             "RESP_CODE": {"type": "VARCHAR2(2)", "desc": "Response"}, "RRN": {"type": "VARCHAR2(12)", "desc": "RRN"},
             "STAN": {"type": "VARCHAR2(6)", "desc": "STAN"}, "TXN_AMT": {"type": "NUMBER", "desc": "Amount"}}, ["RRN", "STAN"])
        
        self.sql_tables["PPDSVA"] = SQLTable("PPDSVA", "Value Added Data",
            {"SVA_ID": {"type": "VARCHAR2(36)", "desc": "UUID"}, "FRAUD_CHECK": {"type": "VARCHAR2(10)", "desc": "Fraud"},
             "RISK_SCORE": {"type": "NUMBER", "desc": "Risk"}, "HOST_RESP_CODE": {"type": "VARCHAR2(4)", "desc": "Host RC"}}, ["RRN", "STAN"])
    
    def add_template(self, t): self.templates[t.id] = t
    def add_response_code(self, rc): self.response_codes[rc.code] = rc
    def add_sql_table(self, tbl): self.sql_tables[tbl.name] = tbl
    
    def add_learned_feature(self, content: str, name: str):
        self.learned_features.append({"name": name, "content": content})
        # Extract patterns
        scenarios = re.findall(r'Scenario.*?(?=Scenario|$)', content, re.DOTALL)
        for s in scenarios:
            self.learned_patterns.append(s.strip())
    
    def get_context_for_ai(self) -> str:
        """Build context string for Claude AI"""
        context = "# Available Transaction Templates:\n"
        for t in self.templates.values():
            context += f"- {t.name}: {t.description} (Category: {t.category}, Network: {t.card_network}, MTI: {t.message_type})\n"
            context += f"  Fields: {json.dumps(t.fields)}\n"
        
        context += "\n# Response Codes:\n"
        for rc in self.response_codes.values():
            context += f"- {rc.code}: {rc.message} ({rc.category})"
            if rc.trigger_field:
                context += f" - Trigger: {rc.trigger_field}={rc.trigger_value}"
            context += "\n"
        
        context += "\n# SQL Tables for Validation:\n"
        for tbl in self.sql_tables.values():
            context += f"- {tbl.name}: {tbl.description}\n"
            context += f"  Key columns: {', '.join(tbl.key_columns)}\n"
            context += f"  Columns: {', '.join(tbl.columns.keys())}\n"
        
        if self.learned_patterns:
            context += "\n# Learned Scenario Patterns (use similar structure):\n"
            for i, pattern in enumerate(self.learned_patterns[:3]):  # Limit to 3
                context += f"\n## Example {i+1}:\n```gherkin\n{pattern[:500]}...\n```\n"
        
        return context
    
    def export_json(self):
        return json.dumps({
            "templates": {k: v.to_dict() for k, v in self.templates.items()},
            "response_codes": {k: asdict(v) for k, v in self.response_codes.items()},
            "learned_features": self.learned_features
        }, indent=2)
    
    def import_json(self, data):
        d = json.loads(data)
        for k, v in d.get("templates", {}).items():
            self.templates[k] = TransactionTemplate(**v)
        for k, v in d.get("response_codes", {}).items():
            self.response_codes[k] = ResponseCode(**v)

# ============================================================================
# CLAUDE AI GENERATOR
# ============================================================================

class ClaudeGenerator:
    """Uses Claude API to generate Karate tests"""
    
    def __init__(self, api_key: str, kb: KnowledgeBase):
        self.api_key = api_key
        self.kb = kb
        self.model = "claude-sonnet-4-20250514"
    
    def generate(self, prompt: str, options: Dict = None) -> str:
        """Generate Karate test using Claude API"""
        options = options or {}
        
        system_prompt = self._build_system_prompt(options)
        user_prompt = self._build_user_prompt(prompt, options)
        
        if HAS_ANTHROPIC and self.api_key:
            return self._call_anthropic_sdk(system_prompt, user_prompt)
        elif HAS_REQUESTS and self.api_key:
            return self._call_anthropic_api(system_prompt, user_prompt)
        else:
            return self._fallback_generate(prompt, options)
    
    def _build_system_prompt(self, options: Dict) -> str:
        return f"""You are an expert Karate test framework developer specializing in ISO8583 payment transaction testing.

Your task is to generate high-quality Karate feature files based on user prompts.

{self.kb.get_context_for_ai()}

# Guidelines:
1. Always use proper Karate syntax with Background and Scenario sections
2. Include appropriate tags (@smoke, @regression, @e2e, @negative, @positive, @sql)
3. Generate dynamic STAN and RRN values using JavaScript functions
4. Use the exact template names and field mappings provided
5. {"Include SQL validation for PPH_TRAN and PPDSVA tables" if options.get("sql", True) else "Do not include SQL validation"}
6. {"Use common_scenarios.feature for reusable calls" if options.get("common", True) else "Write inline API calls"}
7. Add appropriate assertions using 'match' keyword
8. Include comments explaining each section
9. Follow the patterns from learned examples if available

# Output Format:
Return ONLY the Karate feature file content, starting with tags and Feature keyword.
Do not include any explanations or markdown code blocks.
"""

    def _build_user_prompt(self, prompt: str, options: Dict) -> str:
        return f"""Generate a Karate feature file for the following requirement:

{prompt}

Options:
- Include SQL validation: {options.get("sql", True)}
- Use common scenarios: {options.get("common", True)}
- Include documentation comments: {options.get("docs", True)}
"""

    def _call_anthropic_sdk(self, system: str, user: str) -> str:
        """Call Claude using official SDK"""
        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            
            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": user}]
            )
            
            return response.content[0].text
        except Exception as e:
            return f"# Error calling Claude API: {str(e)}\n\n{self._fallback_generate(user, {})}"
    
    def _call_anthropic_api(self, system: str, user: str) -> str:
        """Call Claude using REST API"""
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "system": system,
                    "messages": [{"role": "user", "content": user}]
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["content"][0]["text"]
            else:
                return f"# API Error {response.status_code}: {response.text}\n\n{self._fallback_generate(user, {})}"
        except Exception as e:
            return f"# Error: {str(e)}\n\n{self._fallback_generate(user, {})}"
    
    def _fallback_generate(self, prompt: str, options: Dict) -> str:
        """Fallback generator when API is not available"""
        # Simple rule-based generation
        p = prompt.lower()
        
        # Determine test type
        is_negative = any(w in p for w in ["decline", "negative", "fail", "reject", "insufficient", "expired", "invalid"])
        is_e2e = "e2e" in p or "end-to-end" in p
        
        # Determine transaction type
        txn_type = "purchase"
        if "withdraw" in p or "atm" in p: txn_type = "withdrawal"
        elif "refund" in p: txn_type = "refund"
        elif "reversal" in p: txn_type = "reversal"
        elif "balance" in p: txn_type = "balance"
        
        # Determine network
        network = "visa"
        if "mastercard" in p or "mc " in p: network = "mastercard"
        
        # Find template
        template = None
        for t in self.kb.templates.values():
            if t.category == txn_type and t.card_network == network:
                template = t
                break
        if not template:
            template = list(self.kb.templates.values())[0]
        
        # Determine response code
        exp_rc = "00"
        exp_status = "COMPLETED"
        overrides = {}
        
        if is_negative:
            if "insufficient" in p:
                exp_rc, exp_status = "51", "DECLINED"
                overrides = {"DE4": "999999999999"}
            elif "expired" in p:
                exp_rc, exp_status = "54", "DECLINED"
                overrides = {"DE14": "2001"}
            elif "invalid" in p:
                exp_rc, exp_status = "14", "DECLINED"
                overrides = {"DE2": "1234567890123456"}
            else:
                exp_rc, exp_status = "05", "DECLINED"
        
        # Build feature
        tags = ["@" + ("e2e" if is_e2e else "smoke")]
        tags.append("@" + txn_type)
        tags.append("@" + network)
        tags.append("@negative" if is_negative else "@positive")
        if options.get("sql", True):
            tags.append("@sql")
        
        feature = f"""{' '.join(tags)}
Feature: {network.title()} {txn_type.title()} - {'Declined' if is_negative else 'Approved'}

  # Generated by AI Karate Generator (Fallback Mode)
  # Template: {template.name}
  # Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

  Background:
    * url cosmosUrl
    * def templateName = '{template.name}'
    * def generateSTAN = function(){{ return Math.floor(Math.random() * 999999).toString().padStart(6, '0') }}
    * def generateRRN = function(){{ return Math.floor(Math.random() * 999999999999).toString().padStart(12, '0') }}
"""
        
        if options.get("sql", True):
            feature += """
    # SQL Query helpers
    * def queryPPHTRAN = function(rrn, stan){ return DbUtils.query("SELECT * FROM PPH_TRAN WHERE RRN='" + rrn + "' AND STAN='" + stan + "'") }
    * def queryPPDSVA = function(rrn, stan){ return DbUtils.query("SELECT * FROM PPDSVA WHERE RRN='" + rrn + "' AND STAN='" + stan + "'") }
"""
        
        feature += """
    * configure headers = { 'Content-Type': 'application/json' }

"""
        
        # Scenario
        scenario_name = f"{txn_type.title()} - {'Declined' if is_negative else 'Approved'}"
        ovr_parts = ["DE11: '#(stan)'", "DE37: '#(rrn)'"] + [f"{k}: '{v}'" for k, v in overrides.items()]
        
        feature += f"""  @{'negative' if is_negative else 'positive'}
  Scenario: {scenario_name}
    # Generate unique identifiers
    * def stan = generateSTAN()
    * def rrn = generateRRN()
    * def overrides = {{ {', '.join(ovr_parts)} }}

"""
        
        if options.get("common", True):
            feature += """    # Send transaction using common scenario
    * def result = call read('common_scenarios.feature@common_send_0100') { templateName: '#(templateName)', overrides: '#(overrides)' }
    * def response = result.cosmosResponse
"""
        else:
            feature += """    # Send ISO8583 request
    Given path '/template'
    And param id = templateName
    And param type = 'MessageTemplate'
    And request { templateId: '#(templateName)', overrides: '#(overrides)' }
    When method post
    Then status 200
    * def response = response
"""
        
        feature += f"""
    # Validate COSMOS response
    * match response.DE39 == '{exp_rc}'
"""
        if exp_rc == "00":
            feature += "    * match response.DE38 == '#notnull'\n"
        
        if options.get("sql", True):
            feature += f"""
    # Validate PPH_TRAN
    * def pphRecord = queryPPHTRAN(rrn, stan)
    * match pphRecord != null
    * match pphRecord.TXN_STATUS == '{exp_status}'
    * match pphRecord.RESP_CODE == '{exp_rc}'

    # Validate PPDSVA
    * def ppdsvaRecord = queryPPDSVA(rrn, stan)
    * match ppdsvaRecord != null
    * match ppdsvaRecord.FRAUD_CHECK == 'PASS'
"""
        
        return feature

# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(page_title="AI Karate Generator", page_icon="🥋", layout="wide", initial_sidebar_state="collapsed")

# Beautiful CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --primary: #7C3AED;
    --primary-light: #A78BFA;
    --primary-dark: #5B21B6;
    --secondary: #06B6D4;
    --success: #10B981;
    --warning: #F59E0B;
    --danger: #EF4444;
    --bg: #F8FAFC;
    --card: #FFFFFF;
    --text: #1E293B;
    --text-light: #64748B;
    --border: #E2E8F0;
}

* { font-family: 'Plus Jakarta Sans', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #F0F4FF 0%, #FAFBFF 50%, #F5F0FF 100%);
}

#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

.main-header {
    background: linear-gradient(135deg, var(--primary) 0%, #9333EA 50%, var(--secondary) 100%);
    border-radius: 24px;
    padding: 2.5rem;
    margin: -1rem -1rem 2rem -1rem;
    text-align: center;
    position: relative;
    overflow: hidden;
    box-shadow: 0 20px 40px -12px rgba(124, 58, 237, 0.35);
}

.main-header::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -20%;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%);
    border-radius: 50%;
}

.main-header h1 {
    font-size: 2.5rem;
    font-weight: 800;
    color: white;
    margin: 0;
    position: relative;
    z-index: 1;
}

.main-header p {
    color: rgba(255,255,255,0.9);
    font-size: 1.1rem;
    margin-top: 0.5rem;
    position: relative;
    z-index: 1;
}

.api-status {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: rgba(255,255,255,0.2);
    padding: 0.5rem 1rem;
    border-radius: 100px;
    margin-top: 1rem;
    font-size: 0.85rem;
    color: white;
}

.api-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.api-dot.connected { background: #10B981; box-shadow: 0 0 10px #10B981; }
.api-dot.disconnected { background: #EF4444; }

.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin: 1.5rem 0;
}

.stat-card {
    background: white;
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    border: 1px solid var(--border);
    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
}

.stat-value {
    font-size: 2.25rem;
    font-weight: 800;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1;
}

.stat-label {
    font-size: 0.75rem;
    color: var(--text-light);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.5rem;
    font-weight: 600;
}

.section-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text);
    margin: 1.5rem 0 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.card {
    background: white;
    border-radius: 16px;
    padding: 1.5rem;
    border: 1px solid var(--border);
    margin: 1rem 0;
}

.example-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
    margin: 1rem 0;
}

.example-btn {
    background: white;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.875rem 1rem;
    font-size: 0.85rem;
    color: var(--text);
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: left;
}

.example-btn:hover {
    border-color: var(--primary);
    background: rgba(124, 58, 237, 0.05);
    transform: translateY(-2px);
}

.code-output {
    background: #1E1E2E;
    border-radius: 16px;
    overflow: hidden;
    margin: 1rem 0;
}

.code-header {
    background: #2D2D3F;
    padding: 0.75rem 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.code-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
}

.code-dot.red { background: #FF5F57; }
.code-dot.yellow { background: #FEBC2E; }
.code-dot.green { background: #28C840; }

.code-title {
    color: rgba(255,255,255,0.6);
    font-size: 0.8rem;
    margin-left: 0.5rem;
    font-family: 'JetBrains Mono', monospace;
}

.powered-by {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: var(--text-light);
    margin: 0.5rem 0;
}

.claude-badge {
    background: linear-gradient(135deg, #D97706, #F59E0B);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 100px;
    font-size: 0.75rem;
    font-weight: 600;
}

/* Streamlit overrides */
.stTabs [data-baseweb="tab-list"] {
    background: white;
    border-radius: 14px;
    padding: 4px;
    gap: 4px;
    border: 1px solid var(--border);
}

.stTabs [data-baseweb="tab"] {
    font-weight: 600;
    font-size: 0.875rem;
    color: var(--text-light);
    border-radius: 10px;
    padding: 0.625rem 1.25rem;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, var(--primary), var(--primary-dark)) !important;
    color: white !important;
}

.stButton > button {
    font-weight: 700;
    background: linear-gradient(135deg, var(--primary), var(--primary-dark));
    color: white;
    border: none;
    border-radius: 12px;
    padding: 0.75rem 1.5rem;
    font-size: 0.95rem;
    box-shadow: 0 8px 16px -4px rgba(124, 58, 237, 0.35);
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 24px -4px rgba(124, 58, 237, 0.45);
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    border: 2px solid var(--border) !important;
    border-radius: 12px !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.1) !important;
}

.stDownloadButton > button {
    background: linear-gradient(135deg, var(--success), #059669) !important;
    box-shadow: 0 8px 16px -4px rgba(16, 185, 129, 0.35) !important;
}

.template-card {
    background: white;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem;
    margin: 0.5rem 0;
    transition: all 0.2s;
}

.template-card:hover {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.1);
}
</style>
""", unsafe_allow_html=True)


def main():
    # Session State
    if 'kb' not in st.session_state:
        st.session_state.kb = KnowledgeBase()
    if 'api_key' not in st.session_state:
        st.session_state.api_key = ""
    if 'selected_prompt' not in st.session_state:
        st.session_state.selected_prompt = ""
    
    kb = st.session_state.kb
    
    # Check API status
    api_connected = bool(st.session_state.api_key)
    
    # Header
    st.markdown(f'''
    <div class="main-header">
        <h1>🥋 AI Karate Generator</h1>
        <p>Powered by Claude AI • Train on your tests • Generate with natural language</p>
        <div class="api-status">
            <span class="api-dot {"connected" if api_connected else "disconnected"}"></span>
            {"Claude API Connected" if api_connected else "API Key Required"}
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Stats
    st.markdown(f'''
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value">{len(kb.templates)}</div>
            <div class="stat-label">Templates</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(kb.response_codes)}</div>
            <div class="stat-label">Response Codes</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(kb.sql_tables)}</div>
            <div class="stat-label">SQL Tables</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(kb.learned_features)}</div>
            <div class="stat-label">Files Learned</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["✨ Generate", "🔑 API Key", "📚 Train", "➕ Add", "📋 View"])
    
    # ==================== TAB 1: GENERATE ====================
    with tab1:
        st.markdown('<div class="section-title">✨ Generate Karate Tests with AI</div>', unsafe_allow_html=True)
        
        if not api_connected:
            st.warning("⚠️ Add your Claude API key in the 'API Key' tab for AI-powered generation. Fallback mode will be used otherwise.")
        
        st.markdown('<div class="powered-by">Powered by <span class="claude-badge">Claude AI</span></div>', unsafe_allow_html=True)
        
        # Examples
        st.markdown("**Quick Examples** (click to use)")
        examples = [
            ("🎯", "E2E approved Visa purchase with SQL validation for PPH_TRAN and PPDSVA"),
            ("❌", "Negative test for declined transaction due to insufficient funds"),
            ("🏧", "ATM withdrawal test for $500 with balance check"),
            ("↩️", "Visa refund transaction with reversal validation"),
            ("📊", "Data-driven regression tests for multiple amounts"),
            ("💳", "MasterCard e-commerce purchase with 3DS validation"),
        ]
        
        cols = st.columns(3)
        for i, (icon, text) in enumerate(examples):
            with cols[i % 3]:
                if st.button(f"{icon} {text[:35]}...", key=f"ex_{i}", use_container_width=True):
                    st.session_state.selected_prompt = text
        
        st.markdown("---")
        
        # Prompt
        prompt = st.text_area(
            "Describe the test you want to generate",
            value=st.session_state.selected_prompt,
            height=120,
            placeholder="Example: Write an E2E test for declined Visa purchase due to expired card with full SQL validation including PPH_TRAN status check and PPDSVA fraud validation"
        )
        
        # Options
        col1, col2, col3 = st.columns(3)
        with col1:
            include_sql = st.checkbox("🗄️ Include SQL Validation", value=True)
        with col2:
            use_common = st.checkbox("🔗 Use Common Scenarios", value=True)
        with col3:
            include_docs = st.checkbox("📝 Add Documentation", value=True)
        
        st.markdown("")
        
        if st.button("🚀 Generate with Claude AI", type="primary", use_container_width=True):
            if prompt.strip():
                generator = ClaudeGenerator(st.session_state.api_key, kb)
                
                with st.spinner("🤖 Claude is generating your test..."):
                    feature = generator.generate(prompt, {
                        "sql": include_sql,
                        "common": use_common,
                        "docs": include_docs
                    })
                
                st.success("✅ Test generated successfully!")
                
                st.markdown('''
                <div class="code-output">
                    <div class="code-header">
                        <span class="code-dot red"></span>
                        <span class="code-dot yellow"></span>
                        <span class="code-dot green"></span>
                        <span class="code-title">generated_test.feature</span>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
                
                st.code(feature, language="gherkin")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button("📥 Download .feature", feature, "generated_test.feature", use_container_width=True)
                with col2:
                    st.button("📋 Copy Code", use_container_width=True)
            else:
                st.warning("Please enter a prompt")
    
    # ==================== TAB 2: API KEY ====================
    with tab2:
        st.markdown('<div class="section-title">🔑 Claude API Configuration</div>', unsafe_allow_html=True)
        
        st.markdown('''
        <div class="card">
            <h4>Connect to Claude AI</h4>
            <p style="color: #64748B; font-size: 0.9rem;">
                Enter your Anthropic API key to enable AI-powered test generation.
                Get your API key from <a href="https://console.anthropic.com/" target="_blank">console.anthropic.com</a>
            </p>
        </div>
        ''', unsafe_allow_html=True)
        
        api_key = st.text_input(
            "Anthropic API Key",
            value=st.session_state.api_key,
            type="password",
            placeholder="sk-ant-api03-..."
        )
        
        if st.button("💾 Save API Key", use_container_width=True):
            st.session_state.api_key = api_key
            if api_key:
                st.success("✅ API Key saved! Claude AI is now connected.")
            else:
                st.warning("API Key cleared. Using fallback generator.")
        
        st.markdown("---")
        
        st.markdown("**API Status**")
        if st.session_state.api_key:
            st.success(f"🟢 Connected - Using model: claude-sonnet-4-20250514")
            st.info(f"SDK Available: {'✅ Yes' if HAS_ANTHROPIC else '❌ No (using REST API)'}")
        else:
            st.warning("🔴 Not connected - Using fallback rule-based generator")
        
        st.markdown("---")
        
        st.markdown("**What Claude AI Enables:**")
        st.markdown("""
        - 🧠 **Intelligent Understanding** - Understands complex test requirements
        - 📝 **Context-Aware** - Uses your templates, codes, and learned patterns
        - 🎯 **Accurate Generation** - Produces production-ready Karate tests
        - 🔄 **Pattern Learning** - Adapts to your testing style
        """)
    
    # ==================== TAB 3: TRAIN ====================
    with tab3:
        st.markdown('<div class="section-title">📚 Train on Your Feature Files</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 📁 Upload Files")
            uploaded = st.file_uploader("Upload .feature files", type=["feature", "txt"], accept_multiple_files=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 📝 Or Paste Content")
            pasted = st.text_area("Paste Karate feature", height=200)
            st.markdown('</div>', unsafe_allow_html=True)
            
            if st.button("🧠 Train AI on These Files", type="primary", use_container_width=True):
                count = 0
                if uploaded:
                    for f in uploaded:
                        content = f.read().decode('utf-8')
                        kb.add_learned_feature(content, f.name)
                        count += 1
                if pasted.strip():
                    kb.add_learned_feature(pasted, "pasted_content")
                    count += 1
                
                if count > 0:
                    st.success(f"✅ Learned from {count} file(s)! Claude will use these patterns.")
                    st.balloons()
        
        with col2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 📊 Learned Content")
            
            if kb.learned_features:
                for f in kb.learned_features:
                    st.markdown(f"✅ **{f['name']}**")
                
                st.markdown("---")
                st.markdown(f"**{len(kb.learned_patterns)} scenario patterns learned**")
                
                if kb.learned_patterns:
                    with st.expander("View Patterns"):
                        for i, p in enumerate(kb.learned_patterns[:3]):
                            st.code(p[:300] + "...", language="gherkin")
            else:
                st.info("Upload feature files to teach the AI your patterns")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # ==================== TAB 4: ADD ====================
    with tab4:
        st.markdown('<div class="section-title">➕ Add Custom Templates & Codes</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 💳 Add Transaction Template")
            
            with st.form("add_template"):
                t_id = st.text_input("Template ID", placeholder="visa_ecom_0100")
                t_name = st.text_input("Name", placeholder="fwd_visa_ecom_0100")
                t_desc = st.text_input("Description", placeholder="Visa E-Commerce")
                
                c1, c2 = st.columns(2)
                with c1:
                    t_cat = st.selectbox("Category", ["purchase", "withdrawal", "refund", "reversal", "balance"])
                    t_mti = st.selectbox("MTI", ["0100", "0200", "0400"])
                with c2:
                    t_net = st.selectbox("Network", ["visa", "mastercard", "amex"])
                    t_proc = st.text_input("Proc Code", "000000")
                
                t_fields = st.text_area("Fields JSON", '{"DMTI": "0100", "DE2": "4111111111111111"}')
                
                if st.form_submit_button("➕ Add Template", use_container_width=True):
                    if t_id and t_name:
                        try:
                            kb.add_template(TransactionTemplate(
                                t_id, t_name, t_desc, t_cat, t_net, t_mti, t_proc,
                                json.loads(t_fields), [t_cat, t_net]
                            ))
                            st.success(f"✅ Added: {t_name}")
                        except:
                            st.error("Invalid JSON")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 🔢 Add Response Code")
            
            with st.form("add_rc"):
                rc_code = st.text_input("Code", placeholder="55")
                rc_msg = st.text_input("Message", placeholder="Invalid PIN")
                rc_cat = st.selectbox("Category", ["approved", "declined", "error"])
                rc_field = st.text_input("Trigger Field", placeholder="DE52")
                rc_val = st.text_input("Trigger Value")
                
                if st.form_submit_button("➕ Add Code", use_container_width=True):
                    if rc_code and rc_msg:
                        kb.add_response_code(ResponseCode(rc_code, rc_msg, rc_cat, rc_field, rc_val))
                        st.success(f"✅ Added: {rc_code}")
            st.markdown('</div>', unsafe_allow_html=True)
    
    # ==================== TAB 5: VIEW ====================
    with tab5:
        st.markdown('<div class="section-title">📋 Knowledge Base</div>', unsafe_allow_html=True)
        
        st.markdown("#### Templates")
        cols = st.columns(3)
        for i, t in enumerate(kb.templates.values()):
            with cols[i % 3]:
                st.markdown(f'''
                <div class="template-card">
                    <div style="font-size: 1.5rem;">{t.icon}</div>
                    <div style="font-weight: 600;">{t.description}</div>
                    <div style="font-size: 0.8rem; color: #64748B;">{t.name}</div>
                    <div style="font-size: 0.75rem; color: #A78BFA; margin-top: 0.5rem;">{t.category} • {t.card_network}</div>
                </div>
                ''', unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("#### Response Codes")
        
        for rc in kb.response_codes.values():
            icon = "🟢" if rc.category == "approved" else "🔴" if rc.category == "declined" else "🟡"
            st.markdown(f"{icon} **{rc.code}** - {rc.message}")
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 Export Knowledge Base", use_container_width=True):
                st.download_button("⬇️ Download", kb.export_json(), "knowledge_base.json")
        with col2:
            uploaded_kb = st.file_uploader("📥 Import", type=["json"], key="import_kb")
            if uploaded_kb and st.button("Import", use_container_width=True):
                kb.import_json(uploaded_kb.read().decode('utf-8'))
                st.success("✅ Imported!")
                st.rerun()


if __name__ == "__main__":
    main()
