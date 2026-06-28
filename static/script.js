// ====== TOKYO SYSTEM - Dashboard Scripts ======

// Toggle Switch Handler
document.addEventListener('DOMContentLoaded', function() {
    const toggles = document.querySelectorAll('.toggle-switch input');
    toggles.forEach(toggle => {
        toggle.addEventListener('change', function() {
            const card = this.closest('.command-card');
            const badge = card ? card.querySelector('.badge') : null;
            if (badge) {
                if (this.checked) {
                    badge.textContent = 'Active';
                    badge.className = 'badge badge-success';
                } else {
                    badge.textContent = 'Disabled';
                    badge.className = 'badge badge-warning';
                }
            }
        });
    });
});

// ====== Confirm Delete ======
function confirmDelete(message) {
    return confirm(message || 'هل أنت متأكد من الحذف؟');
}

// ====== Copy to Clipboard ======
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert('تم النسخ!');
    }).catch(() => {
        alert('فشل النسخ');
    });
}

// ====== Show Toast Notification ======
function showToast(message, type = 'success') {
    const colors = {
        success: '#00ff88',
        error: '#ff2d55',
        warning: '#ffd700',
        info: '#00d4ff'
    };
    
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 24px;
        background: #1a1a1a;
        border: 1px solid ${colors[type] || colors.info};
        border-radius: 8px;
        color: white;
        font-family: 'Cairo', sans-serif;
        z-index: 9999;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        max-width: 350px;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.5s';
        setTimeout(() => toast.remove(), 500);
    }, 3000);
}

// ====== API Calls ======
async function apiCall(url, method = 'POST', data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        if (data) {
            options.body = JSON.stringify(data);
        }
        const response = await fetch(url, options);
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showToast('حدث خطأ في الاتصال', 'error');
        return null;
    }
}

// ====== Auto Roles ======
function addLevelRole() {
    const level = prompt('أدخل المستوى:');
    const roleId = prompt('أدخل ID الرتبة:');
    if (level && roleId) {
        apiCall('/api/addlevelrole', 'POST', { level: parseInt(level), role_id: roleId })
            .then(() => location.reload());
    }
}

function deleteLevelRole(level) {
    if (confirmDelete(`حذف الرتبة التلقائية للمستوى ${level}؟`)) {
        apiCall(`/api/removelevelrole/${level}`, 'POST')
            .then(() => location.reload());
    }
}

// ====== Self Roles ======
function addSelfRole() {
    const roleId = prompt('أدخل ID الرتبة:');
    const emoji = prompt('أدخل الإيموجي (اختياري):');
    if (roleId) {
        apiCall('/api/addselfrole', 'POST', { role_id: roleId, emoji: emoji || '' })
            .then(() => location.reload());
    }
}

function deleteSelfRole(roleId) {
    if (confirmDelete('حذف هذه الرتبة الاختيارية؟')) {
        apiCall(`/api/removeselfrole/${roleId}`, 'POST')
            .then(() => location.reload());
    }
}

// ====== Starboard ======
function setStarboard() {
    const channelId = prompt('أدخل ID قناة Starboard:');
    const threshold = prompt('عدد النجوم المطلوب (افتراضي 3):');
    if (channelId) {
        apiCall('/api/setstarboard', 'POST', {
            channel_id: channelId,
            threshold: parseInt(threshold) || 3
        }).then(() => location.reload());
    }
}

// ====== Notifications ======
function addTwitch() {
    const streamer = prompt('أدخل اسم المقدم:');
    const channel = prompt('أدخل ID قناة الإشعارات:');
    if (streamer && channel) {
        apiCall('/api/addtwitch', 'POST', { streamer, channel })
            .then(() => location.reload());
    }
}

function addYouTube() {
    const channelId = prompt('أدخل معرف القناة:');
    const channel = prompt('أدخل ID قناة الإشعارات:');
    if (channelId && channel) {
        apiCall('/api/addyoutube', 'POST', { channel_id: channelId, channel })
            .then(() => location.reload());
    }
}

function deleteNotification(service, identifier) {
    if (confirmDelete('حذف هذا الإشعار؟')) {
        apiCall('/api/removenotification', 'POST', { service, identifier })
            .then(() => location.reload());
    }
}

// ====== Temp Channels ======
function setTempCategory() {
    const categoryId = prompt('أدخل ID الكاتيجوري:');
    if (categoryId) {
        apiCall('/api/settempcat', 'POST', { category_id: categoryId })
            .then(() => location.reload());
    }
}

// ====== Filter Actions ======
function filterActions(type) {
    window.location.href = `/mod_actions?filter=${type}`;
}

// ====== Export Data ======
function exportData(type) {
    showToast(`جاري تصدير بيانات ${type}...`, 'info');
    // يمكن إضافة منطق التصدير هنا
}

// ====== Load Animations ======
document.addEventListener('DOMContentLoaded', function() {
    // إضافة تأثير ظهور للبطاقات
    const cards = document.querySelectorAll('.card, .stat-card, .command-card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = `all 0.4s ease ${index * 0.05}s`;
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 100);
    });
});
