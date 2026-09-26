from setuptools import setup, find_packages

setup(
    name="netflix_recommender",
    version="0.1.3",
    packages=find_packages(where="."), 
    include_package_data=True,
    install_requires=[
        "python-dotenv==1.1.1",
        "requests==2.32.4",
        "pandas==2.2.2",
        "numpy==2.2.6",
        "pyyaml==6.0.2",
        "feast==0.51.0",
        "sentence_transformers==5.0.0",
        "redis==6.2.0",
        "dvc==3.61.0",
        "mlflow==3.1.4",
        "h2==4.2.0",
        "asyncio==3.4.3",
        "httpx==0.28.1",
        "pymilvus==2.3.7"
    ],
)
