import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Union, List, Optional, Tuple
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, MultiLabelBinarizer
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer
import logging


class DataStrategy(ABC):
    """
    Abstract class difining strategy for cleaning data
    """
    @abstractmethod
    def handle_data(self, data: pd.DataFrame) -> Union[pd.DataFrame, pd.Series]:
        pass


class DataPreprocessStrategy(DataStrategy):
    def handle_data(self, data: pd.DataFrame, datetime_cols: Optional[List[str]] = None) -> pd.DataFrame:
        try:
            # Drop duplicates or invalid data if any
            num_duplicates = data.duplicated().sum()
            na_pct = data.isna().mean()
            cols_to_drop = na_pct[na_pct > 0.8].index
            data = data.drop(columns=cols_to_drop)
                
            data.dropna(inplace=True, how='all')
            data.drop_duplicates(inplace=True)
            
            if datetime_cols is not None:
                for col in datetime_cols:
                    try:
                        data[col] = pd.to_datetime(data[col])
                    except Exception:
                        logging.error(f"Convert datetime error when in column {col}")
                    
            return data
        except Exception as e:
            logging.error(f"Error in preprocessing data: {e},")
            raise e
        
class DataDivideStrategy(DataStrategy):
    """
    Strategy for dividing data into train and test
    """ 
    def handle_data(self, data: pd.DataFrame, test_size: float = 0.2) -> Union[pd.DataFrame, pd.DataFrame]:
        try:
            train_df, test_df = train_test_split(data, test_size=test_size, random_state=42)
            
            return train_df, test_df
        except Exception as e:
            logging.error(f"Error in dividing data: {e}.")
            raise e
    
class DataEncodeStrategy(DataStrategy):
    """
    Strategy for encoding specific categorical features
    """
    def handle_data(self, df_train: pd.DataFrame,
                    df_test: Optional[pd.DataFrame] = None, 
                    method: str = "onehot", 
                    columns: List[str] = []) -> pd.DataFrame:
        if not columns:
            raise ValueError("You must specify at least one column to encode.")
        
        for col in columns:
            if col not in df_train.columns:
                raise ValueError(f"Column {col} not found in DataFrame.")
            
        if method == "label":
            for col in columns:
                le = LabelEncoder()
                df_train[col] = le.fit_transform(df_train[col].astype(str))
                if df_test is not None:
                    df_test[col] = le.transform(df_test[col].astype(str))
                
            return df_train, df_test
        elif method == "onehot":
            encoder = OneHotEncoder(
                handle_unknown='ignore',  
                sparse_output=False,          
            )

            df_train_cat = encoder.fit_transform(df_train[columns])
                
            new_cols = encoder.get_feature_names_out(columns)
            
            df_train_oh = pd.DataFrame(df_train_cat, columns=new_cols, 
                                       index=df_train.index)
            
            df_train = pd.concat([df_train.drop(columns, axis=1), df_train_oh], axis=1)
            
            if df_test is not None:
                df_test_cat = encoder.transform(df_test[columns])
                df_test_oh = pd.DataFrame(df_test_cat, 
                                          new_cols, 
                                          df_test.index)
                df_test = pd.concat([df_test.drop(columns, axis=1), df_test_oh], axis=1)
            
            return df_train, df_test
        else:
            raise ValueError("Unsupported encoding method. Use 'lable' or 'onehot'.")
    
class DataNormalizeStrategy(DataStrategy):
    def handle_data(self, df_train: pd.DataFrame,
                    df_test: Optional[pd.DataFrame] = None,
                    method: str = "standard", 
                    columns: Union[List[str], None] = None,
                    log_transform_columns: Union[List[str], None] = None) -> pd.DataFrame:
        """
        :param method: 'standard' or 'minmax'
        :param columns: List of numeric column names to normalize. If None, auto-select numeric columns.
        """
        try:
            if columns is None:
                columns = df_train.select_dtypes(include=['number']).columns.tolist()
            
            # Step 1: Optional log-transform
            if log_transform_columns:
                for col in log_transform_columns:
                    if col in df_train.columns:
                        df_train[col] = np.log1p(df_train[col])
                        if df_test is not None:
                            df_test[col] = np.log1p(df_test[col])
            
            # Step 2: Scaling
            if method == "standard":
                scaler = StandardScaler()
            elif method == "minmax":
                scaler = MinMaxScaler()
            else:
                    raise ValueError("Unsupported method. Choose 'standard' or 'minmax'.")

            df_train[columns] = scaler.fit_transform(df_train[columns])
            if df_test is not None:
                df_test[columns] = scaler.transform(df_test[columns])

            return df_train, df_test
        except Exception as e:
                logging.error(f"Error in normalizing data: {e}")
                raise e

class TextVectorizeStrategy(DataStrategy):
    def handle_data(
        self,
        df_train: pd.DataFrame,
        df_test: Optional[pd.DataFrame] = None,
        column: str = "",
        max_features: int = 1000,
        output_col: Optional[str] = None,
    ) -> Union[pd.DataFrame, Tuple[pd.DataFrame, pd.DataFrame]]:
        output_col = output_col or f"{column}_tfidf"
        if not column:
            raise ValueError("You must specify a text column to vectorize.")
        vectorizer = TfidfVectorizer(max_features=max_features)
        tfidf_train = vectorizer.fit_transform(df_train[column].astype(str))

        df_train[output_col] = [row for row in tfidf_train.toarray()]

        df_train = df_train.drop(columns=[column])

        if df_test is not None:
            tfidf_test = vectorizer.transform(df_test[column].astype(str))
            df_test[output_col] = [row for row in tfidf_test.toarray()]
            df_test = df_test.drop(columns=[column])
            return df_train, df_test

        return df_train, None
         
class BERTVectorizeStrategy(DataStrategy):
    """
    Strategy for vectorizing text columns using all-MiniLM-L6-v2 SentenceTransformer.
    """
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def handle_data(
        self,
        df_train: pd.DataFrame,
        df_test: Optional[pd.DataFrame] = None,
        column: str = "",
        output_col: Optional[str] = None,
    ) -> Union[pd.DataFrame, Tuple[pd.DataFrame, pd.DataFrame]]:
        output_col = output_col or f"{column}_bert"
        if not column:
            raise ValueError("You must specify a text column to vectorize.")

        # Process train set
        texts_train = df_train[column].astype(str).tolist()
        embeddings_train = self.model.encode(texts_train, show_progress_bar=True,
                                             normalize_embeddings=True)
        df_train[output_col] = [emb.tolist() for emb in embeddings_train]
        df_train = df_train.drop(columns=[column])

        # Process test set if exists
        if df_test is not None:
            texts_test = df_test[column].astype(str).tolist()
            embeddings_test = self.model.encode(texts_test, show_progress_bar=True,
                                                normalize_embeddings=True)
            df_test[output_col] = [emb.tolist() for emb in embeddings_test]
            df_test = df_test.drop(columns=[column])
            return df_train, df_test

        return df_train, None
    
class MultiLabelEncodeStrategy(DataStrategy):
    """
    Strategy for encoding multi-label categorical columns (like list of countries).
    Each category is converted into one-hot columns using MultiLabelBinarizer.
    """
    def handle_data(self,
                    df_train: pd.DataFrame,
                    columns: List[str],
                    df_test: Optional[pd.DataFrame] = None
                   ) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """
        :param columns: List of columns that are multi-label categorical (lists of categories).
        """
        if not columns:
            raise ValueError("You must specify at least one column to encode.")
        
        mlb_dict = {}

        for col in columns:
            if col not in df_train.columns:
                raise ValueError(f"Column '{col}' not found in DataFrame.")
            
            mlb = MultiLabelBinarizer()

            # Fit and transform train data
            train_encoded = mlb.fit_transform(df_train[col])
            new_cols = [f"{col}_{cls}" for cls in mlb.classes_]

            df_train_encoded = pd.DataFrame(train_encoded, columns=new_cols, index=df_train.index)
            df_train = pd.concat([df_train.drop(columns=[col]), df_train_encoded], axis=1)

            mlb_dict[col] = mlb

            # Transform test data if provided
            if df_test is not None:
                if col not in df_test.columns:
                    raise ValueError(f"Column '{col}' not found in test DataFrame.")

                test_encoded = mlb.transform(df_test[col])
                df_test_encoded = pd.DataFrame(test_encoded, columns=new_cols, index=df_test.index)
                df_test = pd.concat([df_test.drop(columns=[col]), df_test_encoded], axis=1)

        return df_train, df_test
    
    
class DataCleaning:
    def __init__(self, data: pd.DataFrame, strategy: DataStrategy):
        self.data = data
        self.strategy = strategy
        
    def handle_data(self) -> Union[pd.DataFrame, pd.Series]:
        try:
            return self.strategy.handle_data(self.data)
        except Exception as e:
            logging.error(f"Error while handling data: {e}.")
            raise e
         