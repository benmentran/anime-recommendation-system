from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.dates import days_ago

with DAG(
    dag_id="master_pipeline",
    start_date=days_ago(1),
    schedule_interval="@daily", 
    catchup=False
) as dag:

    crawl = TriggerDagRunOperator(
        task_id="trigger_crawl_trending",
        trigger_dag_id="fetch_extract_features",
    )

    vectorize = TriggerDagRunOperator(
        task_id="trigger_vectorization",
        trigger_dag_id="vectorize_features",
    )

    feast_update = TriggerDagRunOperator(
        task_id="trigger_feast_registry",
        trigger_dag_id="update_feast",
    )

    save_to_redis = TriggerDagRunOperator(
        task_id="trigger_save_to_redis",
        trigger_dag_id="save_features_to_redis",
    )

    crawl >> vectorize >> feast_update >> save_to_redis
