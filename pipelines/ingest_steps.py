from pathlib import Path

import pandas as pd

from pipelines.ingest_strategy import IngestContext

service_path = Path(__file__).resolve().parents[1]

def ingest_df(
    source_path: str | Path,
    sep: str = "\t",
    header: int | None = None,
    names: list[str] | None = None,
    encoding: str | None = None
) -> pd.DataFrame:
    """
    ZenML step: ingest given file into DataFrame using explicit parameters.
    Chooses strategy based on file extension via IngestContext.
    """
    context = IngestContext(source_path)
    read_kwargs = {"sep": sep}
    
    if header is not None:
        read_kwargs["header"] = header
        
    if names is not None:
        read_kwargs["names"] = names
        
    if encoding is not None:
        read_kwargs["encoding"] = encoding
        
    return context.read(**read_kwargs)
