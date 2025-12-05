"""
🥋 AI Karate Test Generator - Repository Edition
=================================================
Scans your entire repository to learn patterns from ALL feature files.
Uses Claude AI to generate tests that match YOUR exact style.
"""

import streamlit as st
import json
import re
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field, asdict
from collections import Counter
import zipfile
import io

# Try imports
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

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

@dataclass
class LearnedScenario:
    """A scenario learned from your repository"""
    name: str
    tags: List[str]
    content: str
    file_path: str
    template_used: str = ""
    response_code: str = ""
    has_sql: bool = False
    has_common_calls: bool = False

@dataclass
class LearnedPattern:
    """A reusable pattern learned from your code"""
    pattern_type: str  # background, step, assertion, sql, call
    content: str
    frequency: int = 1
    example_file: str = ""

# ============================================================================
# REPOSITORY SCANNER
# ============================================================================

class RepositoryScanner:
    """Scans repository to learn all Karate patterns"""
    
    def __init__(self):
        self.feature_files: List[Dict] = []
        self.scenarios: List[LearnedScenario] = []
        self.patterns: Dict[str, List[LearnedPattern]] = {
            "backgrounds": [],
            "steps": [],
            "assertions": [],
            "sql_queries": [],
            "calls": [],
            "variables": [],
            "tags": [],
        }
        self.templates_used: Counter = Counter()
        self.response_codes_used: Counter = Counter()
        self.field_mappings: Dict[str, Set[str]] = {}
        self.common_imports: List[str] = []
        self.config_patterns: List[str] = []
        
    def scan_directory(self, base_path: str, progress_callback=None) -> Dict:
        """Scan a directory for all .feature files"""
        base = Path(base_path)
        feature_files = list(base.rglob("*.feature"))
        
        total = len(feature_files)
        results = {"files": 0, "scenarios": 0, "patterns": 0}
        
        for i, file_path in enumerate(feature_files):
            try:
                content = file_path.read_text(encoding='utf-8')
                self._analyze_feature(content, str(file_path))
                results["files"] += 1
                
                if progress_callback:
                    progress_callback((i + 1) / total, f"Scanning {file_path.name}")
            except Exception as e:
                print(f"Error scanning {file_path}: {e}")
        
        results["scenarios"] = len(self.scenarios)
        results["patterns"] = sum(len(p) for p in self.patterns.values())
        
        return results
    
    def scan_uploaded_files(self, files: List, progress_callback=None) -> Dict:
        """Scan uploaded files"""
        results = {"files": 0, "scenarios": 0, "patterns": 0}
        total = len(files)
        
        for i, file in enumerate(files):
            try:
                content = file.read().decode('utf-8')
                self._analyze_feature(content, file.name)
                results["files"] += 1
                
                if progress_callback:
                    progress_callback((i + 1) / total, f"Analyzing {file.name}")
            except Exception as e:
                print(f"Error: {e}")
        
        results["scenarios"] = len(self.scenarios)
        results["patterns"] = sum(len(p) for p in self.patterns.values())
        
        return results
    
    def scan_zip_file(self, zip_file, progress_callback=None) -> Dict:
        """Scan a ZIP file containing feature files"""
        results = {"files": 0, "scenarios": 0, "patterns": 0}
        
        with zipfile.ZipFile(zip_file, 'r') as zf:
            feature_files = [f for f in zf.namelist() if f.endswith('.feature')]
            total = len(feature_files)
            
            for i, file_name in enumerate(feature_files):
                try:
                    content = zf.read(file_name).decode('utf-8')
                    self._analyze_feature(content, file_name)
                    results["files"] += 1
                    
                    if progress_callback:
                        progress_callback((i + 1) / total, f"Analyzing {file_name}")
                except Exception as e:
                    print(f"Error: {e}")
        
        results["scenarios"] = len(self.scenarios)
        results["patterns"] = sum(len(p) for p in self.patterns.values())
        
        return results
    
    def scan_pasted_content(self, content: str, name: str = "pasted") -> Dict:
        """Scan pasted content"""
        self._analyze_feature(content, name)
        return {
            "files": 1,
            "scenarios": len(self.scenarios),
            "patterns": sum(len(p) for p in self.patterns.values())
        }
    
    def _analyze_feature(self, content: str, file_path: str):
        """Analyze a single feature file"""
        lines = content.split('\n')
        
        # Store file info
        feature_info = {
            "path": file_path,
            "name": "",
            "tags": [],
            "backgrounds": [],
            "scenarios": [],
        }
        
        current_section = None
        current_content = []
        current_tags = []
        current_scenario_name = ""
        
        for line in lines:
            stripped = line.strip()
            
            # Feature name
            if stripped.startswith('Feature:'):
                feature_info["name"] = stripped.replace('Feature:', '').strip()
            
            # Tags
            if stripped.startswith('@'):
                tags = re.findall(r'@([\w-]+)', stripped)
                current_tags = tags
                for tag in tags:
                    self._add_pattern("tags", tag, file_path)
            
            # Background
            if stripped.startswith('Background:'):
                if current_section == 'scenario' and current_content:
                    self._save_scenario(current_scenario_name, current_tags, current_content, file_path)
                current_section = 'background'
                current_content = []
                continue
            
            # Scenario
            if stripped.startswith('Scenario:') or stripped.startswith('Scenario Outline:'):
                if current_section == 'background' and current_content:
                    bg_content = '\n'.join(current_content)
                    feature_info["backgrounds"].append(bg_content)
                    self._add_pattern("backgrounds", bg_content, file_path)
                elif current_section == 'scenario' and current_content:
                    self._save_scenario(current_scenario_name, current_tags, current_content, file_path)
                
                current_section = 'scenario'
                current_scenario_name = re.sub(r'^Scenario( Outline)?:', '', stripped).strip()
                current_content = []
                feature_info["tags"].extend(current_tags)
                continue
            
            # Collect content
            if current_section and stripped:
                current_content.append(line)
                self._analyze_line(stripped, file_path)
        
        # Save last scenario
        if current_section == 'scenario' and current_content:
            self._save_scenario(current_scenario_name, current_tags, current_content, file_path)
        
        self.feature_files.append(feature_info)
    
    def _analyze_line(self, line: str, file_path: str):
        """Analyze a single line for patterns"""
        
        # Steps
        if re.match(r'^\* |^Given |^When |^Then |^And |^But ', line):
            normalized = self._normalize_step(line)
            self._add_pattern("steps", normalized, file_path)
        
        # Assertions
        if '* match ' in line or '* assert ' in line:
            self._add_pattern("assertions", line.strip(), file_path)
        
        # SQL queries
        if 'SELECT' in line.upper() or 'query' in line.lower() or 'DbUtils' in line:
            self._add_pattern("sql_queries", line.strip(), file_path)
        
        # Calls
        if 'call read' in line or 'call ' in line:
            self._add_pattern("calls", line.strip(), file_path)
        
        # Variables
        var_match = re.match(r'\* def (\w+)\s*=\s*(.+)', line)
        if var_match:
            self._add_pattern("variables", line.strip(), file_path)
        
        # Template references
        template_match = re.search(r"templateName\s*=\s*['\"]([^'\"]+)['\"]", line)
        if template_match:
            self.templates_used[template_match.group(1)] += 1
        
        # Response codes
        rc_match = re.search(r"DE39['\"]?\s*==\s*['\"]?(\d{2})['\"]?", line)
        if rc_match:
            self.response_codes_used[rc_match.group(1)] += 1
        
        # Field mappings
        field_matches = re.findall(r'(DE\d+)[:\s=]+[\'"]?([^\'"\s,}]+)', line)
        for field, value in field_matches:
            if field not in self.field_mappings:
                self.field_mappings[field] = set()
            self.field_mappings[field].add(value)
    
    def _normalize_step(self, step: str) -> str:
        """Normalize a step for pattern matching"""
        normalized = re.sub(r'["\'][^"\']+["\']', '"{value}"', step)
        normalized = re.sub(r'\d{4,}', '{number}', normalized)
        return normalized.strip()
    
    def _add_pattern(self, pattern_type: str, content: str, file_path: str):
        """Add or update a pattern"""
        for p in self.patterns[pattern_type]:
            if p.content == content:
                p.frequency += 1
                return
        
        self.patterns[pattern_type].append(LearnedPattern(
            pattern_type=pattern_type,
            content=content,
            frequency=1,
            example_file=file_path
        ))
    
    def _save_scenario(self, name: str, tags: List[str], content: List[str], file_path: str):
        """Save a learned scenario"""
        content_str = '\n'.join(content)
        
        # Detect characteristics
        template_match = re.search(r"templateName\s*=\s*['\"]([^'\"]+)['\"]", content_str)
        rc_match = re.search(r"DE39['\"]?\s*==\s*['\"]?(\d{2})['\"]?", content_str)
        
        scenario = LearnedScenario(
            name=name,
            tags=tags,
            content=content_str,
            file_path=file_path,
            template_used=template_match.group(1) if template_match else "",
            response_code=rc_match.group(1) if rc_match else "",
            has_sql='SELECT' in content_str.upper() or 'query' in content_str.lower(),
            has_common_calls='call read' in content_str
        )
        
        self.scenarios.append(scenario)
    
    def get_summary(self) -> Dict:
        """Get summary of learned patterns"""
        return {
            "total_files": len(self.feature_files),
            "total_scenarios": len(self.scenarios),
            "backgrounds": len(self.patterns["backgrounds"]),
            "unique_steps": len(self.patterns["steps"]),
            "assertions": len(self.patterns["assertions"]),
            "sql_queries": len(self.patterns["sql_queries"]),
            "calls": len(self.patterns["calls"]),
            "variables": len(self.patterns["variables"]),
            "unique_tags": len(self.patterns["tags"]),
            "templates_used": dict(self.templates_used.most_common(10)),
            "response_codes_used": dict(self.response_codes_used.most_common(10)),
            "fields_discovered": list(self.field_mappings.keys()),
        }
    
    def get_context_for_claude(self, max_examples: int = 5) -> str:
        """Build comprehensive context for Claude"""
        context = "# LEARNED FROM YOUR REPOSITORY\n\n"
        
        # Summary
        summary = self.get_summary()
        context += f"""## Repository Summary
- Total Feature Files: {summary['total_files']}
- Total Scenarios: {summary['total_scenarios']}
- Unique Step Patterns: {summary['unique_steps']}
- SQL Patterns: {summary['sql_queries']}
- Unique Tags: {summary['unique_tags']}

"""
        
        # Most used templates
        if self.templates_used:
            context += "## Templates Used (by frequency)\n"
            for template, count in self.templates_used.most_common(10):
                context += f"- {template}: {count} times\n"
            context += "\n"
        
        # Response codes
        if self.response_codes_used:
            context += "## Response Codes Used (by frequency)\n"
            for rc, count in self.response_codes_used.most_common(10):
                context += f"- RC {rc}: {count} times\n"
            context += "\n"
        
        # Background patterns
        if self.patterns["backgrounds"]:
            context += "## Common Background Patterns\n"
            for bg in sorted(self.patterns["backgrounds"], key=lambda x: -x.frequency)[:3]:
                context += f"```gherkin\nBackground:\n{bg.content[:500]}\n```\n\n"
        
        # Most common steps
        context += "## Most Common Step Patterns\n"
        for step in sorted(self.patterns["steps"], key=lambda x: -x.frequency)[:15]:
            context += f"- ({step.frequency}x) `{step.content[:100]}`\n"
        context += "\n"
        
        # SQL patterns
        if self.patterns["sql_queries"]:
            context += "## SQL Query Patterns\n"
            for sql in sorted(self.patterns["sql_queries"], key=lambda x: -x.frequency)[:5]:
                context += f"```\n{sql.content}\n```\n"
            context += "\n"
        
        # Call patterns
        if self.patterns["calls"]:
            context += "## Common Scenario Calls\n"
            for call in sorted(self.patterns["calls"], key=lambda x: -x.frequency)[:5]:
                context += f"- `{call.content}`\n"
            context += "\n"
        
        # Example scenarios (most representative)
        context += "## Example Scenarios From Your Repository\n"
        # Get diverse examples
        examples = self._get_diverse_examples(max_examples)
        for i, scenario in enumerate(examples, 1):
            context += f"""
### Example {i}: {scenario.name}
- Tags: {', '.join(scenario.tags)}
- Template: {scenario.template_used or 'N/A'}
- Response Code: {scenario.response_code or 'N/A'}
- Has SQL: {scenario.has_sql}
- Uses Common Calls: {scenario.has_common_calls}

```gherkin
Scenario: {scenario.name}
{scenario.content[:800]}
{"..." if len(scenario.content) > 800 else ""}
```

"""
        
        # Field mappings
        if self.field_mappings:
            context += "## Field Mappings Discovered\n"
            for field, values in sorted(self.field_mappings.items()):
                sample_values = list(values)[:3]
                context += f"- {field}: {', '.join(sample_values)}\n"
        
        return context
    
    def _get_diverse_examples(self, count: int) -> List[LearnedScenario]:
        """Get diverse example scenarios"""
        examples = []
        
        # Get one with SQL
        sql_scenarios = [s for s in self.scenarios if s.has_sql]
        if sql_scenarios:
            examples.append(sql_scenarios[0])
        
        # Get one with common calls
        call_scenarios = [s for s in self.scenarios if s.has_common_calls and s not in examples]
        if call_scenarios:
            examples.append(call_scenarios[0])
        
        # Get different response codes
        seen_rcs = set()
        for s in self.scenarios:
            if s.response_code and s.response_code not in seen_rcs and s not in examples:
                examples.append(s)
                seen_rcs.add(s.response_code)
                if len(examples) >= count:
                    break
        
        # Fill remaining
        for s in self.scenarios:
            if s not in examples:
                examples.append(s)
                if len(examples) >= count:
                    break
        
        return examples[:count]
    
    def find_similar_scenarios(self, prompt: str, limit: int = 3) -> List[LearnedScenario]:
        """Find scenarios similar to the prompt"""
        prompt_lower = prompt.lower()
        keywords = set(re.findall(r'\w+', prompt_lower))
        
        scored = []
        for scenario in self.scenarios:
            score = 0
            scenario_text = (scenario.name + ' ' + ' '.join(scenario.tags) + ' ' + scenario.content).lower()
            
            for keyword in keywords:
                if keyword in scenario_text:
                    score += 1
            
            # Boost for specific matches
            if 'negative' in prompt_lower and any(t in ['negative', 'decline'] for t in scenario.tags):
                score += 3
            if 'e2e' in prompt_lower and 'e2e' in scenario.tags:
                score += 3
            if 'sql' in prompt_lower and scenario.has_sql:
                score += 2
            if 'approved' in prompt_lower and scenario.response_code == '00':
                score += 2
            if 'declined' in prompt_lower and scenario.response_code not in ['00', '']:
                score += 2
            
            scored.append((score, scenario))
        
        scored.sort(key=lambda x: -x[0])
        return [s for _, s in scored[:limit]]
    
    def export_learned_data(self) -> str:
        """Export all learned data as JSON"""
        data = {
            "summary": self.get_summary(),
            "feature_files": self.feature_files,
            "scenarios": [asdict(s) for s in self.scenarios],
            "patterns": {
                k: [{"content": p.content, "frequency": p.frequency} for p in v]
                for k, v in self.patterns.items()
            },
            "templates_used": dict(self.templates_used),
            "response_codes_used": dict(self.response_codes_used),
            "field_mappings": {k: list(v) for k, v in self.field_mappings.items()},
        }
        return json.dumps(data, indent=2)
    
    def import_learned_data(self, json_str: str):
        """Import previously learned data"""
        data = json.loads(json_str)
        
        self.feature_files = data.get("feature_files", [])
        self.templates_used = Counter(data.get("templates_used", {}))
        self.response_codes_used = Counter(data.get("response_codes_used", {}))
        self.field_mappings = {k: set(v) for k, v in data.get("field_mappings", {}).items()}
        
        # Reconstruct scenarios
        for s in data.get("scenarios", []):
            self.scenarios.append(LearnedScenario(**s))
        
        # Reconstruct patterns
        for pattern_type, patterns in data.get("patterns", {}).items():
            for p in patterns:
                self.patterns[pattern_type].append(LearnedPattern(
                    pattern_type=pattern_type,
                    content=p["content"],
                    frequency=p["frequency"]
                ))

# ============================================================================
# KNOWLEDGE BASE
# ============================================================================

class KnowledgeBase:
    def __init__(self):
        self.templates: Dict[str, TransactionTemplate] = {}
        self.response_codes: Dict[str, ResponseCode] = {}
        self.sql_tables: Dict[str, SQLTable] = {}
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
        ]
        for t in templates:
            self.templates[t.id] = t
        
        codes = [
            ResponseCode("00", "Approved", "approved"),
            ResponseCode("05", "Do Not Honor", "declined"),
            ResponseCode("14", "Invalid Card", "declined", "DE2", "1234567890123456"),
            ResponseCode("51", "Insufficient Funds", "declined", "DE4", "999999999999"),
            ResponseCode("54", "Expired Card", "declined", "DE14", "2001"),
            ResponseCode("55", "Invalid PIN", "declined"),
            ResponseCode("61", "Exceeds Limit", "declined", "DE4", "500000000000"),
        ]
        for rc in codes:
            self.response_codes[rc.code] = rc
        
        self.sql_tables["PPH_TRAN"] = SQLTable("PPH_TRAN", "Payment Hub Transaction",
            {"TRAN_ID": {"type": "VARCHAR2(36)"}, "TXN_STATUS": {"type": "VARCHAR2(20)"}, "RESP_CODE": {"type": "VARCHAR2(2)"}, "RRN": {"type": "VARCHAR2(12)"}, "STAN": {"type": "VARCHAR2(6)"}},
            ["RRN", "STAN"])
        
        self.sql_tables["PPDSVA"] = SQLTable("PPDSVA", "Value Added Data",
            {"SVA_ID": {"type": "VARCHAR2(36)"}, "FRAUD_CHECK": {"type": "VARCHAR2(10)"}, "HOST_RESP_CODE": {"type": "VARCHAR2(4)"}},
            ["RRN", "STAN"])
    
    def get_context(self) -> str:
        context = "# AVAILABLE CONFIGURATION\n\n"
        
        context += "## Transaction Templates\n"
        for t in self.templates.values():
            context += f"- {t.name}: {t.description} (Category: {t.category}, Network: {t.card_network})\n"
        
        context += "\n## Response Codes\n"
        for rc in self.response_codes.values():
            trigger = f" [Trigger: {rc.trigger_field}={rc.trigger_value}]" if rc.trigger_field else ""
            context += f"- {rc.code}: {rc.message} ({rc.category}){trigger}\n"
        
        context += "\n## SQL Tables\n"
        for tbl in self.sql_tables.values():
            context += f"- {tbl.name}: {tbl.description} (Keys: {', '.join(tbl.key_columns)})\n"
        
        return context

# ============================================================================
# CLAUDE GENERATOR
# ============================================================================

class ClaudeGenerator:
    def __init__(self, api_key: str, kb: KnowledgeBase, scanner: RepositoryScanner):
        self.api_key = api_key
        self.kb = kb
        self.scanner = scanner
        self.model = "claude-sonnet-4-20250514"
    
    def generate(self, prompt: str, options: Dict = None) -> str:
        options = options or {}
        
        system = self._build_system_prompt(options)
        user = self._build_user_prompt(prompt, options)
        
        if self.api_key and (HAS_ANTHROPIC or HAS_REQUESTS):
            return self._call_claude(system, user)
        else:
            return self._fallback_generate(prompt, options)
    
    def _build_system_prompt(self, options: Dict) -> str:
        prompt = """You are an expert Karate test framework developer. Your task is to generate Karate feature files that EXACTLY match the patterns and style learned from the user's repository.

CRITICAL RULES:
1. Follow the EXACT patterns from the learned repository
2. Use the SAME variable naming conventions
3. Use the SAME step patterns and assertion styles
4. Use the SAME Background structure
5. Use the SAME SQL query patterns if SQL validation is requested
6. Use the SAME call patterns for common scenarios
7. Generate tags that match the repository's tagging conventions

"""
        # Add knowledge base context
        prompt += self.kb.get_context()
        prompt += "\n\n"
        
        # Add learned patterns from repository
        if self.scanner.scenarios:
            prompt += self.scanner.get_context_for_claude(max_examples=5)
        
        prompt += """

OUTPUT RULES:
1. Return ONLY the Karate feature file content
2. Start with appropriate tags
3. Do NOT include markdown code blocks
4. Do NOT include explanations
5. Match the exact style from the repository examples
"""
        return prompt
    
    def _build_user_prompt(self, prompt: str, options: Dict) -> str:
        user = f"Generate a Karate feature file for: {prompt}\n\n"
        
        # Find similar scenarios
        if self.scanner.scenarios:
            similar = self.scanner.find_similar_scenarios(prompt, limit=2)
            if similar:
                user += "Reference these similar scenarios from the repository for style:\n"
                for s in similar:
                    user += f"\n--- {s.name} ---\n{s.content[:500]}\n"
        
        user += f"\nOptions:\n- Include SQL: {options.get('sql', True)}\n- Use common calls: {options.get('common', True)}\n"
        
        return user
    
    def _call_claude(self, system: str, user: str) -> str:
        try:
            if HAS_ANTHROPIC:
                client = anthropic.Anthropic(api_key=self.api_key)
                response = client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=system,
                    messages=[{"role": "user", "content": user}]
                )
                return response.content[0].text
            elif HAS_REQUESTS:
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
                    return response.json()["content"][0]["text"]
                else:
                    return f"# API Error: {response.status_code}\n{self._fallback_generate(user, {})}"
        except Exception as e:
            return f"# Error: {e}\n{self._fallback_generate(user, {})}"
    
    def _fallback_generate(self, prompt: str, options: Dict) -> str:
        """Fallback using learned patterns"""
        p = prompt.lower()
        
        # Find most similar scenario
        if self.scanner.scenarios:
            similar = self.scanner.find_similar_scenarios(prompt, limit=1)
            if similar:
                base = similar[0]
                # Modify the similar scenario
                result = f"# Generated based on: {base.name}\n"
                result += f"# From: {base.file_path}\n\n"
                
                # Use its structure but modify
                content = base.content
                # Simple modifications based on prompt
                if 'approved' in p and base.response_code != '00':
                    content = re.sub(r"DE39.*?==.*?'\d+'", "DE39' == '00'", content)
                
                return f"@generated @ai\nFeature: Generated Test\n\n  Scenario: {prompt[:50]}\n{content}"
        
        # Default minimal generation
        return f"""@generated
Feature: {prompt[:50]}

  Background:
    * url cosmosUrl
    * def templateName = 'fwd_visasig_direct_purchase_0100'

  Scenario: Generated Test
    * def stan = Math.floor(Math.random() * 999999).toString().padStart(6, '0')
    * def rrn = Math.floor(Math.random() * 999999999999).toString().padStart(12, '0')
    
    Given path '/template'
    And param id = templateName
    When method post
    Then status 200
    * match response.DE39 == '00'
"""

# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(page_title="AI Karate Generator", page_icon="🥋", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono&display=swap');

:root {
    --primary: #7C3AED;
    --success: #10B981;
    --warning: #F59E0B;
    --danger: #EF4444;
}

* { font-family: 'Plus Jakarta Sans', sans-serif; }

.stApp { background: linear-gradient(135deg, #F0F4FF 0%, #FAFBFF 50%, #F5F0FF 100%); }
#MainMenu, footer, header { visibility: hidden; }

.header {
    background: linear-gradient(135deg, #7C3AED 0%, #9333EA 50%, #06B6D4 100%);
    border-radius: 20px;
    padding: 2rem;
    text-align: center;
    color: white;
    margin-bottom: 2rem;
}
.header h1 { font-size: 2.5rem; font-weight: 800; margin: 0; }
.header p { opacity: 0.9; margin-top: 0.5rem; }

.stats-row {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 1rem;
    margin: 1.5rem 0;
}
.stat-box {
    background: white;
    border-radius: 12px;
    padding: 1rem;
    text-align: center;
    border: 1px solid #E2E8F0;
}
.stat-num {
    font-size: 1.75rem;
    font-weight: 800;
    background: linear-gradient(135deg, var(--primary), #06B6D4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.stat-label { font-size: 0.7rem; color: #64748B; text-transform: uppercase; font-weight: 600; }

.card {
    background: white;
    border-radius: 16px;
    padding: 1.5rem;
    border: 1px solid #E2E8F0;
    margin: 1rem 0;
}

.section-title {
    font-size: 1.25rem;
    font-weight: 700;
    margin: 1rem 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.pattern-tag {
    display: inline-block;
    background: #F1F5F9;
    padding: 0.25rem 0.75rem;
    border-radius: 100px;
    font-size: 0.75rem;
    margin: 0.125rem;
}

.stTabs [data-baseweb="tab-list"] {
    background: white;
    border-radius: 12px;
    padding: 4px;
    border: 1px solid #E2E8F0;
}
.stTabs [data-baseweb="tab"] {
    font-weight: 600;
    border-radius: 8px;
    color: #64748B;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, var(--primary), #5B21B6) !important;
    color: white !important;
}

.stButton > button {
    background: linear-gradient(135deg, var(--primary), #5B21B6);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 700;
    padding: 0.625rem 1.25rem;
}
</style>
""", unsafe_allow_html=True)


def main():
    if 'scanner' not in st.session_state:
        st.session_state.scanner = RepositoryScanner()
    if 'kb' not in st.session_state:
        st.session_state.kb = KnowledgeBase()
    if 'api_key' not in st.session_state:
        st.session_state.api_key = ""
    
    scanner = st.session_state.scanner
    kb = st.session_state.kb
    summary = scanner.get_summary()
    
    # Header
    st.markdown('''
    <div class="header">
        <h1>🥋 AI Karate Generator</h1>
        <p>Scan your ENTIRE repository • Learn ALL patterns • Generate matching tests</p>
    </div>
    ''', unsafe_allow_html=True)
    
    # Stats
    st.markdown(f'''
    <div class="stats-row">
        <div class="stat-box"><div class="stat-num">{summary["total_files"]}</div><div class="stat-label">Files Scanned</div></div>
        <div class="stat-box"><div class="stat-num">{summary["total_scenarios"]}</div><div class="stat-label">Scenarios</div></div>
        <div class="stat-box"><div class="stat-num">{summary["unique_steps"]}</div><div class="stat-label">Step Patterns</div></div>
        <div class="stat-box"><div class="stat-num">{summary["sql_queries"]}</div><div class="stat-label">SQL Patterns</div></div>
        <div class="stat-box"><div class="stat-num">{summary["unique_tags"]}</div><div class="stat-label">Tags</div></div>
        <div class="stat-box"><div class="stat-num">{len(summary["templates_used"])}</div><div class="stat-label">Templates</div></div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📁 Scan Repository", "✨ Generate", "📊 Learned Patterns", "🔑 API Key", "💾 Export/Import"])
    
    # ========== TAB 1: SCAN ==========
    with tab1:
        st.markdown('<div class="section-title">📁 Scan Your Feature Files</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 📤 Upload Feature Files")
            uploaded = st.file_uploader(
                "Upload .feature files or a ZIP of your repository",
                type=["feature", "txt", "zip"],
                accept_multiple_files=True
            )
            
            if st.button("🔍 Scan Uploaded Files", use_container_width=True):
                if uploaded:
                    progress = st.progress(0)
                    status = st.empty()
                    
                    for file in uploaded:
                        if file.name.endswith('.zip'):
                            results = scanner.scan_zip_file(
                                io.BytesIO(file.read()),
                                lambda p, m: (progress.progress(p), status.text(m))
                            )
                        else:
                            content = file.read().decode('utf-8')
                            results = scanner.scan_pasted_content(content, file.name)
                    
                    progress.progress(1.0)
                    st.success(f"✅ Scanned {results['files']} files, found {results['scenarios']} scenarios!")
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 📂 Scan Local Directory")
            dir_path = st.text_input("Enter path to your Karate repository", placeholder="/path/to/your/karate/tests")
            
            if st.button("🔍 Scan Directory", use_container_width=True):
                if dir_path and os.path.isdir(dir_path):
                    progress = st.progress(0)
                    status = st.empty()
                    
                    results = scanner.scan_directory(
                        dir_path,
                        lambda p, m: (progress.progress(p), status.text(m))
                    )
                    
                    st.success(f"✅ Scanned {results['files']} files, found {results['scenarios']} scenarios!")
                    st.rerun()
                else:
                    st.error("Invalid directory path")
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### 📝 Paste Feature Content")
        pasted = st.text_area("Paste one or more feature files", height=200)
        if st.button("📥 Learn from Pasted Content", use_container_width=True):
            if pasted:
                results = scanner.scan_pasted_content(pasted, "pasted")
                st.success(f"✅ Learned {results['scenarios']} scenarios!")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ========== TAB 2: GENERATE ==========
    with tab2:
        st.markdown('<div class="section-title">✨ Generate Tests Using Learned Patterns</div>', unsafe_allow_html=True)
        
        if not scanner.scenarios:
            st.warning("⚠️ Please scan your repository first in the 'Scan Repository' tab")
        
        # Quick examples
        examples = [
            "E2E approved Visa purchase with SQL validation",
            "Declined transaction due to insufficient funds",
            "ATM withdrawal for $500",
            "MasterCard refund with reversal",
            "Expired card decline scenario",
        ]
        
        cols = st.columns(5)
        for i, ex in enumerate(examples):
            with cols[i]:
                if st.button(f"📝 {ex[:20]}...", key=f"ex{i}", use_container_width=True):
                    st.session_state.prompt = ex
        
        prompt = st.text_area(
            "Describe the test you want",
            value=st.session_state.get('prompt', ''),
            height=100,
            placeholder="Example: Write an E2E test for declined purchase due to expired card with full SQL validation"
        )
        
        col1, col2, col3 = st.columns(3)
        with col1:
            include_sql = st.checkbox("🗄️ Include SQL Validation", value=True)
        with col2:
            use_common = st.checkbox("🔗 Use Common Scenarios", value=True)
        with col3:
            match_style = st.checkbox("🎨 Match Repository Style", value=True)
        
        if st.button("🚀 Generate with Claude AI", type="primary", use_container_width=True):
            if prompt:
                generator = ClaudeGenerator(st.session_state.api_key, kb, scanner)
                
                with st.spinner("🤖 Generating test matching your repository style..."):
                    feature = generator.generate(prompt, {
                        "sql": include_sql,
                        "common": use_common,
                        "match_style": match_style
                    })
                
                st.success("✅ Generated!")
                st.code(feature, language="gherkin")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button("📥 Download .feature", feature, "generated_test.feature", use_container_width=True)
        
        # Show similar scenarios
        if prompt and scanner.scenarios:
            with st.expander("📚 Similar Scenarios in Your Repository"):
                similar = scanner.find_similar_scenarios(prompt)
                for s in similar:
                    st.markdown(f"**{s.name}** ({s.file_path})")
                    st.code(s.content[:300] + "...", language="gherkin")
    
    # ========== TAB 3: PATTERNS ==========
    with tab3:
        st.markdown('<div class="section-title">📊 Learned Patterns from Your Repository</div>', unsafe_allow_html=True)
        
        if not scanner.scenarios:
            st.info("Scan your repository to see learned patterns")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🏷️ Tags Used")
                tags_html = ""
                for p in sorted(scanner.patterns["tags"], key=lambda x: -x.frequency)[:20]:
                    tags_html += f'<span class="pattern-tag">@{p.content} ({p.frequency}x)</span> '
                st.markdown(f'<div>{tags_html}</div>', unsafe_allow_html=True)
                
                st.markdown("#### 📄 Templates Used")
                for template, count in scanner.templates_used.most_common(10):
                    st.markdown(f"- `{template}`: {count} times")
                
                st.markdown("#### 🔢 Response Codes")
                for rc, count in scanner.response_codes_used.most_common(10):
                    st.markdown(f"- RC `{rc}`: {count} times")
            
            with col2:
                st.markdown("#### 📝 Common Step Patterns")
                for p in sorted(scanner.patterns["steps"], key=lambda x: -x.frequency)[:10]:
                    st.code(f"({p.frequency}x) {p.content[:80]}")
                
                st.markdown("#### 🗄️ SQL Patterns")
                for p in sorted(scanner.patterns["sql_queries"], key=lambda x: -x.frequency)[:5]:
                    st.code(p.content[:100])
            
            st.markdown("---")
            st.markdown("#### 📚 Sample Learned Scenarios")
            for s in scanner.scenarios[:5]:
                with st.expander(f"{s.name} ({s.file_path})"):
                    st.markdown(f"**Tags:** {', '.join(s.tags)}")
                    st.markdown(f"**Template:** {s.template_used or 'N/A'} | **RC:** {s.response_code or 'N/A'}")
                    st.code(s.content[:500], language="gherkin")
    
    # ========== TAB 4: API KEY ==========
    with tab4:
        st.markdown('<div class="section-title">🔑 Claude API Configuration</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        api_key = st.text_input("Anthropic API Key", value=st.session_state.api_key, type="password")
        if st.button("💾 Save API Key", use_container_width=True):
            st.session_state.api_key = api_key
            st.success("✅ Saved!" if api_key else "Cleared")
        
        st.markdown("**Status:** " + ("🟢 Connected" if st.session_state.api_key else "🔴 Not connected (using fallback)"))
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ========== TAB 5: EXPORT ==========
    with tab5:
        st.markdown('<div class="section-title">💾 Export / Import Learned Data</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 📤 Export")
            if st.button("Export Learned Data", use_container_width=True):
                data = scanner.export_learned_data()
                st.download_button("⬇️ Download JSON", data, "learned_patterns.json", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### 📥 Import")
            uploaded_data = st.file_uploader("Upload learned data", type=["json"])
            if uploaded_data and st.button("Import", use_container_width=True):
                scanner.import_learned_data(uploaded_data.read().decode('utf-8'))
                st.success("✅ Imported!")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
