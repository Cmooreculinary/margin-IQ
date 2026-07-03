"""POS adapter interface. Every adapter turns a raw export file into a list of
normalized PmixRow-shaped dicts so the ingestion pipeline never has to know
which POS a location runs. Add Square/Clover/Lightspeed by implementing this
interface -- nothing else in the ingestion or analysis pipeline changes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO


class PosAdapter(ABC):
    name: str

    @abstractmethod
    def parse_pmix(self, file: BinaryIO, location_id: str) -> list[dict]:
        """Return a list of dicts shaped like:
        {location_id, plu, item_name, period_start, period_end, units_sold, gross_revenue}
        """
        raise NotImplementedError
