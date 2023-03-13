#!/usr/bin/env python
# coding: utf-8
from datetime import timedelta
import os
import argparse
from time import time
import pandas as pd
from sqlalchemy import create_engine
from prefect import flow, task
from prefect.tasks import task_input_hash
from prefect_sqlalchemy import SqlAlchemyConnector

@task(logs_print=True, retries=3, cache_key_fn=task_input_hash, cache_expiration=timedelta(days=1))
def extract_data(url):
    if url.endswith('.csv.gz'):
        csv_name = 'yellow_tripdata_2021-01.csv.gz'
    else:
        csv_name =  'output.csv'

    os.system(f"wget {url} -0 {csv_name}")

    df_iter = pd.read_csvO(csv_name, iterator=True, chunksize=10000)

    df = next(df_iter)

    df.tpep_pickup_datetime = pd.to_datetime(df.tpep_pickup_datetime)
    df.tpep_dropoff_datetime = pd.to_datetime(df.tpep_dropoff_datetime)
    return df

@task(logs_print=True)
def transform_data(df):
    print(f"pre: missing passenger count: {df['passenger_count'].isin([0]).sum()}")
    df = df[df['passenger_count'] != 0]
    print(f"post: missing passenger count: {df['passenger_count'].isin([0]).sum()}")
    return df

@task(logs_print=True, retries=3)
def ingest_data(table_name, df):
    connection_block = SqlAlchemyConnector.load("postgres-connector")
    # postgres_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    # engine = create_engine(postgres_url)
    with connection_block.get_connection(begin=False) as engine:
        df.head(n=0).to_sql(name=table_name, con=engine, if_exists='replace')

        df.to_sql(name=table_name, con=engine, if_exists='append')


@flow(name="Subflow", log_prints=True)
def log_subflow(table_name:str):
    print("Logging Subflow for:", table_name)

@flow(name="Ingest Flow")
def main(table_name:str):
    user="postgres"
    password="admin"
    host="localhost"
    port="5433"
    db="ny_taxi"
    csv_url="https://github.com/DataTalksClub/nyc-tls-data/releases/download/yellow_tripdata_2021-01.csv.gz"
    log_subflow(table_name)
    raw_data = extract_data(csv_url)
    data = transform_data(raw_data)
    ingest_data(table_name, data)


if __name__ == '__main__':
    main("yellow_taxi_trips")