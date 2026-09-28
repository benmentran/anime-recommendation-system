import logging

import pandas as pd

from pipelines.data_strategy import (
    DataDivideStrategy,
    DataEncodeStrategy,
    DataNormalizeStrategy,
    DataPreprocessStrategy,
    DataStrategy,
    MultiLabelEncodeStrategy,
    TextVectorizeStrategy,
)
from pipelines.feature_engineer import FeatureEngineer


def clean_df(df: pd.DataFrame, datetime_cols: list[str] | None = None) -> pd.DataFrame:
    # Data cleaning
    preprocess_strategy = DataPreprocessStrategy()
    cleaned_df = preprocess_strategy.handle_data(df, datetime_cols)
    logging.info("Preprocessing completed!")

    return cleaned_df
 
def feature_engineer(df: pd.DataFrame,
                    datetime_cols: list[str] | None = None,
                    groupby_cols: list[str] | None = None,
                    ts_col: str = "timestamp",
                    drop_original: bool = False) -> pd.DataFrame:
    # Feature engineering
    df = FeatureEngineer.add_time_features(df, datetime_cols, drop_original)
    df = FeatureEngineer.add_interaction_gap(df, groupby_cols, ts_col)
    logging.info("Feature engineering added time features and interaction gaps")
    
    return df

def divide_df(df: pd.DataFrame, 
            test_size: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Data division
    divider = DataDivideStrategy()
    df_train, df_test = divider.handle_data(df, test_size)
    logging.info("Data split: train %d, test %d", len(df_train), len(df_test))
    
    return df_train, df_test

def encode_df(df_train: pd.DataFrame,
            df_test: pd.DataFrame | None = None,  
            method: str = "onehot", 
            columns: list[str] | None = None) -> pd.DataFrame | pd.Series:
    encode_strategy = DataEncodeStrategy()
    
    return encode_strategy.handle_data(df_train, df_test, method, columns)

def multi_label_encode_df(df_train: pd.DataFrame,
                          columns: list[str],
                          df_test: pd.DataFrame | None = None) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
    """
    Encode multi-label categorical columns (lists) into binary columns.
    """
    strategy = MultiLabelEncodeStrategy()

    return strategy.handle_data(df_train, columns, df_test)


def normalize_df(df_train: pd.DataFrame,
                df_test: pd.DataFrame | None = None, 
                method: str = "standard", 
                columns: list[str] | None = None,
                log_transform_columns: list[str] | None = None) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
    normalize_strategy = DataNormalizeStrategy()
    
    return normalize_strategy.handle_data(df_train, df_test, method, columns, log_transform_columns)
    
def vectorize_text(df_train: pd.DataFrame,
                   column: str,
                   output_col: str | None = None,
                   df_test: pd.DataFrame | None = None,
                   max_features: int = 1000,
                   strategy: DataStrategy | None = None) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
    if strategy is None:
        raise ValueError("You must provide a strategy instance.")
    
    if isinstance(strategy, TextVectorizeStrategy):
        df_train, df_test = strategy.handle_data(df_train, df_test, column, max_features, output_col)
    else:
        df_train, df_test = strategy.handle_data(df_train, df_test, column, output_col)
    
    return df_train, df_test
