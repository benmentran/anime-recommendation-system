from abc import ABC, abstractmethod
from pathlib import Path
import pandas as pd
from typing import Union
import logging


class IngestStrategy(ABC):
    """
    Abstract class difining strategy for ingesting data
    """
    @abstractmethod
    def read(self, source_path: Union[str, Path], **kwargs) -> pd.DataFrame:
        pass
    
class CSVIngestStrategy(IngestStrategy):
    def read(self, source_path: Union[str, Path], **kwargs) -> pd.DataFrame:
        return pd.read_csv(source_path, **kwargs)
    
class HTMLTableIngestStrategy(IngestStrategy):
    def read(self, source_path: Union[str, Path], **kwargs) -> pd.DataFrame:
        html_text = Path(source_path).read_text(encoding=kwargs.pop('encoding', 'utf-8'))
        dfs = pd.read_html(html_text, **kwargs)
        
        return dfs[0]
    
class NDJSONChunkStrategy:
    """Line-streamed NDJSON reader. Never json.load() the whole file."""
    def __init__(self, chunksize: int = 2000):
        self.chunksize = chunksize

    def iter_batches(self, source_path: Union[str, Path], **kwargs):
        import json as _json
        batch = []
        with open(source_path, encoding=kwargs.pop('encoding', 'utf-8')) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                batch.append(_json.loads(line))
                if len(batch) >= self.chunksize:
                    yield pd.DataFrame(batch)
                    batch = []
        if batch:
            yield pd.DataFrame(batch)

    def read(self, source_path: Union[str, Path], **kwargs) -> pd.DataFrame:
        # ponytail: full-read kept only for small files/tests; large files must use iter_batches
        import json as _json
        with open(source_path, encoding=kwargs.pop('encoding', 'utf-8')) as f:
            return pd.DataFrame([_json.loads(l) for l in f if l.strip()])

class IngestContext:
    """Selects appropriate ingest strategy based on file extension."""
    _strategies = {
        '.csv': CSVIngestStrategy(),
        '.html': HTMLTableIngestStrategy(),
        '.data': CSVIngestStrategy(),   # MovieLens .data (tab-separated)
        '.item': CSVIngestStrategy(),   # item metadata
        '.user': CSVIngestStrategy(),   # user metadata
        ".base": CSVIngestStrategy(),
        ".test": CSVIngestStrategy(),
        ".ndjson": NDJSONChunkStrategy(),
    }

    def __init__(self, source_path: Union[str, Path]):
        self.source_path = Path(source_path)
        ext = self.source_path.suffix.lower()
        if ext not in self._strategies:
            raise ValueError(f"No ingest strategy for extension '{ext}'")
        self.strategy = self._strategies[ext]

    def read(self, **kwargs) -> pd.DataFrame:
        try:
            return self.strategy.read(self.source_path, **kwargs)
        except Exception as e:
            logging.error(f"Error while ingesting data from {self.source_path}: {e}")
            raise