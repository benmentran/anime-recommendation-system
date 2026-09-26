import json
import redis
from pathlib import Path
from typing import List, Dict, Any
import logging


# Paths to raw data files
MOVIE_FEATURES_FILE = Path("data/raw/movie_features.json")
MOVIE_CAST_FILE = Path("data/raw/movie_cast_metadata.json")
TV_FEATURES_FILE = Path("data/raw/tv_features.json")
TV_CAST_FILE = Path("data/raw/tv_cast_metadata.json")

# Redis keys (using namespaces for easy querying)
MOVIE_FEATURES_KEY = "movie:features"
MOVIE_CAST_KEY = "movie:cast"
TV_FEATURES_KEY = "tv:features"
TV_CAST_KEY = "tv:cast"


class RedisHelper:
    """
    Helper class for loading movie/TV features and cast metadata into Redis
    in a normalized form to avoid duplication.
    """

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.redis_client = redis.StrictRedis(host=host, port=port, db=db, decode_responses=True)

    def _load_json(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load JSON file containing a list of dictionaries."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _store_features(self, redis_key: str, items: List[Dict[str, Any]]):
        """
        Store features in Redis as a hash, keyed by ID.
        This allows quick retrieval without scanning all data.
        """
        with self.redis_client.pipeline() as pipe:
            for item in items:
                item_id = item.get("id")
                if item_id is not None:
                    pipe.hset(redis_key, item_id, json.dumps(item))
                    
            pipe.execute()

    def _store_cast(self, redis_key: str, items: List[Dict[str, Any]]):
        """
        Store cast metadata in Redis as a hash, keyed by cast ID.
        Each value is a JSON string representing the cast details.
        This avoids storing duplicate cast data for multiple movies/TV shows.
        """
        with self.redis_client.pipeline() as pipe:
            for cast_member in items:
                cast_id = cast_member.get("cast_id")
                if cast_id is not None:
                    pipe.hset(redis_key, cast_id, json.dumps(cast_member))
                    
            pipe.execute()

    def load_all_data(self):
        """Load all movie and TV features/cast into Redis."""
        # Movie features and cast
        movie_features = self._load_json(MOVIE_FEATURES_FILE)
        movie_cast = self._load_json(MOVIE_CAST_FILE)
        self._store_features(MOVIE_FEATURES_KEY, movie_features)
        self._store_cast(MOVIE_CAST_KEY, movie_cast)

        # TV features and cast
        tv_features = self._load_json(TV_FEATURES_FILE)
        tv_cast = self._load_json(TV_CAST_FILE)
        self._store_features(TV_FEATURES_KEY, tv_features)
        self._store_cast(TV_CAST_KEY, tv_cast)

    def get_feature(self, category: str, item_id: str) -> Dict[str, Any]:
        """
        Retrieve a single movie or TV feature by ID.
        category: "movie" or "tv"
        """
        key = MOVIE_FEATURES_KEY if category == "movie" else TV_FEATURES_KEY
        data = self.redis_client.hget(key, item_id)
        
        return json.loads(data) if data else None

    def get_cast_member(self, category: str, cast_id: str) -> Dict[str, Any]:
        """
        Retrieve a single cast member's metadata by ID.
        category: "movie" or "tv"
        """
        key = MOVIE_CAST_KEY if category == "movie" else TV_CAST_KEY
        data = self.redis_client.hget(key, cast_id)
        
        return json.loads(data) if data else None


if __name__ == "__main__":
    helper = RedisHelper()
    helper.load_all_data()
    logging.info("✅ All data loaded into Redis.")
