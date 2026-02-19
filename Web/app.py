from flask import Flask, render_template, request, jsonify, redirect, session, flash, url_for
import pandas as pd
import pickle
import joblib
import os
import re
import math
import numpy as np
from scipy.sparse import hstack
from utils import classify_drug_type
from init import (
    change_password, clear_search_history, get_db, get_search_history, 
    get_search_statistics, get_user_profile, init_database, create_user, 
    log_search_enhanced, track_drug_click, update_user_profile, verify_user, 
    log_search, get_stats, save_drug, get_saved_drugs, remove_saved_drug, is_drug_saved,
    get_all_drugs, add_drug, delete_drug
)
from functools import wraps
from datetime import timedelta

app = Flask(__name__, template_folder='templates', static_folder='static')


app.config['SECRET_KEY'] = 'simple-secret-key-for-demo'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

init_database()

# Decorators
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



class EnhancedDrugRecommendationEngine:
    def __init__(self):
        self.model_package = None
        self.data_final = None
        self.load_models()
        self.symptom_mapping = self._create_symptom_mapping()
    
    def load_models(self):
        try:
            # Đường dẫn chính xác tới file mô hình
            model_path = r"D:\OU\DoAn\DrugRecommandation\Web\models\drug_recommendation_model.pkl"
            fallback_path = r"D:\OU\DoAn\DrugRecommandation\Modeling\final_dataset.csv"
            
            print(f"Trying to load model from: {os.path.abspath(model_path)}")
            
            if os.path.exists(model_path):
                print("Loading trained model...")
                with open(model_path, 'rb') as f:
                    self.model_package = pickle.load(f)
                
                # Thêm hàm classify_drug_type vào model package nếu chưa có
                if 'classify_drug_type' not in self.model_package:
                    self.model_package['classify_drug_type'] = classify_drug_type
                
                self.data_final = self.model_package['data_final']
                print(f"Loaded ML model with {len(self.data_final)} drugs")
                print(f"Model info: {self.model_package.get('training_info', {})}")
                
            elif os.path.exists(fallback_path):
                print("Loading dataset without model...")
                self.data_final = pd.read_csv(fallback_path, encoding='utf-8')
                print(f"Loaded dataset: {len(self.data_final)} drugs")
                
            else:
                print("Loading final_dataset.csv from current directory...")
                current_dataset = "final_dataset.csv"
                if os.path.exists(current_dataset):
                    self.data_final = pd.read_csv(current_dataset, encoding='utf-8')
                    print(f"Loaded current dataset with {len(self.data_final)} drugs")
                else:
                    raise FileNotFoundError("No dataset found")
                
        except Exception as e:
            print(f"Error loading models: {e}")
            # Tạo dummy data backup từ dataset thực
            self.data_final = pd.DataFrame({
                'ten_thuoc': ['Paracetamol: thuốc giảm đau hạ sốt', 'Aspirin: thuốc chống viêm giảm đau', 'Amoxicillin: thuốc kháng sinh'],
                'thanh_phan': ['Paracetamol 500mg', 'Aspirin 325mg', 'Amoxicillin 500mg'],
                'chi_dinh': ['giảm đau, hạ sốt, đau đầu', 'giảm đau, chống viêm, đau khớp', 'nhiễm trùng, viêm phổi, viêm họng'],
                'chong_chi_dinh': ['Suy gan nặng', 'Hen suyễn, xuất huyết', 'Dị ứng penicillin'],
                'tac_dung_phu': ['Buồn nôn, đau bụng', 'Chảy máu dạ dày', 'Tiêu chảy, nôn'],
                'source': ['DieuTri', 'DieuTri', 'DieuTri']
            })
            print(f"Created backup data with {len(self.data_final)} drugs")
        
        # Debug thông tin dataset
        if self.data_final is not None:
            print(f"Dataset info:")
            print(f"   Columns: {self.data_final.columns.tolist()}")
            print(f"   Shape: {self.data_final.shape}")
            print(f"   Sample drug names: {self.data_final['ten_thuoc'].head().tolist()}")
    
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
    
    def predict_drug_category(self, symptoms):
        """Sử dụng mô hình đã được huấn luyện để dự đoán loại thuốc"""
        if not self.model_package:
            print("No trained model available, using rule-based classification")
            return self._rule_based_classification(symptoms)
        
        try:
            symptoms_clean = symptoms.lower().strip()
            
            # TF-IDF transform
            tfidf_vectorizer = self.model_package['tfidf_vectorizer']
            X_text = tfidf_vectorizer.transform([symptoms_clean])
            
            # Numeric features
            safe_features = self.model_package['safe_numeric_features']
            X_numeric = np.zeros((1, len(safe_features)))
            
            # Combine
            X_combined = hstack([X_text, X_numeric])
            
            # Predict
            model = self.model_package['best_model']
            le = self.model_package['le_drug_type']
            
            prediction = model.predict(X_combined)[0]
            probabilities = model.predict_proba(X_combined)[0]
            
            predicted_class = le.inverse_transform([prediction])[0]
            confidence = max(probabilities)
            
            print(f"ML Prediction: {predicted_class} (confidence: {confidence:.3f})")
            
            return {
                'predicted_class': predicted_class,
                'confidence': confidence,
                'method': 'ML'
            }
        except Exception as e:
            print(f"ML prediction error: {e}, falling back to rule-based")
            return self._rule_based_classification(symptoms)
    
    def _rule_based_classification(self, symptoms):
        """Phân loại dựa trên quy tắc khi không có mô hình ML"""
        symptoms_lower = symptoms.lower()
        
        if any(word in symptoms_lower for word in ['đau đầu', 'sốt', 'giảm đau', 'hạ sốt']):
            return {'predicted_class': 'giảm đau hạ sốt', 'confidence': 0.8, 'method': 'rule-based'}
        elif any(word in symptoms_lower for word in ['ho', 'cảm', 'hô hấp', 'phế quản']):
            return {'predicted_class': 'hô hấp', 'confidence': 0.8, 'method': 'rule-based'}
        elif any(word in symptoms_lower for word in ['nhiễm trùng', 'kháng sinh', 'viêm']):
            return {'predicted_class': 'kháng sinh', 'confidence': 0.8, 'method': 'rule-based'}
        elif any(word in symptoms_lower for word in ['đau bụng', 'tiêu chảy', 'dạ dày']):
            return {'predicted_class': 'tiêu hóa', 'confidence': 0.8, 'method': 'rule-based'}
        else:
            return {'predicted_class': 'tổng hợp', 'confidence': 0.5, 'method': 'rule-based'}
    
    def search_by_symptoms(self, symptoms, limit=15):
        """Tìm thuốc với logic cải tiến dựa trên mô hình đã huấn luyện"""
        if self.data_final is None:
            return {'drugs': [], 'detected_symptoms': [], 'total_found': 0}
        
        # ML prediction hoặc rule-based
        ml_prediction = self.predict_drug_category(symptoms)
        
        # Detect symptoms
        symptoms_clean = symptoms.lower()
        detected_symptoms = []
        matched_keywords = set()
        
        for symptom, keywords in self.symptom_mapping.items():
            for keyword in keywords:
                if keyword in symptoms_clean:
                    detected_symptoms.append({
                        'name': symptom, 
                        'category': self._get_symptom_category(symptom)
                    })
                    matched_keywords.update(keywords)
                    break
        
        # Search drugs in chi_dinh column
        matches = []
        
        for idx, row in self.data_final.iterrows():
            if pd.notna(row['chi_dinh']):
                indication = str(row['chi_dinh']).lower()
                score = 0
                matched_symptoms = []
                
                # Score based on keyword matching
                for keyword in matched_keywords:
                    if keyword in indication:
                        score += 1
                        matched_symptoms.append(keyword)
                
                # ML bonus score
                if ml_prediction and score > 0:
                    drug_category = self._classify_drug_from_name(row['ten_thuoc'])
                    if ml_prediction['predicted_class'].lower() in drug_category.lower():
                        score += 2
                        print(f"ML bonus for {row['ten_thuoc'][:50]} - predicted: {ml_prediction['predicted_class']}, drug_cat: {drug_category}")
                
                # Fuzzy matching cho exact symptoms
                for symptom_word in symptoms_clean.split():
                    if len(symptom_word) >= 3 and symptom_word in indication:
                        score += 0.5
                
                # Add to matches if score > 0
                if score > 0:
                    drug_info = self._get_drug_info(idx, row)
                    drug_info['score'] = round(score, 1)
                    drug_info['matched_symptoms'] = matched_symptoms[:3]
                    drug_info['confidence_level'] = self._get_confidence_level(score)
                    matches.append(drug_info)
        
        # Sort by score
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"Found {len(matches)} matches for symptoms: {symptoms}")
        
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
    
    def _classify_drug_from_name(self, drug_name):
        if self.model_package and 'classify_drug_type' in self.model_package:
            # Sử dụng hàm phân loại đã được lưu trong mô hình hoặc từ utils
            classify_func = self.model_package['classify_drug_type']
            return classify_func(drug_name)
        else:
            # Sử dụng hàm từ utils.py
            return classify_drug_type(drug_name)
    
    def _fallback_classify_drug(self, drug_name):
        """Phân loại thuốc fallback khi không có mô hình"""
        if pd.isna(drug_name):
            return 'Tổng hợp'
        
        drug_name = str(drug_name).lower()
        
        if any(word in drug_name for word in ['kháng sinh', 'amoxicillin', 'azithromycin', 'nhiễm trùng']):
            return 'Kháng sinh'
        elif any(word in drug_name for word in ['paracetamol', 'aspirin', 'giảm đau', 'hạ sốt']):
            return 'Giảm đau hạ sốt'
        elif any(word in drug_name for word in ['ho', 'cough', 'hô hấp', 'broncho']):
            return 'Hô hấp'
        elif any(word in drug_name for word in ['dạ dày', 'tiêu hóa', 'omeprazole']):
            return 'Tiêu hóa'
        elif any(word in drug_name for word in ['vitamin', 'khoáng chất', 'bổ sung']):
            return 'Vitamin và bổ sung'
        else:
            return 'Tổng hợp'
    
    def _get_confidence_level(self, score):
        if score >= 3:
            return 'Cao'
        elif score >= 1.5:
            return 'Trung bình' 
        else:
            return 'Thấp'
    
    def _get_drug_info(self, idx, row):
        """Lấy thông tin thuốc từ final_dataset"""
        # Parse drug name and indication
        drug_name = str(row['ten_thuoc']) if pd.notna(row['ten_thuoc']) else f"Thuốc {idx}"
        
        # Extract main name and description
        if ':' in drug_name:
            name_parts = drug_name.split(':', 1)
            main_name = name_parts[0].strip()
            description = name_parts[1].strip() if len(name_parts) > 1 else ""
        else:
            main_name = drug_name
            description = ""
        
        # Get other information
        ingredients = str(row['thanh_phan']) if pd.notna(row['thanh_phan']) else 'Không có thông tin'
        indications = str(row['chi_dinh']) if pd.notna(row['chi_dinh']) else 'Không có thông tin'
        contraindications = str(row['chong_chi_dinh']) if pd.notna(row['chong_chi_dinh']) else 'Không có thông tin'
        side_effects = str(row['tac_dung_phu']) if pd.notna(row['tac_dung_phu']) else 'Không có thông tin'
        source = str(row['source']) if pd.notna(row['source']) else 'Không rõ nguồn'
        
        # Parse to lists
        indication_list = self._parse_to_list(indications)
        ingredients_list = self._parse_to_list(ingredients)
        contraindication_list = self._parse_to_list(contraindications)
        side_effects_list = self._parse_to_list(side_effects)
        
        return {
            'index': idx,
            'name': main_name,
            'description': description,
            'drug_class': self._classify_drug_from_name(drug_name),
            'price': 'Liên hệ để biết giá',
            'manufacturer': 'Xem trên bao bì',
            'source': source,
            'prescription_required': self._requires_prescription(drug_name),
            
            # Detailed information
            'indication': indications,
            'ingredients': ingredients,
            'contraindication': contraindications,
            'side_effects': side_effects,
            
            # Lists for display
            'indication_list': indication_list,
            'ingredients_list': ingredients_list,
            'dosage_list': ['Theo chỉ định của bác sĩ', 'Đọc kỹ hướng dẫn sử dụng'],
            'contraindication_list': contraindication_list,
            'side_effects_list': side_effects_list,
            
            # For search results
            'matched_symptoms': []
        }
    
    def _parse_to_list(self, text):
        """Parse text thành list"""
        if not text or text == 'Không có thông tin':
            return ['Không có thông tin']
        
        # Split by common delimiters
        items = re.split(r'[.;,\n]', text)
        items = [item.strip() for item in items if item.strip()]
        
        # Remove duplicates and empty items
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
            'sources': self.data_final['source'].value_counts().to_dict() if 'source' in self.data_final.columns else {},
            'columns': self.data_final.columns.tolist(),
            'sample_drugs': self.data_final['ten_thuoc'].head(10).tolist(),
            'model_loaded': self.model_package is not None,
            'training_info': self.model_package.get('training_info', {}) if self.model_package else {}
        }

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
    
    return render_template('index.html', user=user)



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
        
        return jsonify({
            'success': True,
            'symptoms': symptoms,
            'results': results,
            'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
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
    """Xóa lịch sử tìm kiếm"""
    try:
        user_id = session['user_id']
        deleted_count = clear_search_history(user_id)
        
        return jsonify({
            'success': True, 
            'message': f'Đã xóa {deleted_count} lịch sử tìm kiếm'
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
            # Redirect về trang chủ với symptoms đã điền sẵn
            return redirect(url_for('index', symptoms=history_item['symptoms']))
        else:
            flash('Không tìm thấy lịch sử tìm kiếm', 'error')
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
    

@app.route('/debug')
def debug():
    stats = engine.get_dataset_stats()
    return jsonify(stats)

@app.route('/save_drug', methods=['POST'])
@login_required
def save_drug_route():
    """API lưu thuốc vào danh sách yêu thích"""
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
    """API xóa thuốc khỏi danh sách đã lưu"""
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
    """API kiểm tra thuốc đã được lưu chưa"""
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
        
        user = {
            'user_id': session['user_id'],
            'username': session['username'],
            'full_name': session['full_name'],
            'role': session['role']
        }
        
        print(f"Rendering template with {len(saved_drugs)} drugs")  # Debug log
        return render_template('saved_drugs.html', 
                             saved_drugs=saved_drugs, 
                             user=user)
                             
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
        
        if engine.data_final is not None:
            df = engine.data_final
            search = request.args.get('search', '')
            page = int(request.args.get('page', 1))
            per_page = 50
            
            # Lọc theo tìm kiếm
            if search:
                mask = df['ten_thuoc'].str.contains(search, case=False, na=False) | \
                       df['chi_dinh'].str.contains(search, case=False, na=False)
                filtered_df = df[mask]
            else:
                filtered_df = df
            

            # Phân trang
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paged_df = filtered_df.iloc[start_idx:end_idx]

            for idx, row in paged_df.iterrows():
                drug_name = str(row['ten_thuoc']) if pd.notna(row['ten_thuoc']) else f"Thuốc {idx}"
                
                drug_info = {
                    'index': idx,  # Sử dụng index gốc từ DataFrame
                    'drug_name': drug_name,
                    'drug_class': engine._classify_drug_from_name(drug_name),
                    'indication': str(row['chi_dinh']) if pd.notna(row['chi_dinh']) else 'Không có thông tin',
                    'ingredients': str(row['thanh_phan']) if pd.notna(row['thanh_phan']) else 'Không có thông tin',
                    'contraindication': str(row['chong_chi_dinh']) if pd.notna(row['chong_chi_dinh']) else 'Không có thông tin',
                    'side_effects': str(row['tac_dung_phu']) if pd.notna(row['tac_dung_phu']) else 'Không có thông tin',
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
                             user=user)
                             
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
        
        # Lấy tất cả thuốc
        all_drugs = get_all_drugs(search if search else None, 'both')
        
        # Phân trang
        total_drugs = len(all_drugs)
        total_pages = math.ceil(total_drugs / per_page) if total_drugs > 0 else 1
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        drugs = all_drugs[start_idx:end_idx]
        
        # Pagination info
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
                             user=session)
                             
    except Exception as e:
        print(f"Error in admin_drugs: {e}")
        flash(f'Lỗi tải danh sách thuốc: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/drug/add', methods=['GET', 'POST'])
@admin_required
def add_drug():
    """Thêm thuốc mới """
    if request.method == 'POST':
        try:
            drug_name = request.form.get('drug_name', '').strip()
            drug_class = request.form.get('drug_class', '').strip()
            ingredients = request.form.get('ingredients', '').strip()
            indication = request.form.get('indication', '').strip()
            
            if not drug_name:
                flash('Tên thuốc không được để trống', 'error')
                return render_template('admin/drug_form.html', mode='add', user=session)
            
            drug_id = add_drug(drug_name, drug_class, ingredients, indication)
            flash(f'Đã thêm thuốc thành công (ID: {drug_id})', 'success')
            return redirect(url_for('admin_drugs'))
            
        except Exception as e:
            flash(f'Lỗi thêm thuốc: {str(e)}', 'error')
    
    return render_template('admin/drug_form.html', mode='add', user=session)

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
@admin_required  # Chỉ admin mới xem được
def stats():
    """Trang thống kê"""
    try:
        # Lấy thống kê cơ bản
        basic_stats = get_stats()
        
        # Lấy thêm một số thống kê đơn giản
        conn = get_db()
        
        # Thống kê trong 7 ngày gần đây
        recent_stats = conn.execute('''
            SELECT 
                COUNT(*) as searches_7days,
                COUNT(DISTINCT user_id) as active_users
            FROM search_logs 
            WHERE search_time >= date('now', '-7 days')
        ''').fetchone()
        
        # Top 5 triệu chứng phổ biến
        top_symptoms = conn.execute('''
            SELECT symptoms, COUNT(*) as count
            FROM search_logs 
            GROUP BY LOWER(symptoms)
            ORDER BY count DESC 
            LIMIT 5
        ''').fetchall()
        
        # Thống kê thuốc đã lưu
        saved_stats = conn.execute('''
            SELECT 
                COUNT(*) as total_saved,
                COUNT(DISTINCT user_id) as users_with_saved
            FROM saved_drugs
        ''').fetchone()
        
        conn.close()
        
        # Chuẩn bị data đơn giản
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