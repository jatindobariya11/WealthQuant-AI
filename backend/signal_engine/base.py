from abc import ABC, abstractmethod
from typing import Dict, Any

class SignalContributor(ABC):
    """Base class for all Signal Desk contributors."""
    
    @abstractmethod
    def compute(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute the signal contribution.
        
        Args:
            data (Dict[str, Any]): The raw market data for the symbol.
            context (Dict[str, Any]): Contextual market data (e.g., FII/DII, global markets).
            
        Returns:
            Dict[str, Any]: A dictionary containing the contributor's score, state, and metrics.
        """
        pass
