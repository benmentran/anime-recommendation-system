from pathlib import Path
import logging
import yaml
from pipelines.ingest_steps import ingest_df

project_root = Path(__file__).resolve().parents[1]
logging.basicConfig(level=logging.INFO)


def _load_params():
    with open(project_root / "params.yaml") as f:
        cfg = yaml.safe_load(f)
    return cfg["pipelines"]["ingest"]


def ingest_ml100k_pipeline():
    # Load params
    params = _load_params()

    base_path = project_root / params["base_path"]
    processed_dir = project_root / params["processed_dir"]
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Ingest ratings
    ratings = ingest_df(base_path / "u.data", sep="\t",
                        header=None, names=["user_id","item_id","rating","timestamp"])

    # Ingest movies
    movies = ingest_df(base_path / "u.item", sep="|", header=None, encoding="latin-1",
                       names=["movie_id","title","release_date","video_release_date","IMDb_URL",
                              "unknown","Action","Adventure","Animation","Children's","Comedy",
                              "Crime","Documentary","Drama","Fantasy","Film-Noir","Horror",
                              "Musical","Mystery","Romance","Sci-Fi","Thriller","War","Western"])

    # Ingest users
    users = ingest_df(base_path / "u.user", sep="|", header=None,
                      names=["user_id","age","gender","occupation","zip_code"])

    # Save processed files
    ratings.to_csv(processed_dir / "ratings.csv", index=False)
    movies.to_csv(processed_dir / "movies.csv", index=False)
    users.to_csv(processed_dir / "users.csv", index=False)

    logging.info("Ingestion complete. Processed files are in %s", processed_dir)

if __name__ == "__main__":
    ingest_ml100k_pipeline()
