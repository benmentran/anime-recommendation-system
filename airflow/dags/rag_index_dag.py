import asyncio
from airflow.decorators import dag, task
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_PYTHON_PATH = Path(__file__).parent.parent / ".venv/bin/python3.10"

@dag(
    dag_id='rag_index',
    description='embed anime_catalog -> Qdrant (full, no limit)',
    start_date=datetime(2026, 9, 26),
    schedule='@daily',
    catchup=False,
)
def rag_index_dag():
    @task.external_python(task_id="rag_index",
                        python=PROJECT_PYTHON_PATH,
                        retries=2, retry_delay=timedelta(minutes=30))
    def _run():
        from pipelines.rag_index import main

        asyncio.run(main())  # no limit: full re-embed (done-file skips indexed)

    _run()

rag_index_dag = rag_index_dag()
