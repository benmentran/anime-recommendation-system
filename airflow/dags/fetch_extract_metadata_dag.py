import asyncio
from airflow.decorators import dag, task
from datetime import datetime, timedelta
from pathlib import Path


RAW_DIR = Path(__file__).parent.parent / "data/raw"
PROJECT_PYTHON_PATH = Path(__file__).parent.parent / ".venv/bin/python3.10"
SEED_IDS = [1, 5, 21]  # fallback only when discovery is disabled AND no manual IDs
TOP_LIMIT = 5000

@dag(
    dag_id='fetch_extract_features',
    description='Crawl anime metadata (Jikan URL-only, skip-when-fresh)',
    start_date=datetime(2025, 8, 6),
    schedule='0 */6 * * *',  # every 6 hours
    catchup=False,
)
def fetch_extract_anime_metadata_dag():
    @task.external_python(task_id="fetch_extract_anime_metadata",
                        python=PROJECT_PYTHON_PATH,
                        retries=2, retry_delay=timedelta(minutes=30))
    def _run(**context):
        from pipelines.collection import crawl
        from pipelines.discovery import discover_all
        from services.anime_service.clients.jikan_client import JikanClient

        conf = (context.get("dag_run").conf if context.get("dag_run") else None) or {}
        manual = [int(i) for i in conf.get("mal_ids", [])]

        async def _discover():
            client = JikanClient()
            try:
                return await discover_all(client, conf.get("top_limit", TOP_LIMIT))
            finally:
                await client.close()

        if conf.get("discovery", True):
            discovered = asyncio.run(_discover())
        else:
            discovered = list(SEED_IDS)
        mal_ids = discovered + [i for i in manual if i not in set(discovered)]
        asyncio.run(crawl(mal_ids))

    _run()

fetch_extract_anime_metadata_dag = fetch_extract_anime_metadata_dag()
