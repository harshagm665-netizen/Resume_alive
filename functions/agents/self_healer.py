"""
functions/agents/self_healer.py — Agent responsible for diagnosing and fixing errors.
"""
from typing import Dict, Any, Callable
from loguru import logger
from agents.base_agent import BaseAgent
from llm.client import llm
from llm.temperature import TaskType
from monitoring.self_healing import self_healing_engine

class SelfHealerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Self Healer",
            role="Site Reliability Engineer",
            goal="Diagnose errors, lookup known fixes, and suggest or execute remediation.",
            task_type=TaskType.ERROR_DIAGNOSIS
        )
        self.register_tool("get_known_fix", "Check if we have seen this error before", self_healing_engine.get_known_fix)
        self.register_tool("store_fix", "Store a new fix for future use", self_healing_engine.store_fix)

    def handle_error(self, error: Exception, context: str, retry_func: Callable = None) -> Any:
        """Attempts to diagnose and heal an error."""
        error_msg = str(error)
        logger.warning(f"[{self.name}] Intercepted error in {context}: {error_msg}")
        
        fingerprint = self_healing_engine.fingerprint(error_msg)
        known_fix = self_healing_engine.get_known_fix(fingerprint)
        
        if known_fix:
            logger.info(f"[{self.name}] Applying known fix: {known_fix}")
            # In a full implementation, known_fix would be an actionable JSON payload
            # (e.g. {"action": "wait", "args": {"seconds": 5}})
            if "wait" in known_fix and retry_func:
                import time
                time.sleep(5)
                logger.info(f"[{self.name}] Retrying after wait...")
                return retry_func()
                
        # If no known fix, consult LLM for diagnosis
        system = "You are an SRE diagnosing a system error. Suggest a fix action. Return JSON: {'action': 'wait|rotate_key|disable_module', 'reason': '...'}"
        user = f"Context: {context}\nError: {error_msg}"
        
        try:
            diagnosis = llm.chat_json(system, user, self.task_type)
            action = diagnosis.get("action")
            logger.info(f"[{self.name}] Diagnosis: {action} - {diagnosis.get('reason')}")
            
            if action:
                self_healing_engine.store_fix(fingerprint, action)
                
            return None # Return None if we couldn't auto-execute the fix
            
        except Exception as e:
            logger.error(f"[{self.name}] Diagnosis failed: {e}")
            return None
