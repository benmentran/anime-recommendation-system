import asyncio
from airflow.decorators import dag, task
from datetime import datetime, timedelta
from airflow.sensors.external_task import ExternalTaskSensor
from pathlib import Path


RAW_DIR = Path(__file__).parent.parent / "data/raw"
PROJECT_PYTHON_PATH = Path(__file__).parent.parent / ".venv/bin/python3.10"

@dag(
    dag_id='vectorize_features',
    description='stream anime_raw -> anime_catalog (SQL-first, Python fallback)',
    start_date=datetime(2025, 7, 25),
    schedule='0 */6 * * *',  # every 6 hours
    catchup=False,
)
def vectorize_trending_metadata():
    @task.external_python(task_id="transform_anime",
                        python=PROJECT_PYTHON_PATH,
                        retries=2, retry_delay=timedelta(minutes=30))
    def process_anime():
        from pipelines.transform import main  # ponytail: SQL path in db/002_transform.sql; fallback here

        asyncio.run(main())

    @task.external_python(task_id="assert_catalog",
                          python=PROJECT_PYTHON_PATH,
                          retries=0)
    def assert_catalog():
        from scripts.assert_catalog import main  # quality gate: raises -> DAG fails

        asyncio.run(main())

    wait_for_fetch = ExternalTaskSensor(
        task_id="wait_for_fetch_extract_features",
        external_dag_id="fetch_extract_features",
        external_task_id=None,
        poke_interval=60,
        timeout=3600,
    )

    anime_task = process_anime()
    quality_gate = assert_catalog()
    wait_for_fetch >> anime_task >> quality_gate

vectorize_trending_metadata = vectorize_trending_metadata()
