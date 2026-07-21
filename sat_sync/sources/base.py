from abc import ABC, abstractmethod

class Source(ABC):

    name: str

    @abstractmethod
    def identities(self):
        """Return identities from this source."""
        pass