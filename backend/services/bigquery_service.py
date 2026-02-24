import os
import pandas as pd
from typing import List, Dict, Any

class BigQueryService:
    def __init__(self, project_id: str = None):
        from google.cloud import bigquery
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "crown-cdw-intelia-dev")
        print(f"Initializing BigQuery client for project: {self.project_id}")
        self.client = bigquery.Client(project=self.project_id)

    def fetch_data(self, dataset_id: str, table_id: str, limit: int = None) -> pd.DataFrame:
        limit_clause = f" LIMIT {limit}" if limit else ""
        query = f"SELECT * FROM `{self.project_id}.{dataset_id}.{table_id}`{limit_clause}"
        return self.client.query(query).to_dataframe()

    def update_dedup_results(self, dataset_id: str, table_id: str, results_df: pd.DataFrame):
        """
        Writes the results to a new table with '_dedup_results' suffix.
        """
        output_table_id = f"{table_id}_dedup_results"
        full_table_path = f"{self.project_id}.{dataset_id}.{output_table_id}"
        
        print(f"Writing results to {full_table_path}...")
        
        # Configure the load job
        job_config = self.client.load_table_from_dataframe(
            results_df, full_table_path, job_config=None
        )
        job_config.result() # Wait for the job to complete
        print(f"Successfully wrote {len(results_df)} rows to BigQuery.")
        return full_table_path

    def perform_vector_search(self, dataset_id: str, table_id: str, query_embedding: List[float], top_k: int = 10):
        """
        Uses BigQuery's native VECTOR_SEARCH to find similar records.
        Note: Requires a vector index on the target table.
        """
        table_path = f"{self.project_id}.{dataset_id}.{table_id}"
        
        # This is a conceptual query - real world requires an embedding column named 'embedding'
        query = f"""
        SELECT *
        FROM VECTOR_SEARCH(
            TABLE `{table_path}`,
            'embedding',
            (SELECT {query_embedding} as query_embedding),
            top_k => {top_k}
        )
        """
        return self.client.query(query).to_dataframe()

    def get_preview(self, dataset_id: str, table_id: str) -> List[Dict[str, Any]]:
        df = self.fetch_data(dataset_id, table_id, limit=10)
        return df.to_dict(orient="records")
