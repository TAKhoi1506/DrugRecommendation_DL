from flask import Flask, render_template, request, jsonify, redirect, session, flash, url_for
import pandas as pd
import os
import re
import json
import uuid
import math
import hashlib
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
from werkzeug.utils import secure_filename
from init import (
    change_password, clear_search_history, get_db, get_search_history, 
    get_search_statistics, get_user_profile, init_database, create_user, 
    log_search_enhanced, track_drug_click, update_user_profile, verify_user, 
    get_stats, save_drug, get_saved_drugs, remove_saved_drug, is_drug_saved,
    get_all_drugs, get_all_users, add_drug as add_drug_to_master, delete_drug,
    update_drug as update_drug_to_master, update_user_role, delete_user_account,
)
from functools import wraps
from datetime import timedelta


class EnhancedDrugRecommendationEngine:
    def __init__(self):
        self.data_final = None
        self.tokenizer = None
        self.phobert_model = None
        self.drug_embeddings = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.max_length = int(os.getenv("DRUG_MAX_LENGTH", "128"))

        self.name_col = 'ten_thuoc'
        self.ingredients_col = 'thanh_phan'
        self.indication_col = 'chi_dinh'
        self.contra_col = 'chong_chi_dinh'
        self.side_effect_col = 'tac_dung_phu'
        self.usage_col = None
        self.caution_col = None
        self.packing_col = None
        self.dosage_form_col = None
        self.manufacturer_col = None
        self.price_col = None
        self.category_col = None
        self.source_col = 'source'

        self.load_models()
        self.symptom_mapping = self._create_symptom_mapping()

    # class PhoBERTFineTuner(nn.Module):
    #     def __init__(self, model_name="vinai/phobert-base", hidden_dim=768):
    #         super().__init__()
    #         self.phobert = AutoModel.from_pretrained(model_name)
    #         self.attention = nn.MultiheadAttention(embed_dim=hidden_dim, num_heads=8, batch_first=True)
    #         self.dropout = nn.Dropout(0.1)
    #         self.projection = nn.Linear(hidden_dim, hidden_dim)

    #     def forward(self, input_ids, attention_mask):
    #         outputs = self.phobert(input_ids=input_ids, attention_mask=attention_mask)
    #         hidden_states = outputs.last_hidden_state
    #         key_padding_mask = (attention_mask == 0)
    #         attention_output, _ = self.attention(
    #             hidden_states, hidden_states, hidden_states,
    #             key_padding_mask=key_padding_mask,
    #             need_weights=False,
    #         )
    #         cls_output = attention_output[:, 0, :]
    #         cls_output = self.dropout(cls_output)
    #         embeddings = self.projection(cls_output)
    #         embeddings = F.normalize(embeddings, p=2, dim=1)
    #         return embeddings

    class PhoBERTFineTuner(nn.Module):
        def __init__(self, model_name="vinai/phobert-base", hidden_dim=768, dropout=0.1):
            super().__init__()
            self.phobert = AutoModel.from_pretrained(model_name)
            self.attention = nn.MultiheadAttention(
                embed_dim=hidden_dim, num_heads=8, batch_first=True
            )
            self.projection = nn.Sequential(
                nn.LayerNorm(hidden_dim),
                nn.Dropout(float(dropout)),
                nn.Linear(hidden_dim, 768),
            )

        @staticmethod
        def _masked_mean_pool(token_embeddings, attention_mask):
            mask = attention_mask.unsqueeze(-1).type_as(token_embeddings)
            return (token_embeddings * mask).sum(1) / mask.sum(1).clamp(min=1e-6)

        def forward(self, input_ids, attention_mask):
            outputs = self.phobert(input_ids=input_ids, attention_mask=attention_mask)
            hidden_states = outputs.last_hidden_state
            key_padding_mask = (attention_mask == 0)
            attention_output, _ = self.attention(
                hidden_states, hidden_states, hidden_states,
                key_padding_mask=key_padding_mask,
                need_weights=False,
            )
            pooled = self._masked_mean_pool(attention_output, attention_mask)
            embeddings = self.projection(pooled)
            return F.normalize(embeddings, p=2, dim=1)

    def _get_drug_category(self, row):
        if self.category_col and self.category_col in row and pd.notna(row[self.category_col]):
            return str(row[self.category_col])
        return 'Khác'

    def _is_unwanted_image_url(self, url):
        u = str(url).lower()
        unwanted_keywords = [
            'logo', 'static-website', 'banner', 'avatar', 'zalo',
            'visa', 'mastercard', 'jcb', 'momo', 'napas', 'apple-pay',
            'dmca', 'bct', 'freeship', 'search-rx', 'near-by-store',
            'nurse', 'cod', 'blue-tick', 'topbanner', 'badg'
        ]
        if any(k in u for k in unwanted_keywords):
            return True
        if u.endswith('.svg'):
            return True
        return False

    def _score_image_url(self, url):
        u = str(url).lower()
        score = 0
        if '/images/ecommerce/' in u or '/images/product/' in u:
            score += 5
        if '/digital/' in u:
            score += 3
        if '_1.' in u or '_1_' in u:
            score += 1
        if self._is_unwanted_image_url(u):
            score -= 10
        return score

    def _extract_image_urls(self, value):
        def normalize_url(raw_url):
            if not raw_url:
                return None

            text = str(raw_url).strip()
            if not text or text.lower() == 'nan':
                return None

            if self._is_unwanted_image_url(text):
                return None

            if text.startswith('http://') or text.startswith('https://'):
                return text

            match = re.search(r'https?://[^\s\"\'\|\],]+', text)
            if match:
                candidate = match.group(0)
                if not self._is_unwanted_image_url(candidate):
                    return candidate

            return None

        if value is None:
            return []

        if isinstance(value, (list, tuple, set)):
            iterable_values = list(value)
        else:
            text = str(value).strip()
            if not text or text.lower() == 'nan':
                return []

            if text.startswith('[') and text.endswith(']'):
                try:
                    import ast
                    parsed = ast.literal_eval(text)
                    if isinstance(parsed, (list, tuple, set)):
                        iterable_values = list(parsed)
                    else:
                        iterable_values = [parsed]
                except Exception:
                    iterable_values = [text]
            else:
                iterable_values = [text]

        candidates = []
        for item in iterable_values:
            text = str(item).strip()
            if not text or text.lower() == 'nan':
                continue

            urls = re.findall(r'https?://[^\s\"\'\|\],]+', text)
            if urls:
                for url in urls:
                    normalized = normalize_url(url)
                    if normalized:
                        candidates.append(normalized)
                continue

            normalized = normalize_url(text)
            if normalized:
                candidates.append(normalized)

        unique_candidates = []
        seen = set()
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                unique_candidates.append(candidate)

        return unique_candidates

    def _extract_image_url(self, value):
        image_urls = self._extract_image_urls(value)
        if not image_urls:
            return None
        return sorted(image_urls, key=self._score_image_url, reverse=True)[0]

    def _get_image_url(self, row):
        if self.image_col and self.image_col in row and pd.notna(row[self.image_col]):
            return self._extract_image_url(row[self.image_col])

        for candidate in ('image_url', 'images', 'image'):
            if candidate in row and pd.notna(row[candidate]):
                image_url = self._extract_image_url(row[candidate])
                if image_url:
                    return image_url

        return None

    def _get_image_urls(self, row):
        image_urls = []

        if self.image_col and self.image_col in row and pd.notna(row[self.image_col]):
            image_urls.extend(self._extract_image_urls(row[self.image_col]))

        for candidate in ('image_url', 'images', 'image'):
            if candidate in row and pd.notna(row[candidate]):
                image_urls.extend(self._extract_image_urls(row[candidate]))

        unique_urls = []
        seen = set()
        for image_url in image_urls:
            if image_url not in seen:
                seen.add(image_url)
                unique_urls.append(image_url)

        ranked_urls = sorted(unique_urls, key=self._score_image_url, reverse=True)
        return ranked_urls[:5]

    def _detect_columns(self):
        columns = set(self.data_final.columns.tolist())
        self.name_col = 'drug_name' if 'drug_name' in columns else 'ten_thuoc'
        self.ingredients_col = 'active_ingredient' if 'active_ingredient' in columns else 'thanh_phan'
        self.indication_col = 'indication' if 'indication' in columns else 'chi_dinh'
        self.contra_col = 'contraindication' if 'contraindication' in columns else 'chong_chi_dinh'
        self.side_effect_col = 'side_effect' if 'side_effect' in columns else 'tac_dung_phu'
        self.usage_col = 'usage' if 'usage' in columns else ('cach_dung' if 'cach_dung' in columns else None)
        self.caution_col = 'caution' if 'caution' in columns else ('luu_y' if 'luu_y' in columns else None)
        self.packing_col = 'packing' if 'packing' in columns else ('quy_cach_dong_goi' if 'quy_cach_dong_goi' in columns else None)
        self.dosage_form_col = 'dosage_form' if 'dosage_form' in columns else ('dang_bao_che' if 'dang_bao_che' in columns else None)
        self.manufacturer_col = 'manufacturer' if 'manufacturer' in columns else ('nha_san_xuat' if 'nha_san_xuat' in columns else None)
        self.price_col = 'price' if 'price' in columns else None
        self.image_col = 'image_url' if 'image_url' in columns else (
            'images' if 'images' in columns else (
                'image' if 'image' in columns else None
            )
        )
        self.category_col = 'category_grouped_model' if 'category_grouped_model' in columns else (
            'category_grouped' if 'category_grouped' in columns else (
                'category' if 'category' in columns else None
            )
        )
        self.source_col = 'source' if 'source' in columns else None

    def _build_search_text(self, row):
        name = str(row.get(self.name_col, '')) if pd.notna(row.get(self.name_col, '')) else ''
        ingredient = str(row.get(self.ingredients_col, '')) if pd.notna(row.get(self.ingredients_col, '')) else ''
        indication = str(row.get(self.indication_col, '')) if pd.notna(row.get(self.indication_col, '')) else ''
        contraindication = str(row.get(self.contra_col, '')) if pd.notna(row.get(self.contra_col, '')) else ''
        return (
            f"Tên thuốc: {name}. "
            f"Hoạt chất: {ingredient}. "
            f"Chỉ định: {indication}. "
            f"Chống chỉ định: {contraindication}"
        ).strip()

    def _deduplicate_dataset_for_serving(self):
        """Loại bỏ bản ghi trùng nhẹ để serving ổn định hơn."""
        if self.data_final is None or len(self.data_final) == 0:
            return

        before = len(self.data_final)
        subset_cols = []
        for col in [self.name_col, self.ingredients_col, self.indication_col]:
            if col in self.data_final.columns:
                subset_cols.append(col)

        if not subset_cols:
            return

        self.data_final = self.data_final.drop_duplicates(subset=subset_cols, keep='first').reset_index(drop=True)
        after = len(self.data_final)

        if after < before:
            print(f"Deduplicated serving dataset: removed {before - after} duplicated rows")

    def _load_phobert_model(self, model_path):
        if not os.path.exists(model_path):
            print(f"PhoBERT checkpoint not found: {model_path}")
            return

        try:
            print(f"Loading PhoBERT checkpoint from: {model_path}")
            self.tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base")
            self.phobert_model = self.PhoBERTFineTuner().to(self.device)

            state_dict = torch.load(model_path, map_location=self.device)
            self.phobert_model.load_state_dict(state_dict, strict=True)
            self.phobert_model.eval()
            print("PhoBERT checkpoint loaded successfully")
        except Exception as e:
            print(f"Failed to load PhoBERT checkpoint: {e}")
            self.phobert_model = None
            self.tokenizer = None

    def _encode_texts(self, texts, batch_size=32, max_length=None):
        if self.phobert_model is None or self.tokenizer is None:
            return None

        if max_length is None:
            max_length = int(self.max_length)

        embeddings = []
        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                encoded = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=max_length,
                    return_tensors='pt'
                )
                encoded = {k: v.to(self.device) for k, v in encoded.items()}
                batch_emb = self.phobert_model(
                    encoded['input_ids'],
                    encoded['attention_mask']
                )
                embeddings.append(batch_emb.cpu())

        return torch.cat(embeddings, dim=0)

    def _build_cache_meta(self, dataset_path, model_path, max_length=None):
        if max_length is None:
            max_length = int(self.max_length)

        dataset_abs = os.path.abspath(dataset_path)
        model_abs = os.path.abspath(model_path)

        return {
            'dataset_path': dataset_abs,
            'dataset_mtime': os.path.getmtime(dataset_abs),
            'dataset_size': os.path.getsize(dataset_abs),
            'model_path': model_abs,
            'model_mtime': os.path.getmtime(model_abs),
            'model_size': os.path.getsize(model_abs),
            'rows': int(len(self.data_final)) if self.data_final is not None else 0,
            'name_col': self.name_col,
            'ingredients_col': self.ingredients_col,
            'indication_col': self.indication_col,
            'max_length': int(max_length),
            'model_arch': 'PhoBERTFineTuner',
            'cache_version': 1,
        }

    def _get_cache_path(self, dataset_path, model_path):
        web_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(web_dir, 'cache')
        os.makedirs(cache_dir, exist_ok=True)

        key = f"{os.path.abspath(dataset_path)}|{os.path.abspath(model_path)}|phobert_finetuner_v1"
        key_hash = hashlib.md5(key.encode('utf-8')).hexdigest()[:16]
        return os.path.join(cache_dir, f"drug_embeddings_{key_hash}.pt")

    def _try_load_embedding_cache(self, cache_path, expected_meta):
        if not os.path.exists(cache_path):
            return False

        try:
            payload = torch.load(cache_path, map_location='cpu')
            cache_meta = payload.get('meta', {})
            cache_embeddings = payload.get('embeddings')

            if cache_embeddings is None:
                return False

            for k, v in expected_meta.items():
                if cache_meta.get(k) != v:
                    return False

            if cache_embeddings.shape[0] != expected_meta['rows']:
                return False

            self.drug_embeddings = cache_embeddings
            print(f"Loaded embeddings cache: {cache_path}")
            print(f"Cached embeddings shape: {tuple(self.drug_embeddings.shape)}")
            return True
        except Exception as e:
            print(f"Failed to load embedding cache ({cache_path}): {e}")
            return False

    def _save_embedding_cache(self, cache_path, meta):
        if self.drug_embeddings is None:
            return

        try:
            torch.save({'meta': meta, 'embeddings': self.drug_embeddings.cpu()}, cache_path)
            print(f"Saved embeddings cache: {cache_path}")
        except Exception as e:
            print(f"Failed to save embedding cache: {e}")

    def _build_drug_embeddings(self, cache_path=None, cache_meta=None):
        if self.data_final is None or self.phobert_model is None:
            return

        try:
            print("Building PhoBERT embeddings for official dataset...")
            texts = [self._build_search_text(row) for _, row in self.data_final.iterrows()]
            self.drug_embeddings = self._encode_texts(texts, batch_size=32, max_length=self.max_length)
            print(f"Built embeddings shape: {tuple(self.drug_embeddings.shape)}")

            if cache_path and cache_meta:
                self._save_embedding_cache(cache_path, cache_meta)
        except Exception as e:
            print(f"Failed to build embeddings: {e}")
            self.drug_embeddings = None
    
    def load_models(self):
        try:
            web_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(web_dir, ".."))

            official_dataset_path = os.getenv(
                "DRUG_DATASET_PATH",
                os.path.join(project_root, "preprocessData_All", "merged_drug_data_mapped(2).csv")
            )
            official_model_path = os.getenv(
                "DRUG_PHOBERT_PATH",
                os.path.join(project_root, "Modeling", "phobert_finetuned(3)_latest.pth")
            )

            print(f"Loading official dataset: {official_dataset_path}")
            if not os.path.exists(official_dataset_path):
                raise FileNotFoundError(f"Official dataset not found: {official_dataset_path}")

            self.data_final = pd.read_csv(official_dataset_path, encoding='utf-8')
            self._detect_columns()
            self._deduplicate_dataset_for_serving()
            print(f"Loaded official dataset: {len(self.data_final)} drugs")

            # Load official PhoBERT checkpoint + precompute embeddings
            self._load_phobert_model(official_model_path)
            if self.phobert_model is not None:
                cache_meta = self._build_cache_meta(official_dataset_path, official_model_path, max_length=self.max_length)
                cache_path = self._get_cache_path(official_dataset_path, official_model_path)

                if not self._try_load_embedding_cache(cache_path, cache_meta):
                    self._build_drug_embeddings(cache_path=cache_path, cache_meta=cache_meta)
                
        except Exception as e:
            print(f"Error loading official dataset/PhoBERT: {e}")
            self.data_final = None
            self.tokenizer = None
            self.phobert_model = None
            self.drug_embeddings = None
        
        # Debug thông tin dataset
        if self.data_final is not None:
            print(f"Dataset info:")
            print(f"- Columns: {self.data_final.columns.tolist()}")
            print(f"- Shape: {self.data_final.shape}")
            print(f"- Name column: {self.name_col}")
            print(f"- Inference max_length: {self.max_length}")

    def _create_symptom_mapping(self):
        return {
            'đau đầu': ['đau đầu', 'nhức đầu', 'migraine', 'đau nửa đầu', 'headache'],
            'sốt': ['sốt', 'fever', 'nóng sốt', 'ốm sốt', 'sốt cao', 'hạ sốt'],
            'ho': ['ho', 'cough', 'ho khan', 'ho có đờm', 'ho kéo dài', 'ho dai dẳng'],
            'đau bụng': ['đau bụng', 'đau dạ dày', 'đau tử tràng', 'quặn bụng', 'stomach'],
            'tiêu chảy': ['tiêu chảy', 'diarrhea', 'đi lỏng', 'phân lỏng', 'tiêu chay'],
            'cảm lạnh': ['cảm lạnh', 'cảm cúm', 'nghẹt mũi', 'flu', 'cúm', 'cold'],
            'đau họng': ['đau họng', 'viêm họng', 'sưng họng', 'khàn tiếng', 'sore throat'],
            'dị ứng': ['dị ứng', 'ngứa', 'mẩn đỏ', 'allergy', 'phát ban', 'allergic'],
            'viêm nhiễm': ['viêm', 'nhiễm trùng', 'infection', 'kháng sinh', 'nhiễm khuẩn'],
            'đau khớp': ['đau khớp', 'viêm khớp', 'đau cơ', 'đau xương', 'arthritis'],
            'buồn nôn': ['buồn nôn', 'nôn mửa', 'nausea', 'ói mửa', 'nôn'],
            'mệt mỏi': ['mệt mỏi', 'mệt', 'fatigue', 'kiệt sức', 'yếu'],
            'chóng mặt': ['chóng mặt', 'hoa mắt', 'dizzy', 'dizziness', 'đầu quay'],
            'táo bón': ['táo bón', 'khó đi tiêu', 'constipation', 'táo bon'],
            'viêm da': ['viêm da', 'eczema', 'dermatitis', 'da viêm', 'da bị viêm']
        }
    
    def search_by_symptoms(self, symptoms, limit=15):
        """Tìm thuốc theo triệu chứng chỉ bằng semantic retrieval PhoBERT."""
        if self.data_final is None:
            return {'drugs': [], 'detected_symptoms': [], 'total_found': 0}

        if self.phobert_model is None or self.drug_embeddings is None:
            print("PhoBERT model/embeddings unavailable, cannot run semantic search")
            symptoms_clean = symptoms.lower().strip()
            detected_symptoms = []
            for symptom, keywords in self.symptom_mapping.items():
                if any(keyword in symptoms_clean for keyword in keywords):
                    detected_symptoms.append({
                        'name': symptom,
                        'category': self._get_symptom_category(symptom)
                    })

            return {
                'drugs': [],
                'detected_symptoms': detected_symptoms,
                'total_found': 0,
                'ml_prediction': {
                    'predicted_class': None,
                    'confidence': None,
                    'method': 'PhoBERT-unavailable'
                }
            }

        return self._search_by_symptoms_phobert(symptoms, limit=limit)

    def _search_by_symptoms_phobert(self, symptoms, limit=15):
        symptoms_clean = symptoms.lower().strip()

        detected_symptoms = []
        for symptom, keywords in self.symptom_mapping.items():
            if any(keyword in symptoms_clean for keyword in keywords):
                detected_symptoms.append({
                    'name': symptom,
                    'category': self._get_symptom_category(symptom)
                })

        ml_prediction = {'predicted_class': None, 'confidence': None, 'method': 'PhoBERT-semantic'}

        query_text = symptoms.strip()
        query_emb = self._encode_texts([query_text], batch_size=1, max_length=self.max_length)
        if query_emb is None:
            return {'drugs': [], 'detected_symptoms': detected_symptoms, 'total_found': 0}

        # cosine similarity vì embeddings đã normalize
        sims = torch.matmul(self.drug_embeddings, query_emb[0].unsqueeze(1)).squeeze(1).numpy()
        top_k = min(max(limit * 3, 20), len(sims))
        top_indices = np.argpartition(-sims, top_k - 1)[:top_k]
        top_indices = top_indices[np.argsort(-sims[top_indices])]

        matches = []
        for idx in top_indices:
            score = float(sims[idx])
            row = self.data_final.iloc[idx]
            drug_info = self._get_drug_info(idx, row)
            drug_info['score'] = round(score, 4)
            drug_info['matched_symptoms'] = [s['name'] for s in detected_symptoms[:3]]
            drug_info['confidence_level'] = 'Cao' if score >= 0.65 else ('Trung bình' if score >= 0.45 else 'Thấp')
            matches.append(drug_info)

        if matches:
            ml_prediction['predicted_class'] = matches[0].get('drug_class')
            ml_prediction['confidence'] = matches[0].get('score')

        return {
            'drugs': matches[:limit],
            'detected_symptoms': detected_symptoms,
            'total_found': len(matches),
            'ml_prediction': ml_prediction
        }
    
    def _get_symptom_category(self, symptom):
        categories = {
            'đau đầu': 'Thần kinh',
            'chóng mặt': 'Thần kinh',
            'mệt mỏi': 'Tổng quát',
            'sốt': 'Tổng quát',
            'ho': 'Hô hấp',
            'cảm lạnh': 'Hô hấp',
            'đau họng': 'Hô hấp',
            'đau bụng': 'Tiêu hóa',
            'tiêu chảy': 'Tiêu hóa',
            'buồn nôn': 'Tiêu hóa',
            'táo bón': 'Tiêu hóa',
            'dị ứng': 'Da liễu',
            'viêm da': 'Da liễu',
            'đau khớp': 'Cơ xương khớp',
            'viêm nhiễm': 'Nhiễm khuẩn'
        }
        return categories.get(symptom, 'Tổng quát')
    
    def _get_drug_category(self, row):
        if self.category_col and self.category_col in row and pd.notna(row[self.category_col]):
            return str(row[self.category_col])
        return 'Khác'

    def _extract_image_url(self, value):
        def is_unwanted_url(url):
            u = str(url).lower()
            unwanted_keywords = [
                'logo', 'static-website', 'banner', 'avatar', 'zalo',
                'visa', 'mastercard', 'jcb', 'momo', 'napas', 'apple-pay',
                'dmca', 'bct', 'freeship', 'search-rx', 'near-by-store',
                'nurse', 'cod', 'blue-tick', 'topbanner', 'badg'
            ]
            if any(k in u for k in unwanted_keywords):
                return True
            if u.endswith('.svg'):
                return True
            return False

        def score_url(url):
            u = str(url).lower()
            score = 0

            if '/images/ecommerce/' in u or '/images/product/' in u:
                score += 5
            if '/digital/' in u:
                score += 3
            if '_1.' in u or '_1_' in u:
                score += 1

            if is_unwanted_url(u):
                score -= 10

            return score

        def choose_best(candidates):
            if not candidates:
                return None
            unique_candidates = []
            seen = set()
            for c in candidates:
                if c and c not in seen:
                    seen.add(c)
                    unique_candidates.append(c)

            if not unique_candidates:
                return None

            # Ưu tiên ảnh có điểm cao nhất
            ranked = sorted(unique_candidates, key=score_url, reverse=True)
            best = ranked[0]

            # Nếu toàn bộ đều kém, vẫn tránh URL rõ ràng là logo nếu có thể
            if is_unwanted_url(best):
                for c in ranked:
                    if not is_unwanted_url(c):
                        return c
            return best

        if value is None:
            return None

        if isinstance(value, (list, tuple)):
            candidates = []
            for item in value:
                image_url = self._extract_image_url(item)
                if image_url:
                    candidates.append(image_url)
            return choose_best(candidates)

        text = str(value).strip()
        if not text or text.lower() == 'nan':
            return None

        if text.startswith('[') and text.endswith(']'):
            try:
                import ast
                parsed = ast.literal_eval(text)
                if isinstance(parsed, (list, tuple)):
                    candidates = []
                    for item in parsed:
                        image_url = self._extract_image_url(item)
                        if image_url:
                            candidates.append(image_url)
                    return choose_best(candidates)
            except Exception:
                pass

        urls = re.findall(r'https?://[^\s\"\'\|\],]+', text)
        if urls:
            return choose_best(urls)

        if text.startswith('http://') or text.startswith('https://'):
            return text

        return None

    def _get_image_url(self, row):
        if self.image_col and self.image_col in row and pd.notna(row[self.image_col]):
            return self._extract_image_url(row[self.image_col])

        for candidate in ('image_url', 'images', 'image'):
            if candidate in row and pd.notna(row[candidate]):
                image_url = self._extract_image_url(row[candidate])
                if image_url:
                    return image_url

        return None

    def _get_image_urls(self, row):
        image_urls = []

        if self.image_col and self.image_col in row and pd.notna(row[self.image_col]):
            image_urls.extend(self._extract_image_urls(row[self.image_col]))

        for candidate in ('image_url', 'images', 'image'):
            if candidate in row and pd.notna(row[candidate]):
                image_urls.extend(self._extract_image_urls(row[candidate]))

        unique_urls = []
        seen = set()
        for image_url in image_urls:
            if image_url not in seen:
                seen.add(image_url)
                unique_urls.append(image_url)

        ranked_urls = sorted(unique_urls, key=self._score_image_url, reverse=True)
        return ranked_urls[:5]
    
    def _get_drug_info(self, idx, row):
        drug_name = str(row[self.name_col]) if pd.notna(row[self.name_col]) else f"Thuốc {idx}"
        
        if ':' in drug_name:
            name_parts = drug_name.split(':', 1)
            main_name = name_parts[0].strip()
            description = name_parts[1].strip() if len(name_parts) > 1 else ""
        else:
            main_name = drug_name
            description = ""
        
        ingredients = str(row[self.ingredients_col]) if self.ingredients_col in row and pd.notna(row[self.ingredients_col]) else 'Không có thông tin'
        indications = str(row[self.indication_col]) if self.indication_col in row and pd.notna(row[self.indication_col]) else 'Không có thông tin'
        contraindications = str(row[self.contra_col]) if self.contra_col in row and pd.notna(row[self.contra_col]) else 'Không có thông tin'
        side_effects = str(row[self.side_effect_col]) if self.side_effect_col in row and pd.notna(row[self.side_effect_col]) else 'Không có thông tin'
        usage = str(row[self.usage_col]) if self.usage_col and self.usage_col in row and pd.notna(row[self.usage_col]) else 'Không có thông tin'
        caution = str(row[self.caution_col]) if self.caution_col and self.caution_col in row and pd.notna(row[self.caution_col]) else 'Không có thông tin'
        packing = str(row[self.packing_col]) if self.packing_col and self.packing_col in row and pd.notna(row[self.packing_col]) else 'Không có thông tin'
        dosage_form = str(row[self.dosage_form_col]) if self.dosage_form_col and self.dosage_form_col in row and pd.notna(row[self.dosage_form_col]) else 'Không có thông tin'
        manufacturer = str(row[self.manufacturer_col]) if self.manufacturer_col and self.manufacturer_col in row and pd.notna(row[self.manufacturer_col]) else 'Xem trên bao bì'
        price = row[self.price_col] if self.price_col and self.price_col in row and pd.notna(row[self.price_col]) else None
        source = str(row[self.source_col]) if self.source_col and self.source_col in row and pd.notna(row[self.source_col]) else 'Không rõ nguồn'

        if price is None:
            price_text = 'Liên hệ để biết giá'
        else:
            try:
                price_text = f"{float(price):,.0f}đ".replace(',', '.')
            except Exception:
                price_text = str(price)
        
        # Parse to lists
        indication_list = self._parse_to_list(indications)
        ingredients_list = self._parse_to_list(ingredients)
        contraindication_list = self._parse_to_list(contraindications)
        side_effects_list = self._parse_to_list(side_effects)
        usage_list = self._parse_to_list(usage)
        caution_list = self._parse_to_list(caution)
        
        return {
            'index': int(idx),
            'name': main_name,
            'description': description,
            'drug_class': self._get_drug_category(row),
            'image_url': self._get_image_url(row),
            'image_urls': self._get_image_urls(row),
            'price': price_text,
            'manufacturer': manufacturer,
            'source': source,
            'prescription_required': self._requires_prescription(drug_name),
            
            # Detailed information
            'indication': indications,
            'ingredients': ingredients,
            'contraindication': contraindications,
            'side_effects': side_effects,
            'usage': usage,
            'caution': caution,
            'packing': packing,
            'dosage_form': dosage_form,
            
            # Lists for display
            'indication_list': indication_list,
            'ingredients_list': ingredients_list,
            'dosage_list': ['Theo chỉ định của bác sĩ', 'Đọc kỹ hướng dẫn sử dụng'],
            'contraindication_list': contraindication_list,
            'side_effects_list': side_effects_list,
            'usage_list': usage_list,
            'caution_list': caution_list,
            
            # For search results
            'matched_symptoms': []
        }
    
    def _parse_to_list(self, text):
        """Parse text thành list"""
        if not text or text == 'Không có thông tin':
            return ['Không có thông tin']
        
        items = re.split(r'[.;,\n]', text)
        items = [item.strip() for item in items if item.strip()]
        
        seen = set()
        result = []
        for item in items:
            if item and item not in seen and len(item) > 3:
                seen.add(item)
                result.append(item)
        
        return result if result else [text]
    
    def _requires_prescription(self, drug_name):
        """Check if drug requires prescription"""
        prescription_drugs = [
            'antibiotic', 'kháng sinh', 'corticosteroid', 'insulin',
            'morphine', 'tramadol', 'antidepressant', 'anti'
        ]
        
        drug_lower = str(drug_name).lower()
        return any(drug in drug_lower for drug in prescription_drugs)
    
    def get_enhanced_drug_info(self, idx):
        """Lấy chi tiết thuốc"""
        if self.data_final is None or idx >= len(self.data_final):
            return {'error': 'Không tìm thấy thuốc'}
        
        row = self.data_final.iloc[idx]
        return self._get_drug_info(idx, row)
    
    
    def get_dataset_stats(self):
        """Thống kê dataset"""
        if self.data_final is None:
            return {}
        
        return {
            'total_drugs': len(self.data_final),
            'sources': self.data_final[self.source_col].value_counts().to_dict() if self.source_col and self.source_col in self.data_final.columns else {},
            'columns': self.data_final.columns.tolist(),
            'sample_drugs': self.data_final[self.name_col].head(10).tolist(),
            'model_loaded': (self.phobert_model is not None) and (self.drug_embeddings is not None)
        }

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def _allowed_image_file(filename):
    ext = os.path.splitext(str(filename or ''))[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


def to_json_safe(obj):
    """Chuyển đổi kiểu numpy/pandas sang kiểu JSON-native."""
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_json_safe(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [to_json_safe(v) for v in obj.tolist()]

    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass

    return obj



def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Vui lòng đăng nhập để truy cập.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Bạn không có quyền truy cập.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# Khởi tạo DB 
init_database()

# Khởi tạo engine
print("Initializing Drug Recommendation Engine...")
engine = EnhancedDrugRecommendationEngine()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Vui lòng nhập đầy đủ thông tin', 'error')
            return render_template('login.html')
        
        user = verify_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session.permanent = True
            
            flash(f'Chào mừng {user["full_name"]}!', 'success')
            
            # Redirect dựa trên role
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không đúng', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        full_name = request.form.get('full_name', '').strip()
        
        # Validation đơn giản
        if not all([username, password, confirm_password, full_name]):
            flash('Vui lòng điền đầy đủ thông tin', 'error')
            return render_template('register.html')
        
        if len(username) < 3:
            flash('Tên đăng nhập phải có ít nhất 3 ký tự', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Mật khẩu phải có ít nhất 6 ký tự', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp', 'error')
            return render_template('register.html')
        
        try:
            user_id = create_user(username, password, full_name)
            flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
            return redirect(url_for('login'))
        except ValueError as e:
            flash(str(e), 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Đã đăng xuất thành công', 'info')
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    stats = get_stats()
    # Thêm số lượng thuốc có danh mục không hợp lệ
    stats['invalid_drugs_count'] = _get_invalid_drugs_count()
    return render_template('admin/admin_index.html', 
                         user=session, 
                         stats=stats)


@app.route('/')
def index():
      # Lấy thông tin user từ session
    user = None
    if 'user_id' in session:
        user = {
            'user_id': session['user_id'],
            'username': session['username'],
            'full_name': session['full_name'],
            'role': session['role']
        }

    home_stats = engine.get_dataset_stats()
    total_drugs = int(home_stats.get('total_drugs', 0))
    source_count = len(home_stats.get('sources', {}) or {})
    home_stats_display = {
        'total_drugs': total_drugs,
        'total_drugs_text': f"{total_drugs:,}".replace(',', '.'),
        'source_count': source_count,
        'source_count_text': f"{source_count}",
    }
    
    return render_template('index.html', user=user, home_stats=home_stats_display)



@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        symptoms = data.get('symptoms', '')
        
        print(f"Received search request: {symptoms}")
        
        if not symptoms:
            return jsonify({'error': 'Vui lòng nhập triệu chứng'})
        
        results = engine.search_by_symptoms(symptoms, limit=15)
        
        if 'user_id' in session:
            user_agent = request.headers.get('User-Agent', '')
            
            log_search_enhanced(
                session['user_id'], 
                symptoms, 
                len(results['drugs']),
                user_agent
            )

        print(f"Search results: {len(results.get('drugs', []))} drugs found")
        
        payload = {
            'success': True,
            'symptoms': symptoms,
            'results': results,
            'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        return jsonify(to_json_safe(payload))
        
    except Exception as e:
        print(f"Search error: {str(e)}")
        return jsonify({'error': f'Lỗi tìm kiếm: {str(e)}'})


@app.route('/search_history')
@login_required
def search_history_page():
    try:
        user_id = session['user_id']
        history = get_search_history(user_id, limit=50)
        # Lấy thống kê đơn giản
        stats = get_search_statistics(user_id)
        
        user = {
            'user_id': session['user_id'],
            'username': session['username'],
            'full_name': session['full_name'],
            'role': session['role']
        }
        
        return render_template('search_history.html', 
                             history=history, 
                             stats=stats,
                             user=user)
                             
    except Exception as e:
        flash(f'Lỗi tải lịch sử: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/clear_history', methods=['POST'])
@login_required
def clear_history():
    """Xóa lịch sử phân tích"""
    try:
        user_id = session['user_id']
        deleted_count = clear_search_history(user_id)
        
        return jsonify({
            'success': True, 
            'message': f'Đã xóa {deleted_count} lịch sử phân tích'
        })
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Lỗi xóa lịch sử: {str(e)}'
        })

@app.route('/track_click', methods=['POST'])
@login_required
def track_click():
    """Track khi user click vào thuốc"""
    try:
        data = request.get_json()
        drug_index = data.get('drug_index')
        drug_name = data.get('drug_name')
        user_id = session['user_id']
        
        track_drug_click(user_id, drug_index, drug_name)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/repeat_search/<int:history_id>')
@login_required
def repeat_search(history_id):
    """Lặp lại tìm kiếm từ lịch sử"""
    try:
        user_id = session['user_id']
        conn = get_db()
        history_item = conn.execute('''
            SELECT symptoms FROM search_logs 
            WHERE id = ? AND user_id = ?
        ''', (history_id, user_id)).fetchone()
        conn.close()
        
        if history_item:
            return redirect(url_for('index', symptoms=history_item['symptoms']))
        else:
            flash('Không tìm thấy lịch sử phân tích', 'error')
            return redirect(url_for('search_history_page'))
            
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'error')
        return redirect(url_for('search_history_page'))

@app.route('/drug/<int:drug_id>')
def drug_detail(drug_id):
    try:
        drug_info = engine.get_enhanced_drug_info(drug_id)
        if drug_info:
            return jsonify(drug_info)
        else:
            return jsonify({'error': 'Không tìm thấy thông tin thuốc'})
    except Exception as e:
        print(f"Error in drug_detail: {e}")
        return jsonify({'error': f'Lỗi tải thông tin: {str(e)}'})


@app.route('/admin/drug/<int:drug_id>')
@admin_required
def admin_manual_drug_detail(drug_id):
    try:
        conn = get_db()
        drug = conn.execute('''
            SELECT id, drug_name, drug_class, ingredients, indication,
                   dosage_form, packing, usage, caution,
                   contraindication, side_effects, manufacturer, price, image_urls, created_at
            FROM drugs_master
            WHERE id = ?
        ''', (drug_id,)).fetchone()
        conn.close()

        if not drug:
            return jsonify({'error': 'Không tìm thấy thuốc thủ công'})

        drug_name = str(drug['drug_name']) if drug['drug_name'] else f'Thuốc {drug_id}'
        description = ''
        if ':' in drug_name:
            name_parts = drug_name.split(':', 1)
            drug_name = name_parts[0].strip()
            description = name_parts[1].strip() if len(name_parts) > 1 else ''

        ingredients = str(drug['ingredients']) if drug['ingredients'] else 'Không có thông tin'
        indications = str(drug['indication']) if drug['indication'] else 'Không có thông tin'
        drug_class = str(drug['drug_class']) if drug['drug_class'] else 'Chưa phân loại'
        dosage_form = str(drug['dosage_form']) if drug['dosage_form'] else 'Không có thông tin'
        packing = str(drug['packing']) if drug['packing'] else 'Không có thông tin'
        usage = str(drug['usage']) if drug['usage'] else 'Không có thông tin'
        caution = str(drug['caution']) if drug['caution'] else 'Không có thông tin'
        contraindication = str(drug['contraindication']) if drug['contraindication'] else 'Không có thông tin'
        side_effects = str(drug['side_effects']) if drug['side_effects'] else 'Không có thông tin'
        manufacturer = str(drug['manufacturer']) if drug['manufacturer'] else 'Thêm thủ công'
        price_value = drug['price']
        if price_value is None or str(price_value).strip() == '':
            price_text = 'Liên hệ để biết giá'
        else:
            try:
                price_text = f"{float(price_value):,.0f}đ".replace(',', '.')
            except Exception:
                price_text = str(price_value)

        image_urls = []
        raw_image_urls = drug['image_urls']
        if raw_image_urls:
            try:
                parsed_urls = json.loads(raw_image_urls)
                if isinstance(parsed_urls, list):
                    image_urls = [str(url).strip() for url in parsed_urls if str(url).strip()][:5]
            except Exception:
                image_urls = []

        return jsonify({
            'index': int(drug['id']),
            'name': drug_name,
            'description': description,
            'drug_class': drug_class,
            'image_url': image_urls[0] if image_urls else None,
            'image_urls': image_urls,
            'price': price_text,
            'manufacturer': manufacturer,
            'source': 'Thủ công',
            'prescription_required': False,
            'indication': indications,
            'ingredients': ingredients,
            'contraindication': contraindication,
            'side_effects': side_effects,
            'usage': usage,
            'caution': caution,
            'packing': packing,
            'dosage_form': dosage_form,
            'indication_list': engine._parse_to_list(indications),
            'ingredients_list': engine._parse_to_list(ingredients),
            'dosage_list': ['Theo chỉ định của bác sĩ', 'Đọc kỹ hướng dẫn sử dụng'],
            'contraindication_list': engine._parse_to_list(contraindication),
            'side_effects_list': engine._parse_to_list(side_effects),
            'usage_list': engine._parse_to_list(usage),
            'caution_list': engine._parse_to_list(caution),
            'matched_symptoms': []
        })
    except Exception as e:
        print(f"Error in admin_manual_drug_detail: {e}")
        return jsonify({'error': f'Lỗi tải thông tin thuốc thủ công: {str(e)}'})
    

@app.route('/debug')
def debug():
    stats = engine.get_dataset_stats()
    return jsonify(stats)

def _get_valid_categories():
    """Helper: Lấy danh sách categories hợp lệ từ dataset + master"""
    categories = set()
    
    # Từ dataset
    if engine.data_final is not None and engine.category_col and engine.category_col in engine.data_final.columns:
        dataset_cats = engine.data_final[engine.category_col].dropna().unique()
        for cat in dataset_cats:
            if pd.notna(cat) and str(cat).strip() and str(cat).strip().lower() != 'nan':
                categories.add(str(cat).strip())
    
    # Từ drugs_master
    try:
        conn = get_db()
        master_cats = conn.execute('SELECT DISTINCT drug_class FROM drugs_master WHERE drug_class IS NOT NULL AND drug_class != ""').fetchall()
        for row in master_cats:
            if row['drug_class'] and str(row['drug_class']).strip():
                categories.add(str(row['drug_class']).strip())
        conn.close()
    except:
        pass
    
    return sorted(list(categories))


def _get_dataset_categories():
    """Helper: Lấy danh sách categories chỉ từ dataset chính thức"""
    categories = set()

    if engine.data_final is not None and engine.category_col and engine.category_col in engine.data_final.columns:
        dataset_cats = engine.data_final[engine.category_col].dropna().unique()
        for cat in dataset_cats:
            if pd.notna(cat):
                category_text = str(cat).strip()
                if category_text and category_text.lower() != 'nan':
                    categories.add(category_text)

    return sorted(list(categories))

def _get_invalid_drugs_count():
    """Helper: Lấy số lượng thuốc có danh mục không hợp lệ"""
    try:
        valid_categories = _get_valid_categories()
        conn = get_db()
        all_drugs = conn.execute('SELECT drug_class FROM drugs_master').fetchall()
        conn.close()
        
        invalid_count = 0
        for drug in all_drugs:
            drug_class = drug['drug_class'] or ''
            if drug_class and drug_class not in valid_categories:
                invalid_count += 1
        
        return invalid_count
    except:
        return 0


@app.route('/get_categories')
def get_categories():
    """Lấy danh sách categories hợp lệ từ dataset + master"""
    try:
        categories_list = _get_valid_categories()
        return jsonify({'categories': categories_list, 'success': True})
    except Exception as e:
        return jsonify({'categories': [], 'success': False, 'error': str(e)})

@app.route('/save_drug', methods=['POST'])
@login_required
def save_drug_route():
    """Lưu thuốc vào danh sách"""
    try:
        data = request.get_json()
        drug_index = data.get('drug_index')
        drug_name = data.get('drug_name', '')
        drug_class = data.get('drug_class', '')
        symptoms = data.get('symptoms', '')
        score = data.get('score', 0)
        notes = data.get('notes', '')
        
        user_id = session['user_id']
        
        # Kiểm tra đã lưu chưa
        if is_drug_saved(user_id, drug_index):
            return jsonify({'success': False, 'message': 'Thuốc đã có trong danh sách!'})
        
        save_drug(user_id, drug_index, drug_name, drug_class, symptoms, score, notes)
        
        return jsonify({'success': True, 'message': 'Đã lưu thuốc vào danh sách!'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Lỗi lưu thuốc: {str(e)}'})

@app.route('/remove_saved_drug', methods=['POST'])
@login_required
def remove_saved_drug_route():
    """Xóa thuốc khỏi danh sách đã lưu"""
    try:
        data = request.get_json()
        drug_index = data.get('drug_index')
        user_id = session['user_id']
        
        if remove_saved_drug(user_id, drug_index):
            return jsonify({'success': True, 'message': 'Đã xóa thuốc khỏi danh sách!'})
        else:
            return jsonify({'success': False, 'message': 'Không tìm thấy thuốc để xóa!'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Lỗi xóa thuốc: {str(e)}'})

@app.route('/check_saved_drug/<int:drug_index>')
@login_required
def check_saved_drug(drug_index):
    """Kiểm tra thuốc đã được lưu chưa"""
    try:
        user_id = session['user_id']
        is_saved = is_drug_saved(user_id, drug_index)
        return jsonify({'is_saved': is_saved})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/saved_drugs')
@login_required
def saved_drugs_page():
    """Trang danh sách thuốc đã lưu"""
    try:
        user_id = session['user_id']
        print(f"Loading saved drugs for user_id: {user_id}")  # Debug log
        
        saved_drugs = get_saved_drugs(user_id)
        print(f"Found {len(saved_drugs)} saved drugs")  # Debug log
        
        # Lấy thông tin chi tiết cho từng thuốc
        for drug in saved_drugs:
            print(f"Processing drug: {drug}")  # Debug log
            try:
                detailed_info = engine.get_enhanced_drug_info(drug['drug_index'])
                if 'error' not in detailed_info:
                    drug.update(detailed_info)
                    print(f"Updated drug info successfully")  # Debug log
                else:
                    print(f"Error getting drug info: {detailed_info}")  # Debug log
            except Exception as e:
                print(f"Exception getting drug info: {e}")  # Debug log
                pass  # Giữ thông tin cơ bản nếu không lấy được chi tiết
        
        # Filters for saved list
        saved_search = request.args.get('search', '')
        saved_category = request.args.get('category', '')

        # Lọc saved_drugs theo search / category nếu có
        if saved_search:
            saved_drugs = [d for d in saved_drugs if saved_search.lower() in (str(d.get('drug_name','')).lower() or '')]

        if saved_category:
            saved_drugs = [d for d in saved_drugs if saved_category.lower() in (str(d.get('drug_class','')).lower() or '')]

        # Build categories for saved list filter
        saved_categories = sorted(list({str(d.get('drug_class','')).strip() for d in get_saved_drugs(user_id) if d.get('drug_class')}))

        user = {
            'user_id': session['user_id'],
            'username': session['username'],
            'full_name': session['full_name'],
            'role': session['role']
        }
        
        print(f"Rendering template with {len(saved_drugs)} drugs")  # Debug log
        return render_template('saved_drugs.html', 
                             saved_drugs=saved_drugs, 
                             user=user,
                             saved_categories=saved_categories,
                             selected_saved_category=saved_category,
                             saved_search=saved_search)
                             
    except Exception as e:
        print(f"Error in saved_drugs_page: {e}")  # Debug log
        flash(f'Lỗi tải danh sách thuốc: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    print(f"DEBUG: profile called")  # Debug log
    print(f"DEBUG: session = {session}")
    """Trang profile người dùng"""
    try:
        user_id = session['user_id']
        profile = get_user_profile(user_id)
        
        if not profile:
            flash('Không tìm thấy thông tin người dùng', 'error')
            return redirect(url_for('index'))
        
        user = {
            'user_id': session['user_id'],
            'username': session['username'],
            'full_name': session['full_name'],
            'role': session['role']
        }
        
        print(f"DEBUG: Rendering profile template with data: {profile}")
        return render_template('profile.html', profile=profile, user=user)
        
    except Exception as e:
        print(f"DEBUG: Error in profile: {e}")
        flash(f'Lỗi tải profile: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    """Cập nhật thông tin profile"""
    try:
        user_id = session['user_id']
        full_name = request.form.get('full_name', '').strip()
        
        # Validation
        if not full_name:
            flash('Họ và tên không được để trống', 'error')
            return redirect(url_for('profile'))
        
        if len(full_name) < 2:
            flash('Họ và tên phải có ít nhất 2 ký tự', 'error')
            return redirect(url_for('profile'))
        
        # Update profile
        if update_user_profile(user_id, full_name):
            # Update session
            session['full_name'] = full_name
            flash('Cập nhật thông tin thành công!', 'success')
        else:
            flash('Cập nhật thông tin thất bại', 'error')
        
        return redirect(url_for('profile'))
        
    except Exception as e:
        flash(f'Lỗi cập nhật: {str(e)}', 'error')
        return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password_route():
    """Đổi mật khẩu"""
    try:
        user_id = session['user_id']
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not current_password:
            flash('Vui lòng nhập mật khẩu hiện tại', 'error')
            return redirect(url_for('profile'))
        
        if not new_password:
            flash('Vui lòng nhập mật khẩu mới', 'error')
            return redirect(url_for('profile'))
        
        if len(new_password) < 6:
            flash('Mật khẩu mới phải có ít nhất 6 ký tự', 'error')
            return redirect(url_for('profile'))
        
        if new_password != confirm_password:
            flash('Mật khẩu xác nhận không khớp', 'error')
            return redirect(url_for('profile'))
        
        # Change password
        if change_password(user_id, current_password, new_password):
            flash('Đổi mật khẩu thành công!', 'success')
            print(f"DEBUG: Changed password for user {user_id}")
        else:
            flash('Đổi mật khẩu thất bại', 'error')
        
        return redirect(url_for('profile'))
        
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('profile'))
    except Exception as e:
        print(f"DEBUG: Error in change_password: {e}")
        flash(f'Lỗi đổi mật khẩu: {str(e)}', 'error')
        return redirect(url_for('profile'))


@app.route('/drugs')
def all_drugs():
    try:
        drugs = []
        categories = []
        search = request.args.get('search', '')
        # Basic filters
        category = request.args.get('category', '')
        manufacturer = request.args.get('manufacturer', '')
        dosage_form = request.args.get('dosage_form', '')
        min_price = request.args.get('min_price', '')
        max_price = request.args.get('max_price', '')
        
        if engine.data_final is not None:
            df = engine.data_final
            page = int(request.args.get('page', 1))
            per_page = 50
            name_col = engine.name_col
            indication_col = engine.indication_col
            ingredients_col = engine.ingredients_col
            contra_col = engine.contra_col
            side_effect_col = engine.side_effect_col
            
            # Lọc theo tìm kiếm
            if search:
                mask = df[name_col].astype(str).str.contains(search, case=False, na=False) | \
                       df[indication_col].astype(str).str.contains(search, case=False, na=False)
                filtered_df = df[mask]
            else:
                filtered_df = df
            # Áp dụng các bộ lọc cơ bản
            if category:
                if engine.category_col and engine.category_col in df.columns:
                    filtered_df = filtered_df[
                        filtered_df[engine.category_col].astype(str).str.strip().str.lower() == category.strip().lower()
                    ]

            if manufacturer:
                if engine.manufacturer_col and engine.manufacturer_col in df.columns:
                    filtered_df = filtered_df[filtered_df[engine.manufacturer_col].astype(str).str.contains(manufacturer, case=False, na=False)]

            if dosage_form:
                if engine.dosage_form_col and engine.dosage_form_col in df.columns:
                    filtered_df = filtered_df[filtered_df[engine.dosage_form_col].astype(str).str.contains(dosage_form, case=False, na=False)]

            try:
                if min_price:
                    minp = float(re.sub(r'[^0-9\.]', '', min_price))
                    if engine.price_col and engine.price_col in df.columns:
                        filtered_df = filtered_df[pd.to_numeric(filtered_df[engine.price_col], errors='coerce') >= minp]

                if max_price:
                    maxp = float(re.sub(r'[^0-9\.]', '', max_price))
                    if engine.price_col and engine.price_col in df.columns:
                        filtered_df = filtered_df[pd.to_numeric(filtered_df[engine.price_col], errors='coerce') <= maxp]
            except Exception:
                pass

            # Build list of available categories for the filter UI
            categories = _get_dataset_categories()

            # Phân trang
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paged_df = filtered_df.iloc[start_idx:end_idx]

            for idx, row in paged_df.iterrows():
                drug_name = str(row[name_col]) if pd.notna(row[name_col]) else f"Thuốc {idx}"
                
                drug_info = {
                    'index': idx,  # Sử dụng index gốc từ DataFrame
                    'drug_name': drug_name,
                    'image_url': engine._get_image_url(row),
                    'drug_class': str(row[engine.category_col]) if engine.category_col and engine.category_col in row and pd.notna(row[engine.category_col]) else 'Khác',
                    'indication': str(row[indication_col]) if indication_col in row and pd.notna(row[indication_col]) else 'Không có thông tin',
                    'ingredients': str(row[ingredients_col]) if ingredients_col in row and pd.notna(row[ingredients_col]) else 'Không có thông tin',
                    'contraindication': str(row[contra_col]) if contra_col in row and pd.notna(row[contra_col]) else 'Không có thông tin',
                    'side_effects': str(row[side_effect_col]) if side_effect_col in row and pd.notna(row[side_effect_col]) else 'Không có thông tin',
                    'score': 0,
                    'confidence': 'medium',
                    'matched_symptoms': []
                }
                
                drugs.append(drug_info)
            
            # Thông tin phân trang (giữ nguyên)
            total_drugs = len(filtered_df)
            total_pages = (total_drugs + per_page - 1) // per_page if total_drugs > 0 else 1
            
            pagination_info = {
                'page': page,
                'per_page': per_page,
                'total': total_drugs,
                'total_pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'prev_num': page - 1 if page > 1 else None,
                'next_num': page + 1 if page < total_pages else None
            }
        else:
            pagination_info = {
                'page': 1, 'per_page': 50, 'total': 0, 'total_pages': 0,
                'has_prev': False, 'has_next': False, 'prev_num': None, 'next_num': None
            }
        
        # Lấy thông tin user
        user = None
        if 'user_id' in session:
            user = {
                'user_id': session['user_id'],
                'username': session['username'],
                'full_name': session['full_name'],
                'role': session['role']
            }
        
        return render_template('drugs_list.html', 
                     drugs=drugs,
                     search=search,
                     pagination=pagination_info,
                     user=user,
                     categories=categories,
                     selected_category=category,
                     selected_manufacturer=manufacturer,
                     selected_dosage_form=dosage_form,
                     selected_min_price=min_price,
                     selected_max_price=max_price)
                             
    except Exception as e:
        print(f"Error in all_drugs: {e}")
        flash(f'Lỗi tải danh sách thuốc: {str(e)}', 'error')
        return redirect(url_for('index'))



# =========================== ADMIN =================================
@app.route('/admin/drugs')
@admin_required
def admin_drugs():
    try:
        search = request.args.get('search', '')
        page = int(request.args.get('page', 1))
        per_page = 20  # Số thuốc mỗi trang

        # additional admin filters
        selected_category = request.args.get('category', '')
        selected_source = request.args.get('source', '')
        selected_manufacturer = request.args.get('manufacturer', '')

        # Lấy tất cả thuốc (dataset + manual)
        all_drugs = get_all_drugs(search if search else None, 'both')

        # Build filter lists for UI
        categories = _get_dataset_categories()
        sources = ['dataset', 'manual']
        manufacturers = sorted(list({(d.get('manufacturer') or '').strip() for d in all_drugs if d.get('manufacturer')}))

        # Áp dụng bộ lọc admin trên danh sách thu được
        filtered = all_drugs
        if selected_category:
            filtered = [
                d for d in filtered
                if str(d.get('drug_class', '')).strip().lower() == selected_category.strip().lower()
            ]
        if selected_source:
            filtered = [d for d in filtered if selected_source.lower() == str(d.get('source','')).lower()]
        if selected_manufacturer:
            filtered = [d for d in filtered if selected_manufacturer.lower() in (str(d.get('manufacturer','')).lower())]

        # Phân trang trên danh sách đã lọc
        total_drugs = len(filtered)
        total_pages = math.ceil(total_drugs / per_page) if total_drugs > 0 else 1
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        drugs = filtered[start_idx:end_idx]
        
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total_drugs,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_num': page - 1 if page > 1 else None,
            'next_num': page + 1 if page < total_pages else None
        }
        
        return render_template('admin/drug_management.html',
                     drugs=drugs,
                     search=search,
                     pagination=pagination,
                     user=session,
                     categories=categories,
                     selected_category=selected_category,
                     sources=sources,
                     selected_source=selected_source,
                     manufacturers=manufacturers,
                     selected_manufacturer=selected_manufacturer)
                             
    except Exception as e:
        print(f"Error in admin_drugs: {e}")
        flash(f'Lỗi tải danh sách thuốc: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))


@app.route('/admin/users')
@admin_required
def admin_users():
    try:
        search = request.args.get('search', '').strip()
        role = request.args.get('role', '').strip()

        users = get_all_users(search_term=search or None, role=role or None)

        admin_count = sum(1 for user in users if user.get('role') == 'admin')
        regular_count = sum(1 for user in users if user.get('role') == 'user')

        return render_template(
            'admin/users.html',
            user=session,
            users=users,
            search=search,
            selected_role=role,
            total_users=len(users),
            admin_count=admin_count,
            regular_count=regular_count,
        )
    except Exception as e:
        print(f"Error in admin_users: {e}")
        flash(f'Lỗi tải danh sách người dùng: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))


@app.route('/admin/users/<int:user_id>/role', methods=['POST'])
@admin_required
def admin_update_user_role(user_id):
    try:
        new_role = request.form.get('role', '').strip()
        current_user_id = session.get('user_id')

        conn = get_db()
        target_user = conn.execute('SELECT id, username, role FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()

        if not target_user:
            flash('Không tìm thấy người dùng để cập nhật', 'error')
            return redirect(url_for('admin_users'))

        if user_id == current_user_id:
            flash('Bạn không thể thay đổi role của chính mình tại đây', 'error')
            return redirect(url_for('admin_users'))

        if target_user['username'] == 'admin':
            flash('Không thể thay đổi role của tài khoản admin mặc định', 'error')
            return redirect(url_for('admin_users'))

        if new_role not in ('user', 'admin'):
            flash('Role không hợp lệ', 'error')
            return redirect(url_for('admin_users'))

        if update_user_role(user_id, new_role):
            flash('Đã cập nhật role người dùng', 'success')
        else:
            flash('Không tìm thấy người dùng để cập nhật', 'error')
    except Exception as e:
        flash(f'Lỗi cập nhật role: {str(e)}', 'error')

    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    try:
        current_user_id = session.get('user_id')
        current_role = session.get('role')

        if user_id == current_user_id:
            flash('Không thể xóa chính tài khoản đang đăng nhập', 'error')
            return redirect(url_for('admin_users'))

        conn = get_db()
        target_user = conn.execute('SELECT id, role, username FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()

        if not target_user:
            flash('Không tìm thấy người dùng để xóa', 'error')
            return redirect(url_for('admin_users'))

        if target_user['username'] == 'admin':
            flash('Không thể xóa tài khoản admin mặc định', 'error')
            return redirect(url_for('admin_users'))

        if target_user['role'] == 'admin' and current_role != 'admin':
            flash('Bạn không có quyền xóa tài khoản admin khác', 'error')
            return redirect(url_for('admin_users'))

        if delete_user_account(user_id):
            flash('Đã xóa người dùng thành công', 'success')
        else:
            flash('Không thể xóa người dùng', 'error')
    except Exception as e:
        flash(f'Lỗi xóa người dùng: {str(e)}', 'error')

    return redirect(url_for('admin_users'))

@app.route('/admin/drug/add', methods=['GET', 'POST'], endpoint='add_drug')
@admin_required
def add_drug_route():
    """Thêm thuốc mới """
    if request.method == 'POST':
        try:
            drug_name = request.form.get('drug_name', '').strip()
            drug_class = request.form.get('drug_class', '').strip()
            ingredients = request.form.get('ingredients', '').strip()
            indication = request.form.get('indication', '').strip()
            dosage_form = request.form.get('dosage_form', '').strip() or None
            packing = request.form.get('packing', '').strip() or None
            usage = request.form.get('usage', '').strip() or None
            caution = request.form.get('caution', '').strip() or None
            contraindication = request.form.get('contraindication', '').strip() or None
            side_effects = request.form.get('side_effects', '').strip() or None
            manufacturer = request.form.get('manufacturer', '').strip() or None
            price_raw = request.form.get('price', '').strip()
            price = None

            image_urls = []
            for i in range(1, 6):
                image_value = request.form.get(f'image_url_{i}', '').strip()
                if not image_value:
                    continue

                if not re.match(r'^https?://', image_value, flags=re.IGNORECASE):
                    flash(f'URL ảnh #{i} không hợp lệ. Vui lòng nhập link bắt đầu bằng http:// hoặc https://', 'error')
                    return render_template('admin/drug_form.html', mode='add', user=session)

                image_urls.append(image_value)

            # Nhận thêm ảnh upload từ máy
            uploaded_image_urls = []
            upload_files = request.files.getlist('image_files')
            upload_files = [f for f in upload_files if f and str(getattr(f, 'filename', '')).strip()]

            if upload_files:
                upload_dir = os.path.join(app.static_folder, 'uploads', 'drugs')
                os.makedirs(upload_dir, exist_ok=True)

                for upload_file in upload_files:
                    if not _allowed_image_file(upload_file.filename):
                        flash('Chỉ hỗ trợ ảnh định dạng JPG, JPEG, PNG, WEBP', 'error')
                        return render_template('admin/drug_form.html', mode='add', user=session)

                    safe_name = secure_filename(upload_file.filename)
                    extension = os.path.splitext(safe_name)[1].lower()
                    unique_name = f"{uuid.uuid4().hex}{extension}"
                    output_path = os.path.join(upload_dir, unique_name)
                    upload_file.save(output_path)

                    static_rel = f"uploads/drugs/{unique_name}".replace('\\', '/')
                    uploaded_image_urls.append(url_for('static', filename=static_rel))

            # Ưu tiên ảnh upload trước, sau đó ảnh URL
            merged_image_urls = list(dict.fromkeys(uploaded_image_urls + image_urls))
            if len(merged_image_urls) > 5:
                flash('Chỉ được tối đa 5 ảnh (gồm cả URL và ảnh tải từ máy)', 'error')
                return render_template('admin/drug_form.html', mode='add', user=session)

            if price_raw:
                try:
                    price_digits = re.sub(r'[^0-9]', '', price_raw)
                    price = float(price_digits) if price_digits else None
                except ValueError:
                    flash('Giá tiền không hợp lệ', 'error')
                    return render_template('admin/drug_form.html', mode='add', user=session)
            
            if not drug_name:
                flash('Tên thuốc không được để trống', 'error')
                return render_template('admin/drug_form.html', mode='add', user=session)
            
            # Validate drug_class is in approved categories
            if not drug_class:
                flash('Vui lòng chọn danh mục thuốc', 'error')
                return render_template('admin/drug_form.html', mode='add', user=session)
            
            valid_categories = _get_valid_categories()
            if drug_class not in valid_categories:
                flash(f'Danh mục "{drug_class}" không hợp lệ. Vui lòng chọn một danh mục từ danh sách.', 'error')
                return render_template('admin/drug_form.html', mode='add', user=session)
            
            drug_id = add_drug_to_master(
                drug_name,
                drug_class,
                ingredients,
                indication,
                dosage_form=dosage_form,
                packing=packing,
                usage=usage,
                caution=caution,
                contraindication=contraindication,
                side_effects=side_effects,
                manufacturer=manufacturer,
                price=price,
                image_urls=merged_image_urls,
            )
            flash(f'Đã thêm thuốc thành công (ID: {drug_id})', 'success')
            return redirect(url_for('admin_drugs'))
            
        except Exception as e:
            flash(f'Lỗi thêm thuốc: {str(e)}', 'error')
    
    return render_template('admin/drug_form.html', mode='add', user=session)

@app.route('/admin/drug/edit/<int:drug_id>', methods=['GET', 'POST'], endpoint='edit_drug')
@admin_required
def edit_drug_route(drug_id):
    """Chỉnh sửa thuốc thủ công"""
    if request.method == 'GET':
        # Lấy thông tin thuốc cần edit
        try:
            conn = get_db()
            drug = conn.execute('''
                SELECT id, drug_name, drug_class, ingredients, indication,
                       dosage_form, packing, usage, caution,
                       contraindication, side_effects, manufacturer, price, image_urls
                FROM drugs_master
                WHERE id = ?
            ''', (drug_id,)).fetchone()
            conn.close()
            
            if not drug:
                flash('Không tìm thấy thuốc để chỉnh sửa', 'error')
                return redirect(url_for('admin_drugs'))
            
            # Parse image_urls from JSON
            image_urls = []
            if drug['image_urls']:
                try:
                    image_urls = json.loads(drug['image_urls'])
                except:
                    pass
            
            drug_dict = {
                'id': drug['id'],
                'drug_name': drug['drug_name'],
                'drug_class': drug['drug_class'],
                'ingredients': drug['ingredients'],
                'indication': drug['indication'],
                'dosage_form': drug['dosage_form'],
                'packing': drug['packing'],
                'usage': drug['usage'],
                'caution': drug['caution'],
                'contraindication': drug['contraindication'],
                'side_effects': drug['side_effects'],
                'manufacturer': drug['manufacturer'],
                'price': drug['price'],
                'image_urls': image_urls
            }
            
            return render_template('admin/drug_form.html', mode='edit', drug=drug_dict, user=session)
            
        except Exception as e:
            flash(f'Lỗi tải thông tin thuốc: {str(e)}', 'error')
            return redirect(url_for('admin_drugs'))
    
    elif request.method == 'POST':
        try:
            drug_name = request.form.get('drug_name', '').strip()
            drug_class = request.form.get('drug_class', '').strip()
            ingredients = request.form.get('ingredients', '').strip()
            indication = request.form.get('indication', '').strip()
            dosage_form = request.form.get('dosage_form', '').strip() or None
            packing = request.form.get('packing', '').strip() or None
            usage = request.form.get('usage', '').strip() or None
            caution = request.form.get('caution', '').strip() or None
            contraindication = request.form.get('contraindication', '').strip() or None
            side_effects = request.form.get('side_effects', '').strip() or None
            manufacturer = request.form.get('manufacturer', '').strip() or None
            price_raw = request.form.get('price', '').strip()
            price = None

            image_urls = []
            for i in range(1, 6):
                image_value = request.form.get(f'image_url_{i}', '').strip()
                if not image_value:
                    continue

                if not re.match(r'^https?://', image_value, flags=re.IGNORECASE):
                    flash(f'URL ảnh #{i} không hợp lệ. Vui lòng nhập link bắt đầu bằng http:// hoặc https://', 'error')
                    return redirect(url_for('edit_drug', drug_id=drug_id))

                image_urls.append(image_value)

            # Nhận thêm ảnh upload từ máy
            uploaded_image_urls = []
            upload_files = request.files.getlist('image_files')
            upload_files = [f for f in upload_files if f and str(getattr(f, 'filename', '')).strip()]

            if upload_files:
                upload_dir = os.path.join(app.static_folder, 'uploads', 'drugs')
                os.makedirs(upload_dir, exist_ok=True)

                for upload_file in upload_files:
                    if not _allowed_image_file(upload_file.filename):
                        flash('Chỉ hỗ trợ ảnh định dạng JPG, JPEG, PNG, WEBP', 'error')
                        return redirect(url_for('edit_drug', drug_id=drug_id))

                    safe_name = secure_filename(upload_file.filename)
                    extension = os.path.splitext(safe_name)[1].lower()
                    unique_name = f"{uuid.uuid4().hex}{extension}"
                    output_path = os.path.join(upload_dir, unique_name)
                    upload_file.save(output_path)

                    static_rel = f"uploads/drugs/{unique_name}".replace('\\', '/')
                    uploaded_image_urls.append(url_for('static', filename=static_rel))

            # Ưu tiên ảnh upload trước, sau đó ảnh URL
            merged_image_urls = list(dict.fromkeys(uploaded_image_urls + image_urls))
            if len(merged_image_urls) > 5:
                flash('Chỉ được tối đa 5 ảnh (gồm cả URL và ảnh tải từ máy)', 'error')
                return redirect(url_for('edit_drug', drug_id=drug_id))

            if price_raw:
                try:
                    price_digits = re.sub(r'[^0-9]', '', price_raw)
                    price = float(price_digits) if price_digits else None
                except ValueError:
                    flash('Giá tiền không hợp lệ', 'error')
                    return redirect(url_for('edit_drug', drug_id=drug_id))
            
            if not drug_name:
                flash('Tên thuốc không được để trống', 'error')
                return redirect(url_for('edit_drug', drug_id=drug_id))
            
            # Validate drug_class is in approved categories
            if not drug_class:
                flash('Vui lòng chọn danh mục thuốc', 'error')
                return redirect(url_for('edit_drug', drug_id=drug_id))
            
            valid_categories = _get_valid_categories()
            if drug_class not in valid_categories:
                flash(f'Danh mục "{drug_class}" không hợp lệ. Vui lòng chọn một danh mục từ danh sách.', 'error')
                return redirect(url_for('edit_drug', drug_id=drug_id))
            
            # Update drug
            if update_drug_to_master(
                drug_id,
                drug_name,
                drug_class,
                ingredients,
                indication,
                dosage_form=dosage_form,
                packing=packing,
                usage=usage,
                caution=caution,
                contraindication=contraindication,
                side_effects=side_effects,
                manufacturer=manufacturer,
                price=price,
                image_urls=merged_image_urls,
            ):
                flash(f'Đã cập nhật thuốc thành công (ID: {drug_id})', 'success')
                return redirect(url_for('admin_drugs'))
            else:
                flash('Không tìm thấy thuốc để cập nhật', 'error')
                return redirect(url_for('admin_drugs'))
            
        except Exception as e:
            flash(f'Lỗi cập nhật thuốc: {str(e)}', 'error')
            return redirect(url_for('edit_drug', drug_id=drug_id))

@app.route('/admin/drug/delete/<int:drug_id>', methods=['POST'])
@admin_required
def delete_drug_route(drug_id):
    """Xóa thuốc"""
    try:
        if delete_drug(drug_id):
            flash('Đã xóa thuốc thành công', 'success')
        else:
            flash('Không tìm thấy thuốc để xóa', 'error')
    except Exception as e:
        flash(f'Lỗi xóa thuốc: {str(e)}', 'error')
    
    return redirect(url_for('admin_drugs'))



@app.route('/admin/stats')
@admin_required  
def stats():
    """Trang thống kê"""
    try:
        basic_stats = get_stats()
        
        conn = get_db()
        
        # Thống kê trong 7 ngày gần đây
        recent_stats = conn.execute('''
            SELECT 
                COUNT(*) as searches_7days,
                COUNT(DISTINCT user_id) as active_users
            FROM search_logs 
            WHERE search_time >= date('now', '-7 days')
        ''').fetchone()
        
        top_symptoms = conn.execute('''
            SELECT symptoms, COUNT(*) as count
            FROM search_logs 
            GROUP BY LOWER(symptoms)
            ORDER BY count DESC 
            LIMIT 20
        ''').fetchall()
        
        
        saved_stats = conn.execute('''
            SELECT 
                COUNT(*) as total_saved,
                COUNT(DISTINCT user_id) as users_with_saved
            FROM saved_drugs
        ''').fetchone()
        
        conn.close()
        
        
        stats_data = {
            'total_users': basic_stats['total_users'],
            'total_searches': basic_stats['total_searches'],
            'searches_7days': recent_stats['searches_7days'] if recent_stats else 0,
            'active_users': recent_stats['active_users'] if recent_stats else 0,
            'total_saved': saved_stats['total_saved'] if saved_stats else 0,
            'users_with_saved': saved_stats['users_with_saved'] if saved_stats else 0,
            'top_symptoms': [dict(row) for row in top_symptoms],
            'recent_searches': basic_stats.get('recent_searches', [])
        }
        
        return render_template('admin/stats.html', 
                             stats=stats_data,
                             user=session)
                             
    except Exception as e:
        print(f"Error in stats: {e}")
        flash(f'Lỗi tải thống kê: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)