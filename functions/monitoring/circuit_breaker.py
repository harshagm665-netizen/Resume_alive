"""
functions/monitoring/circuit_breaker.py — Circuit Breaker pattern.
"""
from typing import Callable, Any
import time
from loguru import logger

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED" # CLOSED (ok), OPEN (failing), HALF_OPEN (testing)

    def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info("Circuit Breaker HALF_OPEN: Testing recovery...")
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit Breaker is OPEN. Call blocked to prevent cascade failure.")

        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                logger.info("Circuit Breaker CLOSED: Recovery successful.")
                self.state = "CLOSED"
                self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.failure_threshold:
                logger.error("Circuit Breaker OPEN: Threshold reached.")
                self.state = "OPEN"
            raise e
