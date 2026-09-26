import os
from pathlib import Path
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

RAW_DIR = Path(__file__).parent.parent / "data/raw"
PROJECT_PYTHON_PATH = Path(__file__).parent.parent / ".venv/bin/python3.10"


default_args = {
    'start_date': datetime(2025, 7, 25),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='update_feast',
    description='Update new trending features to Feast',
    schedule_interval='0 */6 * * *',
    catchup=False,
    default_args=default_args,
) as dag:

    apply_feast = BashOperator(
        task_id="feast_apply",
        bash_command="""
        source /root/myproject/netflix-movie-recommendation-system/.venv/bin/activate
        && cd /root/myproject/netflix-movie-recommendation-system/feature_repo
        && feast apply -c feature_repo
        """
    )

    materialize = BashOperator(
        task_id="feast_materialize",
        bash_command="""
        source /root/myproject/netflix-movie-recommendation-system/.venv/bin/activate
        && cd /root/myproject/netflix-movie-recommendation-system/feature_repo
        && feast materialize-incremental -c feature_repo $(date +%FT%T)
        """
    )

    wait_for_vectorize = ExternalTaskSensor(
        task_id="wait_for_vectorize_features",
        external_dag_id="vectorize_features",
        external_task_id=None,
        poke_interval=60,
        timeout=3600,
    )

    wait_for_vectorize >> [apply_feast, materialize]
