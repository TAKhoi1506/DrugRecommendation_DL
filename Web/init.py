import os
import sqlite3
import pandas as pd
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'simple_app.db')

def init_database():
    """Khởi tạo cơ sở dữ liệu"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Bảng users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bảng search logs 
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            symptoms TEXT NOT NULL,
            results_count INTEGER,
            search_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Bảng thuốc đã lưu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_drugs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            drug_index INTEGER NOT NULL,
            drug_name TEXT NOT NULL,
            drug_class TEXT,
            symptoms TEXT,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, drug_index)
        )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS search_favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        drug_index INTEGER,
        drug_name TEXT,
        click_count INTEGER DEFAULT 1,
        last_clicked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drugs_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_name TEXT NOT NULL,
            drug_class TEXT,
            ingredients TEXT,
            indication TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tạo admin mặc định
    cursor.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
    if cursor.fetchone()[0] == 0:
        admin_password = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO users (username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?)
        ''', ('admin', admin_password, 'Administrator', 'admin'))
        print("Created admin account: admin/admin123")
    

    cursor.execute('SELECT COUNT(*) FROM drugs_master')
    if cursor.fetchone()[0] == 0:
        sample_drugs = [
            ('Paracetamol 500mg', 'Giảm đau hạ sốt', 'Paracetamol 500mg', 'Giảm đau, hạ sốt, đau đầu'),
            ('Aspirin 325mg', 'Giảm đau chống viêm', 'Aspirin 325mg', 'Giảm đau, chống viêm, đau khớp'),
            ('Amoxicillin 500mg', 'Kháng sinh', 'Amoxicillin 500mg', 'Nhiễm trùng, viêm phổi, viêm họng'),
            ('Omeprazole 20mg', 'Tiêu hóa', 'Omeprazole 20mg', 'Viêm dạ dày, trào ngược'),
            ('Vitamin C 1000mg', 'Vitamin', 'Vitamin C 1000mg', 'Tăng cường miễn dịch')
        ]
        
        for drug in sample_drugs:
            cursor.execute('''
                INSERT INTO drugs_master (drug_name, drug_class, ingredients, indication)
                VALUES (?, ?, ?, ?)
            ''', drug)
        
        print("Added 5 sample drugs")
    
    conn.commit()
    conn.close()
    print(f"Database initialized: {DB_PATH}")



def get_db():
    """Lấy kết nối database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_user(username, password, full_name):
    """Tạo user mới"""
    conn = get_db()
    try:
        password_hash = generate_password_hash(password)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, password_hash, full_name)
            VALUES (?, ?, ?)
        ''', (username, password_hash, full_name))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Tên đăng nhập đã tồn tại")
    finally:
        conn.close()

def verify_user(username, password):
    """Xác thực user"""
    conn = get_db()
    user = conn.execute(
        'SELECT * FROM users WHERE username = ?', (username,)
    ).fetchone()
    conn.close()
    
    if user and check_password_hash(user['password_hash'], password):
        return dict(user)
    return None

def log_search(user_id, symptoms, results_count,user_agent):
    conn = get_db()
    conn.execute('''
        INSERT INTO search_logs (user_id, symptoms, results_count, user_agent)
        VALUES (?, ?, ?, ?)
    ''', (user_id, symptoms, results_count,user_agent))
    conn.commit()
    conn.close()

def get_stats():
    conn = get_db()
    
    total_users = conn.execute('SELECT COUNT(*) FROM users WHERE role != "admin"').fetchone()[0]
    total_searches = conn.execute('SELECT COUNT(*) FROM search_logs').fetchone()[0]
    dataset_count = 0
    try:
        from app import engine
        if hasattr(engine, 'data_final') and engine.data_final is not None:
            dataset_count = len(engine.data_final)
    except:
        dataset_count = 0
    
    total_drugs = dataset_count

    recent_searches = conn.execute('''
        SELECT sl.symptoms, sl.results_count, sl.search_time, u.username
        FROM search_logs sl
        LEFT JOIN users u ON sl.user_id = u.id
        ORDER BY sl.search_time DESC LIMIT 5
    ''').fetchall()
    
    conn.close()
    
    return {
        'total_users': total_users,
        'total_searches': total_searches,
        'total_drugs': total_drugs,
        'recent_searches': recent_searches
    }

def save_drug(user_id, drug_index, drug_name, drug_class, symptoms, score, notes=""):
    """Lưu thuốc vào danh sách yêu thích"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO saved_drugs 
            (user_id, drug_index, drug_name, drug_class, symptoms, score, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, drug_index, drug_name, drug_class, symptoms, score, notes))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"Error saving drug: {e}")
        raise
    finally:
        conn.close()

def get_saved_drugs(user_id):
    """Lấy danh sách thuốc đã lưu của user"""
    conn = get_db()
    saved_drugs = conn.execute('''
        SELECT * FROM saved_drugs 
        WHERE user_id = ? 
        ORDER BY saved_at DESC
    ''', (user_id,)).fetchall()
    conn.close()
    return [dict(drug) for drug in saved_drugs]

def remove_saved_drug(user_id, drug_index):
    """Xóa thuốc khỏi danh sách đã lưu"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM saved_drugs 
        WHERE user_id = ? AND drug_index = ?
    ''', (user_id, drug_index))
    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_rows > 0

def is_drug_saved(user_id, drug_index):
    """Kiểm tra thuốc đã được lưu chưa"""
    conn = get_db()
    result = conn.execute('''
        SELECT COUNT(*) FROM saved_drugs 
        WHERE user_id = ? AND drug_index = ?
    ''', (user_id, drug_index)).fetchone()[0]
    conn.close()
    return result > 0



def log_search_enhanced(user_id, symptoms, results_count, user_agent = None):
    """Ghi log tìm kiếm với thông tin chi tiết"""
    conn = get_db()
    # Kiểm tra xem cột user_agent có tồn tại không
    try:
        conn.execute('''
            INSERT INTO search_logs (user_id, symptoms, results_count, user_agent)
            VALUES (?, ?, ?, ?)
        ''', (user_id, symptoms, results_count, user_agent))
    except sqlite3.OperationalError:
        # Fallback nếu không có cột user_agent
        conn.execute('''
            INSERT INTO search_logs (user_id, symptoms, results_count)
            VALUES (?, ?, ?)
        ''', (user_id, symptoms, results_count))
    conn.commit()
    conn.close()

def get_search_history(user_id, limit=50):
    """Lấy lịch sử tìm kiếm của user"""
    conn = get_db()
    history = conn.execute('''
        SELECT * FROM search_logs 
        WHERE user_id = ? 
        ORDER BY search_time DESC 
        LIMIT ?
    ''', (user_id, limit)).fetchall()
    conn.close()
    return [dict(item) for item in history]

def get_search_statistics(user_id):
    """Thống kê tìm kiếm của user"""
    conn = get_db()
    
    # Tổng số lần tìm kiếm
    total_searches = conn.execute('''
        SELECT COUNT(*) FROM search_logs WHERE user_id = ?
    ''', (user_id,)).fetchone()[0]
    
    # Triệu chứng được tìm nhiều nhất
    top_symptoms = conn.execute('''
        SELECT symptoms, COUNT(*) as count 
        FROM search_logs 
        WHERE user_id = ? 
        GROUP BY LOWER(symptoms) 
        ORDER BY count DESC 
        LIMIT 5
    ''', (user_id,)).fetchall()
    
    return {
        'total_searches': total_searches,
        'top_symptoms': [dict(item) for item in top_symptoms]
    }

def clear_search_history(user_id):
    """Xóa lịch sử tìm kiếm"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM search_logs WHERE user_id = ?', (user_id,))
    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_rows

def track_drug_click(user_id, drug_index, drug_name):
    """Theo dõi click vào thuốc"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO search_favorites 
        (user_id, drug_index, drug_name, click_count, last_clicked)
        VALUES (?, ?, ?, 
            COALESCE((SELECT click_count FROM search_favorites WHERE user_id = ? AND drug_index = ?), 0) + 1,
            CURRENT_TIMESTAMP)
    ''', (user_id, drug_index, drug_name, user_id, drug_index))
    conn.commit()
    conn.close()

def get_user_profile(user_id):
    """Lấy thông tin profile của user"""
    conn = get_db()
    user = conn.execute('''
        SELECT id, username, full_name, role, created_at
        FROM users 
        WHERE id = ?
    ''', (user_id,)).fetchone()
    conn.close()

    if user:
        return dict(user)
    return None

def update_user_profile(user_id, full_name):
    """Cập nhật thông tin profile của user"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users SET full_name = ? WHERE id = ?
    ''', (full_name, user_id))
    
    conn.commit()
    updated_rows = cursor.rowcount
    conn.close()
    
    return updated_rows > 0

def change_password(user_id, current_password, new_password):
    """Đổi mật khẩu"""
    conn = get_db()
    
    # Verify current password
    user = conn.execute('''
        SELECT password_hash FROM users WHERE id = ?
    ''', (user_id,)).fetchone()
    
    if not user:
        conn.close()
        raise ValueError("Không tìm thấy người dùng")
    
    if not check_password_hash(user['password_hash'], current_password):
        conn.close()
        raise ValueError("Mật khẩu hiện tại không đúng")
    
    # Update password
    new_password_hash = generate_password_hash(new_password)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET password_hash = ? WHERE id = ?
    ''', (new_password_hash, user_id))
    
    conn.commit()
    updated_rows = cursor.rowcount
    conn.close()
    
    return updated_rows > 0




def get_all_drugs(search_term=None, source='both'):
    """Lấy danh sách thuốc từ cả dataset và drugs_master"""
    
    # Lấy từ drugs_master
    conn = get_db()
    
    if search_term:
        drugs_master = conn.execute('''
            SELECT id, drug_name, drug_class, ingredients, indication, created_at, 'manual' as source
            FROM drugs_master 
            WHERE drug_name LIKE ? OR ingredients LIKE ?
            ORDER BY created_at DESC
        ''', (f'%{search_term}%', f'%{search_term}%')).fetchall()
    else:
        drugs_master = conn.execute('''
            SELECT id, drug_name, drug_class, ingredients, indication, created_at, 'manual' as source
            FROM drugs_master 
            ORDER BY created_at DESC
        ''').fetchall()
    
    conn.close()
    
    # Lấy từ dataset
    dataset_drugs = []
    
    try:
        from app import engine
        
        if hasattr(engine, 'data_final') and engine.data_final is not None:
            df = engine.data_final
            
            # Filter by search term
            if search_term:
                mask = df['ten_thuoc'].astype(str).str.contains(search_term, case=False, na=False) | \
                       df['chi_dinh'].astype(str).str.contains(search_term, case=False, na=False)
                df = df[mask]
            
            # Convert dataset to list
            for idx, row in df.iterrows():
                drug_name = str(row['ten_thuoc']) if pd.notna(row['ten_thuoc']) else f"Thuốc {idx}"
                
                dataset_drugs.append({
                    'id': idx,
                    'drug_name': drug_name,
                    'drug_class': 'Dataset',  
                    'ingredients': str(row.get('thanh_phan', '')) if pd.notna(row.get('thanh_phan')) else None,
                    'indication': str(row.get('chi_dinh', '')) if pd.notna(row.get('chi_dinh')) else None,
                    'source': 'dataset',
                    'created_at': None
                })
                
    except Exception as e:
        print(f"Error loading dataset: {e}")
    
    # Kết hợp và trả về
    all_drugs = [dict(drug) for drug in drugs_master] + dataset_drugs
    
    if source == 'manual':
        return [dict(drug) for drug in drugs_master]
    elif source == 'dataset':
        return dataset_drugs
    else:
        return all_drugs


def add_drug(drug_name, drug_class, ingredients, indication):
    """Thêm thuốcn"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO drugs_master (drug_name, drug_class, ingredients, indication, created_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (drug_name, drug_class, ingredients, indication))
    
    drug_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return drug_id

def delete_drug(drug_id):
    """Xóa thuốc"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM drugs_master WHERE id = ?', (drug_id,))
    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_rows > 0

# Khởi tạo khi import
if __name__ == "__main__":
    init_database()
    print("Available functions:")
    import inspect
    current_module = inspect.getmembers(inspect.getmodule(inspect.currentframe()))
    for name, obj in current_module:
        if inspect.isfunction(obj):
            print(f"- {name}")