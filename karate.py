"""
🥋 AI Karate Test Generator Pro
================================
- Train on your existing Karate feature files
- Add custom templates and transaction types
- Generate tests from natural language prompts
- Learn from your repository structure
"""

import streamlit as st
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
import random
import string

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class TransactionTemplate:
    """Custom transaction template"""
    id: str
    name: str
    description: str
    category: str  # purchase, withdrawal, refund, reversal, balance, etc.
    card_network: str  # visa, mastercard, amex, discover, etc.
    message_type: str  # 0100, 0200, 0400, etc.
    processing_code: str
    fields: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)

@dataclass
class ResponseCode:
    """Response code definition"""
    code: str
    message: str
    category: str  # approved, declined, error
    trigger_field: str = ""  # which field triggers this
    trigger_value: str = ""  # value that triggers this

@dataclass
class FieldDefinition:
    """ISO8583 field definition"""
    id: str
    name: str
    description: str
    data_type: str  # numeric, alphanumeric, binary
    length: int
    format: str = ""  # YYMM, HHMMSS, etc.
    example: str = ""

@dataclass 
class SQLTable:
    """SQL table definition for validation"""
    name: str
    description: str
    columns: Dict[str, Dict[str, str]] = field(default_factory=dict)
    key_columns: List[str] = field(default_factory=list)

# ============================================================================
# KNOWLEDGE BASE - Expandable
# ============================================================================

class KnowledgeBase:
    """Centralized knowledge base that can be extended"""
    
    def __init__(self):
        self.templates: Dict[str, TransactionTemplate] = {}
        self.response_codes: Dict[str, ResponseCode] = {}
        self.field_definitions: Dict[str, FieldDefinition] = {}
        self.sql_tables: Dict[str, SQLTable] = {}
        self.learned_patterns: Dict[str, Any] = {}
        self.custom_scenarios: List[Dict] = []
        
        # Load defaults
        self._load_default_templates()
        self._load_default_response_codes()
        self._load_default_fields()
        self._load_default_sql_tables()
    
    def _load_default_templates(self):
        """Load default transaction templates"""
        defaults = [
            TransactionTemplate(
                id="visa_purchase_0100",
                name="fwd_visasig_direct_purchase_0100",
                description="Visa Signature Direct Purchase",
                category="purchase",
                card_network="visa",
                message_type="0100",
                processing_code="000000",
                fields={
                    "DMTI": "0100", "DE2": "4144779500060809", "DE3": "000000",
                    "DE4": "000000000700", "DE11": "{stan}", "DE14": "2512",
                    "DE18": "3535", "DE22": "900", "DE32": "59000000754",
                    "DE35": "4144779500060809D251210112345129",
                    "DE37": "{rrn}", "DE41": "TERMID01", "DE42": "MERCHANT01",
                    "DE43": "Test Merchant Location"
                },
                tags=["visa", "purchase", "signature", "pos"]
            ),
            TransactionTemplate(
                id="mastercard_purchase_0100",
                name="fwd_mastercard_purchase_0100",
                description="MasterCard Purchase Authorization",
                category="purchase",
                card_network="mastercard",
                message_type="0100",
                processing_code="000000",
                fields={
                    "DMTI": "0100", "DE2": "5500000000000004", "DE3": "000000",
                    "DE4": "000000001000", "DE11": "{stan}", "DE14": "2512",
                    "DE18": "5411", "DE22": "051", "DE37": "{rrn}",
                    "DE41": "TERMID02", "DE42": "MC_MERCHANT"
                },
                tags=["mastercard", "purchase", "pos"]
            ),
            TransactionTemplate(
                id="visa_atm_withdrawal_0100",
                name="fwd_visa_atm_withdrawal_0100",
                description="Visa ATM Cash Withdrawal",
                category="withdrawal",
                card_network="visa",
                message_type="0100",
                processing_code="010000",
                fields={
                    "DMTI": "0100", "DE2": "4111111111111111", "DE3": "010000",
                    "DE4": "000000005000", "DE11": "{stan}", "DE14": "2512",
                    "DE18": "6011", "DE22": "051", "DE37": "{rrn}",
                    "DE41": "ATM00001", "DE42": "BANK_ATM_01"
                },
                tags=["visa", "atm", "withdrawal", "cash"]
            ),
            TransactionTemplate(
                id="visa_refund_0100",
                name="fwd_visa_refund_0100",
                description="Visa Refund/Credit",
                category="refund",
                card_network="visa",
                message_type="0100",
                processing_code="200000",
                fields={
                    "DMTI": "0100", "DE2": "4144779500060809", "DE3": "200000",
                    "DE4": "000000000500", "DE11": "{stan}", "DE14": "2512",
                    "DE37": "{rrn}", "DE41": "TERMID01", "DE42": "MERCHANT01"
                },
                tags=["visa", "refund", "credit"]
            ),
            TransactionTemplate(
                id="visa_reversal_0400",
                name="fwd_visa_reversal_0400",
                description="Visa Reversal",
                category="reversal",
                card_network="visa",
                message_type="0400",
                processing_code="000000",
                fields={
                    "DMTI": "0400", "DE2": "4144779500060809", "DE3": "000000",
                    "DE4": "000000000700", "DE11": "{stan}", "DE14": "2512",
                    "DE37": "{rrn}", "DE41": "TERMID01", "DE90": "{original_data}"
                },
                tags=["visa", "reversal", "void"]
            ),
            TransactionTemplate(
                id="visa_balance_inquiry_0100",
                name="fwd_visa_balance_inquiry_0100",
                description="Visa Balance Inquiry",
                category="balance",
                card_network="visa",
                message_type="0100",
                processing_code="310000",
                fields={
                    "DMTI": "0100", "DE2": "4144779500060809", "DE3": "310000",
                    "DE4": "000000000000", "DE11": "{stan}", "DE14": "2512",
                    "DE37": "{rrn}", "DE41": "ATM00001"
                },
                tags=["visa", "balance", "inquiry", "atm"]
            ),
            TransactionTemplate(
                id="mastercard_cashback_0100",
                name="fwd_mastercard_cashback_0100",
                description="MasterCard Purchase with Cashback",
                category="cashback",
                card_network="mastercard",
                message_type="0100",
                processing_code="090000",
                fields={
                    "DMTI": "0100", "DE2": "5500000000000004", "DE3": "090000",
                    "DE4": "000000015000", "DE11": "{stan}", "DE14": "2512",
                    "DE18": "5411", "DE37": "{rrn}", "DE41": "TERMID02",
                    "DE54": "000000005000"  # Cashback amount
                },
                tags=["mastercard", "cashback", "purchase"]
            ),
        ]
        
        for template in defaults:
            self.templates[template.id] = template
    
    def _load_default_response_codes(self):
        """Load default response codes"""
        defaults = [
            ResponseCode("00", "Approved", "approved"),
            ResponseCode("01", "Refer to Issuer", "declined"),
            ResponseCode("05", "Do Not Honor", "declined", "DE2", "4111111111111114"),
            ResponseCode("14", "Invalid Card Number", "declined", "DE2", "1234567890123456"),
            ResponseCode("51", "Insufficient Funds", "declined", "DE4", "999999999999"),
            ResponseCode("54", "Expired Card", "declined", "DE14", "2001"),
            ResponseCode("55", "Invalid PIN", "declined", "DE52", ""),
            ResponseCode("61", "Exceeds Withdrawal Limit", "declined", "DE4", "500000000000"),
            ResponseCode("62", "Restricted Card", "declined", "DE2", "4111111111111113"),
            ResponseCode("65", "Activity Limit Exceeded", "declined"),
            ResponseCode("75", "PIN Tries Exceeded", "declined"),
            ResponseCode("91", "Issuer Unavailable", "error"),
            ResponseCode("96", "System Malfunction", "error"),
        ]
        
        for rc in defaults:
            self.response_codes[rc.code] = rc
    
    def _load_default_fields(self):
        """Load default field definitions"""
        defaults = [
            FieldDefinition("DMTI", "Message Type Indicator", "Message type", "numeric", 4, "", "0100"),
            FieldDefinition("DE2", "Primary Account Number", "Card number", "numeric", 19, "", "4144779500060809"),
            FieldDefinition("DE3", "Processing Code", "Transaction type code", "numeric", 6, "TTAABB", "000000"),
            FieldDefinition("DE4", "Transaction Amount", "Amount in cents", "numeric", 12, "", "000000000700"),
            FieldDefinition("DE7", "Transmission Date/Time", "Date and time", "numeric", 10, "MMDDhhmmss", ""),
            FieldDefinition("DE11", "System Trace Audit Number", "Unique trace number", "numeric", 6, "", "001234"),
            FieldDefinition("DE12", "Local Transaction Time", "Time of transaction", "numeric", 6, "hhmmss", ""),
            FieldDefinition("DE13", "Local Transaction Date", "Date of transaction", "numeric", 4, "MMDD", ""),
            FieldDefinition("DE14", "Expiration Date", "Card expiry", "numeric", 4, "YYMM", "2512"),
            FieldDefinition("DE18", "Merchant Category Code", "MCC", "numeric", 4, "", "5411"),
            FieldDefinition("DE22", "Point of Service Entry Mode", "How card was read", "numeric", 3, "", "051"),
            FieldDefinition("DE32", "Acquiring Institution ID", "Acquirer ID", "numeric", 11, "", ""),
            FieldDefinition("DE35", "Track 2 Data", "Magnetic stripe data", "alphanumeric", 37, "", ""),
            FieldDefinition("DE37", "Retrieval Reference Number", "RRN", "alphanumeric", 12, "", "024405001234"),
            FieldDefinition("DE38", "Authorization ID", "Approval code", "alphanumeric", 6, "", "ABC123"),
            FieldDefinition("DE39", "Response Code", "Transaction result", "numeric", 2, "", "00"),
            FieldDefinition("DE41", "Terminal ID", "Card acceptor terminal", "alphanumeric", 8, "", "TERMID01"),
            FieldDefinition("DE42", "Merchant ID", "Card acceptor ID", "alphanumeric", 15, "", "MERCHANT01"),
            FieldDefinition("DE43", "Merchant Name/Location", "Merchant details", "alphanumeric", 40, "", ""),
            FieldDefinition("DE49", "Currency Code", "Transaction currency", "numeric", 3, "", "840"),
            FieldDefinition("DE52", "PIN Data", "Encrypted PIN", "binary", 8, "", ""),
            FieldDefinition("DE54", "Additional Amounts", "Cashback, etc.", "alphanumeric", 120, "", ""),
            FieldDefinition("DE55", "ICC Data", "EMV chip data", "binary", 999, "", ""),
        ]
        
        for field_def in defaults:
            self.field_definitions[field_def.id] = field_def
    
    def _load_default_sql_tables(self):
        """Load default SQL table definitions"""
        self.sql_tables["PPH_TRAN"] = SQLTable(
            name="PPH_TRAN",
            description="Primary Payment Hub Transaction Table",
            columns={
                "TRAN_ID": {"type": "VARCHAR2(36)", "desc": "Transaction UUID"},
                "MSG_TYPE": {"type": "VARCHAR2(4)", "desc": "Message Type"},
                "PAN": {"type": "VARCHAR2(19)", "desc": "Masked PAN"},
                "PROC_CODE": {"type": "VARCHAR2(6)", "desc": "Processing Code"},
                "TXN_AMT": {"type": "NUMBER(15,2)", "desc": "Amount"},
                "STAN": {"type": "VARCHAR2(6)", "desc": "STAN"},
                "RRN": {"type": "VARCHAR2(12)", "desc": "RRN"},
                "AUTH_CODE": {"type": "VARCHAR2(6)", "desc": "Auth Code"},
                "RESP_CODE": {"type": "VARCHAR2(2)", "desc": "Response Code"},
                "TERM_ID": {"type": "VARCHAR2(8)", "desc": "Terminal ID"},
                "MERCHANT_ID": {"type": "VARCHAR2(15)", "desc": "Merchant ID"},
                "TXN_STATUS": {"type": "VARCHAR2(20)", "desc": "Status"},
                "CREATED_DT": {"type": "TIMESTAMP", "desc": "Created Date"},
            },
            key_columns=["RRN", "STAN"]
        )
        
        self.sql_tables["PPDSVA"] = SQLTable(
            name="PPDSVA",
            description="Payment Processing Data Store - Value Added",
            columns={
                "SVA_ID": {"type": "VARCHAR2(36)", "desc": "SVA Record ID"},
                "TRAN_ID": {"type": "VARCHAR2(36)", "desc": "Transaction ID"},
                "RRN": {"type": "VARCHAR2(12)", "desc": "RRN"},
                "STAN": {"type": "VARCHAR2(6)", "desc": "STAN"},
                "NETWORK_ID": {"type": "VARCHAR2(10)", "desc": "Network"},
                "RISK_SCORE": {"type": "NUMBER(5,2)", "desc": "Risk Score"},
                "FRAUD_CHECK": {"type": "VARCHAR2(10)", "desc": "Fraud Result"},
                "HOST_RESP_CODE": {"type": "VARCHAR2(4)", "desc": "Host Response"},
                "PROCESS_TIME_MS": {"type": "NUMBER(10)", "desc": "Process Time"},
            },
            key_columns=["RRN", "STAN"]
        )
    
    # ========== ADD METHODS ==========
    
    def add_template(self, template: TransactionTemplate):
        """Add a new transaction template"""
        self.templates[template.id] = template
    
    def add_response_code(self, rc: ResponseCode):
        """Add a new response code"""
        self.response_codes[rc.code] = rc
    
    def add_field_definition(self, field_def: FieldDefinition):
        """Add a new field definition"""
        self.field_definitions[field_def.id] = field_def
    
    def add_sql_table(self, table: SQLTable):
        """Add a new SQL table definition"""
        self.sql_tables[table.name] = table
    
    def add_custom_scenario(self, scenario: Dict):
        """Add a custom scenario pattern"""
        self.custom_scenarios.append(scenario)
    
    # ========== EXPORT/IMPORT ==========
    
    def export_to_json(self) -> str:
        """Export knowledge base to JSON"""
        data = {
            "templates": {k: v.to_dict() for k, v in self.templates.items()},
            "response_codes": {k: asdict(v) for k, v in self.response_codes.items()},
            "custom_scenarios": self.custom_scenarios,
            "learned_patterns": self.learned_patterns
        }
        return json.dumps(data, indent=2)
    
    def import_from_json(self, json_str: str):
        """Import knowledge base from JSON"""
        data = json.loads(json_str)
        
        if "templates" in data:
            for k, v in data["templates"].items():
                self.templates[k] = TransactionTemplate(**v)
        
        if "response_codes" in data:
            for k, v in data["response_codes"].items():
                self.response_codes[k] = ResponseCode(**v)
        
        if "custom_scenarios" in data:
            self.custom_scenarios.extend(data["custom_scenarios"])

# ============================================================================
# FEATURE ANALYZER
# ============================================================================

class FeatureAnalyzer:
    """Analyzes Karate feature files to learn patterns"""
    
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
        self.analyzed_files: List[Dict] = []
        self.step_patterns: Dict[str, int] = {}
        self.scenario_patterns: List[Dict] = []
    
    def analyze(self, content: str, filename: str = "unknown") -> Dict:
        """Analyze a feature file and learn patterns"""
        analysis = {
            "filename": filename,
            "feature_name": "",
            "tags": [],
            "backgrounds": [],
            "scenarios": [],
            "steps": [],
            "variables": [],
            "sql_queries": [],
            "calls": [],
            "templates_used": [],
            "response_codes_used": []
        }
        
        lines = content.split('\n')
        current_section = None
        current_content = []
        current_tags = []
        
        for line in lines:
            stripped = line.strip()
            
            # Feature name
            if stripped.startswith('Feature:'):
                analysis["feature_name"] = stripped.replace('Feature:', '').strip()
            
            # Tags
            if stripped.startswith('@'):
                tags = re.findall(r'@(\w+[-\w]*)', stripped)
                current_tags = tags
                analysis["tags"].extend(tags)
            
            # Sections
            if stripped.startswith('Background:'):
                current_section = 'background'
                current_content = []
                continue
            
            if stripped.startswith('Scenario:') or stripped.startswith('Scenario Outline:'):
                if current_section == 'background' and current_content:
                    analysis["backgrounds"].append('\n'.join(current_content))
                
                current_section = 'scenario'
                scenario_name = re.sub(r'^Scenario( Outline)?:', '', stripped).strip()
                current_content = [(stripped, current_tags)]
                current_tags = []
                continue
            
            if current_section:
                current_content.append(stripped) if current_section == 'background' else None
                
                # Learn step patterns
                if re.match(r'^\* |^Given |^When |^Then |^And |^But ', stripped):
                    analysis["steps"].append(stripped)
                    self._learn_step(stripped)
                
                # Variables
                var_match = re.search(r'\* def (\w+)', stripped)
                if var_match:
                    analysis["variables"].append(var_match.group(1))
                
                # SQL
                if 'SELECT' in stripped.upper() or 'query' in stripped.lower():
                    analysis["sql_queries"].append(stripped)
                
                # Calls
                if 'call read' in stripped:
                    analysis["calls"].append(stripped)
                
                # Templates used
                template_match = re.search(r"templateName\s*=\s*['\"]([^'\"]+)['\"]", stripped)
                if template_match:
                    analysis["templates_used"].append(template_match.group(1))
                
                # Response codes
                rc_match = re.search(r"DE39['\"]?\s*==\s*['\"]?(\d{2})['\"]?", stripped)
                if rc_match:
                    analysis["response_codes_used"].append(rc_match.group(1))
        
        # Store last scenario
        if current_section == 'scenario' and current_content:
            analysis["scenarios"].append({
                "content": current_content,
                "tags": current_tags
            })
        
        self.analyzed_files.append(analysis)
        self._update_knowledge_base(analysis)
        
        return analysis
    
    def _learn_step(self, step: str):
        """Learn from a step pattern"""
        # Normalize
        normalized = re.sub(r'[\'"][^"\']+[\'"]', '"{value}"', step)
        normalized = re.sub(r'\d{4,}', '{number}', normalized)
        
        self.step_patterns[normalized] = self.step_patterns.get(normalized, 0) + 1
    
    def _update_knowledge_base(self, analysis: Dict):
        """Update knowledge base with learned patterns"""
        # Add to learned patterns
        self.kb.learned_patterns.setdefault("steps", {}).update(self.step_patterns)
        self.kb.learned_patterns.setdefault("templates_used", []).extend(analysis["templates_used"])
        self.kb.learned_patterns.setdefault("response_codes_used", []).extend(analysis["response_codes_used"])

# ============================================================================
# TEST GENERATOR
# ============================================================================

class TestGenerator:
    """Generates Karate tests from prompts using knowledge base"""
    
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
    
    def generate(self, prompt: str, options: Dict = None) -> str:
        """Generate Karate test from prompt"""
        options = options or {}
        
        # Parse intent
        intent = self._parse_prompt(prompt)
        
        # Apply options
        intent["include_sql"] = options.get("include_sql", True)
        intent["use_common_calls"] = options.get("use_common_calls", True)
        intent["include_docs"] = options.get("include_docs", True)
        
        # Find best matching template
        template = self._find_template(intent)
        
        # Generate feature
        return self._generate_feature(intent, template)
    
    def _parse_prompt(self, prompt: str) -> Dict:
        """Parse prompt to understand intent"""
        prompt_lower = prompt.lower()
        
        intent = {
            "test_type": "positive",
            "transaction_type": "purchase",
            "card_network": "visa",
            "expected_result": "approved",
            "decline_reason": None,
            "amount": None,
            "custom_fields": {},
            "tags": [],
            "scenario_count": 1
        }
        
        # Test type
        if any(w in prompt_lower for w in ["negative", "decline", "reject", "fail"]):
            intent["test_type"] = "negative"
            intent["expected_result"] = "declined"
        
        if "e2e" in prompt_lower or "end-to-end" in prompt_lower:
            intent["test_type"] = "e2e"
            intent["tags"].append("e2e")
        
        if "regression" in prompt_lower:
            intent["test_type"] = "regression"
            intent["tags"].append("regression")
        
        if "smoke" in prompt_lower:
            intent["tags"].append("smoke")
        
        # Transaction type
        transaction_keywords = {
            "withdrawal": ["withdraw", "atm", "cash out"],
            "refund": ["refund", "credit", "return"],
            "reversal": ["reversal", "void", "cancel"],
            "balance": ["balance", "inquiry"],
            "cashback": ["cashback", "cash back"],
            "purchase": ["purchase", "buy", "payment", "sale"]
        }
        
        for txn_type, keywords in transaction_keywords.items():
            if any(kw in prompt_lower for kw in keywords):
                intent["transaction_type"] = txn_type
                break
        
        # Card network
        network_keywords = {
            "mastercard": ["mastercard", "mc", "master card"],
            "amex": ["amex", "american express"],
            "discover": ["discover"],
            "visa": ["visa"]
        }
        
        for network, keywords in network_keywords.items():
            if any(kw in prompt_lower for kw in keywords):
                intent["card_network"] = network
                break
        
        # Decline reason
        for code, rc in self.kb.response_codes.items():
            if rc.message.lower() in prompt_lower or any(w in prompt_lower for w in rc.message.lower().split()):
                if rc.category == "declined":
                    intent["decline_reason"] = rc
                    intent["expected_result"] = "declined"
                    break
        
        # Amount
        amount_match = re.search(r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', prompt)
        if amount_match:
            amount = float(amount_match.group(1).replace(',', ''))
            intent["amount"] = str(int(amount * 100)).zfill(12)
        
        # Multiple scenarios
        if any(w in prompt_lower for w in ["multiple", "several", "batch", "data-driven"]):
            intent["scenario_count"] = 3
        
        return intent
    
    def _find_template(self, intent: Dict) -> TransactionTemplate:
        """Find best matching template"""
        scores = {}
        
        for tid, template in self.kb.templates.items():
            score = 0
            
            # Match category
            if template.category == intent["transaction_type"]:
                score += 10
            
            # Match network
            if template.card_network == intent["card_network"]:
                score += 5
            
            # Match tags
            for tag in intent["tags"]:
                if tag in template.tags:
                    score += 2
            
            scores[tid] = score
        
        if scores:
            best_id = max(scores, key=scores.get)
            return self.kb.templates[best_id]
        
        # Default
        return list(self.kb.templates.values())[0]
    
    def _generate_feature(self, intent: Dict, template: TransactionTemplate) -> str:
        """Generate complete feature file"""
        lines = []
        
        # Tags
        tags = self._build_tags(intent, template)
        lines.append(tags)
        
        # Feature
        feature_name = self._build_feature_name(intent, template)
        lines.append(f"Feature: {feature_name}")
        lines.append("")
        
        if intent.get("include_docs"):
            lines.append(f"  # Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"  # Template: {template.name}")
            lines.append(f"  # Category: {template.category}")
            lines.append(f"  # Network: {template.card_network}")
            lines.append("")
        
        # Background
        lines.append(self._generate_background(intent, template))
        
        # Scenarios
        if intent["scenario_count"] > 1:
            lines.append(self._generate_data_driven_scenario(intent, template))
        else:
            lines.append(self._generate_scenario(intent, template))
        
        return '\n'.join(lines)
    
    def _build_tags(self, intent: Dict, template: TransactionTemplate) -> str:
        """Build tags line"""
        tags = set(intent["tags"])
        tags.add(template.card_network)
        tags.add(template.category)
        
        if intent["expected_result"] == "approved":
            tags.add("positive")
        else:
            tags.add("negative")
        
        if intent.get("include_sql"):
            tags.add("sql")
        
        return "@" + " @".join(sorted(tags))
    
    def _build_feature_name(self, intent: Dict, template: TransactionTemplate) -> str:
        """Build feature name"""
        parts = [template.card_network.title(), template.category.title()]
        
        if intent["expected_result"] == "declined" and intent["decline_reason"]:
            parts.append(f"- {intent['decline_reason'].message}")
        elif intent["expected_result"] == "approved":
            parts.append("- Approved")
        
        if intent.get("include_sql"):
            parts.append("with SQL Validation")
        
        return " ".join(parts)
    
    def _generate_background(self, intent: Dict, template: TransactionTemplate) -> str:
        """Generate Background section"""
        lines = ["  Background:"]
        lines.append("    * url cosmosUrl")
        lines.append(f"    * def templateName = '{template.name}'")
        lines.append("")
        lines.append("    # Dynamic generators")
        lines.append("    * def generateSTAN = function(){ return Math.floor(Math.random() * 999999).toString().padStart(6, '0') }")
        lines.append("    * def generateRRN = function(){ return Math.floor(Math.random() * 999999999999).toString().padStart(12, '0') }")
        lines.append("")
        
        if intent.get("include_sql"):
            for table_name, table in self.kb.sql_tables.items():
                key_cols = " AND ".join([f"{c}='\" + {c.lower()} + \"'" for c in table.key_columns])
                lines.append(f"    # Query {table_name}")
                lines.append(f"    * def query{table_name.replace('_', '')} = ")
                lines.append("    \"\"\"")
                lines.append(f"    function({', '.join([c.lower() for c in table.key_columns])}) {{")
                lines.append(f"      var DbUtils = Java.type('com.intuit.karate.demo.util.DbUtils');")
                lines.append(f"      return DbUtils.query(\"SELECT * FROM {table_name} WHERE {key_cols}\");")
                lines.append("    }")
                lines.append("    \"\"\"")
                lines.append("")
        
        lines.append("    * configure headers = { 'Content-Type': 'application/json' }")
        lines.append("")
        
        return '\n'.join(lines)
    
    def _generate_scenario(self, intent: Dict, template: TransactionTemplate) -> str:
        """Generate single scenario"""
        lines = []
        
        # Determine expected values
        if intent["expected_result"] == "approved":
            exp_rc = "00"
            exp_status = "COMPLETED"
            overrides = {}
        else:
            rc = intent["decline_reason"]
            exp_rc = rc.code if rc else "05"
            exp_status = "DECLINED"
            overrides = {}
            if rc and rc.trigger_field and rc.trigger_value:
                overrides[rc.trigger_field] = rc.trigger_value
        
        if intent.get("amount"):
            overrides["DE4"] = intent["amount"]
        
        # Scenario tags
        scenario_tags = ["@" + intent["test_type"]]
        if intent.get("include_sql"):
            scenario_tags.append("@sql")
        
        lines.append("  " + " ".join(scenario_tags))
        
        # Scenario name
        if exp_rc == "00":
            name = f"{template.category.title()} - Approved"
        else:
            reason = intent["decline_reason"].message if intent["decline_reason"] else "Declined"
            name = f"{template.category.title()} - {reason}"
        
        lines.append(f"  Scenario: {name}")
        lines.append("")
        
        # Generate values
        lines.append("    # Generate unique identifiers")
        lines.append("    * def stan = generateSTAN()")
        lines.append("    * def rrn = generateRRN()")
        lines.append("")
        
        # Overrides
        override_parts = ["DE11: '#(stan)'", "DE37: '#(rrn)'"]
        for field, value in overrides.items():
            override_parts.append(f"{field}: '{value}'")
        
        lines.append(f"    * def overrides = {{ {', '.join(override_parts)} }}")
        lines.append("")
        
        # Send request
        if intent.get("use_common_calls"):
            lines.append("    # Send using common scenario")
            lines.append(f"    * def result = call read('common_scenarios.feature@common_send_0100') {{ templateName: '#(templateName)', overrides: '#(overrides)' }}")
            lines.append("    * def response = result.cosmosResponse")
        else:
            lines.append("    # Send request")
            lines.append("    Given path '/template'")
            lines.append("    And param id = templateName")
            lines.append("    And param type = 'MessageTemplate'")
            lines.append("    And request { templateId: '#(templateName)', overrides: '#(overrides)' }")
            lines.append("    When method post")
            lines.append("    Then status 200")
            lines.append("    * def response = response")
        
        lines.append("")
        
        # Validate response
        lines.append("    # Validate COSMOS response")
        lines.append(f"    * match response.DE39 == '{exp_rc}'")
        if exp_rc == "00":
            lines.append("    * match response.DE38 == '#notnull'")
        lines.append("")
        
        # SQL validation
        if intent.get("include_sql"):
            for table_name, table in self.kb.sql_tables.items():
                func_name = f"query{table_name.replace('_', '')}"
                lines.append(f"    # Validate {table_name}")
                lines.append(f"    * def {table_name.lower()} = {func_name}(rrn, stan)")
                lines.append(f"    * match {table_name.lower()} != null")
                
                if table_name == "PPH_TRAN":
                    lines.append(f"    * match {table_name.lower()}.TXN_STATUS == '{exp_status}'")
                    lines.append(f"    * match {table_name.lower()}.RESP_CODE == '{exp_rc}'")
                elif table_name == "PPDSVA":
                    lines.append(f"    * match {table_name.lower()}.HOST_RESP_CODE == '{exp_rc}'")
                    lines.append(f"    * match {table_name.lower()}.FRAUD_CHECK == 'PASS'")
                
                lines.append("")
        
        return '\n'.join(lines)
    
    def _generate_data_driven_scenario(self, intent: Dict, template: TransactionTemplate) -> str:
        """Generate data-driven scenario outline"""
        lines = []
        
        lines.append("  @regression @data-driven")
        lines.append(f"  Scenario Outline: {template.category.title()} - <description>")
        lines.append("")
        lines.append("    * def stan = generateSTAN()")
        lines.append("    * def rrn = generateRRN()")
        lines.append("    * def overrides = { DE11: '#(stan)', DE37: '#(rrn)', DE2: '<pan>', DE4: '<amount>' }")
        lines.append("")
        lines.append("    Given path '/template'")
        lines.append("    And param id = templateName")
        lines.append("    And request { templateId: '#(templateName)', overrides: '#(overrides)' }")
        lines.append("    When method post")
        lines.append("    Then status 200")
        lines.append("    And match response.DE39 == '<expectedRC>'")
        lines.append("")
        
        if intent.get("include_sql"):
            lines.append("    * def pph = queryPPHTRAN(rrn, stan)")
            lines.append("    * match pph.TXN_STATUS == '<expectedStatus>'")
            lines.append("")
        
        lines.append("    Examples:")
        lines.append("      | description         | pan                | amount       | expectedRC | expectedStatus |")
        lines.append("      | Approved Low        | 4144779500060809   | 000000000100 | 00         | COMPLETED      |")
        lines.append("      | Approved Medium     | 4144779500060809   | 000000010000 | 00         | COMPLETED      |")
        lines.append("      | Insufficient Funds  | 4111111111111112   | 999999999999 | 51         | DECLINED       |")
        lines.append("      | Expired Card        | 4144779500060809   | 000000000100 | 54         | DECLINED       |")
        lines.append("")
        
        return '\n'.join(lines)

# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(page_title="AI Karate Generator Pro", page_icon="🥋", layout="wide")

# CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono&display=swap');

.stApp { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); }

.header-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px;
    padding: 2rem;
    margin-bottom: 2rem;
    color: white;
    text-align: center;
}

.header-card h1 { font-size: 2.5rem; font-weight: 700; margin: 0; }
.header-card p { opacity: 0.9; margin-top: 0.5rem; }

.section-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1rem 0;
}

.stat-pill {
    display: inline-block;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    padding: 0.4rem 1rem;
    border-radius: 20px;
    font-size: 0.85rem;
    margin: 0.25rem;
}

.template-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    padding: 1rem;
    margin: 0.5rem 0;
}

.template-card:hover {
    border-color: #667eea;
    background: rgba(102, 126, 234, 0.1);
}

.code-output {
    background: #1e1e1e;
    border-radius: 10px;
    padding: 1rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
}
</style>
""", unsafe_allow_html=True)

def main():
    # Session state
    if 'kb' not in st.session_state:
        st.session_state.kb = KnowledgeBase()
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = FeatureAnalyzer(st.session_state.kb)
    if 'generator' not in st.session_state:
        st.session_state.generator = TestGenerator(st.session_state.kb)
    
    kb = st.session_state.kb
    analyzer = st.session_state.analyzer
    generator = st.session_state.generator
    
    # Header
    st.markdown('''
    <div class="header-card">
        <h1>🥋 AI Karate Test Generator Pro</h1>
        <p>Train • Add Templates • Generate Tests from Natural Language</p>
    </div>
    ''', unsafe_allow_html=True)
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "✨ Generate",
        "📚 Train",
        "➕ Add Templates",
        "📋 Knowledge Base",
        "⬇️ Export/Import"
    ])
    
    # ========== TAB 1: GENERATE ==========
    with tab1:
        st.markdown("### Generate Tests from Natural Language")
        
        # Quick examples
        st.markdown("**Quick Examples** (click to use)")
        examples = [
            "Write E2E test for approved Visa purchase with SQL validation",
            "Generate negative test for insufficient funds decline",
            "Create ATM withdrawal test for $500",
            "Write MasterCard refund test",
            "Generate data-driven regression tests for various amounts"
        ]
        
        col1, col2 = st.columns(2)
        selected = ""
        for i, ex in enumerate(examples):
            with col1 if i % 2 == 0 else col2:
                if st.button(f"📝 {ex[:45]}...", key=f"ex{i}", use_container_width=True):
                    selected = ex
        
        # Prompt input
        prompt = st.text_area(
            "Describe the test you want",
            value=selected,
            height=100,
            placeholder="Example: Write an E2E test for declined Visa purchase due to expired card with SQL validation for PPH_TRAN and PPDSVA"
        )
        
        # Options
        col1, col2, col3 = st.columns(3)
        with col1:
            include_sql = st.checkbox("Include SQL Validation", value=True)
        with col2:
            use_common = st.checkbox("Use Common Scenarios", value=True)
        with col3:
            include_docs = st.checkbox("Include Documentation", value=True)
        
        if st.button("🚀 Generate Test", type="primary", use_container_width=True):
            if prompt:
                with st.spinner("Generating..."):
                    feature = generator.generate(prompt, {
                        "include_sql": include_sql,
                        "use_common_calls": use_common,
                        "include_docs": include_docs
                    })
                
                st.success("✅ Generated!")
                st.code(feature, language="gherkin")
                
                st.download_button(
                    "📥 Download .feature",
                    feature,
                    "generated_test.feature",
                    use_container_width=True
                )
            else:
                st.warning("Please enter a prompt")
    
    # ========== TAB 2: TRAIN ==========
    with tab2:
        st.markdown("### Train on Your Feature Files")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            uploaded = st.file_uploader("Upload .feature files", type=["feature", "txt"], accept_multiple_files=True)
            
            pasted = st.text_area("Or paste feature content", height=250, placeholder="Paste your Karate feature file here...")
            
            if st.button("🧠 Train", use_container_width=True):
                count = 0
                if uploaded:
                    for f in uploaded:
                        content = f.read().decode('utf-8')
                        analyzer.analyze(content, f.name)
                        count += 1
                
                if pasted.strip():
                    analyzer.analyze(pasted, "pasted_content")
                    count += 1
                
                if count > 0:
                    st.success(f"✅ Trained on {count} file(s)!")
                else:
                    st.warning("Please upload or paste content")
        
        with col2:
            st.markdown("### Learned Patterns")
            
            if analyzer.analyzed_files:
                st.markdown(f'''
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                    <span class="stat-pill">📄 {len(analyzer.analyzed_files)} Files</span>
                    <span class="stat-pill">📝 {len(analyzer.step_patterns)} Steps</span>
                </div>
                ''', unsafe_allow_html=True)
                
                with st.expander("Step Patterns"):
                    for step, count in sorted(analyzer.step_patterns.items(), key=lambda x: -x[1])[:10]:
                        st.code(f"({count}x) {step}")
                
                with st.expander("Analyzed Files"):
                    for f in analyzer.analyzed_files:
                        st.write(f"**{f['filename']}**: {len(f['scenarios'])} scenarios")
            else:
                st.info("Upload feature files to start learning")
    
    # ========== TAB 3: ADD TEMPLATES ==========
    with tab3:
        st.markdown("### Add Custom Templates")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("#### New Transaction Template")
            
            with st.form("add_template"):
                t_id = st.text_input("Template ID*", placeholder="visa_purchase_ecom_0100")
                t_name = st.text_input("Template Name*", placeholder="fwd_visa_purchase_ecom_0100")
                t_desc = st.text_input("Description*", placeholder="Visa E-Commerce Purchase")
                t_category = st.selectbox("Category", ["purchase", "withdrawal", "refund", "reversal", "balance", "cashback", "other"])
                t_network = st.selectbox("Card Network", ["visa", "mastercard", "amex", "discover", "other"])
                t_mti = st.selectbox("Message Type", ["0100", "0110", "0200", "0210", "0400", "0410", "0420"])
                t_proc = st.text_input("Processing Code", "000000")
                t_tags = st.text_input("Tags (comma separated)", "visa, purchase, ecom")
                
                st.markdown("**Default Fields** (JSON)")
                t_fields = st.text_area("Fields", value='{\n  "DMTI": "0100",\n  "DE2": "4144779500060809",\n  "DE3": "000000",\n  "DE4": "000000000100"\n}', height=150)
                
                if st.form_submit_button("➕ Add Template", use_container_width=True):
                    if t_id and t_name and t_desc:
                        try:
                            fields = json.loads(t_fields) if t_fields else {}
                            tags = [t.strip() for t in t_tags.split(",") if t.strip()]
                            
                            template = TransactionTemplate(
                                id=t_id,
                                name=t_name,
                                description=t_desc,
                                category=t_category,
                                card_network=t_network,
                                message_type=t_mti,
                                processing_code=t_proc,
                                fields=fields,
                                tags=tags
                            )
                            kb.add_template(template)
                            st.success(f"✅ Added template: {t_name}")
                        except json.JSONDecodeError:
                            st.error("Invalid JSON in fields")
                    else:
                        st.warning("Please fill required fields")
        
        with col2:
            st.markdown("#### Add Response Code")
            
            with st.form("add_rc"):
                rc_code = st.text_input("Response Code*", placeholder="55")
                rc_msg = st.text_input("Message*", placeholder="Invalid PIN")
                rc_cat = st.selectbox("Category", ["approved", "declined", "error"])
                rc_field = st.text_input("Trigger Field", placeholder="DE52")
                rc_value = st.text_input("Trigger Value", placeholder="")
                
                if st.form_submit_button("➕ Add Response Code", use_container_width=True):
                    if rc_code and rc_msg:
                        rc = ResponseCode(rc_code, rc_msg, rc_cat, rc_field, rc_value)
                        kb.add_response_code(rc)
                        st.success(f"✅ Added RC: {rc_code} - {rc_msg}")
            
            st.markdown("---")
            st.markdown("#### Add SQL Table")
            
            with st.form("add_table"):
                tbl_name = st.text_input("Table Name*", placeholder="CUSTOM_TABLE")
                tbl_desc = st.text_input("Description*", placeholder="Custom validation table")
                tbl_keys = st.text_input("Key Columns (comma separated)", "RRN, STAN")
                tbl_cols = st.text_area("Columns (JSON)", '{\n  "COL1": {"type": "VARCHAR2(50)", "desc": "Column 1"}\n}')
                
                if st.form_submit_button("➕ Add Table", use_container_width=True):
                    if tbl_name and tbl_desc:
                        try:
                            cols = json.loads(tbl_cols) if tbl_cols else {}
                            keys = [k.strip() for k in tbl_keys.split(",") if k.strip()]
                            
                            table = SQLTable(tbl_name, tbl_desc, cols, keys)
                            kb.add_sql_table(table)
                            st.success(f"✅ Added table: {tbl_name}")
                        except json.JSONDecodeError:
                            st.error("Invalid JSON")
    
    # ========== TAB 4: KNOWLEDGE BASE ==========
    with tab4:
        st.markdown("### Knowledge Base")
        
        st.markdown(f'''
        <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem;">
            <span class="stat-pill">📄 {len(kb.templates)} Templates</span>
            <span class="stat-pill">🔢 {len(kb.response_codes)} Response Codes</span>
            <span class="stat-pill">🗄️ {len(kb.sql_tables)} SQL Tables</span>
            <span class="stat-pill">📝 {len(kb.field_definitions)} Fields</span>
        </div>
        ''', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Transaction Templates")
            for tid, t in kb.templates.items():
                with st.expander(f"{t.card_network.upper()} - {t.description}"):
                    st.write(f"**ID:** {t.id}")
                    st.write(f"**Name:** {t.name}")
                    st.write(f"**Category:** {t.category}")
                    st.write(f"**MTI:** {t.message_type}")
                    st.write(f"**Tags:** {', '.join(t.tags)}")
                    st.json(t.fields)
        
        with col2:
            st.markdown("#### Response Codes")
            for code, rc in kb.response_codes.items():
                color = "🟢" if rc.category == "approved" else ("🔴" if rc.category == "declined" else "🟡")
                st.write(f"{color} **{code}** - {rc.message}")
            
            st.markdown("#### SQL Tables")
            for name, tbl in kb.sql_tables.items():
                with st.expander(name):
                    st.write(f"**Description:** {tbl.description}")
                    st.write(f"**Keys:** {', '.join(tbl.key_columns)}")
                    for col, info in tbl.columns.items():
                        st.write(f"- {col}: {info['type']}")
    
    # ========== TAB 5: EXPORT/IMPORT ==========
    with tab5:
        st.markdown("### Export / Import Knowledge Base")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Export")
            if st.button("📤 Export to JSON", use_container_width=True):
                json_data = kb.export_to_json()
                st.download_button(
                    "⬇️ Download JSON",
                    json_data,
                    "karate_knowledge_base.json",
                    mime="application/json",
                    use_container_width=True
                )
                st.code(json_data[:500] + "...", language="json")
        
        with col2:
            st.markdown("#### Import")
            uploaded_json = st.file_uploader("Upload JSON", type=["json"])
            
            if uploaded_json:
                if st.button("📥 Import", use_container_width=True):
                    try:
                        content = uploaded_json.read().decode('utf-8')
                        kb.import_from_json(content)
                        st.success("✅ Imported successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
