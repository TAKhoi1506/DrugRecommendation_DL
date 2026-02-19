// DOM Elements
const symptomsInput = document.getElementById('symptomsInput');
const searchBtn = document.getElementById('searchBtn');
const loading = document.getElementById('loading');
const results = document.getElementById('results');
const error = document.getElementById('error');

// Global variable để lưu symptoms hiện tại
let currentSymptoms = '';

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    // Check for symptoms parameter from URL (for repeat search)
    const urlParams = new URLSearchParams(window.location.search);
    const symptoms = urlParams.get('symptoms');
    if (symptoms) {
        symptomsInput.value = symptoms;
        // Auto search after a small delay
        setTimeout(() => {
            search();
        }, 500);
    }
    
    symptomsInput.focus();
    
    // Event listeners
    searchBtn.addEventListener('click', search);
    symptomsInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            search();
        }
    });
});

// Example functions
function setExample(text) {
    symptomsInput.value = text;
    symptomsInput.focus();
}

// Main search function
async function search() {
    const symptoms = symptomsInput.value.trim();
    
    if (!symptoms) {
        showError('Vui lòng nhập triệu chứng bệnh nhân');
        return;
    }

    // Lưu symptoms hiện tại
    currentSymptoms = symptoms;

    loading.style.display = 'block';
    results.style.display = 'none';
    error.style.display = 'none';
    searchBtn.disabled = true;

    try {
        const response = await fetch('/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ symptoms: symptoms })
        });

        const data = await response.json();

        if (data.success) {
            displayResults(data);
        } else {
            showError(data.error || 'Có lỗi xảy ra');
        }
    } catch (err) {
        showError('Lỗi kết nối. Vui lòng thử lại.');
    } finally {
        loading.style.display = 'none';
        searchBtn.disabled = false;
    }
}

// Display search results in collapsed mode
function displayResults(data) {
    const drugs = data.results.drugs;
    const detectedSymptoms = data.results.detected_symptoms;
    
    let resultsHtml = `
        <div class="results-header">
            <h3><i class="fas fa-chart-line"></i> Kết quả phân tích: "${data.symptoms}"</h3>
            <p><i class="fas fa-pills"></i> Tìm thấy ${drugs.length} thuốc phù hợp | 
               <i class="fas fa-clock"></i> ${data.timestamp}</p>
        </div>
    `;

    if (detectedSymptoms.length > 0) {
        resultsHtml += `
            <div class="symptoms-detected">
                <h4><i class="fas fa-stethoscope"></i> Triệu chứng được nhận diện:</h4>
                ${detectedSymptoms.map(symptom => `
                    <span class="symptom-tag ${getCategoryClass(symptom.category || '')}">
                        ${symptom.name}
                    </span>
                `).join('')}
            </div>
        `;
    }

    if (drugs.length === 0) {
        resultsHtml += '<p>Không tìm thấy thuốc phù hợp. Thử với triệu chứng khác hoặc liên hệ chuyên khoa.</p>';
    } else {
        // Hiển thị thuốc ở chế độ thu gọn với nút lưu
        resultsHtml += drugs.map((drug, index) => `
            <div class="drug-card collapsed" id="drug-${index}">
                <!-- Header thuốc - luôn hiển thị -->
                <div class="drug-header">
                    <div class="drug-summary">
                        <div class="drug-name">${index + 1}. ${drug.name}</div>
                        <div class="drug-meta">
                            <span class="drug-class">${drug.drug_class}</span>
                            ${drug.prescription_required ? '<span class="prescription-required"><i class="fas fa-prescription"></i> Cần đơn thuốc</span>' : ''}
                            <span class="drug-price"><i class="fas fa-tag"></i> ${drug.price}</span>
                            <span class="confidence-badge confidence-${drug.confidence_level ? drug.confidence_level.toLowerCase() : 'low'}">
                                ${drug.confidence_level || 'Thấp'}
                            </span>
                        </div>
                        <div class="quick-info">
                            <span class="matched-symptoms">
                                <i class="fas fa-check-circle"></i> Phù hợp: ${(drug.matched_symptoms || []).join(', ') || 'Không có'}
                            </span>
                            <span class="score-info">Score: ${drug.score || 0}</span>
                        </div>
                    </div>
                    
                    <!-- Nút mở rộng/thu gọn và các actions -->
                    <div class="expand-controls">
                        <button class="btn btn-expand" onclick="toggleDrugDetails(${index})">
                            <i class="fas fa-chevron-down" id="expand-icon-${index}"></i>
                            <span id="expand-text-${index}">Xem chi tiết</span>
                        </button>
                        <button class="btn btn-detail" onclick="showDrugDetail(${drug.index}, '${drug.name.replace(/'/g, "\\'")}')">
                            <i class="fas fa-info-circle"></i> Chi tiết đầy đủ
                        </button>
                        <button class="btn btn-save" id="save-btn-${drug.index}" onclick="saveDrugToList(${drug.index}, '${drug.name.replace(/'/g, "\\'")}', '${drug.drug_class}', '${currentSymptoms.replace(/'/g, "\\'")}', ${drug.score || 0})">
                            <i class="fas fa-bookmark"></i> Lưu
                        </button>
                    </div>
                </div>
                
                <!-- Nội dung chi tiết - ẩn ban đầu -->
                <div class="drug-details-content" id="details-${index}" style="display: none;">
                    <div class="drug-details">
                        <div class="detail-section indications">
                            <h4><i class="fas fa-info-circle"></i> Chỉ định & Công dụng</h4>
                            <ul class="detail-list">
                                ${formatListItems(drug.indication_list ? drug.indication_list.slice(0, 3) : ['Không có thông tin'])}
                                ${drug.indication_list && drug.indication_list.length > 3 ? '<li class="more-info">... và nhiều công dụng khác</li>' : ''}
                            </ul>
                        </div>
                        <div class="detail-section ingredients">
                            <h4><i class="fas fa-flask"></i> Thành phần chính</h4>
                            <ul class="detail-list">
                                ${formatListItems(drug.ingredients_list ? drug.ingredients_list.slice(0, 2) : ['Không có thông tin'])}
                                ${drug.ingredients_list && drug.ingredients_list.length > 2 ? '<li class="more-info">... và các thành phần khác</li>' : ''}
                            </ul>
                        </div>
                        <div class="detail-section contraindications">
                            <h4><i class="fas fa-exclamation-triangle"></i> Chống chỉ định</h4>
                            <ul class="detail-list">
                                ${formatListItems(drug.contraindication_list ? drug.contraindication_list.slice(0, 2) : ['Không có thông tin'])}
                                ${drug.contraindication_list && drug.contraindication_list.length > 2 ? '<li class="more-info">... và các chống chỉ định khác</li>' : ''}
                            </ul>
                        </div>

                        <div class="detail-section side-effects">
                            <h4><i class="fas fa-exclamation-circle"></i> Tác dụng phụ</h4>
                            <ul class="detail-list">
                                ${formatListItems(drug.side_effects_list ? drug.side_effects_list.slice(0, 3) : ['Không có thông tin'])}
                                ${drug.side_effects_list && drug.side_effects_list.length > 3 ? '<li class="more-info">... và các tác dụng phụ khác</li>' : ''}
                            </ul>
                        </div>
                    </div>
                    
                    <div class="drug-footer">
                        <div class="manufacturer-info">
                            <i class="fas fa-building"></i> <strong>Nhà sản xuất:</strong> ${drug.manufacturer || 'Xem trên bao bì'}
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
        
        resultsHtml += `
            <div class="clinical-notes">
                <h4><i class="fas fa-user-md"></i> Ghi chú lâm sàng</h4>
                <div class="notes-content">
                    <p>Xem xét tiền sử dị ứng thuốc của bệnh nhân</p>
                    <p>Kiểm tra tương tác với các thuốc đang sử dụng</p>
                    <p>Điều chỉnh liều theo tuổi, cân nặng và chức năng gan, thận</p>
                    <p>Theo dõi tác dụng phụ và hiệu quả điều trị</p>
                </div>
                
                <div class="view-controls">
                    <button class="btn btn-secondary" onclick="expandAllDrugs()">
                        <i class="fas fa-expand-arrows-alt"></i> Mở rộng tất cả
                    </button>
                    <button class="btn btn-secondary" onclick="collapseAllDrugs()">
                        <i class="fas fa-compress-arrows-alt"></i> Thu gọn tất cả
                    </button>
                </div>
            </div>
        `;
    }
    
    results.innerHTML = resultsHtml;
    results.style.display = 'block';
    
    // Kiểm tra trạng thái lưu của các thuốc (nếu user đã đăng nhập)
    checkSavedStatus(drugs);
}

// Kiểm tra trạng thái lưu của thuốc
async function checkSavedStatus(drugs) {
    if (!checkUserLoggedIn()) return;
    
    for (const drug of drugs) {
        try {
            const response = await fetch(`/check_saved_drug/${drug.index}`);
            const data = await response.json();
            
            if (data.is_saved) {
                const saveBtn = document.getElementById(`save-btn-${drug.index}`);
                if (saveBtn) {
                    saveBtn.innerHTML = '<i class="fas fa-check"></i> Đã lưu';
                    saveBtn.classList.add('btn-saved');
                    saveBtn.disabled = true;
                }
            }
        } catch (error) {
            console.log(`Error checking saved status for drug ${drug.index}:`, error);
        }
    }
}

// Lưu thuốc vào danh sách
function saveDrugToList(drugIndex, drugName, drugClass, symptoms, score) {
    // Kiểm tra đăng nhập
    if (!checkUserLoggedIn()) {
        showNotification('Vui lòng đăng nhập để lưu thuốc', 'error');
        return;
    }
    
    const saveBtn = document.getElementById(`save-btn-${drugIndex}`);
    const originalContent = saveBtn.innerHTML;
    
    // Show loading
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang lưu...';
    saveBtn.disabled = true;
    
    fetch('/save_drug', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            drug_index: drugIndex,
            drug_name: drugName,
            drug_class: drugClass,
            symptoms: symptoms,
            score: score
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            saveBtn.innerHTML = '<i class="fas fa-check"></i> Đã lưu';
            saveBtn.classList.add('btn-saved');
            showNotification(data.message, 'success');
        } else {
            saveBtn.innerHTML = originalContent;
            saveBtn.disabled = false;
            showNotification(data.message, 'error');
        }
    })
    .catch(error => {
        saveBtn.innerHTML = originalContent;
        saveBtn.disabled = false;
        showNotification('Lỗi kết nối: ' + error.message, 'error');
    });
}

// Kiểm tra user đã đăng nhập chưa
function checkUserLoggedIn() {
    // Kiểm tra xem có menu "Đăng xuất" không
    const logoutLink = document.querySelector('a[href*="logout"]');
    return logoutLink !== null;
}

// Toggle drug details
function toggleDrugDetails(index) {
    const detailsDiv = document.getElementById(`details-${index}`);
    const expandIcon = document.getElementById(`expand-icon-${index}`);
    const expandText = document.getElementById(`expand-text-${index}`);
    const drugCard = document.getElementById(`drug-${index}`);
    
    if (detailsDiv.style.display === 'none') {
        // Mở rộng
        detailsDiv.style.display = 'block';
        expandIcon.className = 'fas fa-chevron-up';
        expandText.textContent = 'Thu gọn';
        drugCard.classList.remove('collapsed');
        drugCard.classList.add('expanded');
    } else {
        // Thu gọn
        detailsDiv.style.display = 'none';
        expandIcon.className = 'fas fa-chevron-down';
        expandText.textContent = 'Xem chi tiết';
        drugCard.classList.remove('expanded');
        drugCard.classList.add('collapsed');
    }
}

// Expand all drugs
function expandAllDrugs() {
    const drugCards = document.querySelectorAll('.drug-card');
    drugCards.forEach((card, index) => {
        const detailsDiv = document.getElementById(`details-${index}`);
        const expandIcon = document.getElementById(`expand-icon-${index}`);
        const expandText = document.getElementById(`expand-text-${index}`);
        
        if (detailsDiv && detailsDiv.style.display === 'none') {
            detailsDiv.style.display = 'block';
            expandIcon.className = 'fas fa-chevron-up';
            expandText.textContent = 'Thu gọn';
            card.classList.remove('collapsed');
            card.classList.add('expanded');
        }
    });
}

// Collapse all drugs
function collapseAllDrugs() {
    const drugCards = document.querySelectorAll('.drug-card');
    drugCards.forEach((card, index) => {
        const detailsDiv = document.getElementById(`details-${index}`);
        const expandIcon = document.getElementById(`expand-icon-${index}`);
        const expandText = document.getElementById(`expand-text-${index}`);
        
        if (detailsDiv && detailsDiv.style.display !== 'none') {
            detailsDiv.style.display = 'none';
            expandIcon.className = 'fas fa-chevron-down';
            expandText.textContent = 'Xem chi tiết';
            card.classList.remove('expanded');
            card.classList.add('collapsed');
        }
    });
}

// Drug detail modal functions
function showDrugDetail(drugIndex, drugName) {
    // Track click nếu user đã đăng nhập
    if (checkUserLoggedIn()) {
        fetch('/track_click', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                drug_index: drugIndex,
                drug_name: drugName
            })
        }).catch(error => console.log('Track click error:', error));
    }

    const modal = document.createElement('div');
    modal.className = 'drug-detail-modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2><i class="fas fa-pills"></i> Chi tiết thuốc: ${drugName}</h2>
                <span class="close-modal">&times;</span>
            </div>
            <div class="modal-body">
                <div class="loading-detail">
                    <i class="fas fa-spinner fa-spin"></i> Đang tải thông tin...
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    modal.querySelector('.close-modal').onclick = () => {
        document.body.removeChild(modal);
    };
    
    modal.onclick = (e) => {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    };
    
    loadDrugDetail(drugIndex, modal);
}

async function loadDrugDetail(drugIndex, modal) {
    try {
        const response = await fetch(`/drug/${drugIndex}`);
        const drug = await response.json();
        
        if (drug.error) {
            throw new Error(drug.error);
        }
        
        displayDrugDetail(drug, modal);
        
    } catch (error) {
        modal.querySelector('.modal-body').innerHTML = `
            <div class="error">
                <i class="fas fa-exclamation-triangle"></i> 
                Lỗi tải thông tin: ${error.message}
            </div>
        `;
    }
}

function displayDrugDetail(drug, modal) {
    const modalBody = modal.querySelector('.modal-body');
    
    modalBody.innerHTML = `
        <div class="drug-detail-content">
            <div class="detail-overview">
                <div class="drug-title">
                    <h3>${drug.name}</h3>
                    <div class="drug-badges">
                        <span class="badge drug-class-badge">${drug.drug_class}</span>
                        ${drug.prescription_required ? '<span class="badge prescription-badge">Cần đơn thuốc</span>' : ''}
                        <span class="badge price-badge">${drug.price}</span>
                    </div>
                </div>
                <div class="manufacturer-info">
                    <i class="fas fa-building"></i> <strong>Nhà sản xuất:</strong> ${drug.manufacturer}
                </div>
            </div>
            
            <div class="detail-tabs">
                <div class="tab-buttons">
                    <button class="tab-btn active" data-tab="indications">
                        <i class="fas fa-info-circle"></i> Công dụng
                    </button>
                    <button class="tab-btn" data-tab="ingredients">
                        <i class="fas fa-flask"></i> Thành phần
                    </button>
                    <button class="tab-btn" data-tab="contraindications">
                        <i class="fas fa-ban"></i> Chống chỉ định
                    </button>
                    <button class="tab-btn" data-tab="side-effects">
                        <i class="fas fa-warning"></i> Tác dụng phụ
                    </button>
                </div>
                
                <div class="tab-contents">
                    <div class="tab-content active" id="indications">
                        <h4>Chỉ định & Công dụng</h4>
                        <ul class="detail-list">
                            ${formatListItems(drug.indication_list || ['Không có thông tin'])}
                        </ul>
                    </div>
                    
                    <div class="tab-content" id="ingredients">
                        <h4>Thành phần chính</h4>
                        <ul class="detail-list ingredients-list">
                            ${formatListItems(drug.ingredients_list || ['Không có thông tin'])}
                        </ul>
                    </div>
                    
                    
                    <div class="tab-content" id="contraindications">
                        <h4>Chống chỉ định & Cảnh báo</h4>
                        <ul class="detail-list warning-list">
                            ${formatListItems(drug.contraindication_list || ['Không có thông tin'])}
                        </ul>
                        <div class="safety-note">
                            <i class="fas fa-shield-alt"></i>
                            <strong>An toàn:</strong> Tham khảo ý kiến bác sĩ trước khi sử dụng
                        </div>
                    </div>

                     <div class="tab-content" id="side-effects">
                        <h4>Tác dụng phụ có thể gặp</h4>
                        <ul class="detail-list side-effects-list">
                            ${formatListItems(drug.side_effects_list || ['Không có thông tin'])}
                        </ul>
                        <div class="side-effects-warning">
                            <i class="fas fa-exclamation-triangle"></i>
                            <strong>Lưu ý:</strong> Nếu gặp tác dụng phụ nghiêm trọng, ngừng dùng thuốc và liên hệ bác sĩ ngay
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="detail-actions">
                <button class="btn btn-primary" onclick="printDrugInfo('${drug.name}')">
                    <i class="fas fa-print"></i> In thông tin
                </button>
                ${checkUserLoggedIn() ? `
                <button class="btn btn-save" onclick="saveDrugToListFromModal(${drug.index}, '${drug.name.replace(/'/g, "\\'")}', '${drug.drug_class}', '${currentSymptoms.replace(/'/g, "\\'")}', ${drug.score || 0})">
                    <i class="fas fa-bookmark"></i> Lưu vào danh sách
                </button>` : ''}
            </div>
        </div>
    `;
    
    setupTabs(modal);
}

// Lưu thuốc từ modal chi tiết
function saveDrugToListFromModal(drugIndex, drugName, drugClass, symptoms, score) {
    saveDrugToList(drugIndex, drugName, drugClass, symptoms, score);
}

function setupTabs(modal) {
    const tabButtons = modal.querySelectorAll('.tab-btn');
    const tabContents = modal.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            button.classList.add('active');
            const tabId = button.getAttribute('data-tab');
            const targetContent = modal.querySelector(`#${tabId}`);
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });
}

// Utility functions
function formatListItems(items) {
    if (!Array.isArray(items)) {
        if (typeof items === 'string') {
            return `<li>${items}</li>`;
        }
        return `<li>${items}</li>`;
    }
    
    return items.map(item => {
        const cleanItem = item.replace(/^[•\-\*]\s*/, '').trim();
        return `<li>${cleanItem}</li>`;
    }).join('');
}

function getCategoryClass(category) {
    const categoryClasses = {
        'Hô hấp': 'respiratory',
        'Thần kinh': 'neurological', 
        'Tiêu hóa': 'digestive',
        'Da liễu': 'dermatological',
        'Tim mạch': 'cardiovascular',
        'Cơ xương khớp': 'musculoskeletal',
        'Nhiễm khuẩn': 'infectious'
    };
    return categoryClasses[category] || '';
}

function showError(message) {
    error.textContent = message;
    error.style.display = 'block';
    setTimeout(() => {
        error.style.display = 'none';
    }, 5000);
}

function printDrugInfo(drugName) {
    window.print();
}

// Notification function
function showNotification(message, type = 'info') {
    // Tạo notification toast
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    // Style cho notification
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#17a2b8'};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        z-index: 10000;
        display: flex;
        align-items: center;
        gap: 8px;
        animation: slideIn 0.3s ease-out;
        min-width: 250px;
    `;
    
    // Add animation styles if not exists
    if (!document.getElementById('notification-styles')) {
        const styles = document.createElement('style');
        styles.id = 'notification-styles';
        styles.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(styles);
    }
    
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out forwards';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

// ==================== NAVIGATION ==================== 
document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu toggle
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');
    
    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            navToggle.classList.toggle('active');
            navMenu.classList.toggle('active');
        });
    }

    // Close mobile menu when clicking on a link
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            navToggle.classList.remove('active');
            navMenu.classList.remove('active');
        });
    });

    // Active nav link
    const currentPage = window.location.hash || '#home';
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPage) {
            link.classList.add('active');
        }
    });
});

// ==================== SCROLL TO TOP ==================== 
window.addEventListener('scroll', () => {
    const scrollToTop = document.getElementById('scrollToTop');
    if (scrollToTop) {
        if (window.pageYOffset > 300) {
            scrollToTop.classList.add('show');
        } else {
            scrollToTop.classList.remove('show');
        }
    }
});

document.getElementById('scrollToTop')?.addEventListener('click', () => {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
});