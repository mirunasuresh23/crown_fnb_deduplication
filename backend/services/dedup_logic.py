import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from abc import ABC, abstractmethod
import re

def normalize_text(text: str) -> str:
    """
    Standardizes text: lowercase, removes special characters, and strips whitespace.
    """
    if not text:
        return ""
    # Convert to lowercase
    text = text.lower()
    # Remove special characters and punctuation
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text

class DedupStep(ABC):
    @abstractmethod
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        pass

class ExactMatchStep(DedupStep):
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Step 1: Exact match on item_code or barcode/GTIN.
        Adds a 'group_id' and 'match_type' column.
        """
        if 'group_id' not in df.columns:
            df['group_id'] = None
        if 'match_type' not in df.columns:
            df['match_type'] = None

        # Exact match on item_code
        if 'item_code' in df.columns:
            dupes = df[df.duplicated('item_code', keep=False)].sort_values('item_code')
            for item_code, group in dupes.groupby('item_code'):
                group_id = f"exact_item_{item_code}"
                df.loc[group.index, 'group_id'] = group_id
                df.loc[group.index, 'match_type'] = 'exact_item_code'

        # Exact match on barcode (if not already matched)
        if 'barcode' in df.columns:
            remaining = df[df['group_id'].isna()]
            dupes = remaining[remaining.duplicated('barcode', keep=False)].sort_values('barcode')
            for barcode, group in dupes.groupby('barcode'):
                group_id = f"exact_barcode_{barcode}"
                df.loc[group.index, 'group_id'] = group_id
                df.loc[group.index, 'match_type'] = 'exact_barcode'

        return df


class FuzzyMatchStep(DedupStep):
    def __init__(self, model_name: str = "text-embedding-004", threshold: float = 0.90):
        self.model_name = model_name
        self.threshold = threshold
        self.model = None

    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
        if not self.model:
            self.model = TextEmbeddingModel.from_pretrained(self.model_name)
        
        # Vertex AI has a limit of 250 instances per request
        batch_size = 250
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            print(f"Embedding batch {i // batch_size + 1}...")
            inputs = [TextEmbeddingInput(text, "RETRIEVAL_DOCUMENT") for text in batch]
            embeddings = self.model.get_embeddings(inputs)
            all_embeddings.extend([e.values for e in embeddings])
            
        return np.array(all_embeddings)

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Step 2: Fuzzy name match using embeddings and cosine similarity.
        Optimized for large datasets to avoid N*N memory issues.
        """
        remaining = df[df['group_id'].isna()]
        if remaining.empty:
            return df

        print(f"Generating embeddings for {len(remaining)} records...")
        # Apply normalization before embedding
        remaining_normalized = remaining.copy()
        remaining_normalized['norm_descr'] = (remaining['DESCR'].fillna('') + " " + remaining['DESCR60'].fillna('')).apply(normalize_text)
        
        texts = remaining_normalized['norm_descr'].tolist()
        embeddings = self._get_embeddings(texts)
        
        from sklearn.metrics.pairwise import cosine_similarity
        
        # Use a sliding chunk approach to find matches without N*N matrix
        visited = set()
        chunk_size = 5000  # Process 5000 rows at a time against the whole set
        
        print("Calculating similarities in chunks (Hybrid Search)...")
        for i in range(0, len(remaining), chunk_size):
            end_idx = min(i + chunk_size, len(remaining))
            chunk_embeddings = embeddings[i:end_idx]
            
            # 1. Vector Similarity (Cosine)
            sim_chunk = cosine_similarity(chunk_embeddings, embeddings)
            
            for chunk_row_idx in range(len(sim_chunk)):
                actual_idx = i + chunk_row_idx
                if actual_idx in visited:
                    continue
                
                # 2. Keyword Similarity (Jaccard-like overlap)
                # Find potentially similar items based on vector threshold FIRST to limit overhead
                candidate_indices = np.where(sim_chunk[chunk_row_idx] > (self.threshold - 0.15))[0] 
                
                for sim_idx in candidate_indices:
                    if sim_idx == actual_idx: continue
                    
                    # Compute a simple word overlap score (Hybrid)
                    set1 = set(texts[actual_idx].split())
                    set2 = set(texts[sim_idx].split())
                    if not set1 or not set2: overlap = 0
                    else: overlap = len(set1 & set2) / min(len(set1), len(set2))
                    
                    # Combine scores: 70% Vector + 30% Keyword
                    final_score = (0.7 * sim_chunk[chunk_row_idx][sim_idx]) + (0.3 * overlap)
                    
                    if final_score > self.threshold:
                        group_id = f"fuzzy_{remaining.iloc[actual_idx].name}"
                        visited.add(sim_idx)
                        visited.add(actual_idx)
                        df.loc[remaining.index[sim_idx], 'group_id'] = group_id
                        df.loc[remaining.index[sim_idx], 'match_type'] = 'fuzzy_hybrid'
                        df.loc[remaining.index[sim_idx], 'confidence'] = float(final_score)
            
            print(f"Processed chunk {i // chunk_size + 1}/{(len(remaining)-1) // chunk_size + 1}")

        return df


class CrossEncoderRerankerStep(DedupStep):
    def __init__(self, model_name: str = "gemini-2.0-flash-001"):
        self.model_name = model_name
        self.model = None

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Step 3: High-precision re-ranking for fuzzy matches.
        Uses LLM to verify and re-score matches in the 'gray area'.
        """
        if 'group_id' not in df.columns or 'match_type' not in df.columns:
            return df

        # Target records that were matched via hybrid search
        mask = (df['match_type'] == 'fuzzy_hybrid') & (df['confidence'] < 0.95)
        candidates = df[mask]
        
        if candidates.empty:
            return df

        if not self.model:
            from vertexai.generative_models import GenerativeModel
            self.model = GenerativeModel(self.model_name)

        # Re-verify groups
        for group_id, group in candidates.groupby('group_id'):
            if len(group) < 2: continue
            
            # Context for re-ranking
            items_info = ""
            for _, row in group.iterrows():
                items_info += f"Description: {row.get('DESCR', '')} | Spec: {row.get('DESCR60', '')}\n"
            
            prompt = f"""Evaluate if these items are EXACTLY the same product. 
            Pay close attention to differences in:
            - Flavor or Scent (e.g., Lavender vs Cherry)
            - Size or Volume (e.g., 700ML vs 1L)
            - Material or Color
            - Pack Size (e.g., Pack 1 vs Pack 12)
            
            If any of these attributes differ, they are DIFFERENT products.
            Respond with a single number from 0 to 1 representing your confidence that they are the same.
            
            Items:
            {items_info}
            Confidence score:"""
            
            try:
                from vertexai.generative_models import GenerationConfig
                response = self.model.generate_content(
                    prompt, 
                    generation_config=GenerationConfig(temperature=0.0)
                )
                try:
                    score = float(response.text.strip())
                    df.loc[group.index, 'confidence'] = score
                    if score < 0.8:
                        # Demote or break group if LLM confidence is low
                        df.loc[group.index, 'group_id'] = None
                        df.loc[group.index, 'match_type'] = 'rerank_discarded'
                    else:
                        df.loc[group.index, 'match_type'] = 'rerank_verified'
                except:
                    pass
            except:
                continue

        return df

class LLMAssistedStep(DedupStep):
    def __init__(self, model_name: str = "gemini-2.0-flash-001"):
        self.model_name = model_name
        self.model = None

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Step 3: LLM-assisted merge decision for ambiguous cases.
        Targets cases where group_id is fuzzy matched but confidence is borderline.
        """
        if 'group_id' not in df.columns or 'confidence' not in df.columns:
            return df

        # Get group IDs that have at least one ambiguous record
        ambiguous_group_ids = df.loc[(df['match_type'] == 'fuzzy_embedding') & (df['confidence'] < 0.9) & (df['confidence'] > 0.7), 'group_id'].unique()
        ambiguous_group_ids = [gid for gid in ambiguous_group_ids if gid is not None]
        
        if not ambiguous_group_ids:
            return df

        if not self.model:
            from vertexai.generative_models import GenerativeModel
            self.model = GenerativeModel(self.model_name)

        # Iterate through entire groups that have ambiguous members
        for group_id in ambiguous_group_ids:
            group = df[df['group_id'] == group_id]
            if len(group) < 2: continue
            
            # Construct prompt with item details
            items_info = ""
            for _, row in group.iterrows():
                items_info += f"Item: {row.get('DESCR', 'N/A')} ({row.get('DESCR60', 'N/A')})\n"
            
            prompt = f"""Are these items the same product? 
            Check for differences in flavor, scent, size, or pack quantity.
            For example, 'MONIN LAVENDER' and 'MONIN CHERRY' are DIFFERENT.
            Answer 'yes' or 'no' only.
            
            Items:
            {items_info}"""
            try:
                from vertexai.generative_models import GenerationConfig
                response = self.model.generate_content(
                    prompt,
                    generation_config=GenerationConfig(temperature=0.0)
                )
                if "yes" in response.text.lower():
                    df.loc[group.index, 'match_type'] = 'llm_matched'
                else:
                    df.loc[group.index, 'group_id'] = None # Clear group for everyone
                    df.loc[group.index, 'match_type'] = 'llm_discarded'
            except Exception as e:
                print(f"LLM Error for group {group_id}: {e}")
                continue

        return df

class HumanReviewStep(DedupStep):
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Step 4: Human review queue.
        Flags records where LLM was unsure or confidence is still in 'gray area'.
        """
        # Mark for review if match_type is still fuzzy_embedding and confidence is low
        mask = (df['match_type'] == 'fuzzy_embedding') & (df['confidence'] < 0.8)
        df.loc[mask, 'review_required'] = True
        return df

class DedupAgent:
    def __init__(self):
        self.steps = [
            ExactMatchStep(),
            FuzzyMatchStep(),
            CrossEncoderRerankerStep(),
            LLMAssistedStep(),
            HumanReviewStep()
        ]

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        for step in self.steps:
            print(f"Running step: {step.__class__.__name__}")
            df = step.process(df)
            
        # Final Cleanup: Remove any groups that only contain one item
        if 'group_id' in df.columns:
            counts = df['group_id'].value_counts()
            single_item_groups = counts[counts == 1].index
            mask = df['group_id'].isin(single_item_groups)
            if mask.any():
                print(f"Cleaning up {mask.sum()} orphan groups...")
                df.loc[mask, 'group_id'] = None
                df.loc[mask, 'match_type'] = None
                
        return df
