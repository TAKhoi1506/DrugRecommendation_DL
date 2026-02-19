def classify_drug_type(drug_name):
    drug_name = str(drug_name).lower()
    
    if any(word in drug_name for word in [
        'kháng sinh', 'antibiotic', 'cillin', 'mycin', 'floxacin', 'cephalos','amoxicillin', 'azithromycin', 'clarithromycin', 'penicillin',
        'cephalexin', 'ciprofloxacin', 'erythromycin', 'tetracycline','metronidazole', 'sulfamethoxazole', 'trimethoprim', 'doxycycline',
        'ampicillin', 'gentamicin', 'streptomycin', 'nhiễm trùng', 'kháng khuẩn']):
        return 'kháng sinh'
    
    elif any(word in drug_name for word in [
        'paracetamol', 'aspirin', 'ibuprofen', 'acetaminophen', 'tylenol', 'đau', 'giảm đau', 'hạ sốt', 'diclofenac', 'naproxen', 'ketoprofen',
        'piroxicam', 'meloxicam', 'celecoxib', 'indomethacin', 'sốt','chống viêm', 'giảm sốt', 'analgesic', 'antipyretic', 'nsaid',
        'aceclofenac', 'mefenamic', 'etoricoxib', 'lornoxicam']):
        return 'giảm đau hạ sốt'
    
    elif any(word in drug_name for word in [
        'dạ dày', 'tiêu hóa', 'táo bón', 'tiêu chảy', 'nôn', 'buồn nôn','omeprazole', 'ranitidine', 'famotidine', 'lansoprazole',
        'esomeprazole', 'pantoprazole', 'domperidone', 'metoclopramide','loperamide', 'bismuth', 'simethicone', 'lactulose', 'bụng',
        'gastric', 'peptic', 'antacid', 'proton pump', 'diosmectite','probiotics', 'enzym tiêu hóa', 'trợ tiêu hóa'
    ]):
        return 'tiêu hóa'
    
    elif any(word in drug_name for word in [
        'ho', 'cảm', 'cúm', 'viêm họng', 'hen suyễn', 'phế quản', 'expectorant', 'dextromethorphan', 'guaifenesin', 'salbutamol',
        'terbutaline', 'theophylline', 'montelukast', 'budesonide','fluticasone', 'beclomethasone', 'respiratory', 'broncho',
        'cough', 'cold', 'flu', 'asthma', 'viêm mũi', 'xịt mũi','ambroxol', 'bromhexine', 'acetylcysteine', 'carbocisteine']):
        return 'hô hấp'
    
    elif any(word in drug_name for word in [
        'huyết áp', 'tim', 'mạch', 'amlodipine', 'atenolol', 'metoprolol','lisinopril', 'enalapril', 'losartan', 'valsartan', 'nifedipine',
        'diltiazem', 'verapamil', 'furosemide', 'hydrochlorothiazide','carvedilol', 'bisoprolol', 'ramipril', 'candesartan',
        'cardiovascular', 'cardio', 'hypertension', 'tim mạch','telmisartan', 'olmesartan', 'perindopril', 'indapamide']):
        return 'tim mạch'
    
    elif any(word in drug_name for word in [
        'vitamin', 'khoáng chất', 'canxi', 'sắt', 'kẽm', 'magie','vitamin a', 'vitamin b', 'vitamin c', 'vitamin d', 'vitamin e',
        'folic acid', 'biotin', 'omega', 'multivitamin', 'calcium','iron', 'zinc', 'magnesium', 'potassium', 'supplement',
        'tăng cường', 'bổ sung', 'dinh dưỡng', 'khoáng']):
        return 'vitamin và bổ sung'
    
    elif any(word in drug_name for word in [
        'da', 'nấm da', 'viêm da', 'eczema', 'vảy nến', 'mụn','hydrocortisone', 'betamethasone', 'triamcinolone',
        'clotrimazole', 'miconazole', 'ketoconazole', 'terbinafine','dermatology', 'topical', 'cream', 'ointment', 'gel da',
        'fungal', 'antifungal', 'corticosteroid', 'thuốc bôi']):
        return 'da liễu'
    
    elif any(word in drug_name for word in [
        'mắt', 'tai', 'mũi', 'họng', 'viêm mũi', 'viêm tai','chloramphenicol', 'tobramycin', 'ofloxacin', 'dexamethasone',
        'prednisolone', 'artificial tears', 'saline', 'xịt mũi', 'ophthalmic', 'otic', 'nasal', 'throat', 'thuốc nhỏ mắt',
        'thuốc nhỏ tai', 'thuốc xịt mũi']):
        return 'mắt tai mũi họng'
    

    elif any(word in drug_name for word in [
        'thần kinh', 'trầm cảm', 'lo âu', 'an thần', 'ngủ','diazepam', 'lorazepam', 'alprazolam', 'clonazepam',
        'fluoxetine', 'sertraline', 'paroxetine', 'amitriptyline','haloperidol', 'risperidone', 'olanzapine', 'quetiapine',
        'psychiatric', 'neurological', 'antidepressant', 'anxiolytic', 'tâm thần', 'thuốc ngủ', 'chống trầm cảm']):
        return 'thần kinh tâm thần'
    
    elif any(word in drug_name for word in [
        'tiểu đường', 'đường huyết', 'insulin', 'tuyến giáp','metformin', 'glibenclamide', 'gliclazide', 'pioglitazone',
        'levothyroxine', 'methimazole', 'propylthiouracil','endocrine', 'diabetes', 'thyroid', 'hormone', 'nội tiết',
        'đái tháo đường', 'tuyến giáp']):
        return 'nội tiết'
    

    elif any(word in drug_name for word in [
        'phụ khoa', 'kinh nguyệt', 'tránh thai', 'mang thai','estrogen', 'progesterone', 'contraceptive', 'hormone replacement',
        'clomiphene', 'norethisterone', 'ethinylestradiol','gynecology', 'obstetrics', 'pregnancy', 'thuốc tránh thai']):
        return 'phụ khoa'
    
    elif any(word in drug_name for word in [
        'xương', 'khớp', 'viêm khớp', 'gout', 'thấp khớp','allopurinol', 'colchicine', 'prednisolone', 'methylprednisolone',
        'rheumatology', 'arthritis', 'osteoporosis', 'joint','glucosamine', 'chondroitin', 'cơ xương khớp']):
        return 'cơ xương khớp'
    
    elif any(word in drug_name for word in [
        'ung thư', 'hóa trị', 'xạ trị', 'u bướu', 'cancer','chemotherapy', 'oncology', 'tumor', 'atezolizumab',
        'cisplatin', 'carboplatin', 'doxorubicin', 'cyclophosphamide','methotrexate', 'fluorouracil', 'paclitaxel', 'avelumab']):
        return 'ung thư'
    
  
    elif any(word in drug_name for word in [
        'niệu', 'thận', 'bàng quang', 'tiết niệu', 'tiểu','kidney', 'bladder', 'urinary', 'urology',
        'tamsulosin', 'finasteride', 'desmopressin', 'niệu khoa']):
        return 'niệu khoa'

    else:
        return 'tổng hợp'