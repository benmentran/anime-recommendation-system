from airflow.decorators import dag, task
from datetime import datetime, timedelta 
from airflow.sensors.external_task import ExternalTaskSensor
from pathlib import Path


RAW_DIR = Path(__file__).parent.parent / "data/raw"
PROJECT_PYTHON_PATH = Path(__file__).parent.parent / ".venv/bin/python3.10"


@dag(
    dag_id='save_features_to_redis',
    description='Push trending movie & TV features into Redis',
    start_date=datetime(2025, 8, 6),
    schedule='0 */6 * * *',  # every 6 hours
    catchup=False,
)
def save_features_to_redis_dag():
    @task.external_python(task_id="save_features_to_redis", 
                            python=PROJECT_PYTHON_PATH,
                            retries=2, retry_delay=timedelta(minutes=10))
    def _run():
        from utils.redis_helpers import save_features_to_redis

        save_features_to_redis(
            file_path=f"{RAW_DIR}/trending_movie_features.json",
            prefix="movie_id"
        )
        save_features_to_redis(
            file_path=f"{RAW_DIR}/trending_tv_features.json",
            prefix="tv_id"
        )
        save_features_to_redis(
            file_path=f"{RAW_DIR}/trending_movie_cast_metadata.json",
            prefix="cast_id",
            key_field="cast_id"
        )
        save_features_to_redis(
            file_path=f"{RAW_DIR}/trending_tv_cast_metadata.json",
            prefix="cast_id",
            key_field="cast_id"
        )
        
    wait_for_feast = ExternalTaskSensor(
        task_id="wait_for_feast_update",
        external_dag_id="update_feast",
        external_task_id=None,
        poke_interval=60,
        timeout=3600,
    )

    save_task = _run()
    wait_for_feast >> save_task

save_features_to_redis_dag = save_features_to_redis_dag()
