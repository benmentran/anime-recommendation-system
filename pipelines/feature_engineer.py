
import pandas as pd


class FeatureEngineer:
    @staticmethod
    def add_time_features(df: pd.DataFrame,
                          datetime_cols: list[str] | None = None,
                          drop_original: bool = True) -> pd.DataFrame:
        data = df.copy()
        
        if datetime_cols is None:
            datetime_cols = data.select_dtypes(include=['datetime64[ns]', 'datetime64']).columns.tolist()
        
        for col in datetime_cols:
            series = data[col]
            data[f"{col}_year"]      = series.dt.year
            data[f"{col}_month"]     = series.dt.month
            data[f"{col}_day"]       = series.dt.day
            data[f"{col}_hour"]      = series.dt.hour
            data[f"{col}_dayofweek"] = series.dt.dayofweek
            data[f"{col}_is_weekend"] = (series.dt.dayofweek >= 5).astype(int)
        
        if drop_original:
            data = data.drop(columns=datetime_cols)
        
        return data

    @staticmethod
    def add_interaction_gap(df: pd.DataFrame,
                            groupby_cols: list[str] | None = None,
                            ts_col: str = "timestamp") -> pd.DataFrame:
        df = df.copy()
        
        if groupby_cols is None:
            raise ValueError("You must specify groupby_cols to calculate the distance.")
        
        # Sort và shift
        df = df.sort_values(groupby_cols + [ts_col])
        df["prev_ts"] = df.groupby(groupby_cols)[ts_col].shift(1)
        df["time_since_last"] = df[ts_col] - df["prev_ts"]
        df["time_since_last"] = df["time_since_last"].dt.total_seconds()
        
        return df
